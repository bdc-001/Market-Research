"""
Opportunity Universe + liquidity hard gate.

A name never reaches the LLM if it fails market-cap or liquidity.
Unknown liquidity is treated as untradeable.
"""
from __future__ import annotations

import io
import logging
import sys
from typing import Iterable

import pandas as pd
import yfinance as yf

from agents.discovery_config import load_discovery_config
from agents.nse_client import ExchangeClient

logger = logging.getLogger(__name__)
logging.getLogger("yfinance").setLevel(logging.CRITICAL)


def build_opportunity_universe(
    cfg: dict | None = None,
    client: ExchangeClient | None = None,
    progress=None,
) -> pd.DataFrame:
    cfg = cfg or load_discovery_config()
    client = client or ExchangeClient(
        cache_ttl_minutes=int(cfg.get("radar", {}).get("cache_ttl_minutes", 180))
    )
    uni = cfg["universe"]
    rows: list[dict] = []

    for index in uni.get("indices") or []:
        _log(progress, f"Universe: fetching {index}...")
        rows.extend(client.index_constituents(index))

    if uni.get("include_nse_sme"):
        _log(progress, "Universe: fetching NSE SME / Emerge...")
        rows.extend(client.nse_sme_constituents())

    if uni.get("include_smallcap"):
        smallcap_index = uni.get("smallcap_index") or "NIFTY SMALLCAP 250"
        _log(progress, f"Universe: fetching {smallcap_index} (Tier C, secondary)...")
        rows.extend(client.index_constituents(smallcap_index))

    frame = _dedupe(rows)
    if frame.empty:
        _log(progress, "Universe: exchange lists empty")
        return frame

    exclude = {str(t).upper() for t in (uni.get("exclude_tickers") or [])}
    if exclude:
        frame = frame[~frame["ticker"].isin(exclude)].copy()

    _log(progress, f"Universe: {len(frame)} unique names before gates")
    frame = assign_tiers(frame, uni)
    frame = apply_liquidity_gate(
        attach_adv(frame, progress=progress),
        min_adv_inr=float(uni["min_adv_inr"]),
        unknown_is_exclude=bool(cfg["liquidity"].get("unknown_is_exclude", True)),
    )
    primary = set(uni.get("primary_tiers") or ["sme", "microcap"])
    kept = frame[frame["tier"].isin(primary)].copy()
    dropped_c = int((frame["tier"] == "smallcap").sum()) if "tier" in frame.columns else 0
    dropped_unk = int((frame["tier"] == "unknown").sum()) if "tier" in frame.columns else 0
    _log(
        progress,
        f"Universe: {len(kept)} primary (SME+microcap) after liquidity; "
        f"held-out smallcap={dropped_c}, unknown-tier={dropped_unk}",
    )
    kept["in_universe"] = True
    return kept.reset_index(drop=True)


def assign_tiers(df: pd.DataFrame, uni: dict) -> pd.DataFrame:
    """Tier A SME, B microcap 50-1000 Cr, C smallcap 1000-5000 Cr. Do not mix."""
    if df.empty:
        df["tier"] = pd.Series(dtype=str)
        return df
    micro_max = float(uni.get("microcap_max_cr", 1000))
    small_max = float(uni.get("smallcap_max_cr", 5000))
    mcap_min = float(uni.get("mcap_min_cr", 50))
    tiers = []
    for _, row in df.iterrows():
        tiers.append(_tier_for_row(row, mcap_min, micro_max, small_max))
    out = df.copy()
    out["tier"] = tiers
    return out


def _tier_for_row(row, mcap_min: float, micro_max: float, small_max: float) -> str:
    src = f"{row.get('source') or ''} {row.get('exchange') or ''}".upper()
    if "SME" in src or "EMERGE" in src:
        return "sme"
    mcap = _finite(row.get("mcap_cr"))
    if mcap is not None:
        if mcap_min <= mcap <= micro_max:
            return "microcap"
        if micro_max < mcap <= small_max:
            return "smallcap"
        return "out"
    if "MICROCAP" in src:
        return "microcap"
    if "SMALLCAP" in src:
        return "smallcap"
    return "unknown"


def _finite(value) -> float | None:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    if n != n or n <= 0:
        return None
    return n


def apply_mcap_gate(
    df: pd.DataFrame,
    min_cr: float,
    max_cr: float,
    unknown_policy: str = "keep",
) -> pd.DataFrame:
    if df.empty:
        return df
    mcap = pd.to_numeric(df.get("mcap_cr"), errors="coerce")
    known = mcap.notna()
    in_band = (mcap >= float(min_cr)) & (mcap <= float(max_cr))
    if unknown_policy == "exclude":
        keep = known & in_band
    else:
        keep = (~known) | in_band
    return df.loc[keep].copy()


