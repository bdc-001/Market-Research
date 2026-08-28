"""
Evidence expansion for opportunity candidates only.

Not more scoring. Retrieve facts, answer the binding/scale/execution
questions, then decide whether the candidate is Council-ready.
"""
from __future__ import annotations

import io
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"

_INR_CR = 1e7


def expand_candidates(cards: list[dict], progress=None) -> list[dict]:
    """Run expansion on opportunity candidates. If none, expand the best order-win lead."""
    targets = [c for c in cards or [] if c.get("stage") == "opportunity_candidate"]
    if not targets:
        leads = [
            c for c in cards or []
            if c.get("stage") == "event_lead"
            and c.get("event_type") in {"large_order_win", "export_order"}
            and (c.get("full_filing_available") or c.get("filing_text"))
        ]
        leads.sort(key=_lead_rank, reverse=True)
        targets = leads[:1]
    packs = []
    for card in targets:
        if progress:
            progress(f"Evidence expansion: {card.get('ticker')} (candidate only, no extra scoring)")
        pack = expand_candidate(card)
        packs.append(pack)
        path = write_expansion_report(pack)
        pack["report_path"] = str(path)
        card["expansion"] = {
            "verdict": pack.get("verdict"),
            "report_path": str(path),
            "open_questions": pack.get("open_questions") or [],
        }
        if progress:
            progress(f"Expansion report: {path} verdict={pack.get('verdict')}")
    return packs


def expand_sample_cards(cards: list[dict], progress=None) -> list[dict]:
    """Expand an already-picked sample. Does not rescore."""
    packs = []
    for card in cards or []:
        if progress:
            progress(f"Evidence expansion: {card.get('ticker')} type={card.get('event_type')}")
        pack = expand_candidate(card)
        packs.append(pack)
        path = write_expansion_report(pack)
        pack["report_path"] = str(path)
        card["expansion"] = {
            "verdict": pack.get("verdict"),
            "report_path": str(path),
            "open_questions": pack.get("open_questions") or [],
        }
        if progress:
            progress(f"Expansion report: {path} verdict={pack.get('verdict')}")
    return packs


def _facts_line(facts: dict) -> str:
    bits = []
    if facts.get("amount_inr_cr") is not None:
        bits.append(f"amount ₹{facts.get('amount_inr_cr')} Cr")
    if facts.get("customer"):
        bits.append(f"customer `{facts.get('customer')}`")
    if facts.get("order_book_cr") is not None:
        bits.append(f"book ₹{facts.get('order_book_cr')} Cr")
    if facts.get("gst_excluded") is not None:
        bits.append(f"gst_excluded `{facts.get('gst_excluded')}`")
    if facts.get("execution_months") is not None:
        bits.append(f"execution_months `{facts.get('execution_months')}`")
    if facts.get("fy_orders_cr") is not None:
        bits.append(f"fy_orders ₹{facts.get('fy_orders_cr')} Cr")
    if facts.get("binding_language"):
        bits.append(f"binding `{facts.get('binding_language')}`")
    return " · ".join(bits) or "none parsed"


def _lead_rank(card: dict) -> tuple:
    """Prefer a work-order filing that also discloses the existing book over the largest rupee figure."""
    filing = (card.get("filing_text") or "").lower()
    has_book = "unexecuted order book" in filing or "order book" in filing
    has_work = "work order" in filing or "purchase order" in filing
    amount = float(
        card.get("amount_inr_cr")
        or (card.get("materiality") or {}).get("amount_inr_cr")
        or 0
    )
    return (int(has_book and has_work), amount)


