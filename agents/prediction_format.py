"""
Parse dual council output: human prose plus a machine-readable prediction.

No extra Gemini call — the existing prompt just appends a JSON marker.
"""
from __future__ import annotations

import json
import re

PREDICTION_MARKER = "|||PREDICTION|||"

JSON_APPENDIX = f"""

{PREDICTION_MARKER}
After the human-readable answer, output that marker on its own line, then a
single JSON object (no markdown fence) with exactly these fields:
{{
  "thesis": "bullish" | "bearish" | "neutral",
  "confidence": 0.0,
  "prediction_direction": "positive" | "negative" | "flat",
  "horizon_days": 30,
  "investment_horizon": "1-3y",
  "evidence": ["short fact", "short fact"],
  "evidence_ids": ["E001", "E002"],
  "evidence_labels": ["trailing_pe", "price"],
  "risks": ["short risk"],
  "key_assumption": "one sentence",
  "reasoning_summary": "one or two sentences; not a chain of thought",
  "final_decision": "buy" | "watch" | "avoid" | "hold"
}}
Two horizons are separate and must not be conflated:
- prediction_direction + horizon_days = the SHORT-TERM (default 30-day) signal.
- final_decision + investment_horizon = the LONGER-TERM (1-3y) investment stance.
Cite evidence_ids only from YOUR supplied package, or evidence_labels
(python maps labels to IDs). Never invent E0xx. Chartist should use labels
(price, sma20, rsi, …); Python assigns those IDs. final_decision is required
only for the editor; other agents may omit it or set it to null.
Confidence is stored and never used for ranking.
"""

_THESES = {"bullish", "bearish", "neutral"}
_DIRS = {"positive", "negative", "flat"}
_DECISIONS = {"buy", "watch", "avoid", "hold"}
DECISIONS = _DECISIONS
_HORIZONS = {"1-3y", "1-3Y", "3-5y", "5y+", "long", "short"}
_ID_RE = re.compile(r"E\d{3,}")

UNKNOWN_PREDICTION = {
    "thesis": "unknown",
    "confidence": None,
    "prediction_direction": None,
    "horizon_days": None,
    "investment_horizon": None,
    "evidence": [],
    "evidence_ids": [],
    "evidence_labels": [],
    "invalid_evidence_ids": [],
    "validator_status": None,
    "risks": [],
    "key_assumption": "",
    "reasoning_summary": "",
    "final_decision": None,
}


def parse_dual_output(raw: str) -> tuple[str, dict]:
    """
    Returns (prose_for_humans, parsed_prediction).

    On parse failure the prediction has thesis=unknown and empty fields.
    The full raw string is never discarded; callers store it separately.
    """
    text = raw or ""
    if PREDICTION_MARKER in text:
        prose, _, tail = text.partition(PREDICTION_MARKER)
    else:
        prose, tail = text, text

    parsed = _clean_json(tail.strip()) if tail.strip() else {}
    if not parsed:
        matches = list(re.finditer(r"\{[\s\S]*\}", text))
        if matches:
            parsed = _clean_json(matches[-1].group(0))

    return prose.strip(), _normalize(parsed)


def decision_from_editor(parsed: dict, prose: str) -> str:
    """Prefer JSON final_decision; fall back to the memo verdict line."""
    decision = parsed.get("final_decision") if parsed else None
    if decision in _DECISIONS:
        return decision

    text = (prose or "").lower()
    for label, mapped in (
        ("strong buy", "buy"),
        ("accumulate", "buy"),
        ("avoid", "avoid"),
        ("hold", "hold"),
        ("watch", "watch"),
        ("buy", "buy"),
        ("sell", "avoid"),
    ):
        if label in text:
            return mapped
    return "watch"