def apply_liquidity_gate(
    df: pd.DataFrame,
    min_adv_inr: float,
    unknown_is_exclude: bool = True,
) -> pd.DataFrame:
    """Hard exclude. An amazing catalyst cannot override this."""
    if df.empty:
        return df
    adv = pd.to_numeric(df.get("adv_inr"), errors="coerce")
    turnover = pd.to_numeric(df.get("turnover_inr"), errors="coerce")
    best = adv.copy()
    best = best.fillna(turnover)
    known = best.notna() & (best > 0)
    liquid = known & (best >= float(min_adv_inr))
    if unknown_is_exclude:
        keep = liquid
    else:
        keep = liquid | ~known
    out = df.loc[keep].copy()
    out["liquidity_ok"] = True
    out["liquidity_inr"] = best.loc[keep]
    return out


def attach_adv(df: pd.DataFrame, progress=None) -> pd.DataFrame:
    if df.empty:
        df["adv_inr"] = pd.Series(dtype=float)
        return df
    tickers = [f"{t}.NS" for t in df["ticker"].tolist()]
    _log(progress, f"Universe: computing 20d ADV for {len(tickers)} names...")
    hist = _download(tickers, period="1mo")
    adv_map: dict[str, float] = {}
    for ticker in df["ticker"]:
        close, volume = _series_pair(hist, f"{ticker}.NS")
        if close is None or volume is None or len(close) < 5 or len(volume) < 5:
            continue
        n = min(len(close), len(volume), 20)
        traded = (close.iloc[-n:] * volume.iloc[-n:]).dropna()
        if traded.empty:
            continue
        adv_map[ticker] = float(traded.mean())
    out = df.copy()
    out["adv_inr"] = out["ticker"].map(adv_map)
    return out


def enrich_symbols(
    tickers: Iterable[str],
    universe: pd.DataFrame,
    cfg: dict,
    progress=None,
) -> pd.DataFrame:
    """
    Attach mcap / ADV / analyst count for announcement symbols.
    Names that fail mcap or liquidity never leave this function.
    """
    uni = cfg["universe"]
    wanted = [str(t).upper() for t in tickers if t]
    if not wanted:
        return pd.DataFrame()

    known = universe[universe["ticker"].isin(wanted)].copy() if not universe.empty else pd.DataFrame()
    missing = [t for t in wanted if t not in set(known["ticker"] if not known.empty else [])]
    extra_rows = []
    if missing:
        _log(progress, f"Universe: enriching {len(missing)} announcement-only names...")
        extra_rows = _fundamentals(missing)
    extra = pd.DataFrame(extra_rows)
    if extra.empty:
        frame = known
    elif known.empty:
        frame = extra
    else:
        frame = pd.concat([known, extra], ignore_index=True)
    if frame.empty:
        return frame
    frame = frame.drop_duplicates(subset=["ticker"], keep="first")
    # Announcement-only names need a known microcap band; unknown mcap is not a pass.
    in_primary = set(known["ticker"].tolist()) if not known.empty else set()
    extras_mask = ~frame["ticker"].isin(in_primary) if in_primary else pd.Series(True, index=frame.index)
    extra_part = frame.loc[extras_mask].copy()
    known_part = frame.loc[~extras_mask].copy() if in_primary else frame.iloc[0:0]
    extra_part = apply_mcap_gate(
        extra_part,
        uni.get("mcap_min_cr", 50),
        uni.get("microcap_max_cr", 1000),
        unknown_policy="exclude",
    )
    if not extra_part.empty:
        extra_part["tier"] = "microcap"
        extra_part["source"] = extra_part.get("source", "announcement")
    frame = pd.concat([known_part, extra_part], ignore_index=True) if not extra_part.empty else known_part
    if frame.empty:
        return frame
    primary = set(uni.get("primary_tiers") or ["sme", "microcap"])
    if "tier" not in frame.columns:
        frame = assign_tiers(frame, uni)
    frame = frame[frame["tier"].isin(primary)].copy()
    if "adv_inr" not in frame.columns or frame["adv_inr"].isna().any():
        frame = attach_adv(frame, progress=progress)
    frame = apply_liquidity_gate(
        frame,
        min_adv_inr=float(uni["min_adv_inr"]),
        unknown_is_exclude=bool(cfg["liquidity"].get("unknown_is_exclude", True)),
    )
    return frame.reset_index(drop=True)


def _fundamentals(tickers: list[str]) -> list[dict]:
    out = []
    for ticker in tickers:
        info = _info(ticker)
        mcap = info.get("marketCap") if "marketCap" in info else None
        mcap_cr = (float(mcap) / 1e7) if mcap else None
        revenue = info.get("totalRevenue") if "totalRevenue" in info else None
        revenue_cr = (float(revenue) / 1e7) if revenue else None
        analyst_n, analyst_status = _analyst_from_info(info)
        out.append({
            "ticker": ticker,
            "exchange": "NSE",
            "source": "announcement",
            "company_name": info.get("shortName") or ticker,
            "last_price": info.get("currentPrice") or info.get("previousClose"),
            "turnover_inr": None,
            "volume": info.get("averageVolume"),
            "mcap_cr": mcap_cr,
            "revenue_cr": revenue_cr,
            "analyst_n": analyst_n,
            "analyst_status": analyst_status,
            "adv_inr": None,
        })
    return out