def expand_candidate(card: dict) -> dict:
    ticker = str(card.get("ticker") or "").upper()
    evidence = card.get("evidence") or {}
    filing = str(card.get("filing_text") or "")
    subject = str(card.get("subject") or evidence.get("source_text") or "")
    facts = _facts_from_card(card, subject, filing)
    fundamentals = _fundamentals(ticker)
    customer_hits = _search(
        f"{facts.get('customer') or ''} company India".strip() or f"{ticker} customer"
    )
    ar_hits = _search(f"{ticker} annual report investor presentation order book")
    questions = _answer_questions(card, facts, fundamentals, customer_hits)
    open_q = [q["id"] for q in questions if q["status"] in {"unknown", "unproven"}]
    verdict = _verdict(card, facts, fundamentals, questions)
    return {
        "ticker": ticker,
        "as_of": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "event": {
            "event_id": evidence.get("event_id") or card.get("event_id"),
            "source_id": evidence.get("source_id") or card.get("source_id"),
            "event_type": card.get("event_type"),
            "direction": evidence.get("direction") or card.get("direction"),
            "source_text": subject,
            "event_date": card.get("event_date") or card.get("announced_at"),
            "extracted_facts": facts,
            "economic_interpretation": (card.get("materiality") or {}).get("reason")
            or evidence.get("economic_interpretation"),
        },
        "retrieval": _retrieval_slots(card, facts, fundamentals, customer_hits, ar_hits),
        "fundamentals": fundamentals,
        "customer_search": customer_hits,
        "document_search": ar_hits,
        "questions": questions,
        "open_questions": open_q,
        "verdict": verdict,
        "council_prompt": (
            "Is this genuinely an asymmetric opportunity, or is the apparent "
            "catalyst misleading? Do not rediscover the event. Use this pack."
        ),
    }


def write_expansion_report(pack: dict, dest: Path | None = None) -> Path:
    REPORTS.mkdir(exist_ok=True)
    dest = dest or REPORTS / f"discovery_expansion_{pack['ticker']}_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
    ev = pack.get("event") or {}
    facts = ev.get("extracted_facts") or {}
    fund = pack.get("fundamentals") or {}
    lines = [
        f"# Discovery · Evidence expansion — {pack.get('ticker')}",
        "",
        f"Generated: {pack.get('as_of')}",
        f"**Verdict:** `{pack.get('verdict')}`",
        "",
        "This is not a new score. It is the evidence pack the Council should receive.",
        "",
        "## Structured event (immutable)",
        "",
        f"- event_id: `{ev.get('event_id')}`",
        f"- company: `{pack.get('ticker')}`",
        f"- event_type: `{ev.get('event_type')}`",
        f"- direction: `{ev.get('direction')}`",
        f"- source_id: `{ev.get('source_id')}`",
        f"- event_date: {ev.get('event_date')}",
        f"- source_text: {ev.get('source_text')}",
        f"- extracted_facts: {_facts_line(facts)}",
        f"- economic_interpretation: {ev.get('economic_interpretation')}",
        "",
        "## Retrieval",
        "",
    ]
    for slot in pack.get("retrieval") or []:
        lines.append(f"- **{slot['label']}:** {slot['status']} — {slot['detail']}")
    lines += ["", "## Fundamentals (Yahoo)", ""]
    for key in (
        "revenue_cr", "ebitda_cr", "total_debt_cr", "total_cash_cr",
        "fcf_cr", "operating_cf_cr", "promoter_holding_pct", "trailing_pe",
        "mcap_cr", "last_close",
    ):
        lines.append(f"- {key}: {_fmt(fund.get(key))}")
    lines += ["", "## Questions", ""]
    for q in pack.get("questions") or []:
        lines += [
            f"### {q['id']}. {q['question']}",
            "",
            f"**Status:** {q['status']}",
            "",
            q["answer"],
            "",
        ]
    lines += [
        "## Council instruction",
        "",
        pack.get("council_prompt"),
        "",
        "Bull/Bear must not decide from scratch whether an event exists. "
        "They receive this pack and argue whether the catalyst is real, "
        "material, executable, and still mispriced.",
        "",
    ]
    dest.write_text("\n".join(lines), encoding="utf-8")
    return dest


