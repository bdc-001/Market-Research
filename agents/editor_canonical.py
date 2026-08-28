"""
Canonical Editor decision is the single source of truth.

The LLM may write a memo whose Verdict line disagrees with its JSON.
Python rewrites the visible verdict to match the structured decision
before anything is shown or stored. No extra model call.
"""
from __future__ import annotations

import re

from agents.prediction_format import DECISIONS, UNKNOWN_PREDICTION

# The decision expresses the LONGER-TERM (1-3y) investment stance, so it maps
# to a thesis. It deliberately does NOT map to prediction_direction, which is a
# separate SHORT-TERM (30-day) signal the model estimates on its own.
DECISION_TO_THESIS = {
    "buy": "bullish",
    "avoid": "bearish",
    "watch": "neutral",
    "hold": "neutral",
}
_DIRS = {"positive", "negative", "flat"}

VERDICT_LABEL = {
    "buy": "Buy",
    "avoid": "Avoid",
    "watch": "Watch",
    "hold": "Hold",
}

_SIGNAL_LINE = re.compile(
    r"^(\s*[-*]?\s*\*\*(?:30-Day Signal|30 Day Signal)\*\*\s*:)(.*)$",
    re.IGNORECASE | re.MULTILINE,
)
_HORIZON_LINE = re.compile(
    r"^(\s*[-*]?\s*\*\*(?:Investment Horizon|Target Horizon)\*\*\s*:)(.*)$",
    re.IGNORECASE | re.MULTILINE,
)

SIGNAL_LABEL = {
    "positive": "Positive",
    "negative": "Negative",
    "flat": "Flat",
}

_VERDICT_LINE = re.compile(
    r"^(\s*[-*]?\s*\*\*Verdict\*\*\s*:)(.*)$",
    re.IGNORECASE | re.MULTILINE,
)


def align_parsed(parsed: dict | None) -> dict:
    """
    Make the two horizons canonical and internally consistent WITHOUT
    conflating them:

      - final_decision (1-3y stance) -> thesis. Decision wins.
      - prediction_direction + horizon_days = the independent 30-day signal;
        Python never derives it from the decision.
    """
    data = dict(parsed or UNKNOWN_PREDICTION)
    decision = data.get("final_decision")
    if decision not in DECISIONS:
        decision = "watch"
        data["final_decision"] = decision

    data["thesis"] = DECISION_TO_THESIS[decision]

    if not data.get("investment_horizon"):
        data["investment_horizon"] = "1-3y"

    # Short-term signal stays independent; only fill defaults if missing.
    direction = data.get("prediction_direction")
    if direction not in _DIRS:
        direction = "flat"
    data["prediction_direction"] = direction
    if data.get("horizon_days") is None:
        data["horizon_days"] = 30

    # Explicit, separable blocks so the evaluator never has to guess which
    # target it is scoring.
    data["prediction"] = {
        "direction": direction,
        "horizon_days": data["horizon_days"],
    }
    data["investment_thesis"] = {
        "horizon": data["investment_horizon"],
        "stance": decision,
        "thesis": data["thesis"],
    }
    return data


def memo_verdict_token(prose: str) -> str | None:
    """Extract a decision token from the memo Verdict line, if any."""
    match = _VERDICT_LINE.search(prose or "")
    if not match:
        return None
    text = match.group(2).lower()
    for label, mapped in (
        ("strong buy", "buy"),
        ("accumulate", "buy"),
        ("avoid", "avoid"),
        ("sell", "avoid"),
        ("hold", "hold"),
        ("watch", "watch"),
        ("buy", "buy"),
    ):
        if label in text:
            return mapped
    return None


def patch_memo_signal(prose: str, direction: str) -> str:
    label = SIGNAL_LABEL.get(direction, "Flat")
    text = prose or ""
    if _SIGNAL_LINE.search(text):
        return _SIGNAL_LINE.sub(rf"\1 {label}", text, count=1)
    match = _VERDICT_LINE.search(text)
    banner = f"- **30-Day Signal**: {label}\n"
    if match:
        return text[: match.end()] + "\n" + banner + text[match.end():]
    return banner + text


def patch_memo_horizon(prose: str, horizon: str) -> str:
    label = "1-3 Years" if str(horizon or "").lower() in ("1-3y", "1-3 years") else str(horizon or "1-3 Years")
    text = prose or ""
    if _HORIZON_LINE.search(text):
        return _HORIZON_LINE.sub(rf"\1 {label}", text, count=1)
    return text


def patch_memo_verdict(prose: str, decision: str) -> str:
    label = VERDICT_LABEL.get(decision, "Watch")
    text = prose or ""
    replacement = rf"\1 {label}"
    if _VERDICT_LINE.search(text):
        text = _VERDICT_LINE.sub(replacement, text, count=1)
    else:
        title = re.search(r"^# .+$", text, re.MULTILINE)
        banner = f"**Canonical decision:** {label}\n"
        if title:
            start = title.end()
            text = text[:start] + "\n\n" + banner + text[start:]
        else:
            text = banner + "\n" + text
    return text


def memo_signal_token(prose: str) -> str | None:
    match = _SIGNAL_LINE.search(prose or "")
    if not match:
        return None
    text = match.group(2).lower()
    for label, mapped in (
        ("positive", "positive"),
        ("negative", "negative"),
        ("flat", "flat"),
    ):
        if label in text:
            return mapped
    return None


def is_consistent(prose: str, parsed: dict) -> bool:
    decision = (parsed or {}).get("final_decision")
    token = memo_verdict_token(prose)
    if decision not in DECISIONS:
        return False
    if token is None:
        return False
    if token != decision:
        return False
    direction = (parsed or {}).get("prediction_direction")
    signal = memo_signal_token(prose)
    if signal is not None and direction in _DIRS and signal != direction:
        return False
    return True


def enforce(prose: str, parsed: dict | None) -> tuple[str, dict, bool]:
    """
    Returns (memo, canonical_json, was_already_consistent).

    Verdict line follows 1-3y stance. 30-Day Signal line follows the
    independent short-term prediction. Python writes both.
    """
    canonical = align_parsed(parsed)
    already = is_consistent(prose, canonical)
    memo = prose or ""
    memo = patch_memo_verdict(memo, canonical["final_decision"])
    memo = patch_memo_horizon(memo, canonical["investment_horizon"])
    memo = patch_memo_signal(memo, canonical["prediction_direction"])
    return memo, canonical, already
