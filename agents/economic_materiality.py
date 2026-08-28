"""
Economic materiality 0-5.

Interpretation is computed from the structured event_type on EventEvidence.
Full-filing keyword soup must not change the event class.
"""
from __future__ import annotations

from agents.event_record import (
    EventEvidence,
    attach_interpretation,
    build_evidence,
    canonical_event_type,
    interpretation_matches_type,
    refine_event_type,
)

INVESTIGATE_UNKNOWN_ORDER = (
    2,
    "Potential catalyst — materiality cannot yet be established (size not in the filing text).",
)


def economic_materiality(event: dict, row: dict, cfg: dict | None = None) -> dict:
    cfg = cfg or {}
    event["event_type"] = refine_event_type(
        event.get("event_type"),
        event.get("subject") or "",
        event.get("filing_text") or "",
    )
    evidence = build_evidence(event)
    amount = _finite(evidence.extracted_facts.get("amount_inr_cr")) or _finite(event.get("amount_inr_cr"))
    revenue = _finite(row.get("revenue_cr"))
    mcap = _finite(row.get("mcap_cr"))
    order_types = {"large_order_win", "export_order", "new_customer"}
    vs_rev = vs_mcap = None
    if evidence.event_type in order_types:
        vs_rev = (amount / revenue) if amount and revenue and revenue > 0 else None
        vs_mcap = (amount / mcap) if amount and mcap and mcap > 0 else None

    score, reason, direction = _score_for_type(
        evidence.event_type, amount, vs_rev, vs_mcap, evidence,
    )
    if not interpretation_matches_type(evidence.event_type, reason):
        score, reason, direction = _score_for_type(
            evidence.event_type, amount, vs_rev, vs_mcap, evidence, strict=True,
        )
    attach_interpretation(evidence, reason, direction)
    event["evidence"] = evidence.as_dict()
    event["event_type"] = evidence.event_type
    event["direction"] = direction

    impact = _economic_impact(evidence.event_type, score, direction)
    stage = _stage(score)
    return {
        "score": score,
        "reason": reason,
        "economic_impact": impact,
        "order_to_revenue": vs_rev,
        "order_to_market_cap": vs_mcap,
        "amount_inr_cr": amount,
        "revenue_cr": revenue,
        "mcap_cr": mcap,
        "direction": direction,
        "stage": stage,
        "event_id": evidence.event_id,
        "source_id": evidence.source_id,
        "status": {
            0: "administrative", 1: "minor", 2: "potentially_useful",
            3: "meaningful", 4: "major", 5: "transformational",
        }[score],
    }


def _score_for_type(
    event_type: str,
    amount,
    vs_rev,
    vs_mcap,
    evidence: EventEvidence,
    strict: bool = False,
) -> tuple[int, str, str]:
    et = canonical_event_type(event_type)
    if et in {"large_order_win", "export_order", "new_customer"}:
        if vs_rev is not None:
            return _ratio_score(vs_rev, "trailing revenue")
        if vs_mcap is not None:
            return _ratio_score(vs_mcap, "market cap")
        if amount is not None:
            return 2, f"Order of ₹{amount:.1f} Cr stated; revenue/mcap missing so materiality is unproven.", "positive"
        return 2, INVESTIGATE_UNKNOWN_ORDER[1], "positive"
    if et == "capacity_expansion":
        if vs_rev is not None and vs_rev >= 0.5:
            return 5, "Capacity scale is large versus current revenue.", "positive"
        if amount:
            return 3, "Capacity event with a stated rupee amount.", "positive"
        return 2, "Capacity/commissioning disclosed without scale versus the current business.", "positive"
    if et == "promoter_purchase":
        return 2, "Promoter purchase is a useful lead; stake size vs equity is not established.", "positive"
    if et == "promoter_sale":
        return 2, "Promoter sale can signal governance or funding stress; size vs equity is not established.", "negative"
    if et == "management_change":
        return 1, "MD/KMP appointment is not an opportunity until a strategic change is evidenced.", "unknown"
    if et == "preferential_issue":
        return 2, "Preferential/warrant issue: could be capital or dilution. Direction unknown.", "unknown"
    if et == "fund_raise":
        return 1, "Capital raising (including NCDs) is financing, not a hidden earnings catalyst.", "unknown"
    if et == "regulatory_approval":
        return 1, "Regulatory/license filing; grant vs withdrawal and economic impact are not established.", "unknown"
    if et == "financial_results":
        return 1, "Results filing without a stated beat/miss/guidance change.", "unknown"
    if et in {"partnership", "new_product", "acquisition", "export_expansion"}:
        return 2, f"{et.replace('_', ' ')} disclosed; economic scale is not established.", "unknown"
    if et == "debt_reduction":
        return 2, "Debt reduction can improve the balance sheet; quantum is not established.", "positive"
    if et == "divestiture":
        return 2, "Divestiture disclosed; proceeds and earnings impact are not established.", "unknown"
    return 1, "Filing is interesting as a lead; economic materiality is not established.", "unknown"


def _ratio_score(ratio: float, label: str) -> tuple[int, str, str]:
    pct = f"{ratio:.0%} of {label}"
    if ratio < 0.05:
        return 1, f"Immaterial ({pct}).", "positive"
    if ratio < 0.20:
        return 3, f"Meaningful ({pct}).", "positive"
    if ratio < 0.50:
        return 4, f"Major ({pct}).", "positive"
    return 5, f"Transformational ({pct}).", "positive"


def _economic_impact(event_type: str, score: int, direction: str) -> dict:
    pos = "positive" if direction == "positive" and score >= 2 else (
        "negative" if direction == "negative" else "unknown"
    )
    duration = "unknown"
    if event_type in {"large_order_win", "export_order", "new_customer"}:
        duration = "1-6 months" if score <= 3 else "6-18 months"
    elif event_type == "capacity_expansion":
        duration = "1-3 years"
    revenue_types = {
        "large_order_win", "export_order", "capacity_expansion",
        "new_product", "new_customer", "export_expansion",
    }
    return {
        "revenue": pos if event_type in revenue_types else "unknown",
        "margin": "unknown",
        "cash_flow": "unknown",
        "duration": duration,
    }


def _stage(score: int) -> str:
    if score <= 1:
        return "discard_lead"
    if score == 2:
        return "event_lead"
    return "opportunity_candidate"


def _finite(value):
    if value is None or value == "":
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    if n != n or n <= 0:
        return None
    return n