def _facts_from_card(card: dict, subject: str, filing: str) -> dict:
    blob = f"{subject}\n{filing}"
    amount = card.get("amount_inr_cr") or (card.get("materiality") or {}).get("amount_inr_cr")
    if amount is None:
        amount = _parse_order_crore(blob)
    customer = card.get("customer_or_counterparty") or _parse_customer(blob)
    llp = re.search(r"(WEISDOM DESIGN BUILD LLP|[A-Z][A-Z0-9&.\- ]{3,40} LLP)", blob)
    return {
        "amount_inr_cr": amount,
        "customer": (llp.group(1).strip() if llp else customer),
        "gst_excluded": bool(re.search(r"excluding gst", blob, re.I)),
        "work_order": bool(re.search(r"work order", blob, re.I)),
        "binding_language": _binding_language(blob),
        "order_book_cr": _parse_named_crore(blob, r"unexecuted order book"),
        "fy_orders_cr": _parse_named_crore(blob, r"received orders worth"),
        "ordinary_course": bool(re.search(r"ordinary\s+course of business\?\s*Yes", blob, re.I)),
        "related_party": (
            False if re.search(r"related party transactions\?\s*No", blob, re.I)
            else True if re.search(r"related party transactions\?\s*Yes", blob, re.I)
            else None
        ),
        "execution_months": int(m.group(1)) if (m := re.search(r"(\d+)\s*Months", blob, re.I)) else None,
        "filing_excerpt": filing[:1200],
    }


def _parse_named_crore(text: str, prefix: str):
    match = re.search(prefix + r"[^\d₹]*₹?\s*([\d,.]+)\s*crore", text or "", re.I)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None


def _search_crore(text: str, pattern: str):
    match = re.search(pattern, text or "", re.I)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None


def _search_amount(text: str, pattern: str):
    match = re.search(pattern, text or "", re.I)
    return match.group(1).strip() if match else None


def _parse_order_crore(text: str):
    match = re.search(
        r"(?:worth|order(?:\s+of)?|valued at)\s*[₹rs.\s]*([\d,.]+)\s*crore",
        text or "",
        re.I,
    )
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None


def _parse_customer(text: str) -> str | None:
    match = re.search(
        r"(?:from|awarded by|placed by)\s+([A-Z][A-Za-z0-9&.\- ]{2,60}?)(?:\s*,|\s+to\s+be|\s+for\s|\.|$)",
        text or "",
    )
    if match:
        return match.group(1).strip()
    if re.search(r"weisdom", text or "", re.I):
        return "Weisdom Group"
    return None


def _binding_language(text: str) -> str:
    t = (text or "").lower()
    if "letter of award" in t or "loa" in t:
        return "letter_of_award"
    if "letter of intent" in t or "loi" in t:
        return "letter_of_intent"
    if "work order" in t or "purchase order" in t:
        return "work_or_purchase_order"
    if "bagging" in t or "contract" in t:
        return "order_intimation"
    return "unspecified"


def _fundamentals(ticker: str) -> dict:
    out = {
        "revenue_cr": None, "ebitda_cr": None, "total_debt_cr": None,
        "total_cash_cr": None, "fcf_cr": None, "operating_cf_cr": None,
        "promoter_holding_pct": None, "trailing_pe": None, "mcap_cr": None,
        "last_close": None, "errors": [],
    }
    old = sys.stderr
    sys.stderr = io.StringIO()
    try:
        import yfinance as yf
        tk = yf.Ticker(f"{ticker}.NS")
        info = tk.info or {}
        out["mcap_cr"] = _cr(info.get("marketCap"))
        out["trailing_pe"] = _num(info.get("trailingPE"))
        insiders = _num(info.get("heldPercentInsiders"))
        out["promoter_holding_pct"] = round(insiders * 100.0, 2) if insiders is not None else None
        out["total_debt_cr"] = _cr(info.get("totalDebt"))
        out["total_cash_cr"] = _cr(info.get("totalCash"))
        out["fcf_cr"] = _cr(info.get("freeCashflow"))
        out["operating_cf_cr"] = _cr(info.get("operatingCashflow"))
        out["last_close"] = _num(info.get("previousClose") or info.get("currentPrice"))
        out["revenue_cr"] = _statement_cr(tk, "financials", "Total Revenue")
        out["ebitda_cr"] = _statement_cr(tk, "financials", "EBITDA")
        out["quarterly_revenue_cr"] = _statement_cr(tk, "quarterly_financials", "Total Revenue")
    except Exception as exc:
        out["errors"].append(str(exc))
    finally:
        sys.stderr = old
    return out


