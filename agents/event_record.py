"""
Immutable event evidence. Interpretation is derived from this object only.

SOURCE → STRUCTURED EVENT → VALIDATE → ECONOMIC ANALYSIS
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

TAXONOMY = (
    "promoter_purchase",
    "promoter_sale",
    "management_change",
    "large_order_win",
    "capacity_expansion",
    "fund_raise",
    "preferential_issue",
    "regulatory_approval",
    "new_customer",
    "new_product",
    "acquisition",
    "divestiture",
    "financial_results",
    "debt_reduction",
    "export_order",
    "export_expansion",
    "partnership",
    "other_catalyst",
)

# Aliases from older runs / LLM output.
ALIASES = {
    "promoter_buying": "promoter_purchase",
    "strategic_partnership": "partnership",
}

# Reasons that must not appear for a given event_type.
FORBIDDEN_REASON_FRAGMENTS = {
    "large_order_win": (
        "promoter buying", "promoter purchase", "promoter sale",
        "managing director", "ncd", "debenture", "migration",
        "preferential", "warrant issue",
    ),
    "export_order": (
        "promoter buying", "managing director", "ncd", "preferential",
    ),
    "promoter_purchase": (
        "work order", "bagging", "letter of award", "capacity",
        "managing director appointment",
    ),
    "management_change": (
        "promoter buying", "work order", "bagging", "order of",
    ),
    "preferential_issue": ("promoter buying", "work order", "bagging"),
    "fund_raise": ("promoter buying", "work order"),
}


@dataclass
class EventEvidence:
    event_id: str
    company: str
    event_type: str
    direction: str
    source_id: str
    source_text: str
    event_date: str
    extracted_facts: dict = field(default_factory=dict)
    economic_interpretation: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def canonical_event_type(raw: str | None) -> str:
    name = str(raw or "other_catalyst").strip()
    name = ALIASES.get(name, name)
    if name not in TAXONOMY:
        return "other_catalyst"
    return name


def build_evidence(event: dict) -> EventEvidence:
    # Announcement identity only. Full PDF lives in extracted_facts so
    # shareholding tables cannot reclassify the event.
    subject = str(event.get("subject") or "").strip()
    if not subject:
        subject = str(event.get("source_text") or "").strip().split("\n")[0]
    return EventEvidence(
        event_id=str(event.get("event_id") or ""),
        company=str(event.get("ticker") or event.get("company") or "").upper(),
    event_type=refine_event_type(
        canonical_event_type(event.get("event_type")),
        subject,
        str(event.get("filing_text") or "")[:1500],
    ),
        direction=str(event.get("direction") or "unknown"),
        source_id=str(event.get("source_id") or ""),
        source_text=subject,
        event_date=str(event.get("event_date") or event.get("announced_at") or ""),
        extracted_facts={
            "amount_inr_cr": event.get("amount_inr_cr"),
            "customer_or_counterparty": event.get("customer_or_counterparty"),
            "catalyst": event.get("catalyst"),
            "attachment": event.get("attachment"),
            "filing_excerpt": str(event.get("filing_text") or event.get("filing_excerpt") or "")[:2000],
        },
        economic_interpretation="",
    )


def refine_event_type(event_type: str | None, subject: str, filing_text: str = "") -> str:
    """
    Narrow the type from the announcement subject. Full-PDF keyword soup
    must not override an order/capacity classification.
    """
    et = canonical_event_type(event_type)
    subj = (subject or "").lower()
    if et in {"large_order_win", "export_order", "new_customer", "capacity_expansion"}:
        return et
    if _is_promoter_purchase(subj):
        return "promoter_purchase"
    if _is_promoter_sale(subj):
        return "promoter_sale"
    if _is_fund_raise(subj):
        return "fund_raise"
    if et in {"preferential_issue", "other_catalyst", "unclassified"}:
        head = (filing_text or "")[:1500].lower()
        if _is_fund_raise(head):
            return "fund_raise"
    return et


def _is_promoter_purchase(text: str) -> bool:
    if "regulation 7(2)" in text or "sebi (pit)" in text or "promotor" in text:
        return "sale" not in text and "sold" not in text
    return False


def _is_promoter_sale(text: str) -> bool:
    if "regulation 7(2)" in text or "promotor" in text or "promoter" in text:
        return "sold" in text or "sale of" in text
    return False


def _is_fund_raise(text: str) -> bool:
    return any(tok in text for tok in ("ncd", "non convertible", "debenture"))


def interpretation_matches_type(event_type: str, reason: str) -> bool:
    et = canonical_event_type(event_type)
    text = (reason or "").lower()
    for frag in FORBIDDEN_REASON_FRAGMENTS.get(et, ()):
        if frag in text:
            return False
    return True


def attach_interpretation(evidence: EventEvidence, reason: str, direction: str) -> EventEvidence:
    if not interpretation_matches_type(evidence.event_type, reason):
        raise ValueError(
            f"Interpretation {reason!r} is not valid for {evidence.event_type}"
        )
    evidence.economic_interpretation = reason
    evidence.direction = direction
    return evidence
