"""Python event filter — runs before any LLM call."""
from __future__ import annotations

import re

from agents.event_record import canonical_event_type


def classify_subject(subject: str, cfg: dict) -> dict:
    text = (subject or "").lower()
    text = re.sub(r"\s+", " ", text).strip()
    keywords = cfg.get("event_keywords") or {}
    drop = [d.lower() for d in (cfg.get("drop_keywords") or [])]

    matched_type = None
    matched_term = None
    for event_type, terms in keywords.items():
        for term in terms:
            if term.lower() in text:
                matched_type = canonical_event_type(event_type)
                matched_term = term
                break
        if matched_type:
            break

    dropped_by = next((d for d in drop if d in text), None)
    keep = bool(matched_type)
    return {
        "keep": keep,
        "event_type": matched_type or "unclassified",
        "matched_term": matched_term,
        "dropped": (not keep) and bool(dropped_by or True),
        "drop_reason": (
            None if keep
            else (f"routine:{dropped_by}" if dropped_by else "no_catalyst_keyword")
        ),
        "subject": subject,
    }


def filter_announcements(rows: list[dict], cfg: dict) -> list[dict]:
    kept = []
    for row in rows:
        verdict = classify_subject(row.get("subject") or "", cfg)
        if not verdict["keep"]:
            continue
        item = dict(row)
        item["event_type"] = verdict["event_type"]
        item["matched_term"] = verdict["matched_term"]
        kept.append(item)
    return kept
