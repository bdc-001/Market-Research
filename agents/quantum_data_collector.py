"""
QuanTum Data Collector Agent (v2)
Pulls live price, volume, technicals, returns, and volatility for Nifty
stocks using yfinance. Stores to SQLite for historical tracking.

Enhancements over v1:
  - Computes 1m/3m/6m/12m price returns (for momentum factor)
  - Computes 20-day annualized volatility (for risk factor)
  - Computes average volume ratio (today vs 20-day avg)
  - Fetches additional fundamentals: profit_margin, dividend_yield, PB ratio
"""
import yfinance as yf
import pandas as pd
import numpy as np
import sqlite3
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from turso_db import get_db_smart
import io
import logging
from datetime import datetime, timedelta

# Suppress yfinance's noisy error messages for delisted tickers
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

NIFTY_UNIVERSE = [
    # Large Cap Blue Chips
    "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", "HINDUNILVR",
    "ITC", "SBIN", "BHARTIARTL", "KOTAKBANK", "AXISBANK", "LT",
    "HCLTECH", "ASIANPAINT", "MARUTI", "BAJFINANCE", "TITAN",
    "NESTLEIND", "WIPRO", "ULTRACEMCO", "POWERGRID", "SUNPHARMA",
    "NTPC", "BAJAJFINSV", "HDFCLIFE", "TECHM", "DIVISLAB",
    # Auto (M&M, Bajaj Auto, Eicher, Hero replace dead TATAMTRDVR)
    "M&M", "BAJAJ-AUTO", "EICHERMOT", "HEROMOTOCO",
    # Mid Cap Growth
    "TATAPOWER", "JSWSTEEL", "HINDALCO", "COALINDIA",
    "DRREDDY", "CIPLA", "BRITANNIA", "DABUR", "MARICO", "GODREJCP",
    "PIDILITIND", "BERGEPAINT", "HAVELLS", "VOLTAS",
    # Defence & Capital Goods
    "HAL", "BEL", "BHEL", "ABB", "SIEMENS", "CUMMINSIND",
    "THERMAX", "GRINDWELL", "BEML",
    # Banking & Finance
    "PNB", "BANKBARODA", "CANBK", "FEDERALBNK", "IDFCFIRSTB",
    "CHOLAFIN", "MUTHOOTFIN", "BAJAJHLDNG",
    "SHRIRAMFIN", "INDUSINDBK",
    # Consumer & Retail
    "DMART", "TRENT", "NYKAA", "ETERNAL", "PAYTM",
    "TATACONSUM", "JUBLFOOD", "IRCTC",
    # Pharma
    "LUPIN", "TORNTPHARM", "AUROPHARMA", "GLAND", "ALKEM",
    # IT
    "PERSISTENT", "LTIM", "MPHASIS", "COFORGE",
    # Infra & Real Estate
    "DLF", "GODREJPROP", "PRESTIGE", "OBEROIRLTY",
    "GMRAIRPORT", "ADANIENT", "ADANIPORTS",
    # Green Energy & Power
    "ADANIGREEN", "TATAPOWER", "SJVN", "NHPC", "JSWENERGY",
    # Insurance
    "LICI",
]

DB_PATH = "quantum_signals.db"