def _normalize(parsed: dict) -> dict:
    if not parsed:
        return dict(UNKNOWN_PREDICTION)

    thesis = str(parsed.get("thesis") or "unknown").lower().strip()
    if thesis not in _THESES:
        thesis = "unknown"

    direction = parsed.get("prediction_direction")
    if direction is not None:
        direction = str(direction).lower().strip()
        if direction not in _DIRS:
            direction = None

    decision = parsed.get("final_decision")
    if decision is not None:
        decision = str(decision).lower().replace(" ", "_").strip()
        decision = {
            "strong_buy": "buy",
            "accumulate": "buy",
            "sell": "avoid",
        }.get(decision, decision)
        if decision not in _DECISIONS:
            decision = None

    try:
        confidence = float(parsed["confidence"]) if parsed.get("confidence") is not None else None
        if confidence is not None:
            confidence = max(0.0, min(1.0, confidence))
    except (TypeError, ValueError):
        confidence = None

    try:
        horizon = int(parsed["horizon_days"]) if parsed.get("horizon_days") is not None else None
    except (TypeError, ValueError):
        horizon = None

    investment_horizon = parsed.get("investment_horizon")
    if investment_horizon is not None:
        investment_horizon = str(investment_horizon).strip()
        if not investment_horizon:
            investment_horizon = None

    evidence = parsed.get("evidence") or []
    evidence_ids = parsed.get("evidence_ids") or []
    evidence_labels = parsed.get("evidence_labels") or []
    risks = parsed.get("risks") or []
    if not isinstance(evidence, list):
        evidence = [str(evidence)]
    if not isinstance(evidence_ids, list):
        evidence_ids = [str(evidence_ids)]
    if not isinstance(evidence_labels, list):
        evidence_labels = [str(evidence_labels)]
    if not isinstance(risks, list):
        risks = [str(risks)]

    # Only keep well-formed IDs here; scope validation happens in the
    # orchestrator, which knows which IDs each agent was actually given.
    clean_ids = []
    for raw_id in evidence_ids:
        token = str(raw_id).strip().upper()
        match = _ID_RE.fullmatch(token)
        if match:
            clean_ids.append(token)

    return {
        "thesis": thesis,
        "confidence": confidence,
        "prediction_direction": direction,
        "horizon_days": horizon,
        "investment_horizon": investment_horizon,
        "evidence": [str(x) for x in evidence],
        "evidence_ids": clean_ids,
        "evidence_labels": [str(x) for x in evidence_labels],
        "invalid_evidence_ids": [],
        "validator_status": None,
        "risks": [str(x) for x in risks],
        "key_assumption": str(parsed.get("key_assumption") or ""),
        "reasoning_summary": str(parsed.get("reasoning_summary") or ""),
        "final_decision": decision,
    }


def validate_evidence_ids(parsed: dict | None, allowed_ids) -> dict:
    """Backward-compatible wrapper; prefer agents.evidence_validator.validate."""
    if not parsed:
        return parsed
    allowed = {str(x).strip().upper() for x in (allowed_ids or [])}
    cited = [str(x).strip().upper() for x in (parsed.get("evidence_ids") or [])]
    valid, invalid = [], []
    for token in cited:
        if not _ID_RE.fullmatch(token):
            invalid.append(token)
        elif allowed and token not in allowed:
            invalid.append(token)
        else:
            valid.append(token)
    parsed["evidence_ids"] = valid
    parsed["invalid_evidence_ids"] = invalid
    parsed["validator_status"] = "repaired" if invalid else "pass"
    return parsed


def _clean_json(text: str) -> dict:
    try:
        if "```json" in text:
            raw = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            raw = text.split("```")[1].split("```")[0].strip()
        else:
            raw = text.strip()
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def dumps(obj) -> str:
    return json.dumps(_jsonable(obj), ensure_ascii=False)


def _jsonable(value):
    if value is None:
        return None
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if hasattr(value, "item"):
        try:
            return _jsonable(value.item())
        except Exception:
            pass
    if isinstance(value, float) and value != value:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
