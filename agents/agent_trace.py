"""
Live agent-handoff visualisation for the Streamlit run section.

Records what each stage received and passed on, and draws an animated
pipeline in the same tab that is executing — not a separate page.
"""
from __future__ import annotations

from datetime import datetime

PREVIEW_CHARS = 6000
LIVE_CHARS = 1800

COUNCIL_STAGES = [
    ("evidence", "Evidence", "python"),
    ("research", "Historian", "muse"),
    ("scout", "Scout", "muse"),
    ("financial", "Quant", "muse"),
    ("bull", "Bull", "muse"),
    ("bear", "Bear", "muse"),
    ("technical", "Chartist", "muse"),
    ("editor", "Editor", "muse"),
]

QUANTUM_STAGES = [
    ("verify", "Verifier", "python"),
    ("regime", "Regime", "python"),
    ("news", "News", "muse"),
    ("prices", "Prices", "python"),
    ("flow", "Flow", "python"),
    ("earnings", "Earnings", "python"),
    ("scores", "Scorer", "python"),
    ("entry", "Entry", "python"),
    ("portfolio", "Portfolio", "python"),
    ("decay", "Decay", "python"),
    ("report", "Report", "python"),
    ("critic", "Critic", "muse"),
]

DISCOVERY_STAGES = [
    ("universe", "Universe", "python"),
    ("radar", "Filings radar", "python"),
    ("gates", "Liquidity gate", "python"),
    ("filings", "PDF filings", "python"),
    ("extract", "Event extract", "muse"),
    ("materiality", "Materiality", "python"),
    ("episodes", "Episodes", "python"),
    ("expansion", "Evidence expand", "python"),
    ("report", "Report", "python"),
]

DISCOVERY_COUNCIL_STAGES = [
    ("pack", "Evidence pack", "python"),
    ("research", "Historian", "muse"),
    ("financial", "Quant", "muse"),
    ("bull", "Bull", "muse"),
    ("bear", "Bear", "muse"),
    ("technical", "Chartist", "muse"),
    ("editor", "Editor", "muse"),
    ("episode", "Episode", "python"),
]

STAGES = {
    "council": COUNCIL_STAGES,
    "quantum": QUANTUM_STAGES,
    "discovery": DISCOVERY_STAGES,
    "discovery_council": DISCOVERY_COUNCIL_STAGES,
}

__all__ = [
    "TraceLog",
    "LivePipeline",
    "render_agent_trace",
    "trace_to_markdown",
    "clip",
    "df_brief",
    "news_brief",
]


def clip(text, limit: int = PREVIEW_CHARS) -> str:
    if text is None:
        return ""
    raw = str(text).strip()
    if len(raw) <= limit:
        return raw
    return raw[:limit] + f"\n\n… truncated ({len(raw):,} characters total)"


def df_brief(df, columns: list[str] | None = None, n: int = 8) -> str:
    if df is None:
        return "(none)"
    try:
        if getattr(df, "empty", False):
            return "(empty)"
        if not hasattr(df, "columns"):
            return str(df.head(n) if hasattr(df, "head") else df)
        cols = columns or [
            c for c in (
                "ticker", "sector", "composite_score", "conviction",
                "entry_status", "entry_score", "position_weight_pct", "close",
            ) if c in df.columns
        ]
        if not cols:
            cols = list(df.columns[:6])
        return df[cols].head(n).to_string(index=False)
    except Exception as exc:
        try:
            return str(df.head(n) if hasattr(df, "head") else df)
        except Exception:
            return f"(preview failed: {exc})"


def news_brief(news_data: list | None, n: int = 8) -> str:
    if not news_data:
        return "(none)"
    lines = []
    for item in news_data[:n]:
        lines.append(
            f"{item.get('symbol', '?')}  sent={item.get('sentiment')}  "
            f"{item.get('event_type', '')}: {str(item.get('catalyst') or '')[:120]}"
        )
    extra = len(news_data) - min(n, len(news_data))
    if extra > 0:
        lines.append(f"… and {extra} more")
    return "\n".join(lines)


class TraceLog:
    def __init__(self, pipeline: str, title: str, on_event=None):
        self.pipeline = pipeline
        self.title = title
        self.created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.steps: list[dict] = []
        self.on_event = on_event
        self.active_id = None

    def begin(self, step_id: str):
        self.active_id = step_id
        if self.on_event:
            self.on_event("start", step_id, self)

    def add(
        self,
        *,
        step_id: str,
        name: str,
        kind: str,
        receives_from: list[str],
        sends_to: list[str],
        received: str,
        passed: str,
        parsed: dict | None = None,
        note: str = "",
    ):
        passed_s = passed or ""
        self.steps.append({
            "id": step_id,
            "name": name,
            "kind": kind,
            "receives_from": receives_from,
            "sends_to": sends_to,
            "received": clip(received),
            "passed": clip(passed_s),
            "passed_chars": len(passed_s),
            "parsed": parsed,
            "note": note,
        })
        self.active_id = None
        if self.on_event:
            self.on_event("done", step_id, self)

    def add_agent(
        self,
        agent,
        *,
        step_id: str,
        name: str,
        receives_from: list[str],
        sends_to: list[str],
        received: str,
        kind: str = "gemini",
    ):
        self.add(
            step_id=step_id,
            name=name,
            kind=kind,
            receives_from=receives_from,
            sends_to=sends_to,
            received=received,
            passed=getattr(agent, "last_prose", "") or "",
            parsed=getattr(agent, "last_parsed", None),
        )

    def as_dict(self) -> dict:
        return {
            "pipeline": self.pipeline,
            "title": self.title,
            "created": self.created,
            "steps": self.steps,
        }