def _statement_cr(ticker_obj, attr: str, row: str):
    try:
        frame = getattr(ticker_obj, attr)
        if frame is None or getattr(frame, "empty", True) or row not in frame.index:
            return None
        series = frame.loc[row].dropna()
        if series.empty:
            return None
        return _cr(series.iloc[0])
    except Exception:
        return None


def _search(query: str) -> list[dict]:
    if not query.strip():
        return []
    try:
        from agents.evidence_acquisition import _web_search
        hits, _status = _web_search(query, max_results=5)
        return hits
    except Exception:
        return []


def _retrieval_slots(card, facts, fund, customer_hits, ar_hits) -> list[dict]:
    filing_ok = bool(card.get("full_filing_available") or facts.get("filing_excerpt"))
    return [
        {"label": "Full filing", "status": "found" if filing_ok else "not_found",
         "detail": "PDF text retrieved" if filing_ok else "attachment not retrieved"},
        {"label": "Latest quarterly results", "status": _found(fund.get("quarterly_revenue_cr")),
         "detail": f"₹{_fmt(fund.get('quarterly_revenue_cr'))} Cr" if fund.get("quarterly_revenue_cr") else "Yahoo quarterly revenue missing"},
        {"label": "Annual report", "status": "found" if ar_hits else "not_found",
         "detail": (ar_hits[0].get("title") if ar_hits else "not retrieved")},
        {"label": "Investor presentation", "status": "not_found",
         "detail": "no dedicated IR deck retrieved"},
        {"label": "Existing order book", "status": _found(facts.get("order_book_cr")),
         "detail": (
             f"₹{_fmt(facts.get('order_book_cr'))} Cr unexecuted (from this filing)"
             if facts.get("order_book_cr") else "not in this filing"
         )},
        {"label": "Revenue", "status": _found(fund.get("revenue_cr")),
         "detail": f"₹{_fmt(fund.get('revenue_cr'))} Cr trailing" if fund.get("revenue_cr") else "unknown"},
        {"label": "EBITDA", "status": _found(fund.get("ebitda_cr")),
         "detail": f"₹{_fmt(fund.get('ebitda_cr'))} Cr" if fund.get("ebitda_cr") else "unknown"},
        {"label": "Debt", "status": _found(fund.get("total_debt_cr")),
         "detail": f"₹{_fmt(fund.get('total_debt_cr'))} Cr" if fund.get("total_debt_cr") else "unknown"},
        {"label": "Cash flow", "status": _found(fund.get("fcf_cr") or fund.get("operating_cf_cr")),
         "detail": f"FCF ₹{_fmt(fund.get('fcf_cr'))} Cr / OCF ₹{_fmt(fund.get('operating_cf_cr'))} Cr"},
        {"label": "Promoter holding", "status": _found(fund.get("promoter_holding_pct")),
         "detail": f"{_fmt(fund.get('promoter_holding_pct'))}%" if fund.get("promoter_holding_pct") is not None else "unknown (Yahoo insiders proxy)"},
        {"label": "Customer concentration", "status": "not_found",
         "detail": "not disclosed in this pack"},
        {"label": "Historical execution", "status": "not_found",
         "detail": "no delivery/completion record retrieved"},
        {"label": "Current valuation", "status": _found(fund.get("mcap_cr") or fund.get("trailing_pe")),
         "detail": f"mcap ₹{_fmt(fund.get('mcap_cr'))} Cr · PE {_fmt(fund.get('trailing_pe'))}"},
        {"label": "Price reaction", "status": _found((card.get("market_awareness") or {}).get("abnormal_return")),
         "detail": (
             f"5d |return| {_fmt((card.get('market_awareness') or {}).get('abnormal_return'))}% · "
             f"vol {_fmt((card.get('market_awareness') or {}).get('abnormal_volume'))}× · "
             f"tape {(card.get('market_awareness') or {}).get('tape')}"
         )},
        {"label": "Customer search", "status": "found" if customer_hits else "not_found",
         "detail": (customer_hits[0].get("title") if customer_hits else f"{facts.get('customer')} not independently confirmed")},
    ]


