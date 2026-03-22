"""
QuanTum News Scanner v2 — Deep Impact News Scoring

Upgrades from v1:
  - Gemini now extracts: surprise_factor, event_type (weighted), expected vs actual
  - Market reaction confirmation: cross-references price change + volume spike
  - Final news_impact_score = 0.4*sentiment + 0.3*surprise + 0.2*event_weight + 0.1*reaction

Pipeline: RSS feeds → Gemini extraction → reaction confirmation → deep impact score
"""
import feedparser
import re
import json
import sys
import io
import logging
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
from agents.common import setup_gemini

logging.getLogger("yfinance").setLevel(logging.CRITICAL)

RSS_FEEDS = {
    "Economic Times Markets": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "ET Stocks": "https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms",
    "Moneycontrol": "https://www.moneycontrol.com/rss/MCtopnews.xml",
    "MC Stocks": "https://www.moneycontrol.com/rss/marketoutlook.xml",
    "Business Standard": "https://www.business-standard.com/rss/markets-106.rss",
    "Mint Markets": "https://www.livemint.com/rss/markets",
    "NDTV Profit": "https://feeds.feedburner.com/ndtvprofit-latest",
}

EVENT_TYPE_WEIGHTS = {
    "earnings_beat":       1.00,
    "guidance_upgrade":    1.00,
    "large_order_win":     0.90,
    "promoter_buying":     0.90,
    "analyst_upgrade":     0.85,
    "block_deal":          0.85,
    "policy_benefit":      0.80,
    "capacity_expansion":  0.75,
    "product_launch":      0.70,
    "management_change":   0.65,
    "sector_news":         0.60,
    "general_mention":     0.40,
    "rumor":               0.30,
    "earnings_miss":       0.90,  # high weight but negative sentiment
    "guidance_downgrade":  0.90,
    "analyst_downgrade":   0.85,
    "regulatory_risk":     0.80,
}

DISCOVERY_PROMPT = """\
You are a financial news analyst for Indian stock markets (NSE/BSE).

**Headlines (last 24 hours):**
{headlines}

**Task:** Extract ALL NSE-listed stocks mentioned or directly impacted.

**Output ONLY valid JSON** (no markdown fences):
{{
  "tickers": [
    {{
      "symbol": "RELIANCE",
      "catalyst": "Q3 revenue beats estimates by 8%; Jio subscriber adds 12M",
      "sentiment": 0.8,
      "urgency": "high",
      "event_type": "earnings_beat",
      "surprise_pct": 8.0
    }}
  ]
}}

Field definitions:
- symbol: NSE ticker (e.g. RELIANCE, TCS, HDFCBANK)
- catalyst: 1-2 sentence specific news description
- sentiment: -1.0 (very bearish) to +1.0 (very bullish)
- urgency: "high" | "medium" | "low"
- event_type: one of: earnings_beat, guidance_upgrade, large_order_win,
  promoter_buying, analyst_upgrade, block_deal, policy_benefit,
  capacity_expansion, product_launch, management_change, sector_news,
  general_mention, rumor, earnings_miss, guidance_downgrade,
  analyst_downgrade, regulatory_risk
- surprise_pct: numeric surprise magnitude (e.g. EPS beat by 8% → 8.0,
  order win 2x expected → 100.0, no clear surprise → 0).
  Use 0 if the surprise is unclear from the headline.

Rules:
- Include 20-50 tickers. Prefer breadth.
- Only include NSE-listed stocks with relevant news.
- Do NOT fabricate catalysts. Use actual headline content.
- For sector/policy news, include all major stocks in that sector.
"""


def _is_valid_nse_symbol(sym: str) -> bool:
    """
    Quick validation: NSE symbols are 1-20 uppercase chars,
    may contain & and -, no spaces, no numbers-only.
    Rejects known garbage patterns from Gemini hallucination.
    """
    if not sym or len(sym) > 20:
        return False
    if not any(c.isalpha() for c in sym):
        return False
    if " " in sym:
        return False
    REJECT = {
        "NIFTY", "SENSEX", "BSE", "NSE", "INDEX", "INDIA",
        "NIFTY50", "NIFTYBANK", "BANKNIFTY", "FINNIFTY",
    }
    if sym in REJECT:
        return False
    return True


