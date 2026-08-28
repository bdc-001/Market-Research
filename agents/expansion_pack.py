"""
Parse a Discovery expansion markdown pack into structured fields.

No CHAVDA fallbacks. Missing facts stay missing.
Council must not rediscover the event from this parser.
"""
from __future__ import annotations

import re
from pathlib import Path


def parse_expansion_pack(text: str, ticker: str = "") -> dict:
    event_id = _field(text, r"event_id:\s*`([^`]+)`")
    source_id = _field(text, r"source_id:\s*`([^`]+)`")
    event_type = _field(text, r"event_type:\s*`([^`]+)`")
    direction = _field(text, r"direction:\s*`([^`]+)`")
    company = _field(text, r"company:\s*`([^`]+)`") or ticker
    event_date = _field(text, r"event_date:\s*(.+)")
    source_text = _field(text, r"source_text:\s*(.+)") or ""
    facts_line = _field(text, r"extracted_facts:\s*(.+)") or ""
    interpretation = _field(text, r"economic_interpretation:\s*(.+)") or ""
    verdict = _field(text, r"\*\*Verdict:\*\*\s*`([^`]+)`") or "council_with_gaps"

    amount = _num(_field(facts_line, r"(?:order|amount)\s*₹\s*([\d.]+)"))
    customer = _field(facts_line, r"customer `([^`]+)`")
    book = _num(_field(facts_line, r"book ₹\s*([\d.]+)"))
    months = _int(_field(facts_line, r"(?:execution_months|months) `?(\d+)"))
    fy = _num(_field(facts_line, r"fy_orders ₹\s*([\d.]+)"))
    gst_raw = _field(facts_line, r"gst_excluded `([^`]+)`")
    gst = None if gst_raw is None else gst_raw.lower() == "true"

    tape = _field(text, r"tape\s+`?([a-z_]+)`?") or _field(text, r"tape\s+([a-z_]+)")
    ret_5d = _num(_field(text, r"5d \|return\|\s*([\d.]+)"))
    vol = _num(_field(text, r"vol\s*([\d.]+)"))

    vs_rev = _field(text, r"Order / trailing revenue\s*=\s*([0-9.]+%|unknown)")
    vs_mcap = _field(text, r"Order / market cap\s*=\s*([0-9.]+%|unknown)")
    vs_book = _field(text, r"Order / disclosed unexecuted book\s*=\s*([0-9.]+%|unknown)")

    return {
        "ticker": (company or ticker or "").upper(),
        "event_id": event_id,
        "source_id": source_id,
        "event_type": event_type,
        "direction": direction,
        "event_date": event_date,
        "source_text": source_text,
        "interpretation": interpretation,
        "verdict": verdict,
        "amount_inr_cr": amount,
        "customer": customer,
        "order_book_cr": book,
        "fy_orders_cr": fy,
        "execution_months": months,
        "gst_excluded": gst,
        "tape": tape,
        "abnormal_return_5d_pct": ret_5d,
        "abnormal_volume": vol,
        "order_to_revenue": None if not vs_rev or vs_rev.lower() == "unknown" else vs_rev,
        "order_to_mcap": None if not vs_mcap or vs_mcap.lower() == "unknown" else vs_mcap,
        "order_to_book": None if not vs_book or vs_book.lower() == "unknown" else vs_book,
        "facts_line": facts_line,
        "fundamentals": _fundamentals(text),
        "questions": _questions(text),
        "retrieval": _retrieval(text),
    }


def load_expansion_pack(pack_file: Path, ticker: str = "") -> dict:
    text = Path(pack_file).read_text(encoding="utf-8", errors="replace")
    parsed = parse_expansion_pack(text, ticker=ticker)
    parsed["pack_path"] = str(pack_file)
    parsed["raw"] = text
    return parsed


def _fundamentals(text: str) -> dict:
    out = {}
    for key in (
        "revenue_cr", "ebitda_cr", "total_debt_cr", "total_cash_cr",
        "fcf_cr", "operating_cf_cr", "promoter_holding_pct",
        "trailing_pe", "mcap_cr", "last_close",
    ):
        raw = _field(text, rf"- {key}:\s*(.+)")
        if raw is None or raw.lower() == "unknown":
            continue
        out[key] = _maybe_num(raw)
    return out


def _questions(text: str) -> list[tuple[str, str, str]]:
    out = []
    blocks = re.split(r"### (Q\d+)\.\s*", text)
    i = 1
    while i + 1 < len(blocks):
        qid = blocks[i]
        body = blocks[i + 1]
        title = (body.split("\n", 1)[0] or "").strip()
        out.append((qid, title, body.strip()[:800]))
        i += 2
    return out


def _retrieval(text: str) -> list[dict]:
    out = []
    for match in re.finditer(r"- \*\*(.+?):\*\*\s*(\S+)\s*—\s*(.+)", text):
        out.append({
            "label": match.group(1).strip(),
            "status": match.group(2).strip(),
            "detail": match.group(3).strip(),
        })
    return out


def _field(text: str, pattern: str):
    match = re.search(pattern, text or "", re.I)
    if not match:
        return None
    return match.group(1).strip()


def _num(value):
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", "").replace("%", ""))
    except (TypeError, ValueError):
        return None


def _int(value):
    n = _num(value)
    return int(n) if n is not None else None


def _maybe_num(value):
    n = _num(value)
    return n if n is not None else value
