"""Pull attachment PDFs and harvest rupee amounts. No LLM."""
from __future__ import annotations

import io
import re
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "cache" / "discovery" / "filings"

AMOUNT_RE = re.compile(
    r"(?:rs\.?|inr|₹)\s*([\d,]+(?:\.\d+)?)\s*(crore|cr\.?|lakh|lac)?",
    re.I,
)


def expand_filings(events: list[dict], session=None, max_n: int = 40, progress=None) -> list[dict]:
    CACHE.mkdir(parents=True, exist_ok=True)
    sess = session or requests.Session()
    out = []
    for i, ev in enumerate(events):
        item = dict(ev)
        url = str(item.get("attachment") or "")
        if i >= int(max_n) or not url.startswith("http"):
            item.setdefault("full_filing_available", False)
            item.setdefault("filing_text", "")
            out.append(item)
            continue
        if progress and i == 0:
            progress(f"Evidence expansion: fetching up to {min(len(events), max_n)} filing PDFs...")
        text = _pdf_text(sess, url)
        item["filing_text"] = text[:8000]
        item["full_filing_available"] = bool(text)
        if text:
            # Announcement identity stays on subject. PDF is filing_text only.
            parsed = None
            if (item.get("event_type") or "") in {
                "large_order_win", "export_order", "new_customer",
            }:
                parsed = parse_order_crore(text)
            if parsed and not item.get("amount_inr_cr") and _looks_like_order_amount(item, text):
                item["amount_inr_cr"] = parsed
        out.append(item)
    return out


def _looks_like_order_amount(item: dict, text: str) -> bool:
    blob = f"{item.get('event_type') or ''} {item.get('subject') or ''} {text[:500]}".lower()
    if any(w in blob for w in ("warrant", "preferential", "debenture", "ncd", "allotment of shares")):
        if not any(w in blob for w in ("work order", "bagging", "purchase order", "letter of")):
            return False
    return any(w in blob for w in ("order", "contract", "bagging", "loi", "letter of award", "crore"))


ORDER_VALUE_RES = (
    re.compile(r"work order worth\s*[₹rs.\s]*([\d,.]+)\s*crores?", re.I),
    re.compile(r"total order value[^\d₹]{0,40}[₹rs.\s]*([\d,.]+)\s*crores?", re.I),
    re.compile(r"purchase orders amounting to total of\s*[₹rs.\s]*([\d,.]+)\s*crores?", re.I),
    re.compile(r"valued at\s*[₹rs.\s]*([\d,.]+)\s*crores?", re.I),
    re.compile(
        r"value of the order[s\(\)]*[^\d₹]{0,80}[₹rs.\s]*([\d,.]+)\s*(?:crore|approx)?",
        re.I,
    ),
)


def parse_order_crore(text: str) -> float | None:
    """The order/contract amount, not order-book or share-capital totals."""
    for pattern in ORDER_VALUE_RES:
        match = pattern.search(text or "")
        if not match:
            continue
        start = max(0, match.start() - 40)
        window = (text or "")[start: match.end() + 20].lower()
        if any(bad in window for bad in ("order book", "unexecuted", "share capital", "paid-up", "net worth")):
            continue
        try:
            n = float(match.group(1).replace(",", ""))
        except ValueError:
            continue
        if 0.5 <= n <= 100_000:
            return n
    return None


def parse_rupee_crore(text: str) -> float | None:
    """Largest amount in crores mentioned in the filing text."""
    best = None
    for match in AMOUNT_RE.finditer(text or ""):
        raw = match.group(1).replace(",", "")
        try:
            n = float(raw)
        except ValueError:
            continue
        unit = (match.group(2) or "crore").lower()
        if unit.startswith("l"):
            n = n / 100.0
        if n < 0.5 or n > 1_000_000:
            continue
        if best is None or n > best:
            best = n
    return best


def _pdf_text(session, url: str) -> str:
    key = re.sub(r"[^a-zA-Z0-9]+", "_", url)[-80:]
    path = CACHE / f"{key}.txt"
    if path.exists():
        return path.read_text(encoding="utf-8", errors="replace")
    try:
        resp = session.get(url, timeout=20)
        if resp.status_code != 200 or len(resp.content) < 200:
            return ""
        blob = resp.content[:2_000_000]
        text = _extract(blob)
        if text:
            path.write_text(text[:12000], encoding="utf-8")
        return text
    except Exception:
        return ""


def _extract(content: bytes) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(content))
        pages = []
        for page in reader.pages[:6]:
            pages.append(page.extract_text() or "")
        return "\n".join(pages).strip()
    except Exception:
        return ""
