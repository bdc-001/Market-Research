"""
QuanTum Institutional Flow Tracking Layer (v3) — Bhavcopy Engine

Uses REAL NSE Bhavcopy delivery data from archives:
  https://archives.nseindia.com/products/content/sec_bhavdata_full_DDMMYYYY.csv

Flow factor model:
  flow_score = 0.50 * delivery_score
             + 0.30 * block_deal_score (volume > 5x avg + high delivery)
             + 0.20 * volume_accumulation_score (OBV + sustained volume)

Delivery score is RELATIVE to each stock's own average delivery %
over the lookback period (not absolute thresholds), which captures
genuine institutional accumulation signals.

Weight in model: 10-20% depending on regime.
"""
import requests
import pandas as pd
import numpy as np
import yfinance as yf
from io import StringIO
from datetime import date, timedelta
import time
import sys
import io
import logging

logging.getLogger("yfinance").setLevel(logging.CRITICAL)

logger = logging.getLogger(__name__)


def _pct_rank(series: pd.Series) -> pd.Series:
    return series.rank(pct=True, na_option="keep")


class BhavcopyFetcher:
    """Fetches NSE Bhavcopy CSV from archives for delivery % data."""

    ARCHIVE_URL = "https://archives.nseindia.com/products/content/sec_bhavdata_full_{date}.csv"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })
        self._cache: dict[str, pd.DataFrame] = {}

    def fetch_day(self, d: date) -> pd.DataFrame | None:
        """Fetch Bhavcopy CSV for a specific date."""
        fmt = d.strftime("%d%m%Y")
        if fmt in self._cache:
            return self._cache[fmt]

        url = self.ARCHIVE_URL.format(date=fmt)
        try:
            r = self.session.get(url, timeout=15)
            if r.status_code != 200 or len(r.content) < 1000:
                return None

            df = pd.read_csv(StringIO(r.text))
            df.columns = [c.strip() for c in df.columns]

            # Clean numeric columns (may have leading spaces)
            for col in ["TTL_TRD_QNTY", "DELIV_QTY", "DELIV_PER", "NO_OF_TRADES",
                         "CLOSE_PRICE", "TURNOVER_LACS"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            df["SYMBOL"] = df["SYMBOL"].str.strip()
            df["SERIES"] = df["SERIES"].str.strip()

            # Keep only EQ series
            df = df[df["SERIES"] == "EQ"].copy()

            self._cache[fmt] = df
            return df

        except Exception as e:
            logger.debug(f"Bhavcopy fetch failed for {d}: {e}")
            return None

    def fetch_multi_day(
        self, lookback_days: int = 10, progress_callback=None,
    ) -> pd.DataFrame:
        """
        Fetch Bhavcopy for last N trading days.
        Skips weekends and failed fetches.
        Returns concatenated DataFrame with date column.
        """
        all_frames = []
        fetched = 0
        d = date.today()

        attempts = 0
        while fetched < lookback_days and attempts < lookback_days + 10:
            d -= timedelta(days=1)
            attempts += 1

            # Skip weekends
            if d.weekday() >= 5:
                continue

            if progress_callback and fetched % 3 == 0:
                progress_callback(f"Fetching Bhavcopy {d.strftime('%d-%b')} ({fetched+1}/{lookback_days})...")

            df = self.fetch_day(d)
            if df is not None and not df.empty:
                df["fetch_date"] = d
                all_frames.append(df)
                fetched += 1

            time.sleep(0.3)

        if not all_frames:
            return pd.DataFrame()

        return pd.concat(all_frames, ignore_index=True)


class FlowTracker:
    """
    Computes institutional flow score per stock using:
    1. REAL delivery % from NSE Bhavcopy (relative to stock's own average)
    2. Block deal detection (volume > 5x avg + high delivery)
    3. Volume accumulation (OBV slope + sustained volume)
    """

    def __init__(self):
        self.bhavcopy = BhavcopyFetcher()
        self._bhavcopy_data: pd.DataFrame | None = None

    def compute_flow_scores(
        self, df: pd.DataFrame, progress_callback=None,
    ) -> pd.Series:
        if progress_callback:
            progress_callback("Fetching NSE Bhavcopy delivery data (10 trading days)...")

        # Fetch multi-day Bhavcopy if not already cached
        if self._bhavcopy_data is None or self._bhavcopy_data.empty:
            self._bhavcopy_data = self.bhavcopy.fetch_multi_day(
                lookback_days=10, progress_callback=progress_callback,
            )

        bhav = self._bhavcopy_data
        has_bhavcopy = bhav is not None and not bhav.empty

        if has_bhavcopy and progress_callback:
            unique_dates = bhav["fetch_date"].nunique()
            progress_callback(f"Bhavcopy loaded: {unique_dates} trading days, {len(bhav)} records")

        # Batch-fetch 3 months of history for OBV/volume analysis
        tickers = df["ticker"].tolist()
        symbols = [f"{t}.NS" for t in tickers]
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            hist = yf.download(symbols, period="3mo", interval="1d",
                               progress=False, auto_adjust=True, group_by="ticker")
        except Exception:
            hist = None
        finally:
            sys.stderr = old_stderr

        results = {}
        for _, row in df.iterrows():
            ticker = row["ticker"]
            sym = f"{ticker}.NS"

            # Get Bhavcopy data for this ticker
            ticker_bhav = None
            if has_bhavcopy:
                ticker_bhav = bhav[bhav["SYMBOL"] == ticker]
                if ticker_bhav.empty:
                    ticker_bhav = None

            score = self._score_single(
                ticker, sym, hist, row, ticker_bhav, len(symbols) == 1,
            )
            results[ticker] = score

        flow_raw = df["ticker"].map(results).fillna(50.0)
        return _pct_rank(flow_raw).fillna(0.5) * 100

    def _score_single(
        self, ticker: str, sym: str, hist_data, row: pd.Series,
        ticker_bhav: pd.DataFrame | None, single: bool,
    ) -> float:
        try:
            # ── A. Delivery Score (50% weight) ─────────────────────────────
            delivery_score = 50.0

            if ticker_bhav is not None and len(ticker_bhav) >= 2:
                # Latest day's delivery %
                latest = ticker_bhav.sort_values("fetch_date", ascending=False).iloc[0]
                latest_deliv_pct = latest.get("DELIV_PER", 0)
                if pd.isna(latest_deliv_pct):
                    latest_deliv_pct = 0

                # Average delivery % over lookback
                avg_deliv_pct = ticker_bhav["DELIV_PER"].mean()

                if avg_deliv_pct > 0 and latest_deliv_pct > 0:
                    # Score relative to stock's own average
                    if latest_deliv_pct > avg_deliv_pct * 1.30:
                        delivery_score = 100
                    elif latest_deliv_pct > avg_deliv_pct * 1.15:
                        delivery_score = 80
                    elif latest_deliv_pct > avg_deliv_pct:
                        delivery_score = 60
                    else:
                        delivery_score = 30

                    # Bonus: delivery % trending up over the period
                    if len(ticker_bhav) >= 3:
                        sorted_bhav = ticker_bhav.sort_values("fetch_date")
                        first_half = sorted_bhav["DELIV_PER"].iloc[:len(sorted_bhav)//2].mean()
                        second_half = sorted_bhav["DELIV_PER"].iloc[len(sorted_bhav)//2:].mean()
                        if second_half > first_half * 1.05:
                            delivery_score = min(100, delivery_score + 10)

            elif ticker_bhav is not None and len(ticker_bhav) == 1:
                # Only 1 day — use absolute thresholds
                dp = ticker_bhav.iloc[0].get("DELIV_PER", 0)
                if pd.notna(dp):
                    if dp > 65:
                        delivery_score = 90
                    elif dp > 55:
                        delivery_score = 70
                    elif dp > 45:
                        delivery_score = 55
                    else:
                        delivery_score = 35

            # ── B. Block Deal Score (30% weight) ───────────────────────────
            block_deal_score = 40.0

            if ticker_bhav is not None and not ticker_bhav.empty:
                latest = ticker_bhav.sort_values("fetch_date", ascending=False).iloc[0]
                avg_vol = ticker_bhav["TTL_TRD_QNTY"].mean()
                latest_vol = latest.get("TTL_TRD_QNTY", 0)
                latest_dp = latest.get("DELIV_PER", 0)

                if pd.notna(latest_vol) and pd.notna(avg_vol) and avg_vol > 0:
                    vol_multiple = latest_vol / avg_vol
                    dp_val = latest_dp if pd.notna(latest_dp) else 0

                    # Block deal = massive volume spike + high delivery
                    if vol_multiple > 5.0 and dp_val > 60:
                        block_deal_score = 100
                    elif vol_multiple > 3.0 and dp_val > 55:
                        block_deal_score = 85
                    elif vol_multiple > 2.0 and dp_val > 50:
                        block_deal_score = 70
                    elif vol_multiple > 1.5:
                        block_deal_score = 55
                    else:
                        block_deal_score = 35

            # ── C. Volume Accumulation Score (20% weight) ──────────────────
            vol_accum_score = 50.0

            if hist_data is not None:
                try:
                    if single:
                        close = hist_data["Close"].squeeze().dropna()
                        volume = hist_data["Volume"].squeeze().dropna()
                    else:
                        if sym in hist_data.columns.get_level_values(0):
                            close = hist_data[sym]["Close"].dropna()
                            volume = hist_data[sym]["Volume"].dropna()
                        else:
                            close = pd.Series(dtype=float)
                            volume = pd.Series(dtype=float)

                    if len(close) >= 20 and len(volume) >= 20:
                        # OBV slope
                        daily_ret = close.pct_change()
                        sign = daily_ret.apply(
                            lambda x: 1 if x > 0 else (-1 if x < 0 else 0)
                        )
                        obv = (volume * sign).cumsum()
                        obv_recent = obv.tail(20)
                        if len(obv_recent) >= 5:
                            x = np.arange(len(obv_recent))
                            slope = np.polyfit(x, obv_recent.values, 1)[0]
                            avg_vol_hist = volume.tail(20).mean()
                            obv_score = 50 + min(50, max(-50,
                                slope / (avg_vol_hist + 1) * 1000))
                        else:
                            obv_score = 50

                        # Sustained volume: how many of last 10 days above avg
                        avg_vol_20 = float(volume.rolling(20).mean().iloc[-1])
                        if avg_vol_20 > 0:
                            days_above = int((volume.tail(10) > avg_vol_20).sum())
                            sustained = days_above / 10 * 100
                        else:
                            sustained = 50

                        vol_accum_score = 0.60 * obv_score + 0.40 * sustained

                except Exception:
                    pass

            # ── Composite Flow Score ───────────────────────────────────────
            flow = (0.50 * delivery_score +
                    0.30 * block_deal_score +
                    0.20 * vol_accum_score)

            return max(0, min(100, flow))

        except Exception:
            return 50.0

    def get_delivery_detail(self, ticker: str) -> dict | None:
        """Returns delivery data summary for report display."""
        if self._bhavcopy_data is None or self._bhavcopy_data.empty:
            return None

        bhav = self._bhavcopy_data[self._bhavcopy_data["SYMBOL"] == ticker]
        if bhav.empty:
            return None

        latest = bhav.sort_values("fetch_date", ascending=False).iloc[0]
        return {
            "delivery_pct": latest.get("DELIV_PER"),
            "avg_delivery_pct": bhav["DELIV_PER"].mean(),
            "traded_qty": latest.get("TTL_TRD_QNTY"),
            "delivery_qty": latest.get("DELIV_QTY"),
            "days_of_data": len(bhav),
        }