def trace_to_markdown(trace: dict | None) -> str:
    """CLI / file handoff log. Same payload Streamlit would show."""
    if not trace:
        return "# Agent trace\n\n(empty)\n"
    lines = [
        f"# {trace.get('title') or 'Agent trace'}",
        "",
        f"Generated: {trace.get('created')}",
        f"Pipeline: `{trace.get('pipeline')}`",
        "",
        "Each stage shows what it **received** and what it **passed on**.",
        "This is the handoff log, not a scoreboard.",
        "",
    ]
    for i, step in enumerate(trace.get("steps") or [], 1):
        received_from = ", ".join(step.get("receives_from") or ["(start)"])
        sends_to = ", ".join(step.get("sends_to") or ["(end)"])
        lines += [
            f"## {i}. {step.get('name')}  [{step.get('kind')}]",
            "",
            f"- id: `{step.get('id')}`",
            f"- receives from: {received_from}",
            f"- passes to: {sends_to}",
        ]
        if step.get("note"):
            lines.append(f"- note: {step['note']}")
        lines += [
            "",
            "### Received",
            "",
            "```",
            step.get("received") or "(empty)",
            "```",
            "",
            f"### Passed on ({int(step.get('passed_chars') or 0):,} chars)",
            "",
            "```",
            step.get("passed") or "(empty)",
            "```",
            "",
        ]
        parsed = step.get("parsed")
        if parsed:
            import json
            lines += [
                "### Structured",
                "",
                "```json",
                json.dumps(parsed, indent=2, default=str)[:8000],
                "```",
                "",
            ]
    return "\n".join(lines)


def _pipeline_html(pipeline: str, completed_ids: list[str], active_id: str | None, banner: str) -> str:
    stages = STAGES.get(pipeline) or []
    done = set(completed_ids)
    chips = []
    for i, (sid, name, kind) in enumerate(stages):
        state = "q-wait"
        if sid in done:
            state = "q-done"
        if sid == active_id:
            state = "q-active"
        mark = "✓" if sid in done else str(i + 1)
        if sid == active_id:
            mark = "●"
        chips.append(
            f'<div class="q-chip q-{kind} {state}">'
            f'<span class="q-num">{mark}</span>'
            f'<span class="q-name">{name}</span>'
            f'<span class="q-kind">{kind}</span>'
            f"</div>"
        )
        if i < len(stages) - 1:
            next_id = stages[i + 1][0]
            hot = ""
            if sid in done or sid == active_id or next_id == active_id:
                hot = " q-hot"
            chips.append(f'<div class="q-arrow{hot}">→</div>')

    return (
        FLOW_CSS
        + f'<div class="q-live"><div class="q-banner">{banner}</div>'
        + '<div class="q-flow">'
        + "".join(chips)
        + "</div></div>"
    )


