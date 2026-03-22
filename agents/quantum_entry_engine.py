"""
QuanTum Entry Timing Engine — Execution Alpha Layer

Separates SIGNAL (what to buy) from ENTRY (when to execute).
Uses 4 institutional-grade conditions:
  1. Pullback-to-support (distance to 20DMA)
  2. Volume confirmation (smart money participation)
  3. Volatility compression breakout (5d vs 30d vol)
  4. RSI stability filter (avoid overheated entries)

Entry score = 0.35*pullback + 0.25*volume + 0.25*volatility + 0.15*rsi
Enter only when entry_score >= 70.
"""

import sys
import io
import logging
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

logging.getLogger("yfinance").setLevel(logging.CRITICAL)

MIN_ENTRY_SCORE = 70


def _score_pullback(price: float, sma20: float) -> tuple[float, str]:
    """Score proximity to 20DMA support. Sweet spot: -2% to +3%."""
    if sma20 is None or sma20 <= 0 or price <= 0:
        return 50, "no 20DMA data"

    distance = (price - sma20) / sma20

    if -0.02 <= distance <= 0.03:
        return 100, f"at support ({distance:+.1%} from 20DMA)"
    elif -0.05 <= distance <= 0.05:
        return 70, f"near support ({distance:+.1%} from 20DMA)"
    elif -0.10 <= distance <= 0.10:
        return 40, f"moderate distance ({distance:+.1%} from 20DMA)"
    elif distance > 0.10:
        return 10, f"overextended ({distance:+.1%} above 20DMA)"
    else:
        return 20, f"deep pullback ({distance:+.1%} below 20DMA)"


def _score_volume(volume: float, avg_volume: float) -> tuple[float, str]:
    """Score volume confirmation — institutional participation."""
    if avg_volume is None or avg_volume <= 0:
        return 50, "no volume data"

    ratio = volume / avg_volume

    if ratio > 2.0:
        return 100, f"heavy volume ({ratio:.1f}x avg)"
    elif ratio > 1.5:
        return 80, f"strong volume ({ratio:.1f}x avg)"
    elif ratio > 1.2:
        return 60, f"moderate volume ({ratio:.1f}x avg)"
    elif ratio > 0.8:
        return 40, f"normal volume ({ratio:.1f}x avg)"
    else:
        return 20, f"low volume ({ratio:.1f}x avg)"


def _score_volatility_compression(vol_5d: float, vol_30d: float) -> tuple[float, str]:
    """
    Score volatility compression — breakouts after low vol are strongest.
    Ratio < 0.7 = compressed (ready to break out).
    """
    if vol_30d is None or vol_30d <= 0 or vol_5d is None:
        return 50, "no vol data"

    ratio = vol_5d / vol_30d

    if ratio < 0.6:
        return 100, f"tight compression ({ratio:.2f}x, breakout setup)"
    elif ratio < 0.7:
        return 85, f"compressing ({ratio:.2f}x)"
    elif ratio < 0.8:
        return 70, f"mild compression ({ratio:.2f}x)"
    elif ratio < 1.0:
        return 55, f"normal vol ({ratio:.2f}x)"
    else:
        return 30, f"expanding vol ({ratio:.2f}x, unstable)"


def _score_rsi_stability(rsi: float) -> tuple[float, str]:
    """Score RSI stability — optimal zone: 50-65."""
    if rsi is None or np.isnan(rsi):
        return 50, "no RSI data"

    if 50 <= rsi <= 65:
        return 100, f"optimal zone (RSI {rsi:.0f})"
    elif 45 <= rsi < 50:
        return 75, f"recovering (RSI {rsi:.0f})"
    elif 65 < rsi <= 70:
        return 70, f"mildly hot (RSI {rsi:.0f})"
    elif 40 <= rsi < 45:
        return 50, f"weak (RSI {rsi:.0f})"
    elif 70 < rsi <= 75:
        return 40, f"overbought risk (RSI {rsi:.0f})"
    elif rsi > 75:
        return 10, f"overbought (RSI {rsi:.0f})"
    else:
        return 20, f"oversold (RSI {rsi:.0f})"