def _answer_questions(card, facts, fund, customer_hits) -> list[dict]:
    event_type = card.get("event_type") or ""
    if event_type not in {"large_order_win", "export_order", "new_customer"}:
        return _generic_event_questions(card, facts, fund)
    return _order_questions(card, facts, fund, customer_hits)


def _generic_event_questions(card, facts, fund) -> list[dict]:
    aware = card.get("market_awareness") or {}
    event_type = card.get("event_type") or "unclassified"
    subject = str(card.get("subject") or "")[:240]
    return [
        {
            "id": "Q1",
            "question": "Is the disclosed event real and typed correctly?",
            "status": "disclosed" if (card.get("filing_text") or card.get("full_filing_available")) else "unproven",
            "answer": (
                f"Python type is `{event_type}`. Subject: {subject or 'unknown'}. "
                "This is a company disclosure. Independent confirmation is not in this pack."
            ),
        },
        {
            "id": "Q2",
            "question": "How large is it relative to the existing business or equity?",
            "status": "unknown" if fund.get("revenue_cr") is None and fund.get("mcap_cr") is None else "unproven",
            "answer": (
                f"Trailing revenue ₹{_fmt(fund.get('revenue_cr'))} Cr, "
                f"mcap ₹{_fmt(fund.get('mcap_cr'))} Cr. "
                "This event type has no order-to-revenue ratio unless an amount was parsed."
            ),
        },
        {
            "id": "Q3",
            "question": "What is the economic transmission (earnings, dilution, control, license)?",
            "status": "unknown",
            "answer": (
                "Margin, dilution, cash proceeds, and control change are not established "
                "from this pack. Treat transmission as unknown."
            ),
        },
        {
            "id": "Q4",
            "question": "Can the company execute or absorb this event?",
            "status": "unknown",
            "answer": (
                f"Debt ₹{_fmt(fund.get('total_debt_cr'))} Cr, cash ₹{_fmt(fund.get('total_cash_cr'))} Cr, "
                f"FCF ₹{_fmt(fund.get('fcf_cr'))} Cr. Capacity/funding remains unproven."
            ),
        },
        {
            "id": "Q5",
            "question": "Who is the counterparty or related party, if any?",
            "status": "unknown",
            "answer": (
                f"Customer/counterparty in filing: {facts.get('customer') or 'not parsed'}. "
                "Related-party status "
                + ("No. " if facts.get("related_party") is False else
                   "Yes. " if facts.get("related_party") is True else "unknown. ")
            ),
        },
        {
            "id": "Q6",
            "question": "Is the event already reflected in the stock price?",
            "status": "known" if aware.get("tape") not in {None, "unknown"} else "unknown",
            "answer": (
                f"5-day |return| {_fmt(aware.get('abnormal_return'))}%, "
                f"volume {_fmt(aware.get('abnormal_volume'))}×, tape `{aware.get('tape')}`."
            ),
        },
        {
            "id": "Q7",
            "question": "Does this change earnings trajectory or capital structure?",
            "status": "unproven",
            "answer": (
                "Not established. Trajectory requires confirmed economics for this event type, "
                "which this pack does not prove."
            ),
        },
    ]


