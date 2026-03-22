"""
QuanTum Market Regime Detection Layer

Detects whether the market is in BULL, BEAR, or SIDEWAYS regime
using Nifty 50 price vs 200DMA, market breadth, and India VIX.

Dynamically adjusts factor weights per regime so the model doesn't
generate momentum picks in a bear market or defensive picks in a bull.
"""
import yfinance as yf
import pandas as pd
import numpy as np
import sys
import io
import logging
from datetime import datetime, timedelta

logging.getLogger("yfinance").setLevel(logging.CRITICAL)


# ── Regime-Adjusted Weights ───────────────────────────────────────────────

REGIME_WEIGHTS = {
    "BULL": {
        "week": {
            "momentum": 0.30, "technical": 0.30, "news_catalyst": 0.25,
            "volatility": 0.05, "flow": 0.10,
            "value": 0.00, "quality": 0.00, "sector_growth": 0.00,
            "earnings_revision": 0.00,
        },
        "year": {
            "momentum": 0.20, "earnings_revision": 0.25, "flow": 0.20,
            "value": 0.10, "quality": 0.10, "sector_growth": 0.10,
            "technical": 0.05, "volatility": 0.00, "news_catalyst": 0.00,
        },
        "5years": {
            "quality": 0.25, "sector_growth": 0.25, "earnings_revision": 0.20,
            "value": 0.15, "volatility": 0.10, "momentum": 0.05,
            "technical": 0.00, "flow": 0.00, "news_catalyst": 0.00,
        },
    },
    "BEAR": {
        "week": {
            "volatility": 0.25, "technical": 0.25, "news_catalyst": 0.20,
            "momentum": 0.15, "flow": 0.15,
            "value": 0.00, "quality": 0.00, "sector_growth": 0.00,
            "earnings_revision": 0.00,
        },
        "year": {
            "quality": 0.30, "volatility": 0.20, "flow": 0.15,
            "earnings_revision": 0.15, "value": 0.10, "sector_growth": 0.10,
            "momentum": 0.00, "technical": 0.00, "news_catalyst": 0.00,
        },
        "5years": {
            "quality": 0.30, "value": 0.20, "volatility": 0.20,
            "sector_growth": 0.20, "earnings_revision": 0.10,
            "momentum": 0.00, "technical": 0.00, "flow": 0.00,
            "news_catalyst": 0.00,
        },
    },
    "SIDEWAYS": {
        "week": {
            "technical": 0.30, "news_catalyst": 0.25, "momentum": 0.25,
            "volatility": 0.10, "flow": 0.10,
            "value": 0.00, "quality": 0.00, "sector_growth": 0.00,
            "earnings_revision": 0.00,
        },
        "year": {
            "quality": 0.20, "earnings_revision": 0.20, "flow": 0.15,
            "value": 0.15, "momentum": 0.10, "sector_growth": 0.15,
            "technical": 0.05, "volatility": 0.00, "news_catalyst": 0.00,
        },
        "5years": {
            "quality": 0.25, "sector_growth": 0.25, "value": 0.15,
            "earnings_revision": 0.15, "volatility": 0.15, "momentum": 0.05,
            "technical": 0.00, "flow": 0.00, "news_catalyst": 0.00,
        },
    },
}


