"""
Evidence Acquisition Layer.

Python gathers raw material *before* any council LLM reasons.
Agents receive a role-specific slice of a numbered evidence package.
They do not search the web themselves.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

from agents.technical_compute import compute_snapshot_from_ohlcv, fetch_ohlcv, snapshot_is_valid

DOMAINS = (
    "financials",
    "filings",
    "management",
    "news",
    "competitors",
    "market",
    "corporate_actions",
)

ROLE_DOMAINS = {
    "historian": ("filings", "management", "financials"),
    "scout": ("news", "competitors", "corporate_actions"),
    "quant": ("financials",),
    "debate": DOMAINS,  # Bull and Bear get the same set
    "chartist": ("market",),
    "editor": DOMAINS,
}

INFO_FIELDS = [
    ("shortName", "company_name", "financials"),
    ("sector", "sector", "financials"),
    ("industry", "industry", "financials"),
    ("marketCap", "market_cap", "financials"),
    ("trailingPE", "trailing_pe", "financials"),
    ("forwardPE", "forward_pe", "financials"),
    ("priceToBook", "price_to_book", "financials"),
    ("enterpriseToEbitda", "ev_ebitda", "financials"),
    ("returnOnEquity", "roe", "financials"),
    ("returnOnAssets", "roa", "financials"),
    ("profitMargins", "profit_margin", "financials"),
    ("operatingMargins", "operating_margin", "financials"),
    ("grossMargins", "gross_margin", "financials"),
    ("revenueGrowth", "revenue_growth", "financials"),
    ("earningsGrowth", "earnings_growth", "financials"),
    ("earningsQuarterlyGrowth", "earnings_growth_qoq", "financials"),
    ("debtToEquity", "debt_to_equity", "financials"),
    ("currentRatio", "current_ratio", "financials"),
    ("freeCashflow", "free_cash_flow", "financials"),
    ("operatingCashflow", "operating_cash_flow", "financials"),
    ("totalDebt", "total_debt", "financials"),
    ("totalCash", "total_cash", "financials"),
    ("dividendYield", "dividend_yield", "financials"),
    ("payoutRatio", "payout_ratio", "financials"),
    ("heldPercentInsiders", "insider_holding", "financials"),
    ("sharesOutstanding", "shares_outstanding", "financials"),
    ("fiftyTwoWeekHigh", "high_52w_info", "financials"),
    ("fiftyTwoWeekLow", "low_52w_info", "financials"),
    ("averageVolume", "average_volume", "market"),
]


@dataclass
class EvidenceItem:
    id: str
    domain: str
    label: str
    value: Any
    source: str
    as_of: str
    note: str = ""


@dataclass
class EvidencePackage:
    ticker: str
    as_of: str
    yf_symbol: str
    items: list[EvidenceItem] = field(default_factory=list)
    market_snapshot: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    canonical: dict = field(default_factory=dict)
    acquisition: dict = field(default_factory=dict)

    def add(self, domain: str, label: str, value: Any, source: str, note: str = "") -> EvidenceItem | None:
        if value is None or value == "" or value == "None":
            return None
        if isinstance(value, float) and value != value:
            return None
        item = EvidenceItem(
            id=f"E{len(self.items) + 1:03d}",
            domain=domain,
            label=label,
            value=_jsonable(value),
            source=source,
            as_of=self.as_of,
            note=note,
        )
        self.items.append(item)
        return item

    def for_role(self, role: str) -> list[EvidenceItem]:
        domains = set(ROLE_DOMAINS.get(role, DOMAINS))
        return [item for item in self.items if item.domain in domains]

    def role_ids(self, role: str) -> set[str]:
        """The evidence IDs an agent in this role is actually allowed to cite."""
        return {item.id for item in self.for_role(role)}

    def label_id_map(self, domain: str) -> dict:
        """label -> evidence ID for one domain (e.g. map technical fields to IDs)."""
        return {item.label: item.id for item in self.items if item.domain == domain}

    def _canonical_line(self) -> str:
        c = self.canonical or {}
        if not c.get("price"):
            return "CANONICAL PRICE: unavailable"
        return (
            f"CANONICAL PRICE: {c.get('price')} "
            f"({c.get('quote_type')}, source={c.get('price_source')}, "
            f"as_of={c.get('price_timestamp')}). "
            f"Use this single price. live_price_quote is a separate vendor quote."
        )

    def render(self, role: str, limit: int | None = None) -> str:
        items = self.for_role(role)
        if limit is not None:
            items = items[:limit]
        if not items:
            return (
                f"EVIDENCE PACKAGE for {self.ticker} ({self.as_of}) role={role}\n"
                f"{self._canonical_line()}\n"
                f"No items in domains {ROLE_DOMAINS.get(role, ())}.\n"
                f"Acquisition errors: {self.errors or 'none'}."
            )
        lines = [
            f"EVIDENCE PACKAGE for {self.ticker}  as_of={self.as_of}  role={role}",
            f"yf_symbol={self.yf_symbol}  items={len(items)}  errors={len(self.errors)}",
            self._canonical_line(),
            "Cite ONLY evidence IDs listed in THIS package. Do not invent numbers "
            "or cite IDs you were not given. If an ID is present, that fact was supplied.",
            "",
        ]
        for item in items:
            value = item.value
            if isinstance(value, str) and len(value) > 500:
                value = value[:500] + "…"
            lines.append(f"[{item.id}] {item.domain} / {item.label}")
            lines.append(f"    value: {value}")
            lines.append(f"    source: {item.source}")
            if item.note:
                lines.append(f"    note: {item.note}")
            lines.append("")
        if self.errors:
            lines.append("Acquisition errors (not evidence):")
            for err in self.errors:
                lines.append(f"- {err}")
        return "\n".join(lines).strip()

    def as_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "as_of": self.as_of,
            "yf_symbol": self.yf_symbol,
            "item_count": len(self.items),
            "errors": list(self.errors),
            "canonical": self.canonical,
            "acquisition": self.acquisition,
            "market_snapshot": self.market_snapshot,
            "items": [asdict(item) for item in self.items],
        }


def acquire_evidence(ticker: str, progress=None) -> EvidencePackage:
    symbol = ticker if ticker.endswith((".NS", ".BO")) else f"{ticker}.NS"
    as_of = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    pkg = EvidencePackage(ticker=ticker.upper().replace(".NS", "").replace(".BO", ""), as_of=as_of, yf_symbol=symbol)

    def update(msg: str):
        if progress:
            progress(msg)

    update(f"Evidence: fetching {symbol} from Yahoo Finance…")
    info: dict = {}
    ticker_obj = None
    try:
        import yfinance as yf
        ticker_obj = yf.Ticker(symbol)
        info = ticker_obj.info or {}
        if not isinstance(info, dict):
            info = {}
    except Exception as exc:
        pkg.errors.append(f"yfinance info: {exc}")

    name = str(info.get("shortName") or info.get("longName") or pkg.ticker)

    for key, label, domain in INFO_FIELDS:
        value = info.get(key)
        note = ""
        if label == "debt_to_equity" and value is not None:
            value, note = _canonical_debt_to_equity(value)
        pkg.add(domain, label, value, "yfinance.info", note=note)

    summary = info.get("longBusinessSummary")
    if isinstance(summary, str) and summary.strip():
        pkg.add("filings", "business_summary", summary.strip()[:1200], "yfinance.info")

    if ticker_obj is not None:
        _add_statement_lines(pkg, ticker_obj, "financials", (
            ("Total Revenue", "annual_revenue"),
            ("Net Income", "annual_net_income"),
            ("EBITDA", "annual_ebitda"),
        ))
        _add_statement_lines(pkg, ticker_obj, "quarterly_financials", (
            ("Total Revenue", "quarterly_revenue"),
            ("Net Income", "quarterly_net_income"),
        ))
        _add_news(pkg, ticker_obj)
        _add_actions(pkg, ticker_obj)

    update("Evidence: computing technical snapshot…")
    try:
        ohlcv = fetch_ohlcv(pkg.ticker)
        snapshot = compute_snapshot_from_ohlcv(ohlcv, ticker=pkg.ticker)
    except Exception as exc:
        snapshot = {"valid": False, "error": str(exc)}
        pkg.errors.append(f"ohlcv: {exc}")
    pkg.market_snapshot = snapshot
    if snapshot_is_valid(snapshot):
        for key in (
            "price", "sma20", "sma50", "sma200", "rsi", "macd", "macd_signal",
            "atr", "volume", "volume_vs_average", "high_52w", "low_52w",
            "support", "resistance", "trend", "cross", "bars",
        ):
            pkg.add("market", key, snapshot.get(key), "python.technical_compute")
        pkg.canonical = {
            "price": snapshot.get("price"),
            "price_source": "python.technical_compute",
            "price_timestamp": snapshot.get("as_of"),
            "quote_type": "latest_close",
            "live_price_quote": info.get("currentPrice"),
        }
        # live_price_quote stays on canonical only — never as an evidence item,
        # so agents cannot pick between 1282 and 1298.
    else:
        pkg.errors.append(snapshot.get("error") or "technical snapshot invalid")
        pkg.canonical = {
            "price": info.get("currentPrice"),
            "price_source": "yfinance.info" if info.get("currentPrice") else None,
            "price_timestamp": as_of,
            "quote_type": "live_price_quote" if info.get("currentPrice") else None,
            "live_price_quote": info.get("currentPrice"),
        }

    update("Evidence: searching news, filings, competitors…")
    _add_web_searches(pkg, name)

    if not pkg.items:
        pkg.errors.append("Evidence package is empty")
    update(f"Evidence: {len(pkg.items)} items, {len(pkg.errors)} errors")
    return pkg


def _canonical_debt_to_equity(value):
    """
    yfinance often returns D/E as a percent (36.653 = 36.65%).
    Store a ratio. Values above 10 are treated as percent.
    """
    try:
        number = float(value)
    except (TypeError, ValueError):
        return value, ""
    if number != number:
        return None, ""
    if number > 10:
        return round(number / 100.0, 6), f"normalized from vendor percent {number}"
    return round(number, 6), "ratio"


def _add_statement_lines(pkg: EvidencePackage, ticker_obj, attr: str, rows: Iterable[tuple[str, str]]):
    try:
        frame = getattr(ticker_obj, attr)
        if frame is None or getattr(frame, "empty", True):
            return
        for index_name, label in rows:
            if index_name not in frame.index:
                continue
            series = frame.loc[index_name]
            payload = {}
            for col, val in list(series.items())[:4]:
                key = str(col)[:10]
                payload[key] = _jsonable(val)
            pkg.add("financials", label, payload, f"yfinance.{attr}")
    except Exception as exc:
        pkg.errors.append(f"{attr}: {exc}")


def _add_news(pkg: EvidencePackage, ticker_obj):
    try:
        news = ticker_obj.news or []
    except Exception as exc:
        pkg.errors.append(f"news: {exc}")
        return
    for i, item in enumerate(news[:8]):
        content = item.get("content") if isinstance(item, dict) else None
        if isinstance(content, dict):
            title = content.get("title") or ""
            summary = content.get("summary") or content.get("description") or ""
            pub = (content.get("pubDate") or "")[:10]
        else:
            title = (item or {}).get("title") or ""
            summary = (item or {}).get("summary") or ""
            pub = ""
        headline = " — ".join(p for p in (title, summary) if p)
        if headline:
            pkg.add("news", f"headline_{i+1}", headline[:400], "yfinance.news", note=pub)


def _add_actions(pkg: EvidencePackage, ticker_obj):
    try:
        actions = ticker_obj.actions
        if actions is None or getattr(actions, "empty", True):
            return
        tail = actions.tail(6)
        rows = []
        for idx, row in tail.iterrows():
            rows.append({
                "date": str(idx)[:10],
                "dividends": _jsonable(row.get("Dividends")),
                "splits": _jsonable(row.get("Stock Splits")),
            })
        pkg.add("corporate_actions", "recent_dividends_splits", rows, "yfinance.actions")
    except Exception as exc:
        pkg.errors.append(f"actions: {exc}")


# Status vocabulary for each acquisition source. "not applicable" would be set
# by callers that deliberately skip a source; the others come from retrieval.
SEARCH_STATUSES = ("found", "not_found", "retrieval_failed", "source_unavailable", "not_applicable")


def _add_web_searches(pkg: EvidencePackage, company_name: str):
    queries = [
        ("management", "concall_search", f"{pkg.ticker} {company_name} earnings call transcript highlights"),
        ("filings", "capex_search", f"{pkg.ticker} {company_name} annual report capex plans"),
        ("news", "announcement_search", f"{pkg.ticker} NSE BSE stock latest news announcements"),
        ("competitors", "competitor_search", f"{company_name} main competitors market share India"),
    ]
    for domain, label, query in queries:
        hits, status = _web_search(query)
        pkg.acquisition[label] = {
            "source": label.replace("_search", ""),
            "status": status,
            "attempted": True,
            "result_count": len(hits),
            "query": query,
        }
        if hits:
            pkg.add(domain, label, hits, "duckduckgo", note=query)
        else:
            # Distinguish a failed retrieval from a genuine empty result set.
            pkg.errors.append(f"{label}: {status}")


def _web_search(query: str, max_results: int = 5) -> tuple[list[dict], str]:
    """Returns (hits, status). status is one of SEARCH_STATUSES."""
    try:
        from duckduckgo_search import DDGS
    except Exception:
        return [], "source_unavailable"
    try:
        with DDGS() as ddgs:
            raw = list(ddgs.text(query, max_results=max_results)) or []
    except Exception:
        return [], "retrieval_failed"
    hits = []
    for row in raw:
        title = (row or {}).get("title") or ""
        body = (row or {}).get("body") or (row or {}).get("href") or ""
        if title or body:
            hits.append({"title": title, "body": body[:400]})
    return (hits, "found") if hits else ([], "not_found")


def _jsonable(value):
    if value is None:
        return None
    if hasattr(value, "item"):
        try:
            value = value.item()
        except Exception:
            pass
    if isinstance(value, float) and value != value:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return str(value)
