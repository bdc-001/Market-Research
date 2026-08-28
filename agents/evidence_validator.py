"""
Evidence Lineage Validator.

Agent JSON is not trusted for attribution. Python keeps only IDs that
exist in the slice that agent actually received. Chartist IDs are assigned
from the technical snapshot labels — the model never owns them.
"""
from __future__ import annotations

CHARTIST_LABELS = (
    "price", "sma20", "sma50", "sma200", "rsi", "macd", "macd_signal",
    "atr", "volume", "volume_vs_average", "high_52w", "low_52w",
    "support", "resistance", "trend", "cross", "bars",
)


def allowed_ids(package, role: str) -> set[str]:
    if package is None:
        return set()
    if role == "editor":
        return {item.id for item in package.items}
    return package.role_ids(role)


def label_to_id(package, role: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    items = package.items if role == "editor" else package.for_role(role)
    for item in items:
        mapping[item.label.lower()] = item.id
        mapping[item.id.lower()] = item.id
    return mapping


def attribute_chartist(package, snapshot: dict | None) -> list[str]:
    """Python-owned IDs for whatever technical scalars actually exist."""
    snap = snapshot or {}
    mapping = package.label_id_map("market") if package is not None else {}
    ids = []
    for label in CHARTIST_LABELS:
        if snap.get(label) is None:
            continue
        eid = mapping.get(label)
        if eid:
            ids.append(eid)
    return ids


def validate(parsed: dict | None, package, role: str, snapshot: dict | None = None) -> dict | None:
    """
    PASS / REPAIR. Invalid IDs are never stored as supporting evidence.

    Chartist: ignore model IDs entirely; map snapshot labels → E0xx.
    Other agents: keep IDs in-scope; map evidence_labels; drop the rest.
    """
    if not parsed:
        return parsed

    allowed = allowed_ids(package, role)
    llm_ids = [str(x).strip().upper() for x in (parsed.get("evidence_ids") or [])]

    if role == "chartist":
        attributed = attribute_chartist(package, snapshot)
        invalid = [cid for cid in llm_ids if cid not in set(attributed)]
        parsed["evidence_ids"] = attributed
        parsed["invalid_evidence_ids"] = invalid
        parsed["attribution_source"] = "python.technical_compute"
        parsed["validator_status"] = "repaired" if invalid else "pass"
        return parsed

    mapping = label_to_id(package, role)
    from_labels = []
    for lab in parsed.get("evidence_labels") or []:
        eid = mapping.get(str(lab).strip().lower())
        if eid:
            from_labels.append(eid)

    cited = from_labels + llm_ids
    valid: list[str] = []
    invalid: list[str] = []
    seen: set[str] = set()
    for token in cited:
        if token in seen:
            continue
        seen.add(token)
        if token in allowed:
            valid.append(token)
        else:
            invalid.append(token)

    parsed["evidence_ids"] = valid
    parsed["invalid_evidence_ids"] = invalid
    parsed["validator_status"] = "repaired" if invalid else "pass"
    parsed["attribution_source"] = "validated_ids"
    return parsed
