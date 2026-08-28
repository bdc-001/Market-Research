"""
Phase 2A — episode outcome evaluator + agent-level attribution.

Council is frozen. This module stores predictions as they were, waits until
each horizon elapses, then records what the tape did.

It does not:
- change Council prompts or agents
- populate lessons
- set failure_type (Phase 2B)
- set confidence_calibration (later)
- retune Discovery or QuanTum weights

Three questions stay separate:
- prediction_direction  (was the agent right about price direction?)
- recommendation        (would the agent buy / watch / reject?)
- episodes.final_decision (what did the Editor decide?)
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from agents.episode_store import (
    fetch_episode,
    fetch_predictions,
    fill_missing_recommendations,
    insert_episode_if_missing,
    insert_prediction_if_missing,
    patch_episode_identity,
    upsert_agent_outcome,
    upsert_horizon_outcome,
)

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"

HORIZONS = (30, 60, 90, 180, 365)
FLAT_BAND = 0.03  # |absolute return| <= 3% counts as flat / muted
NIFTY_SYMBOL = "^NSEI"

AGENT_LABELS = {
    "research": "Historian",
    "financial": "Quant",
    "bull": "Bull",
    "bear": "Bear",
    "technical": "Chartist",
    "editor": "Editor",
}

CHAVDA_EPISODE_ID = "53243d44-e51e-44bb-b40b-b2c0992df0c2"
CHAVDA_EVENT_ID = "ev_2522b5ccc6"
CHAVDA_TICKER = "CHAVDA"
CHAVDA_ENTRY_PRICE = 138.05
CHAVDA_ENTRY_DATE = "2026-08-26"
CHAVDA_FINAL_DECISION = "watch"

# Reconstruct episode #1 from the 28-Aug-2026 Council run if the row is missing.
# prediction_direction is the structured field as stored — not inferred from thesis.
CHAVDA_RECOMMENDATIONS = {
    "research": "watch",
    "financial": "watch",
    "bull": "buy",
    "bear": "reject",
    "technical": "watch",
    "editor": "watch",
}
CHAVDA_AGENT_SEED = (
    {
        "agent_name": "research",
        "agent_version": "discovery-council-v1",
        "thesis": "neutral",
        "confidence": 0.42,
        "prediction_direction": "flat",
        "recommendation": "watch",
        "evidence_ids": ["E006", "E009", "E026", "E027", "E032"],
        "parsed": {
            "thesis": "neutral",
            "confidence": 0.42,
            "prediction_direction": "flat",
            "final_decision": "watch",
            "evidence_ids": ["E006", "E009", "E026", "E027", "E032"],
        },
    },
    {
        "agent_name": "financial",
        "agent_version": "discovery-council-v1",
        "thesis": "neutral",
        "confidence": 0.54,
        "prediction_direction": "flat",
        "recommendation": "watch",
        "evidence_ids": ["E006", "E009", "E026", "E024"],
        "parsed": {
            "thesis": "neutral",
            "confidence": 0.54,
            "prediction_direction": "flat",
            "final_decision": "watch",
            "evidence_ids": ["E006", "E009", "E026", "E024"],
        },
    },
    {
        "agent_name": "bull",
        "agent_version": "discovery-council-v1",
        "thesis": "bullish",
        "confidence": 0.58,
        "prediction_direction": "positive",
        "recommendation": "buy",
        "evidence_ids": ["E006", "E024", "E025", "E038", "E039"],
        "parsed": {
            "thesis": "bullish",
            "confidence": 0.58,
            "prediction_direction": "positive",
            "final_decision": "buy",
            "evidence_ids": ["E006", "E024", "E025", "E038", "E039"],
        },
    },
    {
        "agent_name": "bear",
        "agent_version": "discovery-council-v1",
        "thesis": "bearish",
        "confidence": 0.65,
        "prediction_direction": "flat",
        "recommendation": "reject",
        "evidence_ids": ["E006", "E009", "E026", "E032", "E037"],
        "parsed": {
            "thesis": "bearish",
            "confidence": 0.65,
            "prediction_direction": "flat",
            "final_decision": "avoid",
            "evidence_ids": ["E006", "E009", "E026", "E032", "E037"],
        },
    },
    {
        "agent_name": "technical",
        "agent_version": "discovery-council-v1",
        "thesis": "bullish",
        "confidence": 0.52,
        "prediction_direction": "positive",
        "recommendation": "watch",
        "evidence_ids": ["E040", "E041", "E044", "E049"],
        "parsed": {
            "thesis": "bullish",
            "confidence": 0.52,
            "prediction_direction": "positive",
            "final_decision": "watch",
            "evidence_ids": ["E040", "E041", "E044", "E049"],
        },
    },
    {
        "agent_name": "editor",
        "agent_version": "discovery-council-v1",
        "thesis": "neutral",
        "confidence": 0.68,
        "prediction_direction": "flat",
        "recommendation": "watch",
        "evidence_ids": ["E006", "E009", "E026", "E032", "E037"],
        "parsed": {
            "thesis": "neutral",
            "confidence": 0.68,
            "prediction_direction": "flat",
            "final_decision": "watch",
            "evidence_ids": ["E006", "E009", "E026", "E032", "E037"],
        },
    },
)


def parse_iso_date(value) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value).strip()[:10]
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def horizon_target(entry: date, horizon_days: int) -> date:
    return entry + timedelta(days=int(horizon_days))


def horizon_elapsed(entry: date, horizon_days: int, as_of: date) -> bool:
    return as_of >= horizon_target(entry, horizon_days)


def direction_correct(
    prediction_direction: str | None,
    actual_return: float | None,
    flat_band: float = FLAT_BAND,
) -> bool | None:
    """Score prediction_direction against absolute return. Not recommendation."""
    if prediction_direction is None or actual_return is None:
        return None
    d = str(prediction_direction).lower().strip()
    if d == "positive":
        return actual_return > 0
    if d == "negative":
        return actual_return < 0
    if d == "flat":
        return abs(actual_return) <= flat_band
    return None


def watch_decision_quality(
    actual_return: float | None,
    flat_band: float = FLAT_BAND,
) -> str:
    """Editor WATCH is not a directional yes/no. This is a quality label only."""
    if actual_return is None:
        return "pending"
    if abs(actual_return) <= flat_band:
        return "muted_move"
    if actual_return > flat_band:
        return "missed_upside"
    return "missed_downside"


def _series_date(index_value) -> date:
    ts = pd.Timestamp(index_value)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    return ts.date()


def _col(df: pd.DataFrame, name: str) -> pd.Series:
    if df is None or df.empty:
        return pd.Series(dtype=float)
    if name in df.columns:
        series = df[name]
    elif isinstance(df.columns, pd.MultiIndex) and name in df.columns.get_level_values(0):
        series = df[name]
    else:
        return pd.Series(dtype=float)
    if isinstance(series, pd.DataFrame):
        series = series.iloc[:, 0]
    return pd.to_numeric(series.squeeze(), errors="coerce")


def close_on_or_before(df: pd.DataFrame, day: date) -> tuple[float | None, date | None]:
    close = _col(df, "Close")
    if close.empty:
        return None, None
    picked = None
    for idx, value in close.items():
        d = _series_date(idx)
        if d <= day and value == value:
            picked = (float(value), d)
        elif d > day:
            break
    if picked is None:
        return None, None
    return picked


def window_high_low(df: pd.DataFrame, start: date, end: date) -> tuple[float | None, float | None]:
    high = _col(df, "High")
    low = _col(df, "Low")
    close = _col(df, "Close")
    highs, lows = [], []
    source_high = high if not high.empty else close
    source_low = low if not low.empty else close
    for idx, value in source_high.items():
        d = _series_date(idx)
        if start <= d <= end and value == value:
            highs.append(float(value))
    for idx, value in source_low.items():
        d = _series_date(idx)
        if start <= d <= end and value == value:
            lows.append(float(value))
    return (max(highs) if highs else None, min(lows) if lows else None)


def compute_horizon_metrics(
    *,
    entry_price: float,
    entry_date: date,
    horizon_days: int,
    stock: pd.DataFrame | None,
    nifty: pd.DataFrame | None,
    as_of: date,
) -> dict:
    target = horizon_target(entry_date, horizon_days)
    base = {
        "horizon_days": int(horizon_days),
        "status": "pending",
        "entry_price": float(entry_price),
        "exit_price": None,
        "entry_date": entry_date.isoformat(),
        "exit_date": None,
        "absolute_return": None,
        "nifty_return": None,
        "relative_return": None,
        "max_gain": None,
        "max_drawdown": None,
    }
    if as_of < target:
        return base
    if stock is None or stock.empty:
        base["status"] = "missing_data"
        return base

    exit_price, exit_date = close_on_or_before(stock, target)
    if exit_price is None:
        base["status"] = "missing_data"
        return base

    abs_ret = (exit_price - entry_price) / entry_price if entry_price else None
    nifty_ret = None
    if nifty is not None and not nifty.empty:
        n_entry, _ = close_on_or_before(nifty, entry_date)
        n_exit, _ = close_on_or_before(nifty, target)
        if n_entry and n_exit:
            nifty_ret = (n_exit - n_entry) / n_entry
    rel = None if abs_ret is None or nifty_ret is None else abs_ret - nifty_ret

    peak, trough = window_high_low(stock, entry_date, target)
    max_gain = None if peak is None or not entry_price else (peak - entry_price) / entry_price
    max_dd = None if trough is None or not entry_price else (trough - entry_price) / entry_price

    base.update({
        "status": "elapsed",
        "exit_price": round(exit_price, 4),
        "exit_date": exit_date.isoformat() if exit_date else None,
        "absolute_return": None if abs_ret is None else round(abs_ret, 6),
        "nifty_return": None if nifty_ret is None else round(nifty_ret, 6),
        "relative_return": None if rel is None else round(rel, 6),
        "max_gain": None if max_gain is None else round(max_gain, 6),
        "max_drawdown": None if max_dd is None else round(max_dd, 6),
    })
    return base


def _yf_symbol(ticker: str) -> str:
    t = ticker.strip().upper()
    if t.startswith("^") or t.endswith((".NS", ".BO")):
        return t
    return f"{t}.NS"


def fetch_price_history(symbol: str, start: date, end: date) -> pd.DataFrame:
    import yfinance as yf

    data = yf.download(
        symbol,
        start=start.isoformat(),
        end=(end + timedelta(days=5)).isoformat(),
        interval="1d",
        progress=False,
        auto_adjust=True,
    )
    return data if data is not None else pd.DataFrame()


def seed_chavda_episode() -> str:
    """
    Make CHAVDA episode #1. Fills missing identity / recommendation only.
    Does not overwrite prediction_direction or an existing recommendation.
    """
    episode_id = CHAVDA_EPISODE_ID
    insert_episode_if_missing(
        episode_id=episode_id,
        source="discovery_council",
        ticker=CHAVDA_TICKER,
        run_id="chavda-council-20260828",
        horizon_days=30,
        horizon="30d",
        regime="discovery_phase_c",
        final_decision=CHAVDA_FINAL_DECISION,
        entry_price=CHAVDA_ENTRY_PRICE,
        event_id=CHAVDA_EVENT_ID,
        entry_date=CHAVDA_ENTRY_DATE,
        signals={"event_id": CHAVDA_EVENT_ID, "source_id": "src_2522b5ccc6"},
    )
    patch_episode_identity(
        episode_id,
        event_id=CHAVDA_EVENT_ID,
        entry_date=CHAVDA_ENTRY_DATE,
        entry_price=CHAVDA_ENTRY_PRICE,
        final_decision=CHAVDA_FINAL_DECISION,
        event_type="large_order_win",
    )
    for agent in CHAVDA_AGENT_SEED:
        insert_prediction_if_missing(episode_id, agent)
    fill_missing_recommendations(episode_id, fallback=CHAVDA_RECOMMENDATIONS)
    return episode_id


def _bool_or_none(value) -> int | None:
    if value is None:
        return None
    return 1 if value else 0


def evaluate_episode(
    episode_id: str,
    *,
    as_of: date | None = None,
    stock: pd.DataFrame | None = None,
    nifty: pd.DataFrame | None = None,
    fetch_prices: bool = True,
) -> dict:
    as_of = as_of or date.today()
    episode = fetch_episode(episode_id)
    if not episode:
        raise ValueError(f"episode not found: {episode_id}")
    predictions = fetch_predictions(episode_id)
    entry_date = parse_iso_date(episode.get("entry_date"))
    entry_price = episode.get("entry_price")
    try:
        entry_price = float(entry_price) if entry_price not in (None, "") else None
    except (TypeError, ValueError):
        entry_price = None
    ticker = str(episode.get("ticker") or "")

    need_prices = bool(
        entry_date and entry_price
        and any(horizon_elapsed(entry_date, h, as_of) for h in HORIZONS)
    )
    if fetch_prices and need_prices:
        if stock is None:
            stock = fetch_price_history(_yf_symbol(ticker), entry_date, as_of)
        if nifty is None:
            nifty = fetch_price_history(NIFTY_SYMBOL, entry_date, as_of)

    evaluated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    horizons = []
    for days in HORIZONS:
        if not entry_date or entry_price is None:
            metrics = {
                "horizon_days": days,
                "status": "missing_data",
                "entry_price": entry_price,
                "exit_price": None,
                "entry_date": episode.get("entry_date"),
                "exit_date": None,
                "absolute_return": None,
                "nifty_return": None,
                "relative_return": None,
                "max_gain": None,
                "max_drawdown": None,
            }
        else:
            metrics = compute_horizon_metrics(
                entry_price=entry_price,
                entry_date=entry_date,
                horizon_days=days,
                stock=stock,
                nifty=nifty,
                as_of=as_of,
            )
        metrics["episode_id"] = episode_id
        metrics["evaluated_at"] = evaluated_at
        upsert_horizon_outcome(metrics)
        horizons.append(metrics)

        for pred in predictions:
            agent = pred.get("agent_name") or "unknown"
            abs_ret = metrics.get("absolute_return")
            rel_ret = metrics.get("relative_return")
            pending = metrics.get("status") != "elapsed"
            is_editor = agent == "editor"
            quality = None
            correct = None
            if pending:
                quality = "pending" if is_editor else None
            elif is_editor:
                quality = watch_decision_quality(abs_ret)
            else:
                correct = direction_correct(pred.get("prediction_direction"), abs_ret)
            upsert_agent_outcome({
                "episode_id": episode_id,
                "agent": agent,
                "horizon_days": days,
                "actual_return": abs_ret,
                "relative_return": rel_ret,
                "prediction_correct": _bool_or_none(correct),
                "decision_quality": quality,
                "confidence_calibration": None,
                "failure_type": None,
                "evaluated_at": evaluated_at,
            })

    result = {
        "episode_id": episode_id,
        "event_id": episode.get("event_id"),
        "ticker": ticker,
        "entry_price": entry_price,
        "entry_date": episode.get("entry_date"),
        "final_decision": episode.get("final_decision"),
        "as_of": as_of.isoformat(),
        "horizons": horizons,
        "predictions": predictions,
    }
    return result


def _pct(value) -> str:
    if value is None:
        return "pending"
    return f"{value * 100:+.2f}%"


def _yes_no(value) -> str:
    if value is True:
        return "YES"
    if value is False:
        return "NO"
    return "—"


def render_outcome_report(result: dict) -> str:
    ticker = result["ticker"]
    lines = [
        f"# Discovery outcomes: {ticker}",
        "",
        "Phase 2A observation only. Lessons are not populated. "
        "Council architecture is frozen.",
        "",
        "## Episode",
        f"- episode_id: `{result['episode_id']}`",
        f"- event_id: `{result.get('event_id') or ''}`",
        f"- ticker: {ticker}",
        f"- entry_date: {result.get('entry_date')}",
        f"- entry_price: ₹{result.get('entry_price')}",
        f"- council_decision (Editor): **{(result.get('final_decision') or '').upper()}**",
        f"- as_of: {result.get('as_of')}",
        "",
        "Fields are not interchangeable:",
        "- **prediction_direction** — agent view of price direction",
        "- **recommendation** — agent buy / watch / reject",
        "- **final_decision** — Council Editor only",
        "",
        "## Horizons",
        "",
        "| Horizon | Status | Entry | Exit | Abs return | NIFTY | Relative | Max gain | Max DD |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for h in result["horizons"]:
        lines.append(
            "| {days}D | {status} | {entry} | {exit} | {abs_r} | {nifty} | {rel} | {gain} | {dd} |".format(
                days=h["horizon_days"],
                status=h.get("status"),
                entry=h.get("entry_price"),
                exit=h.get("exit_price") if h.get("exit_price") is not None else "—",
                abs_r=_pct(h.get("absolute_return")),
                nifty=_pct(h.get("nifty_return")),
                rel=_pct(h.get("relative_return")),
                gain=_pct(h.get("max_gain")),
                dd=_pct(h.get("max_drawdown")),
            )
        )

    lines += ["", "## Stored predictions", ""]
    lines.append("| Agent | Prediction | Confidence | Recommendation |")
    lines.append("|---|---|---|---|")
    by_agent: dict[str, dict] = {}
    for pred in result.get("predictions") or []:
        name = pred.get("agent_name") or "unknown"
        by_agent[name] = pred
        conf = pred.get("confidence")
        conf_s = f"{float(conf):.2f}" if conf not in (None, "") else "—"
        lines.append(
            "| {label} | {direction} | {conf} | {rec} |".format(
                label=AGENT_LABELS.get(name, name),
                direction=pred.get("prediction_direction") or "—",
                conf=conf_s,
                rec=pred.get("recommendation") or "—",
            )
        )
    lines += [
        "",
        f"Council decision (`episodes.final_decision`): **{(result.get('final_decision') or '').upper()}**",
        "",
        "Bull may recommend buy while the Council decides watch. Those are different questions.",
        "",
        "## Attribution by horizon",
        "",
    ]
    elapsed = [h for h in result["horizons"] if h.get("status") == "elapsed"]
    if not elapsed:
        first = next((h for h in result["horizons"] if h.get("status") == "pending"), None)
        due = ""
        entry = parse_iso_date(result.get("entry_date"))
        if first and entry:
            due = horizon_target(entry, first["horizon_days"]).isoformat()
        lines.append(
            f"All horizons pending as of {result.get('as_of')}. "
            f"First scoreable date: **{due or 'unknown'}** (30D). "
            "Rows are reserved in `agent_outcomes`; `prediction_correct` and "
            "`decision_quality` stay null until then."
        )
        lines.append("")
    else:
        for h in result["horizons"]:
            lines.append(f"### {h['horizon_days']}D  ({h.get('status')})")
            lines.append("")
            if h.get("status") != "elapsed":
                lines.append("Pending.")
                lines.append("")
                continue
            abs_r = h.get("absolute_return")
            lines.append(f"Outcome: {_pct(abs_r)} absolute, {_pct(h.get('relative_return'))} vs NIFTY.")
            lines.append("")
            for name, pred in by_agent.items():
                label = AGENT_LABELS.get(name, name)
                if name == "editor":
                    lines.append(
                        f"- **{label}** recommendation={pred.get('recommendation') or '—'} "
                        f"→ decision quality: {watch_decision_quality(abs_r)}"
                    )
                else:
                    scored = direction_correct(pred.get("prediction_direction"), abs_r)
                    lines.append(
                        f"- **{label}** prediction={pred.get('prediction_direction') or '—'} "
                        f"→ {_pct(abs_r)} → Correct: {_yes_no(scored)}"
                    )
            lines.append("")

    if ticker.upper() == "CHAVDA":
        lines += [
            "## Hypothesis under test (not a lesson)",
            "",
            "₹54.72 Cr order looks large versus trailing revenue, but is 6% of the",
            "disclosed unexecuted book and is spread across 24 months — so the",
            "catalyst may be incremental rather than transformational.",
            "",
            "Bull: 21% of revenue / 14% of market cap plus delayed discovery in an",
            "illiquid small-cap could still produce upside.",
            "",
            "Bear: missing margin, execution, customer and balance-sheet facts",
            "prevent establishing asymmetry. Structured `prediction_direction` on",
            "this run was **flat** (thesis bearish, recommendation reject) — those",
            "three fields are scored separately.",
            "",
            "Do not write a `lessons` row until this episode has elapsed horizons",
            "and a later sample of similar events exists.",
            "",
        ]
    return "\n".join(lines) + "\n"


def write_outcome_report(result: dict) -> Path:
    REPORTS.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    ticker = result.get("ticker") or "UNKNOWN"
    path = REPORTS / f"discovery_outcomes_{ticker}_{stamp}.md"
    path.write_text(render_outcome_report(result), encoding="utf-8")
    return path


def evaluate_chavda(*, as_of: date | None = None, fetch_prices: bool = True) -> dict:
    episode_id = seed_chavda_episode()
    return evaluate_episode(episode_id, as_of=as_of, fetch_prices=fetch_prices)