def _analyst_from_info(info: dict) -> tuple:
    if "numberOfAnalystOpinions" not in info:
        return None, "unknown"
    val = info.get("numberOfAnalystOpinions")
    if val is None:
        return None, "unknown"
    try:
        n = float(val)
    except (TypeError, ValueError):
        return None, "unknown"
    if n != n:
        return None, "unknown"
    return int(n), "verified"


def _info(ticker: str) -> dict:
    try:
        return yf.Ticker(f"{ticker}.NS").info or {}
    except Exception:
        return {}


def attach_fundamentals(df: pd.DataFrame, progress=None) -> pd.DataFrame:
    """Fill analyst_status, revenue, mcap. Missing stays unknown — never coerced to 0."""
    if df.empty:
        return df
    out = df.copy()
    for col, default in (("analyst_n", None), ("analyst_status", "unknown"), ("revenue_cr", None)):
        if col not in out.columns:
            out[col] = default
    out["analyst_status"] = out["analyst_status"].fillna("unknown")
    need = out["analyst_status"].eq("unknown") | out["revenue_cr"].isna() | out["mcap_cr"].isna()
    if not need.any():
        return out
    _log(progress, f"Fundamentals: {int(need.sum())} names (analyst/revenue/mcap)...")
    for idx in out.index[need]:
        ticker = out.at[idx, "ticker"]
        info = _info(ticker)
        n, status = _analyst_from_info(info)
        if status == "verified":
            out.at[idx, "analyst_n"] = n
            out.at[idx, "analyst_status"] = "verified"
        if pd.isna(out.at[idx, "mcap_cr"]) and info.get("marketCap"):
            out.at[idx, "mcap_cr"] = float(info["marketCap"]) / 1e7
        if pd.isna(out.at[idx, "revenue_cr"]) and info.get("totalRevenue"):
            out.at[idx, "revenue_cr"] = float(info["totalRevenue"]) / 1e7
        if pd.isna(out.at[idx, "revenue_cr"]):
            stmt = _statement_revenue_cr(ticker)
            if stmt:
                out.at[idx, "revenue_cr"] = stmt
    return out


def _statement_revenue_cr(ticker: str):
    """Yahoo info.totalRevenue is often empty for SME names; annuals still exist."""
    try:
        import yfinance as yf
        frame = yf.Ticker(f"{ticker}.NS").financials
        if frame is None or getattr(frame, "empty", True) or "Total Revenue" not in frame.index:
            return None
        series = frame.loc["Total Revenue"].dropna()
        if series.empty:
            return None
        return float(series.iloc[0]) / 1e7
    except Exception:
        return None


def attach_analyst_counts(df: pd.DataFrame, progress=None) -> pd.DataFrame:
    return attach_fundamentals(df, progress=progress)


def _dedupe(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=[
            "ticker", "exchange", "source", "company_name",
            "last_price", "turnover_inr", "volume", "mcap_cr",
        ])
    df = pd.DataFrame(rows)
    df["ticker"] = df["ticker"].astype(str).str.upper()
    # Prefer SME source over index when duplicated.
    rank = df["source"].map(lambda s: 0 if "SME" in str(s).upper() else 1)
    df["_rank"] = rank
    df = df.sort_values(["ticker", "_rank"]).drop_duplicates("ticker", keep="first")
    return df.drop(columns=["_rank", "raw"], errors="ignore")


def _download(symbols: list[str], period: str) -> pd.DataFrame | None:
    old = sys.stderr
    sys.stderr = io.StringIO()
    try:
        return yf.download(
            symbols, period=period, interval="1d",
            progress=False, auto_adjust=True, group_by="ticker", threads=True,
        )
    except Exception as exc:
        logger.debug("yfinance download failed: %s", exc)
        return None
    finally:
        sys.stderr = old


def _series_pair(data, yf_symbol: str):
    if data is None or getattr(data, "empty", True):
        return None, None
    try:
        if isinstance(data.columns, pd.MultiIndex):
            if yf_symbol not in data.columns.get_level_values(0):
                return None, None
            block = data[yf_symbol]
            return block["Close"].dropna(), block["Volume"].dropna()
        return data["Close"].dropna(), data["Volume"].dropna()
    except Exception:
        return None, None


def _log(progress, msg: str) -> None:
    if progress:
        progress(msg)
    else:
        print(msg, flush=True)
