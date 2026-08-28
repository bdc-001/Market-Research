"""
Frozen Opportunity Score. Phase A uses catalyst + scarcity only.

Unknown data never becomes a favourable score. Materiality is required
before an order event can score as a strong catalyst.
"""
from __future__ import annotations

import io
import sys

import pandas as pd
import yfinance as yf

from agents.discovery_config import frozen_weights
from agents.economic_materiality import economic_materiality

ORDER_TYPES = {
    "large_order_win", "export_order", "strategic_partnership",
}


def score_opportunities(
    events: list[dict],
    names: pd.DataFrame,
    cfg: dict,
    progress=None,
    news_mentions: dict | None = None,
) -> list[dict]:
    """
    Phase A.2 ranks by economic materiality. The frozen 25/20/20/25/10
    formula is not used as a ranking until quality and inflection exist.
    """
    weights = frozen_weights(cfg)
    assert cfg["opportunity_score"]["frozen"] is True
    scarcity_cfg = cfg.get("scarcity") or {}
    news_mentions = news_mentions or {}
    reactions = _reactions([e["ticker"] for e in events], progress=progress)
    cards = []
    for ev in events:
        ticker = ev["ticker"]
        row = _row(names, ticker)
        mat = economic_materiality(ev, row, cfg.get("materiality") or {})
        rx = reactions.get(ticker) or {}
        awareness = information_awareness(
            analyst_n=row.get("analyst_n"),
            analyst_status=row.get("analyst_status") or "unknown",
            reaction=rx,
            news_n=news_mentions.get(ticker, 0),
            cfg=scarcity_cfg,
        )
        impact = mat.get("economic_impact") or {}
        cards.append({
            **ev,
            **row,
            "weights": weights,
            "opportunity_score": None,
            "rank_score": _rank_score(mat, awareness),
            "phase": "A.2",
            "materiality": mat,
            "economic_impact": impact,
            "market_awareness": awareness,
            "information_quality": {
                "source_verified": bool(ev.get("source_id") and (ev.get("source_text") or ev.get("subject"))),
                "full_filing_available": bool(ev.get("full_filing_available")),
            },
            "stage": mat["stage"],
            "abs_return_5d": rx.get("abs_return_pct"),
            "volume_ratio": rx.get("volume_ratio"),
            "last_close": rx.get("last_close") or row.get("last_price"),
            "news_mentions": news_mentions.get(ticker, 0),
            "confidence": "medium" if mat["stage"] == "opportunity_candidate" else "low",
        })
    cards.sort(
        key=lambda c: (c.get("rank_score") is not None, c.get("rank_score") or 0,
                       (c.get("materiality") or {}).get("score") or 0),
        reverse=True,
    )
    return cards


def information_awareness(analyst_n, analyst_status, reaction: dict, news_n: int, cfg: dict) -> dict:
    abs_ret = _finite(reaction.get("abs_return_pct"))
    vol = _finite(reaction.get("volume_ratio"))
    muted_abs = float(cfg.get("muted_abs_return_pct", 5.0))
    min_vol = float(cfg.get("min_volume_participation", 0.5))
    if str(analyst_status) == "verified" and _finite(analyst_n) is not None:
        analyst = {"status": "verified", "n": int(_finite(analyst_n))}
    else:
        analyst = {"status": "unknown", "n": None}
    if abs_ret is None or vol is None:
        tape = "unknown"
    elif vol < min_vol:
        tape = "thin_trading"
    elif abs_ret <= muted_abs:
        tape = "muted_with_participation"
    else:
        tape = "price_already_moved"
    hidden = (
        tape == "muted_with_participation"
        and (analyst["n"] is None or analyst["n"] <= 2)
        and int(news_n or 0) <= 1
    )
    return {
        "analyst_coverage": analyst,
        "news_mentions": int(news_n or 0),
        "abnormal_return": abs_ret,
        "abnormal_volume": vol,
        "tape": tape,
        "hidden": hidden,
        "awareness": tape,
        "analyst": (
            f"verified {analyst['n']} analysts" if analyst["status"] == "verified"
            else "unknown — coverage not verified"
        ),
    }


def _rank_score(mat: dict, awareness: dict) -> float | None:
    m = int(mat.get("score") or 0)
    if m <= 1:
        return None
    score = m * 20.0
    if awareness.get("tape") == "price_already_moved":
        score *= 0.5
    if int(awareness.get("news_mentions") or 0) >= 5:
        score *= 0.7
    return round(score, 2)


