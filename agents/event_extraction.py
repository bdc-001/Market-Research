"""
LLM extraction of catalyst events, bound to a source_id.

Uses the shared model client with learned-rules memory OFF.
"""
from __future__ import annotations

from agents.common import clean_json, setup_gemini
from agents.event_provenance import bind_extraction, stamp_source_ids
from agents.event_record import canonical_event_type, refine_event_type
from agents.skill_loader import load_skill_body

EXTRACT_PROMPT = """\
{skill}

**Announcements. Each block is one source. python_type is authoritative — do not reclassify.**
{blob}

Extract catalyst events. Output ONLY valid JSON.
"""


def extract_events(events: list[dict], max_events: int = 40, progress=None) -> list[dict]:
    if not events:
        return []
    batch = stamp_source_ids(events[: int(max_events)])
    if progress:
        progress(f"Extraction: sending {len(batch)} sourced events to LLM...")

    lines = []
    by_id = {}
    for ev in batch:
        by_id[ev["source_id"]] = ev
        lines.append(
            f"[{ev['source_id']}] ticker={ev.get('ticker')} "
            f"python_type={ev.get('event_type')} when={ev.get('announced_at')}\n"
            f"   source_text: {ev.get('subject')}\n"
            f"   Do not change python_type. Extract facts that belong to this type only."
        )
    prompt = EXTRACT_PROMPT.format(
        skill=load_skill_body(
            "filing_extractor",
            default="Extract Indian corporate-announcement catalysts as JSON. Return source_id.",
        ),
        blob="\n".join(lines),
    )
    model = setup_gemini(with_memory=False)
    try:
        raw = model.generate_content(prompt).text or ""
    except Exception as exc:
        if progress:
            progress(f"Extraction failed: {exc}")
        return [_fallback(ev) for ev in batch]

    parsed = clean_json(raw)
    extracted = parsed.get("events") if isinstance(parsed, dict) else None
    if not isinstance(extracted, list) or not extracted:
        return [_fallback(ev) for ev in batch]

    out = []
    used = set()
    for item in extracted:
        if not isinstance(item, dict):
            continue
        bound = bind_extraction(item, by_id)
        if bound is None:
            continue
        if bound["source_id"] in used:
            continue
        used.add(bound["source_id"])
        out.append(bound)

    for ev in batch:
        if ev["source_id"] not in used:
            out.append(_fallback(ev))
    return out or [_fallback(ev) for ev in batch]


def _fallback(ev: dict) -> dict:
    subject = ev.get("subject") or ""
    filing_text = ev.get("filing_text") or ""
    event_type = refine_event_type(
        canonical_event_type(ev.get("event_type")), subject, filing_text,
    )
    return {
        "event_id": ev.get("event_id"),
        "source_id": ev.get("source_id"),
        "ticker": str(ev.get("ticker") or "").upper(),
        "event_type": event_type,
        "catalyst": ev.get("subject") or "",
        "why_it_matters": "Keyword-matched filing; LLM extraction unavailable.",
        "amount_inr_cr": ev.get("amount_inr_cr"),
        "timeframe": "1-6 months",
        "sentiment": 0.3,
        "customer_or_counterparty": None,
        "risks": ["extraction fallback"],
        "source": ev.get("source"),
        "subject": subject,
        "source_text": subject,
        "filing_text": filing_text,
        "full_filing_available": bool(ev.get("full_filing_available") or filing_text),
        "announced_at": ev.get("announced_at"),
        "event_date": ev.get("announced_at") or "",
        "attachment": ev.get("attachment"),
        "extraction_confidence": 0.2,
    }


def _num(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
