"""
Corporate Event Scanner.

Fetches NSE/BSE announcements, keeps only catalyst-like subjects,
then optionally folds in RSS headlines that mention a universe name.
"""
from __future__ import annotations

import re

import feedparser

from agents.event_filter import filter_announcements
from agents.nse_client import ExchangeClient

RSS_FEEDS = {
    "Economic Times Markets": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "ET Stocks": "https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms",
    "Moneycontrol": "https://www.moneycontrol.com/rss/MCtopnews.xml",
    "Business Standard": "https://www.business-standard.com/rss/markets-106.rss",
    "Mint Markets": "https://www.livemint.com/rss/markets",
    "NDTV Profit": "https://feeds.feedburner.com/ndtvprofit-latest",
}


def scan_corporate_events(
    cfg: dict,
    universe,
    client: ExchangeClient | None = None,
    progress=None,
) -> list[dict]:
    radar = cfg.get("radar") or {}
    lookback = int(radar.get("announcement_lookback_days", 3))
    limit = int(radar.get("max_raw_announcements", 500))
    client = client or ExchangeClient(
        cache_ttl_minutes=int(radar.get("cache_ttl_minutes", 180))
    )

    raw: list[dict] = []
    _log(progress, "Radar: NSE equity announcements...")
    raw.extend(client.nse_announcements(index="equities", lookback_days=lookback, limit=limit))
    _log(progress, "Radar: NSE SME announcements...")
    raw.extend(client.nse_announcements(index="sme", lookback_days=lookback, limit=limit))
    if cfg.get("universe", {}).get("include_bse_sme"):
        _log(progress, "Radar: BSE announcements...")
        raw.extend(client.bse_announcements(lookback_days=lookback, limit=limit))

    _log(progress, f"Radar: {len(raw)} raw announcements")
    kept = filter_announcements(raw, cfg)
    _log(progress, f"Radar: {len(kept)} after Python event filter")

    name_index = _name_index(universe)
    resolved = []
    for item in kept:
        ticker = (item.get("ticker") or "").upper()
        if ticker:
            item["ticker"] = ticker
            resolved.append(item)
            continue
        matched = _match_name(
            f"{item.get('company_name') or ''} {item.get('subject') or ''}",
            name_index,
        )
        if matched:
            item["ticker"] = matched
            resolved.append(item)

    if radar.get("news_as_secondary"):
        news_hits = _news_for_universe(universe, cfg, progress)
        resolved.extend(news_hits)

    # Deduplicate ticker+subject
    seen = set()
    unique = []
    for item in resolved:
        key = (item.get("ticker"), (item.get("subject") or "")[:180])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    _log(progress, f"Radar: {len(unique)} universe-matched events")
    return unique


def news_mention_counts(universe, progress=None) -> dict[str, int]:
    """How many RSS items mention each universe name. 0 means scanned, not unknown."""
    if universe is None or getattr(universe, "empty", True):
        return {}
    headlines = []
    for url in RSS_FEEDS.values():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:20]:
                headlines.append(f"{entry.get('title') or ''} {entry.get('summary') or ''}")
        except Exception:
            continue
    name_index = _name_index(universe)
    ticker_set = set(universe["ticker"].tolist())
    counts: dict[str, int] = {t: 0 for t in ticker_set}
    for blob in headlines:
        ticker = _ticker_in_text(blob, ticker_set) or _match_name(blob, name_index)
        if ticker:
            counts[ticker] = counts.get(ticker, 0) + 1
    return counts


def _news_for_universe(universe, cfg, progress=None) -> list[dict]:
    if universe is None or getattr(universe, "empty", True):
        return []
    _log(progress, "Radar: scanning RSS for universe names (no LLM)...")
    headlines = []
    for source, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:20]:
                headlines.append({
                    "source": source,
                    "title": entry.get("title") or "",
                    "summary": (entry.get("summary") or "")[:300],
                })
        except Exception:
            continue

    name_index = _name_index(universe)
    ticker_set = set(universe["ticker"].tolist())
    hits = []
    for h in headlines:
        blob = f"{h['title']} {h['summary']}"
        ticker = _ticker_in_text(blob, ticker_set) or _match_name(blob, name_index)
        if not ticker:
            continue
        verdict_subject = h["title"]
        from agents.event_filter import classify_subject
        verdict = classify_subject(verdict_subject + " " + h.get("summary", ""), cfg)
        if not verdict["keep"]:
            continue
        hits.append({
            "source": f"RSS:{h['source']}",
            "ticker": ticker,
            "company_name": ticker,
            "subject": h["title"],
            "announced_at": "",
            "attachment": "",
            "event_type": verdict["event_type"],
            "matched_term": verdict["matched_term"],
            "raw": {"summary": h.get("summary")},
        })
    return hits


def _name_index(universe) -> list[tuple[str, str]]:
    if universe is None or getattr(universe, "empty", True):
        return []
    index = []
    for _, row in universe.iterrows():
        ticker = str(row["ticker"]).upper()
        name = str(row.get("company_name") or ticker)
        cleaned = re.sub(r"\b(ltd|limited|pvt|private|india|inc)\b", "", name, flags=re.I)
        cleaned = re.sub(r"[^a-zA-Z0-9& ]+", " ", cleaned).strip().lower()
        if len(cleaned) >= 4:
            index.append((cleaned, ticker))
        index.append((ticker.lower(), ticker))
    index.sort(key=lambda x: len(x[0]), reverse=True)
    return index


def _match_name(text: str, name_index) -> str | None:
    blob = re.sub(r"[^a-zA-Z0-9& ]+", " ", text or "").lower()
    for name, ticker in name_index:
        if name and name in blob:
            return ticker
    return None


def _ticker_in_text(text: str, tickers: set[str]) -> str | None:
    upper = (text or "").upper()
    for ticker in tickers:
        if len(ticker) < 3:
            continue
        if re.search(rf"\b{re.escape(ticker)}\b", upper):
            return ticker
    return None


def _log(progress, msg: str) -> None:
    if progress:
        progress(msg)
    else:
        print(msg, flush=True)