FLOW_CSS = """
<style>
  .q-live { margin: 4px 0 14px 0; }
  .q-banner {
      font-size: 0.9rem;
      font-weight: 600;
      color: #f5a623;
      margin-bottom: 10px;
      min-height: 1.3em;
  }
  .q-flow {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
      padding: 14px;
      background: rgba(255,255,255,0.04);
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 14px;
  }
  .q-chip {
      display: flex;
      flex-direction: column;
      min-width: 88px;
      max-width: 140px;
      padding: 8px 10px;
      border-radius: 10px;
      border: 1px solid rgba(255,255,255,0.16);
      background: rgba(255,255,255,0.05);
      opacity: 0.45;
      transition: opacity 0.3s ease, transform 0.3s ease, border-color 0.3s ease;
  }
  .q-chip.q-wait { opacity: 0.4; }
  .q-chip.q-done {
      opacity: 1;
      background: rgba(74, 222, 128, 0.18);
      border-color: rgba(74, 222, 128, 0.7);
  }
  .q-chip.q-active {
      opacity: 1;
      animation: q-pulse 1.1s ease-in-out infinite;
  }
  .q-chip.q-muse.q-active,
  .q-chip.q-gemini.q-active {
      background: rgba(240, 147, 251, 0.28);
      border-color: #f093fb;
  }
  .q-chip.q-python.q-active {
      background: rgba(79, 172, 254, 0.28);
      border-color: #4facfe;
  }
  @keyframes q-pulse {
      0%, 100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(245, 166, 35, 0.55); }
      50% { transform: scale(1.07); box-shadow: 0 0 18px 4px rgba(245, 166, 35, 0.35); }
  }
  .q-num { font-size: 0.65rem; color: rgba(255,255,255,0.55); font-weight: 700; }
  .q-name { font-size: 0.8rem; font-weight: 700; color: #fff; line-height: 1.2; }
  .q-kind {
      font-size: 0.6rem;
      color: rgba(255,255,255,0.45);
      text-transform: uppercase;
      letter-spacing: 0.04em;
  }
  .q-arrow {
      color: rgba(255,255,255,0.25);
      font-size: 1.15rem;
      font-weight: 700;
      position: relative;
      min-width: 1.2em;
  }
  .q-arrow.q-hot {
      color: #f5a623;
      animation: q-chevrons 0.7s ease-in-out infinite alternate;
  }
  @keyframes q-chevrons {
      from { transform: translateX(-3px); opacity: 0.45; }
      to { transform: translateX(4px); opacity: 1; }
  }
  .q-handoff {
      font-size: 0.8rem;
      color: rgba(255,255,255,0.65);
      margin-bottom: 8px;
  }
</style>
"""


class LivePipeline:
    """Updates a Streamlit placeholder as each agent starts and finishes."""

    def __init__(self, pipeline: str, flow_slot, handoff_slot):
        self.pipeline = pipeline
        self.flow_slot = flow_slot
        self.handoff_slot = handoff_slot
        self.completed: list[str] = []
        self.active_id: str | None = None
        self.paint("Waiting to start…")

    def paint(self, banner: str):
        html = _pipeline_html(self.pipeline, self.completed, self.active_id, banner)
        self.flow_slot.markdown(html, unsafe_allow_html=True)

    def handle(self, event: str, step_id: str, trace: TraceLog):
        names = {sid: name for sid, name, _kind in STAGES.get(self.pipeline, [])}
        label = names.get(step_id, step_id)
        if event == "start":
            self.active_id = step_id
            self.paint(f"{label} is working…")
            return

        if step_id not in self.completed:
            self.completed.append(step_id)
        self.active_id = None
        step = trace.steps[-1] if trace.steps else None
        dest = ", ".join((step or {}).get("sends_to") or ["next stage"])
        chars = (step or {}).get("passed_chars") or 0
        self.paint(f"{label} finished — passing {chars:,} chars to {dest}")
        if step:
            self._show_handoff(step)

    def finish(self):
        self.active_id = None
        self.paint("Pipeline complete. Expand any stage below to read the full handoff.")

    def _show_handoff(self, step: dict):
        import streamlit as st
        src = ", ".join(step.get("receives_from") or ["(start)"])
        dest = ", ".join(step.get("sends_to") or ["(end)"])
        with self.handoff_slot.container():
            st.markdown(
                f"**Now passing:** {step.get('name')} "
                f"← `{src}` → `{dest}`"
            )
            left, right = st.columns(2)
            with left:
                st.caption("This agent received")
                st.code(clip(step.get("received"), LIVE_CHARS) or "(empty)", language=None)
            with right:
                st.caption("This agent passed on")
                st.code(clip(step.get("passed"), LIVE_CHARS) or "(empty)", language=None)


def render_agent_trace(trace: dict | None, *, heading: str = "Full handoff log"):
    """Static after-run log, shown in the same section that just ran."""
    import streamlit as st

    if not trace or not trace.get("steps"):
        return

    st.markdown(FLOW_CSS, unsafe_allow_html=True)
    st.markdown(f"#### {heading}")
    st.caption("Every payload below is what actually moved between stages.")

    for i, step in enumerate(trace["steps"]):
        received_from = ", ".join(step.get("receives_from") or ["(start)"])
        sends_to = ", ".join(step.get("sends_to") or ["(end)"])
        kind = step.get("kind") or "python"
        label = f"{i + 1}. {step.get('name')}  [{kind}]  →  {sends_to}"
        with st.expander(label, expanded=False):
            st.markdown(
                f'<div class="q-handoff">Receives from <b>{received_from}</b>'
                f" → passes to <b>{sends_to}</b></div>",
                unsafe_allow_html=True,
            )
            if step.get("note"):
                st.caption(step["note"])
            left, right = st.columns(2)
            with left:
                st.markdown("**Received**")
                st.code(step.get("received") or "(empty)", language=None)
            with right:
                chars = step.get("passed_chars") or 0
                st.markdown(f"**Passed on** ({chars:,} chars)")
                st.code(step.get("passed") or "(empty)", language=None)
            parsed = step.get("parsed")
            if parsed:
                st.markdown("**Structured prediction**")
                st.json(parsed)