def _batch_verify_tickers(symbols: list[str]) -> set[str]:
    """
    Batch-verify which tickers exist on yfinance using a single download.
    Much faster than checking one-by-one and suppresses error noise.
    """
    if not symbols:
        return set()

    import logging
    import os
    import io
    import sys

    yf_symbols = [f"{s}.NS" for s in symbols]

    # Suppress yfinance error output during batch check
    old_stderr = sys.stderr
    sys.stderr = io.StringIO()
    yf_logger = logging.getLogger("yfinance")
    old_level = yf_logger.level
    yf_logger.setLevel(logging.CRITICAL)

    try:
        data = yf.download(
            yf_symbols, period="5d", interval="1d",
            progress=False, auto_adjust=True, group_by="ticker",
        )
    except Exception:
        data = None
    finally:
        sys.stderr = old_stderr
        yf_logger.setLevel(old_level)

    if data is None or data.empty:
        return set()

    valid = set()
    for sym in symbols:
        yf_sym = f"{sym}.NS"
        try:
            if len(yf_symbols) == 1:
                close = data["Close"].squeeze().dropna()
            else:
                if yf_sym in data.columns.get_level_values(0):
                    close = data[yf_sym]["Close"].dropna()
                else:
                    continue
            if len(close) > 0:
                valid.add(sym)
        except Exception:
            continue

    return valid