class RegimeDetector:
    """Detects market regime: BULL / BEAR / SIDEWAYS."""

    def detect(self, progress_callback=None) -> dict:
        """
        Returns dict:
          regime: "BULL" | "BEAR" | "SIDEWAYS"
          nifty_close, nifty_200dma, pct_above_200dma,
          breadth_pct, vix, signals (list of reasons)
        """
        if progress_callback:
            progress_callback("Detecting market regime (Nifty 50, VIX, breadth)...")

        result = {
            "regime": "SIDEWAYS",
            "nifty_close": None,
            "nifty_200dma": None,
            "pct_above_200dma": None,
            "breadth_pct": None,
            "vix": None,
            "signals": [],
        }

        # Nifty 50 price vs 200 DMA
        try:
            old_stderr = sys.stderr
            sys.stderr = io.StringIO()
            nifty = yf.download("^NSEI", period="1y", interval="1d",
                                progress=False, auto_adjust=True)
            sys.stderr = old_stderr
            if not nifty.empty and len(nifty) >= 200:
                close = nifty["Close"].squeeze()
                nifty_close = float(close.iloc[-1])
                sma200 = float(close.rolling(200).mean().iloc[-1])
                pct_above = (nifty_close - sma200) / sma200 * 100

                result["nifty_close"] = nifty_close
                result["nifty_200dma"] = sma200
                result["pct_above_200dma"] = round(pct_above, 2)

                if pct_above > 5:
                    result["signals"].append(f"Nifty {pct_above:+.1f}% above 200 DMA (bullish)")
                elif pct_above < -5:
                    result["signals"].append(f"Nifty {pct_above:+.1f}% below 200 DMA (bearish)")
                else:
                    result["signals"].append(f"Nifty near 200 DMA ({pct_above:+.1f}%, neutral)")
        except Exception:
            pass

        # India VIX
        try:
            old_stderr = sys.stderr
            sys.stderr = io.StringIO()
            vix_data = yf.download("^INDIAVIX", period="1mo", interval="1d",
                                   progress=False, auto_adjust=True)
            sys.stderr = old_stderr
            if not vix_data.empty:
                vix_close = vix_data["Close"].squeeze()
                vix = float(vix_close.iloc[-1])
                result["vix"] = round(vix, 2)

                if vix > 25:
                    result["signals"].append(f"India VIX at {vix:.1f} (high fear)")
                elif vix < 14:
                    result["signals"].append(f"India VIX at {vix:.1f} (complacency)")
                else:
                    result["signals"].append(f"India VIX at {vix:.1f} (moderate)")
        except Exception:
            pass

        # Market breadth: % of Nifty 50 constituents above their 50 DMA
        breadth = self._compute_breadth()
        result["breadth_pct"] = breadth

        if breadth is not None:
            if breadth > 60:
                result["signals"].append(f"Breadth {breadth:.0f}% above 50 DMA (broad participation)")
            elif breadth < 40:
                result["signals"].append(f"Breadth {breadth:.0f}% above 50 DMA (narrow market)")
            else:
                result["signals"].append(f"Breadth {breadth:.0f}% above 50 DMA (mixed)")

        # Final classification
        pct = result.get("pct_above_200dma")
        br = result.get("breadth_pct")
        vix_val = result.get("vix")

        bull_signals = 0
        bear_signals = 0

        if pct is not None:
            if pct > 3:
                bull_signals += 1
            elif pct < -3:
                bear_signals += 1

        if br is not None:
            if br > 60:
                bull_signals += 1
            elif br < 40:
                bear_signals += 1

        if vix_val is not None:
            if vix_val < 16:
                bull_signals += 1
            elif vix_val > 22:
                bear_signals += 1

        if bull_signals >= 2:
            result["regime"] = "BULL"
        elif bear_signals >= 2:
            result["regime"] = "BEAR"
        else:
            result["regime"] = "SIDEWAYS"

        if progress_callback:
            progress_callback(f"Market regime: {result['regime']} — " +
                              "; ".join(result["signals"][:3]))

        return result

    def _compute_breadth(self) -> float | None:
        """% of a sample of NSE large-caps above their 50 DMA."""
        sample = [
            "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS",
            "INFY.NS", "HINDUNILVR.NS", "ITC.NS", "SBIN.NS",
            "BHARTIARTL.NS", "LT.NS", "HCLTECH.NS", "SUNPHARMA.NS",
            "KOTAKBANK.NS", "AXISBANK.NS", "BAJFINANCE.NS", "TITAN.NS",
            "MARUTI.NS", "NTPC.NS", "WIPRO.NS", "POWERGRID.NS",
            "HAL.NS", "DRREDDY.NS", "CIPLA.NS", "JSWSTEEL.NS",
            "TATAPOWER.NS", "ADANIGREEN.NS", "BEL.NS", "ABB.NS",
            "DLF.NS", "COALINDIA.NS",
        ]

        above_50dma = 0
        total_valid = 0

        try:
            old_stderr = sys.stderr
            sys.stderr = io.StringIO()
            data = yf.download(sample, period="3mo", interval="1d",
                               progress=False, auto_adjust=True, group_by="ticker")
            sys.stderr = old_stderr
            for sym in sample:
                try:
                    ticker_key = sym.replace(".NS", "")
                    if sym in data.columns.get_level_values(0):
                        close = data[sym]["Close"].dropna()
                    elif ticker_key in data.columns.get_level_values(0):
                        close = data[ticker_key]["Close"].dropna()
                    else:
                        continue

                    if len(close) < 50:
                        continue

                    current = float(close.iloc[-1])
                    sma50 = float(close.rolling(50).mean().iloc[-1])
                    total_valid += 1
                    if current > sma50:
                        above_50dma += 1
                except Exception:
                    continue
        except Exception:
            return None

        if total_valid == 0:
            return None
        return round(above_50dma / total_valid * 100, 1)

    def get_weights(self, regime: str, horizon: str) -> dict:
        """Returns the regime-adjusted factor weights for a given horizon."""
        return REGIME_WEIGHTS.get(regime, REGIME_WEIGHTS["SIDEWAYS"]).get(
            horizon, REGIME_WEIGHTS["SIDEWAYS"]["year"]
        )
