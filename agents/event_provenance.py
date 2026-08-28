"""
Event identity, source binding, and clustering.

An extracted claim is kept only when it maps to one source filing and
the source text can support the event type. Missing fields stay unknown.
"""
from __future__ import annotations

import hashlib
import re
import uuid

from agents.event_record import canonical_event_type, refine_event_type

EVENT_TYPE_EVIDENCE = {
    "large_order_win": (
        "bagging", "purchase order", "work order", "letter of intent",
        "letter of award", "received an order", "received order", "order win",
        "awarded a contract", "new contract", "loi", "loa",
        "orders/contracts", "order of rs", "valued at",
    ),
    "export_order": ("export", "overseas order"),
    "export_expansion": ("export", "overseas"),
    "capacity_expansion": (
        "capacity", "expansion", "new plant", "commissioning",
        "greenfield", "brownfield", "manufacturing", "bess",
    ),
    "promoter_purchase": (
        "regulation 7(2)", "sebi (pit)", "promotor", "promoter purchase",
        "promoter buying", "sast", "purchase of",
    ),
    "promoter_sale": ("promoter sale", "promoter sold", "sale of shares"),
    "fund_raise": ("ncd", "non convertible", "debenture"),
    "preferential_issue": ("preferential", "qip", "warrant", "allotment"),
    "acquisition": ("acquisition", "acquire", "takeover", "joint venture"),
    "divestiture": ("divest", "slump sale"),
    "partnership": ("partnership", "mou", "collaboration"),
    "regulatory_approval": ("approval", "licence", "license", "anda"),
    "new_customer": ("new customer",),
    "new_product": ("product launch", "new product", "commercial production"),
    "debt_reduction": ("debt reduction", "prepay", "repaid"),
    "management_change": ("appointment of", "cessation of", "key managerial"),
    "financial_results": ("financial results", "unaudited", "audited results"),
    "other_catalyst": (),
}


def stamp_source_ids(events: list[dict]) -> list[dict]:
    out = []
    for ev in events:
        item = dict(ev)
        raw = f"{item.get('ticker')}|{item.get('announced_at')}|{item.get('subject')}"
        digest = hashlib.sha1(raw.encode("utf-8", errors="replace")).hexdigest()[:10]
        item["event_id"] = item.get("event_id") or f"ev_{digest}"
        item["source_id"] = item.get("source_id") or f"src_{digest}"
        item["source_text"] = item.get("subject") or ""
        item["event_date"] = item.get("announced_at") or ""
        out.append(item)
    return out


def source_supports_event_type(source_text: str, event_type: str) -> bool:
    text = (source_text or "").lower()
    et = canonical_event_type(event_type)
    tokens = EVENT_TYPE_EVIDENCE.get(et) or EVENT_TYPE_EVIDENCE.get(event_type) or ()
    if not tokens:
        return True
    return any(tok in text for tok in tokens)


def bind_extraction(item: dict, sources_by_id: dict[str, dict]) -> dict | None:
    """
    Attach one source filing to an LLM claim. Reject if the source text
    cannot support the claimed event type.
    """
    source_id = str(item.get("source_id") or "")
    src = sources_by_id.get(source_id)
    if src is None:
        symbol = str(item.get("symbol") or item.get("ticker") or "").upper()
        matches = [
            s for s in sources_by_id.values()
            if str(s.get("ticker") or "").upper() == symbol
        ]
        if len(matches) == 1:
            src = matches[0]
        else:
            return None
    subject = src.get("subject") or ""
    filing_text = src.get("filing_text") or ""
    # Type identity uses the announcement subject, never the full PDF.
    identity_text = subject or (src.get("source_text") or "")
    src_type = canonical_event_type(src.get("event_type"))
    llm_type = canonical_event_type(item.get("event_type"))
    locked = {"other_catalyst", "unclassified", ""}
    if src_type not in locked:
        event_type = src_type
    elif source_supports_event_type(identity_text, llm_type):
        event_type = llm_type
    else:
        return None
    event_type = refine_event_type(event_type, subject, filing_text)
    amount_text = " ".join(
        p for p in (subject, filing_text, src.get("source_text") or "") if p
    )
    python_amount = _parse_amount(src.get("amount_inr_cr"), amount_text)
    llm_amount = _parse_amount(item.get("amount_inr_cr"), amount_text)
    amount = python_amount if python_amount is not None else llm_amount
    return {
        "event_id": src.get("event_id") or str(uuid.uuid4()),
        "source_id": src.get("source_id"),
        "ticker": str(src.get("ticker") or "").upper(),
        "event_type": event_type,
        "catalyst": item.get("catalyst") or src.get("subject"),
        "why_it_matters": item.get("why_it_matters") or "",
        "amount_inr_cr": amount,
        "timeframe": item.get("timeframe") or "1-6 months",
        "sentiment": item.get("sentiment"),
        "customer_or_counterparty": item.get("customer_or_counterparty"),
        "risks": item.get("risks") or [],
        "source": src.get("source"),
        "subject": src.get("subject"),
        "source_text": subject,
        "filing_text": filing_text,
        "full_filing_available": bool(src.get("full_filing_available") or filing_text),
        "announced_at": src.get("announced_at"),
        "event_date": src.get("announced_at") or "",
        "attachment": src.get("attachment"),
        "extraction_confidence": 0.9 if item.get("source_id") else 0.5,
    }


