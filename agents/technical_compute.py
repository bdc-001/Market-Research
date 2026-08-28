"""
Python-owned technical snapshot.

The Chartist LLM never computes indicators and never sees a DataFrame.
It only receives validated scalars (or an invalid snapshot with an error).
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

MIN_BARS = 50


def as_float(value) -> float | None:
    """Coerce yfinance/pandas objects to a single Python float, or None."""
    if value is None:
        return None
    try:
        if isinstance(value, pd.DataFrame):
            if value.empty:
                return None
            value = value.iloc[-1, 0]
        if isinstance(value, pd.Series):
            if value.empty:
                return None
            value = value.iloc[-1]
        if hasattr(value, "item"):
            try:
                value = value.item()
            except (ValueError, AttributeError):
                return None
        number = float(value)
        if number != number:
            return None
        return number
    except (TypeError, ValueError):
        return None


def _col(df: pd.DataFrame, name: str) -> pd.Series:
    if name in df.columns:
        series = df[name]
    elif isinstance(df.columns, pd.MultiIndex) and name in df.columns.get_level_values(0):
        series = df[name]
    else:
        raise KeyError(name)
    if isinstance(series, pd.DataFrame):
        series = series.iloc[:, 0]
    return series.squeeze()


def _rsi(close: pd.Series, period: int = 14) -> float | None:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    value = as_float(100 - (100 / (1 + rs)).iloc[-1])
    if value is None or value < 0 or value > 100:
        return None
    return round(value, 4)


def _macd(close: pd.Series) -> tuple[float | None, float | None]:
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    return (
        round(as_float(macd.iloc[-1]) or 0.0, 4) if as_float(macd.iloc[-1]) is not None else None,
        round(as_float(signal.iloc[-1]) or 0.0, 4) if as_float(signal.iloc[-1]) is not None else None,
    )


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> float | None:
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low).abs(), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    value = as_float(tr.rolling(period).mean().iloc[-1])
    return round(value, 4) if value is not None else None


def _invalid(error: str, **extra) -> dict:
    snap = {
        "valid": False,
        "error": error,
        "as_of": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "bars": extra.get("bars"),
        "price": None,
        "sma20": None,
        "sma50": None,
        "sma200": None,
        "rsi": None,
        "macd": None,
        "macd_signal": None,
        "atr": None,
        "volume": None,
        "volume_vs_average": None,
        "high_52w": None,
        "low_52w": None,
        "support": None,
        "resistance": None,
        "trend": None,
        "cross": None,
    }
    snap.update(extra)
    return snap


def compute_snapshot_from_ohlcv(df: pd.DataFrame, ticker: str = "") -> dict:
    """Build a validated scalar snapshot from an OHLCV frame. Never returns a Series."""
    if df is None or getattr(df, "empty", True):
        return _invalid("No price rows")

    try:
        close = _col(df, "Close").dropna().astype(float)
        high = _col(df, "High").dropna().astype(float)
        low = _col(df, "Low").dropna().astype(float)
        volume = _col(df, "Volume").fillna(0).astype(float)
    except Exception as exc:
        return _invalid(f"OHLCV columns unusable: {exc}")

    bars = int(len(close))
    if bars < MIN_BARS:
        return _invalid(f"Need at least {MIN_BARS} daily bars, got {bars}", bars=bars)

    price = as_float(close.iloc[-1])
    sma20 = as_float(close.rolling(20).mean().iloc[-1]) if bars >= 20 else None
    sma50 = as_float(close.rolling(50).mean().iloc[-1]) if bars >= 50 else None
    sma200 = as_float(close.rolling(200).mean().iloc[-1]) if bars >= 200 else None
    vol = as_float(volume.iloc[-1])
    avg_vol = as_float(volume.rolling(20).mean().iloc[-1]) if bars >= 20 else vol
    vol_ratio = round(vol / avg_vol, 4) if vol is not None and avg_vol else None
    high_52w = as_float(high.tail(min(bars, 252)).max())
    low_52w = as_float(low.tail(min(bars, 252)).min())
    support = as_float(low.tail(20).min()) if bars >= 20 else low_52w
    resistance = as_float(high.tail(20).max()) if bars >= 20 else high_52w
    rsi = _rsi(close)
    macd_val, macd_sig = _macd(close)
    atr = _atr(high, low, close)

    required = {"price": price, "sma20": sma20, "sma50": sma50}
    missing = [k for k, v in required.items() if v is None]
    if missing:
        return _invalid(f"NaN in required fields: {', '.join(missing)}", bars=bars)

    # Comparisons only after scalars exist — this is the Series-ambiguous bug.
    if sma200 is not None:
        trend = "up" if price > sma200 else "down"
    else:
        trend = "up" if price > sma50 else "down"
    if sma50 is not None and sma200 is not None:
        cross = "golden" if sma50 > sma200 else "death"
    else:
        cross = None

    return {
        "valid": True,
        "error": None,
        "ticker": ticker,
        "as_of": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "bars": bars,
        "price": round(price, 4),
        "sma20": round(sma20, 4),
        "sma50": round(sma50, 4),
        "sma200": round(sma200, 4) if sma200 is not None else None,
        "rsi": rsi,
        "macd": macd_val,
        "macd_signal": macd_sig,
        "atr": atr,
        "volume": round(vol, 2) if vol is not None else None,
        "volume_vs_average": vol_ratio,
        "high_52w": round(high_52w, 4) if high_52w is not None else None,
        "low_52w": round(low_52w, 4) if low_52w is not None else None,
        "support": round(support, 4) if support is not None else None,
        "resistance": round(resistance, 4) if resistance is not None else None,
        "trend": trend,
        "cross": cross,
    }


def fetch_ohlcv(ticker: str, period: str = "2y") -> pd.DataFrame:
    import yfinance as yf

    symbol = ticker if ticker.endswith((".NS", ".BO")) else f"{ticker}.NS"
    data = yf.download(symbol, period=period, interval="1d", progress=False, auto_adjust=True)
    return data if data is not None else pd.DataFrame()


def compute_technical_snapshot(ticker: str) -> dict:
    try:
        df = fetch_ohlcv(ticker)
    except Exception as exc:
        return _invalid(f"Price download failed: {exc}")
    return compute_snapshot_from_ohlcv(df, ticker=ticker)


def snapshot_is_valid(snapshot: dict | None) -> bool:
    if not snapshot or not snapshot.get("valid"):
        return False
    for key in ("price", "sma20", "sma50"):
        if not isinstance(snapshot.get(key), (int, float)):
            return False
    return True