class EntryTimingEngine:
    """
    Evaluates entry timing for scored stocks.
    Returns entry_score, entry_allowed, and per-component breakdowns.
    Stocks with entry_allowed=False keep their signal but are marked WAIT.
    """

    def evaluate_entries(
        self,
        scored_df: pd.DataFrame,
        horizon: str = "week",
        progress_callback=None,
    ) -> pd.DataFrame:
        if scored_df.empty:
            return scored_df

        tickers = scored_df["ticker"].tolist()

        # Batch-fetch 2-month history for volatility compression calc
        vol_data = self._fetch_volatility_data(tickers)

        results = []
        for _, row in scored_df.iterrows():
            ticker = row["ticker"]
            close = row.get("close", 0)
            sma20 = row.get("sma20")
            volume = row.get("volume", 0)
            avg_vol = row.get("avg_volume_20d", 0)
            rsi = row.get("rsi")

            # Get vol compression from batch data
            vol_5d, vol_30d = vol_data.get(ticker, (None, None))

            # Score each component
            pullback_score, pullback_note = _score_pullback(close, sma20)
            volume_score, volume_note = _score_volume(volume, avg_vol)
            vol_comp_score, vol_comp_note = _score_volatility_compression(vol_5d, vol_30d)
            rsi_score, rsi_note = _score_rsi_stability(rsi)

            # Weighted composite
            entry_score = (
                0.35 * pullback_score +
                0.25 * volume_score +
                0.25 * vol_comp_score +
                0.15 * rsi_score
            )

            entry_allowed = entry_score >= MIN_ENTRY_SCORE
            status = self._determine_status(
                entry_allowed, pullback_score, volume_score,
                vol_comp_score, rsi_score, entry_score
            )

            results.append({
                "ticker": ticker,
                "entry_score": round(entry_score, 1),
                "entry_allowed": entry_allowed,
                "entry_status": status,
                "pullback_score": pullback_score,
                "pullback_note": pullback_note,
                "volume_score": volume_score,
                "volume_note": volume_note,
                "vol_compression_score": vol_comp_score,
                "vol_compression_note": vol_comp_note,
                "rsi_score": rsi_score,
                "rsi_note": rsi_note,
            })

        entry_df = pd.DataFrame(results)

        if progress_callback:
            allowed = entry_df["entry_allowed"].sum()
            progress_callback(
                f"Entry timing: {allowed}/{len(entry_df)} stocks have optimal entry "
                f"(avg score {entry_df['entry_score'].mean():.0f})"
            )

        return entry_df

    def _determine_status(
        self, allowed, pullback, volume, vol_comp, rsi, total
    ) -> str:
        if allowed:
            if total >= 85:
                return "STRONG ENTER"
            return "ENTER"

        # Find the weakest component to suggest what to wait for
        weakest = min(
            [("pullback to 20DMA", pullback),
             ("volume confirmation", volume),
             ("vol compression", vol_comp),
             ("RSI cooldown", rsi)],
            key=lambda x: x[1]
        )

        if rsi < 30:
            return "WAIT: RSI overheated"
        if pullback < 30:
            return "WAIT: overextended"
        return f"WAIT: {weakest[0]}"

    def _fetch_volatility_data(self, tickers: list[str]) -> dict:
        """Batch-fetch 2mo history to compute 5d vs 30d realized vol."""
        if not tickers:
            return {}

        symbols = [f"{t}.NS" for t in tickers]

        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            data = yf.download(
                symbols, period="2mo", interval="1d",
                progress=False, auto_adjust=True, group_by="ticker",
            )
        except Exception:
            return {}
        finally:
            sys.stderr = old_stderr

        if data is None or data.empty:
            return {}

        result = {}
        for ticker in tickers:
            sym = f"{ticker}.NS"
            try:
                if len(symbols) == 1:
                    close = data["Close"].squeeze().dropna()
                else:
                    if sym not in data.columns.get_level_values(0):
                        continue
                    close = data[sym]["Close"].dropna()

                if len(close) < 30:
                    continue

                returns = close.pct_change().dropna()
                vol_5d = float(returns.tail(5).std() * np.sqrt(252))
                vol_30d = float(returns.tail(30).std() * np.sqrt(252))

                result[ticker] = (vol_5d, vol_30d)
            except Exception:
                continue

        return result
