import json
from .common import BaseAgent, setup_gemini
from duckduckgo_search import DDGS

class ResearchAgent(BaseAgent):
    """
    The Historian: Digs into annual reports, con-calls, and historical data.
    """
    def __init__(self):
        super().__init__("The Historian", "Fundamental Researcher")

    def search(self, query):
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=5))
                return "\n".join([f"- {r['title']}: {r['body']}" for r in results])
        except Exception as e:
            return f"Search Error: {str(e)}"

    def run(self, ticker: str) -> str:
        concall_query = f"{ticker} earnings call transcript key highlights 2024"
        capex_query = f"{ticker} annual report capex plans 2025"
        
        raw_concall = self.search(concall_query)
        raw_capex = self.search(capex_query)
        
        prompt = f"""
        Analyze these search results for {ticker}:
        
        **Con-call Transcripts**:
        {raw_concall}
        
        **Capex Plans**:
        {raw_capex}
        
        **Task**: Summarize Management Guidance, Capex strategy, and any major operational shifts.
        Focus on facts, numbers, and dates.
        """
        response = self.model.generate_content(prompt)
        return response.text

class MarketScout(BaseAgent):
    """
    The News Hound: Scans real-time news, sediment, and competitor moves.
    """
    def __init__(self):
        super().__init__("Market Scout", "News Analyst")

    def search(self, query):
        try:
            with DDGS() as ddgs:
                # Search for news in last month? DDGS doesn't easily support time range in simple text, 
                # but adding '2025' or 'latest news' helps.
                results = list(ddgs.text(query, max_results=5))
                return "\n".join([f"- {r['title']}: {r['body']}" for r in results])
        except Exception as e:
            return f"Search Error: {str(e)}"

    def run(self, ticker: str) -> str:
        news_query = f"{ticker} stock latest news major announcements 2025"
        competitor_query = f"{ticker} main competitors market share changes india 2025"
        
        raw_news = self.search(news_query)
        raw_comp = self.search(competitor_query)
        
        prompt = f"""
        Analyze these market updates for {ticker}:
        
        **Latest News**:
        {raw_news}
        
        **Competitor Landscape**:
        {raw_comp}
        
        **Task**: Identify key order wins, regulatory impacts, and competitive threats in the last 6-12 months.
        Highlight any immediate red flags or catalysists.
        """
        response = self.model.generate_content(prompt)
        return response.text
