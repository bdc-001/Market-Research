"""
The Historian: interprets filings / management / financial evidence.
Does not search when an evidence package is provided.
"""
from .common import BaseAgent


def _package_or_query(ticker: str, evidence_text: str) -> str:
    text = (evidence_text or "").strip()
    if text:
        return text
    try:
        from agents.evidence_acquisition import _web_search
        hits = _web_search(str(ticker))
    except Exception:
        hits = []
    if not hits:
        return f"No evidence package and no search hits for: {ticker}"
    return f"Search results for {ticker} (legacy path, no IDs):\n{hits}"


class ResearchAgent(BaseAgent):
    def __init__(self):
        super().__init__("The Historian", "Fundamental Researcher")

    def run(self, ticker: str, evidence_text: str = "") -> str:
        package = _package_or_query(ticker, evidence_text)
        prompt = f"""
You are the Historian for {ticker}. Analyze ONLY the evidence package below.
Every fact has an ID (E001, …). Cite those IDs. Never invent numbers.
If a topic has no ID, say it is absent — do not say the whole package is empty
when IDs are present.

{package}

Task: Summarize management guidance, capex, and operational shifts.
Focus on facts, numbers, and dates. Cite evidence IDs in each bullet.
"""
        return self.complete(prompt)


class MarketScout(BaseAgent):
    def __init__(self):
        super().__init__("Market Scout", "News Analyst")

    def run(self, ticker: str, evidence_text: str = "") -> str:
        package = _package_or_query(ticker, evidence_text)
        prompt = f"""
You are Market Scout for {ticker}. Analyze ONLY the evidence package below.
Cite evidence IDs. Do not claim "no headlines supplied" if news IDs exist.

{package}

Task: Identify order wins, regulatory impacts, competitive threats, and
near-term catalysts from the supplied news / competitor / corporate-action items.
"""
        return self.complete(prompt)
