"""
Developed Markets Research Agents
Multi-agent pipeline for analyzing developed market economies (USA, EU, Japan).
"""
from agents.common import BaseAgent, setup_gemini
from duckduckgo_search import DDGS
import yfinance as yf

class DevelopedMarketsScout(BaseAgent):
    """Tracks macro trends in developed economies."""
    
    def __init__(self):
        super().__init__("Developed Markets Scout", "Macro Analyst")
    
    def search(self, query):
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=5))
                return "\n".join([f"- {r['title']}: {r['body']}" for r in results])
        except:
            return "Search unavailable"
    
    def run(self, region: str) -> str:
        """Analyzes macro health of a developed market."""
        macro_query = f"{region} GDP inflation unemployment 2025 economic data"
        central_bank_query = f"{region} central bank policy interest rates 2025"
        
        macro_data = self.search(macro_query)
        policy_data = self.search(central_bank_query)
        
        prompt = f"""
        Analyze the macro environment for **{region}**:
        
        **Economic Indicators**: {macro_data}
        **Central Bank Policy**: {policy_data}
        
        Provide:
        1. Macro Health Score (0-100)
        2. Monetary Policy Stance (Dovish/Neutral/Hawkish)
        3. Key Economic Trends
        4. Market Implications
        """
        
        return self.model.generate_content(prompt).text


class EquityValuationAnalyst(BaseAgent):
    """Compares equity market valuations across regions."""
    
    def __init__(self):
        super().__init__("Valuation Analyst", "Equity Strategist")
    
    def get_index_data(self, ticker: str):
        """Fetch basic index data using yfinance."""
        try:
            data = yf.Ticker(ticker)
            info = data.info
            pe = info.get('trailingPE', 'N/A')
            return f"P/E: {pe}"
        except:
            return "Data unavailable"
    
    def run(self, regions: list) -> str:
        """Compares valuations across developed markets."""
        
        # Map regions to index tickers
        index_map = {
            "USA": "^GSPC",  # S&P 500
            "Europe": "^STOXX50E",  # Euro Stoxx 50
            "Japan": "^N225",  # Nikkei 225
        }
        
        valuation_data = ""
        for region in regions:
            ticker = index_map.get(region, "")
            if ticker:
                data = self.get_index_data(ticker)
                valuation_data += f"**{region}**: {data}\n"
        
        prompt = f"""
        Compare equity market valuations:
        
        {valuation_data}
        
        Analyze:
        1. Which market is most attractive on valuation?
        2. Historical context (expensive vs. cheap)
        3. Earnings growth expectations
        """
        
        return self.model.generate_content(prompt).text


class DevelopedMarketsEditor(BaseAgent):
    """Synthesizes developed markets analysis into final report."""
    
    def __init__(self):
        super().__init__("DM Editor", "Report Writer")
    
    def run(self, regions_data: dict, valuation_analysis: str) -> str:
        """Creates comprehensive developed markets report."""
        
        regions_text = ""
        for region, data in regions_data.items():
            regions_text += f"\n### {region}\n{data}\n\n"
        
        prompt = f"""
        Create a **Comprehensive Developed Markets Research Report**:
        
        **Regional Analyses**:
        {regions_text}
        
        **Valuation Comparison**:
        {valuation_analysis}
        
        **Output Structure**:
        
        # Developed Markets Outlook - {{date}}
        
        ## 1. Executive Summary
        - Global Macro Environment (Risk-On or Risk-Off?)
        - Central Bank Policy Divergence
        - Top Investment Themes
        
        ## 2. Regional Deep Dive
        ### USA
        - Fed Policy & Rate Outlook
        - S&P 500 Trends
        - Sector Leadership
        
        ### Europe
        - ECB Policy
        - Growth vs. Recession Risks
        - EUR Implications
        
        ### Japan
        - BoJ Stance
        - Nikkei Momentum
        - USD/JPY Impact
        
        ## 3. Cross-Market Valuation
        - USA vs. Europe vs. Japan
        - India vs. Developed Markets
        
        ## 4. Currency & Commodities
        - USD Strength implications
        - Gold, Oil outlook
        
        ## 5. Investment Strategy
        - Global allocation recommendations with specific percentages
        - Hedging considerations (currency, interest rate)
        - Timeline for positioning (Q1, Q2, etc.)
        
        ## 6. Financial Terms Glossary
        Define ALL complex financial and central banking terms used (at least 15-20 terms):
        - **Fed (Federal Reserve)**: [Clear explanation]
        - **ECB (European Central Bank)**: [Clear explanation]
        - **BoJ (Bank of Japan)**: [Clear explanation]
        - **QE (Quantitative Easing)**: [Clear explanation]
        - **CAPE Ratio**: [Clear explanation]
        - **Risk-On/Risk-Off**: [Clear explanation]
        - **Dovish/Hawkish Policy**: [Clear explanation]
        - **USD/JPY**: [Clear explanation]
        (Include all other terms used)
        
        **CRITICAL REQUIREMENTS**:
        - Minimum 2500 words (excluding glossary)
        - Provide exhaustive regional analysis with specific interest rates, GDP figures, policy actions
        - Include actual central bank meeting dates and decisions
        - Compare markets with valuation tables
        - The glossary must explain EVERY technical term used
        """
        
        return self.model.generate_content(prompt).text
