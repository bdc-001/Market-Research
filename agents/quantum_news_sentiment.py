"""
QuanTum News Sentiment Agent
Scrapes free RSS feeds from Indian financial news sources.
Scores each headline using Gemini → Bullish (+1), Neutral (0), Bearish (-1).
Aggregates per-stock sentiment scores — HORIZON-AWARE scoring.

Weekly  → immediate event-driven catalysts (earnings, results, alerts)
1 Year  → FII/DII accumulation signals, analyst upgrades, earnings guidance
5 Years → structural tailwinds: PLI, govt policy, demographic, ESG, moats
"""
import feedparser
import re
import json
from agents.common import setup_gemini
from datetime import datetime

# Free RSS Feeds (no API keys needed)
RSS_FEEDS = {
    "Economic Times Markets": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "Moneycontrol": "https://www.moneycontrol.com/rss/MCtopnews.xml",
    "Business Standard": "https://www.business-standard.com/rss/markets-106.rss",
    "Mint Markets": "https://www.livemint.com/rss/markets",
    "NDTV Profit": "https://feeds.feedburner.com/ndtvprofit-latest",
}

# Horizon-specific prompt instructions for Gemini
HORIZON_PROMPTS = {
    "week": """\
**Scoring Context — THIS WEEK (1-7 days)**:
You are a short-term momentum trader. Score stocks ONLY on immediate catalysts:
- Earnings releases, quarterly results, revenue beats/misses announced THIS WEEK
- Sudden regulatory approvals or rejections
- Short-term FII/DII buying/selling alerts
- Block deals, insider buying, circuit breakers
- Immediate macro events (RBI rate decision, budget announcements today)

Give HIGH positive scores (+0.6 to +1.0) ONLY to stocks with fresh positive news events.
Give NEGATIVE scores (-0.4 to -1.0) to stocks with immediate bad news.
Score 0 for stocks with no immediate this-week catalyst.
Ignore long-term structural stories — they are NOT relevant for this week.""",

    "year": """\
**Scoring Context — THIS YEAR (6-12 months)**:
You are a positional swing trader following FII/DII money flows. Score stocks on:
- FII/DII accumulation or distribution patterns mentioned in news
- Analyst upgrades/downgrades from reputable brokerages (Goldman, Citi, CLSA, Motilal)
- Management earnings guidance upgrades for the next 2-4 quarters
- Sector rotation signals (which sectors are FIIs moving into?)
- Credit rating upgrades, IPO pipeline, QIP announcements
- Company-specific positive developments: new contracts, capacity expansion

Give HIGH scores to stocks FIIs/DIIs are reportedly accumulating or that have analyst upgrades.
Give NEGATIVE scores to stocks under FII selling pressure or analyst downgrades.
Score 0 for stocks with no institutional-relevant news.""",

    "5years": """\
**Scoring Context — NEXT 5 YEARS (structural wealth creation)**:
You are a long-term value investor following Buffett and Ray Dalio principles.
Score stocks on structural, multi-year themes ONLY:
- Government policy tailwinds: PLI schemes, Make in India, infra spending, defence indigenization
- Sector megatrends: EV adoption curve, renewable energy transition, digital payments, healthcare spending
- Management quality: founder-led companies, proven capital allocators, promoter buying
- Demographic tailwinds: companies benefiting from India's consumption boom, urbanization
- ESG and governance improvements mentioned
- Monopoly/duopoly positions, unassailable market share

Give HIGH scores (+0.5 to +1.0) ONLY to stocks with strong structural multi-year narratives.
Score low or 0 for stocks that only have short-term news — weekly catalysts are irrelevant here.
Score NEGATIVE for stocks facing structural disruption, regulatory overhangs, or governance issues.""",
}


class NewsSentimentAgent:
    """
    Scrapes RSS feeds and assigns per-stock sentiment scores — horizon-aware.
    """

    def __init__(self):
        self.model = setup_gemini()

    def fetch_all_headlines(self) -> list[dict]:
        """Pulls headlines from all RSS feeds."""
        headlines = []
        for source, url in RSS_FEEDS.items():
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:15]:  # top 15 per source
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

    def score_batch(
        self,
        headlines: list[dict],
        tickers: list[str],
        horizon: str = "week",
    ) -> dict[str, float]:
        """
        Sends all headlines to Gemini with horizon-specific scoring instructions.
        Returns dict: {ticker: sentiment_score (-1 to +1)}
        """
        ticker_list = ", ".join(tickers[:50])  # limit prompt size
        headline_text = "\n".join([
            f"- [{h['source']}] {h['title']}"
            for h in headlines[:50]  # use up to 50 headlines
        ])

        horizon_instruction = HORIZON_PROMPTS.get(horizon, HORIZON_PROMPTS["week"])

        prompt = f"""
You are a financial sentiment analyzer for Indian stock markets.

**Headlines (last 24 hours)**:
{headline_text}

**Stock Universe**: {ticker_list}

{horizon_instruction}

**Output ONLY valid JSON** like this (no markdown fences, no explanation):
{{
  "RELIANCE": 0.7,
  "TATAMOTORS": -0.3,
  "INFY": 0.2
}}

Rules:
- Only include tickers that have relevant news for the given scoring context above.
- Omit tickers with no relevant news (do NOT output them with 0 — just omit).
- Scores must be between -1.0 and +1.0.
"""
        try:
            resp = self.model.generate_content(prompt).text.strip()
            resp = re.sub(r"```json|```", "", resp).strip()
            scores = json.loads(resp)
            return {k: max(-1.0, min(1.0, float(v))) for k, v in scores.items()}
        except Exception:
            return {}

    def run(
        self,
        tickers: list[str],
        horizon: str = "week",
        progress_callback=None,
    ) -> tuple[dict[str, float], list[dict]]:
        """
        Full pipeline: fetch headlines → score for specific horizon → return scores.

        Parameters
        ----------
        tickers : list of ticker symbols
        horizon : "week" | "year" | "5years"
        progress_callback : optional callable(str)

        Returns
        -------
        (scores_dict, headlines_list)
        """
        if progress_callback:
            progress_callback(f"📰 [{horizon.upper()}] Fetching RSS feeds (ET, Moneycontrol, Mint)...")

        headlines = self.fetch_all_headlines()

        if progress_callback:
            progress_callback(f"🧠 [{horizon.upper()}] Scoring {len(headlines)} headlines via Gemini...")

        scores = self.score_batch(headlines, tickers, horizon=horizon)

        if progress_callback:
            progress_callback(f"✅ [{horizon.upper()}] Sentiment scored for {len(scores)} stocks")

        return scores, headlines