def catalyst_score(event: dict, row: dict, cfg: dict | None = None) -> tuple[float, dict]:
    cfg = cfg or {}
    unknown = float(cfg.get("unknown_event_score", 35))
    amount = _finite(event.get("amount_inr_cr"))
    revenue = _finite(row.get("revenue_cr"))
    mcap = _finite(row.get("mcap_cr"))
    event_type = event.get("event_type") or "other_catalyst"
    info = {
        "status": "unknown",
        "amount_inr_cr": amount,
        "revenue_cr": revenue,
        "mcap_cr": mcap,
        "vs_revenue": None,
        "vs_mcap": None,
        "note": "Event disclosed; size not established from the filing text.",
    }
    sentiment = event.get("sentiment")
    try:
        sent = float(sentiment) if sentiment is not None else 0.0
    except (TypeError, ValueError):
        sent = 0.0

    if amount is None:
        score = unknown
        if sent < 0:
            score *= 0.4
        return _clip(score), info

    vs_rev = (amount / revenue) if revenue else None
    vs_mcap = (amount / mcap) if mcap else None
    info["vs_revenue"] = vs_rev
    info["vs_mcap"] = vs_mcap

    if vs_rev is not None:
        weak = float(cfg.get("revenue_weak", 0.05))
        moderate = float(cfg.get("revenue_moderate", 0.20))
        major = float(cfg.get("revenue_major", 0.50))
        if vs_rev < weak:
            score, status, note = 30.0, "weak", f"{vs_rev:.0%} of trailing revenue"
        elif vs_rev < moderate:
            score, status, note = 55.0, "moderate", f"{vs_rev:.0%} of trailing revenue"
        elif vs_rev < major:
            score, status, note = 80.0, "material", f"{vs_rev:.0%} of trailing revenue"
        else:
            score, status, note = 95.0, "major", f"{vs_rev:.0%} of trailing revenue"
    elif vs_mcap is not None:
        if vs_mcap < 0.03:
            score, status, note = 32.0, "weak", f"{vs_mcap:.0%} of market cap (revenue unknown)"
        elif vs_mcap < 0.15:
            score, status, note = 58.0, "moderate", f"{vs_mcap:.0%} of market cap (revenue unknown)"
        else:
            score, status, note = 82.0, "material", f"{vs_mcap:.0%} of market cap (revenue unknown)"
    else:
        score, status, note = unknown, "unknown", "Amount stated; revenue and mcap unknown."

    if event_type not in ORDER_TYPES and status in {"material", "major"}:
        score = min(score, 70.0)
    if sent < 0:
        score *= 0.4
    info["status"] = status
    info["note"] = note
    return _clip(score), info


def scarcity_score(analyst_n, reaction: dict, cfg: dict, analyst_status: str = "unknown") -> tuple[float, dict]:
    """
    Unknown ≠ zero. Missing analyst or reaction data contributes 0 (no bonus).
    Low volume is thin trading, not muted awareness.
    """
    w_a = float(cfg.get("analyst_weight", 0.5))
    w_m = float(cfg.get("muted_reaction_weight", 0.5))
    a_score, a_note = _analyst_component(analyst_n, analyst_status)
    r_score, awareness = _reaction_component(reaction, cfg)
    total = w_a * (a_score if a_score is not None else 0.0)
    total += w_m * (r_score if r_score is not None else 0.0)
    return float(total), {
        "analyst": a_note,
        "awareness": awareness,
        "analyst_score": a_score,
        "reaction_score": r_score,
    }


def _analyst_component(analyst_n, analyst_status: str) -> tuple[float | None, str]:
    if str(analyst_status) != "verified":
        return None, "unknown — coverage not verified"
    n = _finite(analyst_n)
    if n is None:
        return None, "unknown — coverage not verified"
    n = int(n)
    if n <= 0:
        return 100.0, "verified 0 analysts"
    if n <= 2:
        return 75.0, f"verified {n} analysts"
    if n <= 5:
        return 45.0, f"verified {n} analysts"
    return 15.0, f"verified {n} analysts"


def _reaction_component(reaction: dict, cfg: dict) -> tuple[float | None, str]:
    abs_ret = _finite(reaction.get("abs_return_pct"))
    vol = _finite(reaction.get("volume_ratio"))
    muted_abs = float(cfg.get("muted_abs_return_pct", 5.0))
    min_vol = float(cfg.get("min_volume_participation", 0.5))
    if abs_ret is None or vol is None:
        return None, "unknown"
    if vol < min_vol:
        return None, "thin_trading"
    if abs_ret <= muted_abs:
        return 100.0, "muted_with_participation"
    return 25.0, "price_already_moved"


def _confidence(materiality: dict, awareness: dict, row: dict) -> str:
    if materiality.get("status") in {"material", "major"} and awareness.get("awareness") in {
        "muted_with_participation", "price_already_moved",
    }:
        if awareness.get("analyst") and "verified" in str(awareness.get("analyst")):
            return "medium"
    if materiality.get("status") == "unknown" or awareness.get("awareness") in {"unknown", "thin_trading"}:
        return "low"
    return "low"


def _reactions(tickers: list[str], progress=None) -> dict[str, dict]:
    unique = list(dict.fromkeys(t for t in tickers if t))
    out = {t: {} for t in unique}
    if not unique:
        return out
    if progress:
        progress(f"Reaction: 5-day price and volume for {len(unique)} names...")
    symbols = [f"{t}.NS" for t in unique]
    old = sys.stderr
    sys.stderr = io.StringIO()
    try:
        data = yf.download(
            symbols, period="1mo", interval="1d",
            progress=False, auto_adjust=True, group_by="ticker", threads=True,
        )
    except Exception:
        data = None
    finally:
        sys.stderr = old
    for ticker in unique:
        close, volume = _pair(data, f"{ticker}.NS")
        if close is None or len(close) < 3:
            continue
        window = close.iloc[-6:] if len(close) >= 6 else close
        abs_ret = abs(float(window.iloc[-1]) / float(window.iloc[0]) - 1.0) * 100
        vol_ratio = None
        if volume is not None and len(volume) >= 6:
            avg = float(volume.iloc[-21:-1].mean()) if len(volume) > 6 else float(volume.mean())
            last = float(volume.iloc[-1])
            if avg > 0:
                vol_ratio = last / avg
        out[ticker] = {
            "abs_return_pct": abs_ret,
            "volume_ratio": vol_ratio,
            "last_close": float(close.iloc[-1]),
        }
    return out


def _row(names: pd.DataFrame, ticker: str) -> dict:
    if names is None or names.empty:
        return {"ticker": ticker}
    hit = names[names["ticker"] == ticker]
    if hit.empty:
        return {"ticker": ticker}
    rec = hit.iloc[0].to_dict()
    rec["ticker"] = ticker
    return rec


def _pair(data, yf_symbol: str):
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


def _finite(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    if n != n:
        return None
    return n


def _clip(score: float) -> float:
    return float(max(0.0, min(100.0, score)))