def _order_questions(card, facts, fund, customer_hits) -> list[dict]:
    amount = _num(facts.get("amount_inr_cr"))
    revenue = _num(fund.get("revenue_cr"))
    mcap = _num(fund.get("mcap_cr"))
    vs_rev = (amount / revenue) if amount and revenue and revenue > 0 else None
    vs_mcap = (amount / mcap) if amount and mcap and mcap > 0 else None
    book = _num(facts.get("order_book_cr"))
    vs_book = (amount / book) if amount and book and book > 0 else None
    aware = card.get("market_awareness") or {}
    q1_status = "disclosed" if facts.get("work_order") and amount else "unproven"
    if facts.get("binding_language") in {"letter_of_intent"}:
        q1_status = "unproven"
    scale_bits = [
        f"Order / trailing revenue = {_pct(vs_rev)}",
        f"Order / market cap = {_pct(vs_mcap)}",
        f"Order / disclosed unexecuted book = {_pct(vs_book)}",
    ]
    if facts.get("fy_orders_cr"):
        scale_bits.append(f"FY orders disclosed in filing = ₹{_fmt(facts.get('fy_orders_cr'))} Cr")
    if vs_book is not None and vs_book < 0.15:
        scale_note = (
            "Against the company's own unexecuted book this is incremental, not a step-change. "
            "Market-cap ratios should not be treated as transformational until revenue is confirmed."
        )
        q2_status = "known"
    elif vs_rev is not None:
        scale_note = "Scale is measured against trailing revenue."
        q2_status = "known"
    elif vs_mcap is not None and vs_mcap >= 1:
        scale_note = (
            "Market-cap scale looks extreme and should be treated as a data-quality warning "
            "until revenue is confirmed."
        )
        q2_status = "known"
    else:
        scale_note = "Revenue missing, so earnings scale is not established."
        q2_status = "unknown"
    return [
        {
            "id": "Q1",
            "question": "Is the order real and binding?",
            "status": q1_status,
            "answer": (
                f"The company intimated a {facts.get('binding_language', 'unspecified')} "
                f"of ₹{_fmt(amount)} Cr"
                f"{' excluding GST' if facts.get('gst_excluded') else ''} "
                f"from {facts.get('customer') or 'an unnamed counterparty'}. "
                + ("The annexure states this is ordinary course of business. " if facts.get("ordinary_course") else "")
                + "This is a company disclosure, not a third-party confirmation. "
                "No signed contract, advance, or LOA copy was independently verified."
            ),
        },
        {
            "id": "Q2",
            "question": "How large is it relative to the company's existing business?",
            "status": q2_status,
            "answer": ". ".join(scale_bits) + ". " + scale_note,
        },
        {
            "id": "Q3",
            "question": "What margin might it generate?",
            "status": "unknown",
            "answer": (
                f"EBITDA is ₹{_fmt(fund.get('ebitda_cr'))} Cr trailing; "
                "the filing does not state contract margin. Margin remains unknown."
            ),
        },
        {
            "id": "Q4",
            "question": "Can the company execute it?",
            "status": "unknown",
            "answer": (
                f"Debt ₹{_fmt(fund.get('total_debt_cr'))} Cr, cash ₹{_fmt(fund.get('total_cash_cr'))} Cr, "
                f"FCF ₹{_fmt(fund.get('fcf_cr'))} Cr. "
                + (
                    f"Unexecuted order book in this filing is ₹{_fmt(facts.get('order_book_cr'))} Cr, "
                    "so the company claims it already executes at this scale. Delivery history was not retrieved. "
                    if facts.get("order_book_cr") else
                    "Order book and delivery history were not retrieved. "
                )
                + "Execution capacity is unproven independently."
            ),
        },
        {
            "id": "Q5",
            "question": f"Who is {facts.get('customer') or 'the customer'} and how credible are they?",
            "status": "found" if customer_hits else "unknown",
            "answer": (
                _hits_text(customer_hits)
                if customer_hits else
                f"{facts.get('customer') or 'The customer'} was not independently identified from web search. "
                "Counterparty credit risk is unknown."
            ),
        },
        {
            "id": "Q6",
            "question": "Is the order already reflected in the stock price?",
            "status": "known" if aware.get("tape") not in {None, "unknown"} else "unknown",
            "answer": (
                f"5-day |return| {_fmt(aware.get('abnormal_return'))}%, "
                f"volume {_fmt(aware.get('abnormal_volume'))}×, tape `{aware.get('tape')}`. "
                + (
                    "Thin trading is not evidence the market ignored it, nor that it has priced it."
                    if aware.get("tape") == "thin_trading" else
                    "Price already moved — less likely still hidden."
                    if aware.get("tape") == "price_already_moved" else
                    "Tape does not prove the event is unpriced."
                )
            ),
        },
        {
            "id": "Q7",
            "question": "Does this change the company's earnings trajectory?",
            "status": "unproven" if vs_book is not None else ("unknown" if vs_rev is None else "unproven"),
            "answer": (
                (
                    f"Against a disclosed unexecuted book of ₹{_fmt(book)} Cr this order is {_pct(vs_book)}, "
                    "so it is unlikely by itself to change the earnings trajectory unless the mix/margin "
                    "is far above the existing book. Revenue is still unconfirmed."
                )
                if vs_book is not None else
                "Cannot say. Trajectory requires confirmed revenue base, margin, duration, "
                "and that the order is incremental rather than replacement of existing work. "
                "Those facts are not in this pack."
            ),
        },
    ]


