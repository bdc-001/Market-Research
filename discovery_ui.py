"""
Discovery sample UI — Streamlit tab.

Observation only. Does not teach agents or write lessons.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from agents.episode_store import (
    fetch_agent_outcomes,
    fetch_horizon_outcomes,
    fetch_predictions,
    list_discovery_council_episodes,
)
from agents.outcome_evaluator import AGENT_LABELS, FLAT_BAND, horizon_target, parse_iso_date

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"

AGENT_ORDER = ("research", "financial", "bull", "bear", "technical", "editor")

_CSS = """
<style>
  .disc-pipe { display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin: 8px 0 18px; }
  .disc-step {
      background: rgba(255,255,255,0.07);
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 999px;
      padding: 8px 14px;
      font-size: 0.78rem;
      font-weight: 700;
      color: rgba(255,255,255,0.85);
  }
  .disc-step.on { background: linear-gradient(135deg, #667eea, #764ba2); color: white; }
  .disc-arrow { color: rgba(255,255,255,0.35); font-weight: 700; }
  .disc-badge {
      display:inline-block; border-radius: 8px; padding: 3px 10px;
      font-size: 0.75rem; font-weight: 800; letter-spacing: 0.04em;
  }
  .disc-watch { background: rgba(245,158,11,0.22); color: #fcd34d; }
  .disc-buy { background: rgba(34,197,94,0.22); color: #4ade80; }
  .disc-reject { background: rgba(239,68,68,0.22); color: #f87171; }
  .disc-pending { background: rgba(147,197,253,0.18); color: #93c5fd; }
  .disc-note {
      background: rgba(255,255,255,0.05);
      border: 1px solid rgba(255,255,255,0.1);
      border-radius: 12px;
      padding: 12px 14px;
      font-size: 0.85rem;
      color: rgba(255,255,255,0.75);
  }
</style>
"""


def render_discovery_tab():
    st.markdown(_CSS, unsafe_allow_html=True)
    st.subheader("Discovery Council — sample & outcomes")
    st.caption(
        "SME / microcap filings → evidence pack → Council → stored predictions → wait for tape. "
        "Agents are not taught. Lessons are empty. CHAVDA is episode #1, not a rule."
    )
    st.markdown(
        '<div class="disc-pipe">'
        '<span class="disc-step on">Discovery</span><span class="disc-arrow">→</span>'
        '<span class="disc-step on">Evidence</span><span class="disc-arrow">→</span>'
        '<span class="disc-step on">Council</span><span class="disc-arrow">→</span>'
        '<span class="disc-step on">Predictions</span><span class="disc-arrow">→</span>'
        '<span class="disc-step">Outcomes (pending)</span>'
        "</div>",
        unsafe_allow_html=True,
    )

    episodes = list_discovery_council_episodes()
    if not episodes:
        st.warning("No Discovery Council episodes yet. Run `python build_discovery_sample.py`.")
        return

    types = {}
    pending_30 = 0
    for ep in episodes:
        et = ep.get("event_type") or "unclassified"
        types[et] = types.get(et, 0) + 1
        due = _first_due(ep)
        if due and date.today() < due:
            pending_30 += 1

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Council episodes", len(episodes))
    c2.metric("Event types", len(types))
    c3.metric("30D still pending", pending_30)
    c4.metric("Lessons written", 0)

    st.markdown(
        '<div class="disc-note">Three questions stay separate: '
        "<b>prediction</b> (direction) · <b>recommendation</b> (buy/watch/reject) · "
        "<b>council decision</b> (Editor only). "
        "Do not promote CHAVDA into a general SME order-win rule.</div>",
        unsafe_allow_html=True,
    )

    view_ep, view_radar, view_help = st.tabs(["Episodes", "Latest radar", "How this learns"])
    with view_ep:
        _render_episodes(episodes, types)
    with view_radar:
        _render_radar()
    with view_help:
        st.markdown(
            """
**Now:** store predictions. Wait.

**25 Sep 2026:** first CHAVDA 30D measurement.

**After enough elapsed episodes:** failure classification
(`wrong_event`, `wrong_materiality`, `wrong_timing`, …) sliced by
**agent × event type × horizon × regime**.

**Only then:** validated lessons, retrieved into the next Council.

One episode tells you what happened to that ticker. It does not tell you a rule.
"""
        )


def _first_due(ep: dict) -> date | None:
    entry = parse_iso_date(ep.get("entry_date") or (ep.get("created_at") or "")[:10])
    if not entry:
        return None
    return horizon_target(entry, 30)


def _badge(decision: str) -> str:
    d = (decision or "watch").lower()
    klass = {"buy": "disc-buy", "reject": "disc-reject"}.get(d, "disc-watch")
    return f'<span class="disc-badge {klass}">{d.upper()}</span>'


def _pct(value) -> str:
    if value in (None, ""):
        return "pending"
    try:
        return f"{float(value) * 100:+.2f}%"
    except (TypeError, ValueError):
        return "pending"


def _latest_report(*patterns: str) -> Path | None:
    matches = []
    for pattern in patterns:
        matches.extend(REPORTS.glob(pattern))
    if not matches:
        return None
    return sorted(matches)[-1]


def _render_episodes(episodes: list[dict], types: dict):
    col_f, col_e = st.columns([1, 2])
    with col_f:
        type_filter = st.selectbox(
            "Event type",
            ["All"] + sorted(types),
            key="disc_type_filter",
        )
    filtered = [
        ep for ep in episodes
        if type_filter == "All" or (ep.get("event_type") or "unclassified") == type_filter
    ]
    labels = []
    for i, ep in enumerate(filtered, start=1):
        labels.append(
            f"{i}. {ep.get('ticker')} · {ep.get('event_type') or '—'} · "
            f"{(ep.get('final_decision') or 'watch').upper()}"
        )
    with col_e:
        choice = st.selectbox("Episode", labels, key="disc_episode_select")
    if not filtered:
        st.info("No episodes of that type.")
        return
    ep = filtered[labels.index(choice)]
    _render_episode_detail(ep, index=episodes.index(ep) + 1)


def _render_episode_detail(ep: dict, index: int):
    ticker = ep.get("ticker") or ""
    decision = ep.get("final_decision") or "watch"
    due = _first_due(ep)
    st.markdown(
        f"### {ticker}  {_badge(decision)}  "
        f'<span class="disc-badge disc-pending">#{index}</span>',
        unsafe_allow_html=True,
    )
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Event type", ep.get("event_type") or "—")
    price = ep.get("entry_price")
    m2.metric("Entry", "—" if price in (None, "") else f"₹{float(price):.2f}")
    m3.metric("Entry date", ep.get("entry_date") or "—")
    m4.metric("30D due", due.isoformat() if due else "—")
    st.caption(f"event_id `{ep.get('event_id') or ''}` · episode `{ep.get('id')}`")

    predictions = fetch_predictions(ep["id"])
    if predictions:
        rows = []
        for pred in sorted(predictions, key=lambda p: AGENT_ORDER.index(p.get("agent_name")) if p.get("agent_name") in AGENT_ORDER else 99):
            name = pred.get("agent_name") or ""
            conf = pred.get("confidence")
            try:
                conf_s = f"{float(conf):.2f}" if conf not in (None, "") else "—"
            except (TypeError, ValueError):
                conf_s = "—"
            rows.append({
                "Agent": AGENT_LABELS.get(name, name),
                "Prediction": pred.get("prediction_direction") or "—",
                "Confidence": conf_s,
                "Recommendation": pred.get("recommendation") or "—",
            })
        st.markdown("**Stored predictions** — not interchangeable with the Council decision")
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.caption(f"Council decision (Editor): **{decision.upper()}**. Bull may recommend buy while the Council watches.")

    horizons = fetch_horizon_outcomes(ep["id"])
    if not horizons:
        st.info("No horizon rows yet. Click Evaluate to reserve pending 30/60/90/180/365D slots.")
    else:
        hrows = []
        for h in horizons:
            hrows.append({
                "Horizon": f"{h.get('horizon_days')}D",
                "Status": h.get("status") or "pending",
                "Abs return": _pct(h.get("absolute_return")),
                "NIFTY": _pct(h.get("nifty_return")),
                "Relative": _pct(h.get("relative_return")),
                "Max gain": _pct(h.get("max_gain")),
                "Max DD": _pct(h.get("max_drawdown")),
            })
        st.markdown("**Horizons**")
        st.dataframe(pd.DataFrame(hrows), use_container_width=True, hide_index=True)

    if st.button("Refresh pending outcomes", key=f"eval_{ep.get('id')}"):
        from agents.outcome_evaluator import evaluate_episode, write_outcome_report
        try:
            result = evaluate_episode(ep["id"], fetch_prices=True)
            path = write_outcome_report(result)
            st.success(f"Updated. Report: {path.name}")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    agent_out = fetch_agent_outcomes(ep["id"])
    if agent_out:
        elapsed = [h for h in horizons if (h.get("status") == "elapsed")]
        if elapsed:
            st.markdown("**Agent attribution (elapsed horizons)**")
            arows = []
            for row in agent_out:
                if row.get("actual_return") in (None, ""):
                    continue
                agent = row.get("agent") or ""
                correct = row.get("prediction_correct")
                if agent == "editor":
                    scored = row.get("decision_quality") or "—"
                elif correct in (1, "1", True):
                    scored = "YES"
                elif correct in (0, "0", False):
                    scored = "NO"
                else:
                    scored = "—"
                arows.append({
                    "Horizon": f"{row.get('horizon_days')}D",
                    "Agent": AGENT_LABELS.get(agent, agent),
                    "Return": _pct(row.get("actual_return")),
                    "Correct / quality": scored,
                })
            if arows:
                st.dataframe(pd.DataFrame(arows), use_container_width=True, hide_index=True)
        else:
            st.caption(
                f"Attribution reserved ({len(agent_out)} rows). "
                f"First scoreable date is the 30D due above. "
                f"Flat band is ±{FLAT_BAND:.0%} absolute return."
            )

    memo = _latest_report(f"discovery_council_{ticker}_*.md")
    pack = _latest_report(f"discovery_expansion_{ticker}_*.md")
    trace = _latest_report(f"discovery_council_trace_{ticker}_*.md")
    outcomes = _latest_report(f"discovery_outcomes_{ticker}_*.md")
    with st.expander("Council memo", expanded=ticker == "CHAVDA"):
        if memo:
            st.markdown(memo.read_text(encoding="utf-8", errors="replace"))
        else:
            st.caption("No memo on disk.")
    with st.expander("Evidence pack"):
        if pack:
            st.markdown(pack.read_text(encoding="utf-8", errors="replace"))
        else:
            st.caption("No expansion pack on disk.")
    with st.expander("Handoff trace"):
        if trace:
            st.markdown(trace.read_text(encoding="utf-8", errors="replace")[:12000])
        else:
            st.caption("No trace on disk.")
    if outcomes:
        with st.expander("Latest outcome report"):
            st.markdown(outcomes.read_text(encoding="utf-8", errors="replace"))


def _render_radar():
    path = _latest_report("discovery_catalyst_*.md")
    sample = _latest_report("discovery_sample_*.md")
    if sample:
        st.markdown(sample.read_text(encoding="utf-8", errors="replace"))
    if path:
        with st.expander("Full latest Discovery catalyst report", expanded=False):
            st.markdown(path.read_text(encoding="utf-8", errors="replace"))
    else:
        st.info("No Discovery catalyst report yet.")
    st.caption("To grow the sample without teaching agents: `python build_discovery_sample.py --lookback 21 --max-n 8`")