def cluster_events(events: list[dict], overlap: float = 0.55) -> list[list[dict]]:
    """Group near-duplicate filings for the same ticker."""
    groups: list[list[dict]] = []
    for ev in events:
        placed = False
        for group in groups:
            if str(group[0].get("ticker")) != str(ev.get("ticker")):
                continue
            if _similar(group[0], ev, overlap):
                group.append(ev)
                placed = True
                break
        if not placed:
            groups.append([ev])
    for i, group in enumerate(groups):
        cid = f"cl_{group[0].get('ticker')}_{i}"
        for ev in group:
            ev["event_cluster_id"] = cid
            ev["company_id"] = str(ev.get("ticker") or "")
    return groups


def pick_cluster_heads(groups: list[list[dict]], max_per_ticker: int = 1) -> list[dict]:
    """One opportunity per cluster, then cap cards per company."""
    heads = []
    for group in groups:
        ranked = sorted(group, key=_cluster_rank, reverse=True)
        head = dict(ranked[0])
        head["cluster_events"] = [
            {
                "event_id": e.get("event_id"),
                "event_type": e.get("event_type"),
                "source_text": e.get("source_text") or e.get("subject"),
                "event_date": e.get("event_date") or e.get("announced_at"),
            }
            for e in ranked
        ]
        heads.append(head)
    heads.sort(key=_cluster_rank, reverse=True)
    seen: dict[str, int] = {}
    out = []
    for head in heads:
        ticker = str(head.get("ticker") or "")
        n = seen.get(ticker, 0)
        if n >= int(max_per_ticker):
            continue
        seen[ticker] = n + 1
        out.append(head)
    return out


def _cluster_rank(ev: dict) -> tuple:
    mat = ev.get("materiality") or {}
    m = mat.get("score") if isinstance(mat, dict) else 0
    try:
        m = int(m or 0)
    except (TypeError, ValueError):
        m = 0
    rank = ev.get("rank_score") or 0
    try:
        rank = float(rank)
    except (TypeError, ValueError):
        rank = 0.0
    return (m, rank)


def _similar(a: dict, b: dict, overlap: float) -> bool:
    if a.get("event_type") and a.get("event_type") == b.get("event_type"):
        da, db = a.get("event_date") or a.get("announced_at"), b.get("event_date") or b.get("announced_at")
        if da and db and str(da)[:10] == str(db)[:10]:
            return True
    ta, tb = _tokens(a.get("source_text") or a.get("subject") or ""), _tokens(
        b.get("source_text") or b.get("subject") or ""
    )
    if not ta or not tb:
        return False
    return len(ta & tb) / len(ta | tb) >= overlap


def _tokens(text: str) -> set[str]:
    stop = {"the", "and", "has", "informed", "exchange", "about", "regarding", "limited", "ltd"}
    return {t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if t not in stop and len(t) > 2}


def _parse_amount(value, source_text: str):
    if value is None or value == "":
        return None
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return None
    if amount != amount or amount <= 0:
        return None
    digits = re.sub(r"[^\d]", "", source_text or "")
    stem = str(int(amount))
    if stem and stem in digits:
        return amount
    return None