class NewsScanner:
    """
    Discovers stocks from news with deep impact scoring:
    sentiment, surprise factor, event type weight, market reaction.
    """

    def __init__(self):
        self.model = setup_gemini()

    def fetch_all_headlines(self) -> list[dict]:
        headlines = []
        for source, url in RSS_FEEDS.items():
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:20]:
                    headlines.append({
                        "source": source,
                        "title": entry.get("title", ""),
                        "summary": entry.get("summary", "")[:300],
                        "link": entry.get("link", ""),
                        "published": entry.get("published", ""),
                    })
            except Exception:
                continue
        return headlines

    def discover_tickers(
        self, headlines: list[dict] | None = None, progress_callback=None,
    ) -> tuple[list[dict], list[dict]]:
        if progress_callback:
            progress_callback("Scanning financial news feeds...")

        if headlines is None:
            headlines = self.fetch_all_headlines()

        if not headlines:
            return [], []

        if progress_callback:
            progress_callback(f"Deep-analysing {len(headlines)} headlines with Gemini...")

        headline_text = "\n".join([
            f"- [{h['source']}] {h['title']}"
            + (f" -- {h['summary'][:120]}" if h.get('summary') else "")
            for h in headlines[:80]
        ])

        prompt = DISCOVERY_PROMPT.format(headlines=headline_text)

        try:
            resp = self.model.generate_content(prompt).text.strip()
            resp = re.sub(r"```json|```", "", resp).strip()
            data = json.loads(resp)
            tickers = data.get("tickers", [])

            cleaned = []
            seen = set()
            for t in tickers:
                sym = t.get("symbol", "").upper().strip()
                if not sym or sym in seen:
                    continue
                # Filter out obviously invalid tickers
                if not _is_valid_nse_symbol(sym):
                    continue
                seen.add(sym)

                sentiment = max(-1.0, min(1.0, float(t.get("sentiment", 0))))
                event_type = t.get("event_type", "general_mention")
                event_weight = EVENT_TYPE_WEIGHTS.get(event_type, 0.40)
                surprise_raw = float(t.get("surprise_pct", 0))

                # Surprise score: 0-100
                abs_surprise = abs(surprise_raw)
                if abs_surprise > 20:
                    surprise_score = 100
                elif abs_surprise > 10:
                    surprise_score = 80
                elif abs_surprise > 5:
                    surprise_score = 60
                elif abs_surprise > 0:
                    surprise_score = 40
                else:
                    surprise_score = 20

                cleaned.append({
                    "symbol": sym,
                    "catalyst": t.get("catalyst", "News mention"),
                    "sentiment": sentiment,
                    "urgency": t.get("urgency", "medium"),
                    "event_type": event_type,
                    "event_weight": event_weight,
                    "surprise_pct": surprise_raw,
                    "surprise_score": surprise_score,
                })

            # Batch-verify tickers exist on yfinance (single download)
            if progress_callback:
                progress_callback(f"Batch-verifying {len(cleaned)} tickers on NSE...")

            all_syms = [t["symbol"] for t in cleaned]
            valid_syms = _batch_verify_tickers(all_syms)

            verified = [t for t in cleaned if t["symbol"] in valid_syms]

            if progress_callback:
                dropped = len(cleaned) - len(verified)
                progress_callback(
                    f"Verified {len(verified)} stocks "
                    f"(dropped {dropped} invalid, "
                    f"+{sum(1 for t in verified if t['sentiment'] > 0)}, "
                    f"-{sum(1 for t in verified if t['sentiment'] < 0)})"
                )

            return verified, headlines

        except Exception as e:
            if progress_callback:
                progress_callback(f"News scan error: {e}")
            return [], headlines

    def add_reaction_scores(
        self, tickers: list[dict], progress_callback=None,
    ) -> list[dict]:
        """
        Cross-references news with actual market reaction:
        price change percentile + volume percentile across the batch.
        """
        if not tickers:
            return tickers

        if progress_callback:
            progress_callback("Checking market reaction to news catalysts...")

        symbols = [f"{t['symbol']}.NS" for t in tickers[:40]]

        try:
            old_stderr = sys.stderr
            sys.stderr = io.StringIO()
            try:
                data_5d = yf.download(symbols, period="5d", interval="1d",
                                      progress=False, auto_adjust=True, group_by="ticker")
                data_1mo = yf.download(symbols, period="1mo", interval="1d",
                                       progress=False, auto_adjust=True, group_by="ticker")
            finally:
                sys.stderr = old_stderr
        except Exception:
            for t in tickers:
                t["reaction_score"] = 50.0
                t["news_impact_score"] = self._compute_impact(t, 50.0)
            return tickers

        price_changes = {}
        volume_ratios = {}

        for t in tickers:
            sym_ns = f"{t['symbol']}.NS"
            try:
                if len(symbols) == 1:
                    close_5d = data_5d["Close"].squeeze().dropna()
                    vol_1mo = data_1mo["Volume"].squeeze().dropna()
                    close_1mo = data_1mo["Close"].squeeze().dropna()
                else:
                    close_5d = data_5d[sym_ns]["Close"].dropna() if sym_ns in data_5d.columns.get_level_values(0) else pd.Series(dtype=float)
                    vol_1mo = data_1mo[sym_ns]["Volume"].dropna() if sym_ns in data_1mo.columns.get_level_values(0) else pd.Series(dtype=float)
                    close_1mo = data_1mo[sym_ns]["Close"].dropna() if sym_ns in data_1mo.columns.get_level_values(0) else pd.Series(dtype=float)

                if len(close_5d) >= 2:
                    pct_change = (float(close_5d.iloc[-1]) / float(close_5d.iloc[0]) - 1) * 100
                    price_changes[t["symbol"]] = pct_change

                if len(vol_1mo) >= 5:
                    recent_vol = float(vol_1mo.iloc[-1])
                    avg_vol = float(vol_1mo.iloc[:-1].mean())
                    if avg_vol > 0:
                        volume_ratios[t["symbol"]] = recent_vol / avg_vol
            except Exception:
                continue

        # Percentile rank price changes and volume ratios
        if price_changes:
            pc_series = pd.Series(price_changes)
            pc_pct = pc_series.rank(pct=True) * 100
        else:
            pc_pct = pd.Series(dtype=float)

        if volume_ratios:
            vr_series = pd.Series(volume_ratios)
            vr_pct = vr_series.rank(pct=True) * 100
        else:
            vr_pct = pd.Series(dtype=float)

        for t in tickers:
            sym = t["symbol"]
            price_pctl = float(pc_pct.get(sym, 50.0))
            vol_pctl = float(vr_pct.get(sym, 50.0))
            reaction = 0.50 * price_pctl + 0.50 * vol_pctl
            t["reaction_score"] = round(reaction, 1)
            t["news_impact_score"] = self._compute_impact(t, reaction)

        return tickers

    def _compute_impact(self, ticker_data: dict, reaction: float) -> float:
        """
        Final news impact = 0.4*sentiment + 0.3*surprise + 0.2*event_weight + 0.1*reaction
        Mapped to 0-100 scale.
        """
        sent_norm = (ticker_data["sentiment"] + 1) / 2.0 * 100  # -1..+1 → 0..100
        surprise = ticker_data.get("surprise_score", 20)
        event_w = ticker_data.get("event_weight", 0.4) * 100
        reaction_norm = reaction

        impact = (0.40 * sent_norm +
                  0.30 * surprise +
                  0.20 * event_w +
                  0.10 * reaction_norm)
        return round(max(0, min(100, impact)), 1)

    def run(self, progress_callback=None) -> tuple[list[dict], list[dict]]:
        """Full pipeline: headlines → discover → reaction check → impact scores."""
        tickers, headlines = self.discover_tickers(progress_callback=progress_callback)
        tickers = self.add_reaction_scores(tickers, progress_callback=progress_callback)
        return tickers, headlines