def _verdict(card, facts, fund, questions) -> str:
    event_type = card.get("event_type") or ""
    if event_type not in {"large_order_win", "export_order", "new_customer"}:
        return "council_with_gaps"
    amount = _num(facts.get("amount_inr_cr"))
    if not amount:
        return "fail_no_amount"
    q1 = next((q for q in questions if q["id"] == "Q1"), None)
    if q1 and q1["status"] == "unproven" and facts.get("binding_language") == "letter_of_intent":
        return "watch_not_binding"
    revenue = _num(fund.get("revenue_cr"))
    mcap = _num(fund.get("mcap_cr")) or _num((card.get("materiality") or {}).get("mcap_cr"))
    vs_rev = (amount / revenue) if amount and revenue else None
    vs_mcap = (amount / mcap) if amount and mcap else None
    book = _num(facts.get("order_book_cr"))
    vs_book = (amount / book) if amount and book else None
    if vs_rev is not None and vs_rev < 0.05:
        return "fail_immaterial"
    if vs_book is not None and vs_book < 0.15:
        return "council_with_gaps"
    if vs_rev is None and vs_mcap is not None and vs_mcap >= 0.20:
        return "council_with_gaps"
    if vs_rev is not None and vs_rev >= 0.20:
        return "council_with_gaps"
    if vs_rev is None and vs_mcap is None:
        return "watch_scale_unknown"
    return "watch_not_yet_material"


def _found(value) -> str:
    return "found" if value not in (None, "", "unknown") else "not_found"


def _hits_text(hits: list[dict]) -> str:
    parts = []
    for hit in hits[:3]:
        title = hit.get("title") or ""
        body = hit.get("body") or ""
        parts.append(f"{title}. {body}".strip())
    return " ".join(parts)[:800] or "No usable hits."


def _cr(value):
    n = _num(value)
    if n is None:
        return None
    return round(n / _INR_CR, 2)


def _num(value):
    if value is None or value == "":
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    if n != n:
        return None
    return n


def _fmt(value) -> str:
    n = _num(value)
    if n is None:
        return "unknown"
    if abs(n) >= 100:
        return f"{n:.0f}"
    return f"{n:.2f}"


def _pct(value) -> str:
    n = _num(value)
    if n is None:
        return "unknown"
    return f"{n:.0%}"