def get_db():
    conn = get_db_smart(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stock_data_v2 (
            ticker TEXT,
            date TEXT,
            close REAL,
            volume REAL,
            avg_volume_20d REAL,
            volume_ratio REAL,
            rsi REAL,
            sma20 REAL,
            sma50 REAL,
            sma200 REAL,
            macd REAL,
            macd_signal REAL,
            return_1m REAL,
            return_3m REAL,
            return_6m REAL,
            return_12m REAL,
            volatility_20d REAL,
            pe_ratio REAL,
            pb_ratio REAL,
            roe REAL,
            debt_equity REAL,
            market_cap REAL,
            profit_margin REAL,
            dividend_yield REAL,
            earnings_yield REAL,
            PRIMARY KEY (ticker, date)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS signal_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            ticker TEXT NOT NULL,
            horizon TEXT NOT NULL,
            composite_score REAL,
            value_rank REAL,
            quality_rank REAL,
            momentum_rank REAL,
            technical_rank REAL,
            volatility_rank REAL,
            factor_agreement INTEGER,
            conviction TEXT,
            close_at_signal REAL,
            verified INTEGER DEFAULT 0,
            actual_return REAL,
            benchmark_return REAL,
            alpha REAL,
            verification_date TEXT
        )
    """)
    conn.commit()
    return conn


class DataCollectorAgent:
    """
    Pulls EOD price data, computes technicals, returns, and volatility
    for the Nifty universe using yfinance.
    """

    def compute_rsi(self, series: pd.Series, period: int = 14) -> pd.Series:
        delta = series.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
        avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def compute_macd(self, series: pd.Series):
        ema12 = series.ewm(span=12, adjust=False).mean()
        ema26 = series.ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        return macd, signal

    def fetch_ticker(self, ticker: str) -> dict | None:
        """Fetches 1y+ of data, computes all factor inputs."""
        try:
            sym = f"{ticker}.NS"
            # Suppress stderr to avoid noisy yfinance "delisted" messages
            old_stderr = sys.stderr
            sys.stderr = io.StringIO()
            try:
                df = yf.download(sym, period="2y", interval="1d",
                                 progress=False, auto_adjust=True)
            finally:
                sys.stderr = old_stderr
            if df.empty or len(df) < 50:
                return None

            close = df["Close"].squeeze()
            volume = df["Volume"].squeeze()

            current_close = float(close.iloc[-1])
            current_volume = float(volume.iloc[-1])

            rsi_series = self.compute_rsi(close)
            rsi = float(rsi_series.iloc[-1]) if not pd.isna(rsi_series.iloc[-1]) else None

            sma20 = float(close.rolling(20).mean().iloc[-1]) if len(close) >= 20 else None
            sma50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else None
            sma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None

            macd_line, macd_sig = self.compute_macd(close)
            macd_val = float(macd_line.iloc[-1])
            macd_sig_val = float(macd_sig.iloc[-1])

            avg_vol_20d = float(volume.rolling(20).mean().iloc[-1]) if len(volume) >= 20 else current_volume
            volume_ratio = current_volume / avg_vol_20d if avg_vol_20d > 0 else 1.0

            # Period returns (guard against insufficient data)
            n = len(close)
            return_1m = (current_close / float(close.iloc[-22]) - 1) if n >= 22 else None
            return_3m = (current_close / float(close.iloc[-66]) - 1) if n >= 66 else None
            return_6m = (current_close / float(close.iloc[-132]) - 1) if n >= 132 else None
            return_12m = (current_close / float(close.iloc[-252]) - 1) if n >= 252 else None

            # Annualized 20-day volatility
            daily_returns = close.pct_change().dropna()
            vol_20d = float(daily_returns.tail(20).std() * np.sqrt(252)) if len(daily_returns) >= 20 else None

            # Fundamentals
            info = {}
            try:
                info = yf.Ticker(sym).info
            except Exception:
                pass

            pe = info.get("trailingPE")
            earnings_yield = (1.0 / pe) if pe and pe > 0 else None

            return {
                "ticker": ticker,
                "date": datetime.today().strftime("%Y-%m-%d"),
                "close": current_close,
                "volume": current_volume,
                "avg_volume_20d": avg_vol_20d,
                "volume_ratio": round(volume_ratio, 2),
                "rsi": rsi,
                "sma20": sma20,
                "sma50": sma50,
                "sma200": sma200,
                "macd": macd_val,
                "macd_signal": macd_sig_val,
                "return_1m": round(return_1m, 4) if return_1m is not None else None,
                "return_3m": round(return_3m, 4) if return_3m is not None else None,
                "return_6m": round(return_6m, 4) if return_6m is not None else None,
                "return_12m": round(return_12m, 4) if return_12m is not None else None,
                "volatility_20d": round(vol_20d, 4) if vol_20d is not None else None,
                "pe_ratio": pe,
                "pb_ratio": info.get("priceToBook"),
                "roe": info.get("returnOnEquity"),
                "debt_equity": info.get("debtToEquity"),
                "market_cap": info.get("marketCap"),
                "profit_margin": info.get("profitMargins"),
                "dividend_yield": info.get("dividendYield"),
                "earnings_yield": round(earnings_yield, 4) if earnings_yield else None,
            }
        except Exception:
            return None

    def run(self, tickers=None, progress_callback=None) -> pd.DataFrame:
        if tickers is None:
            tickers = list(dict.fromkeys(NIFTY_UNIVERSE))  # deduplicate

        conn = get_db()
        rows = []
        total = len(tickers)

        for i, ticker in enumerate(tickers):
            if progress_callback:
                progress_callback(f"Fetching {ticker} ({i+1}/{total})...")
            data = self.fetch_ticker(ticker)
            if data:
                rows.append(data)
                try:
                    cols = list(data.keys())
                    placeholders = ", ".join([f":{c}" for c in cols])
                    col_names = ", ".join(cols)
                    conn.execute(
                        f"INSERT OR REPLACE INTO stock_data_v2 ({col_names}) VALUES ({placeholders})",
                        data,
                    )
                except Exception:
                    pass

        conn.commit()
        conn.close()

        return pd.DataFrame(rows) if rows else pd.DataFrame()
