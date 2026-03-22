"""
Emerging Markets Research Agents
Multi-agent pipeline for analyzing emerging market economies.
"""
from agents.common import BaseAgent, setup_gemini
from duckduckgo_search import DDGS

class EmergingMarketsScout(BaseAgent):
    """Tracks macro trends in emerging economies."""
    
    def __init__(self):
        super().__init__("Emerging Markets Scout", "Macro Analyst")
    
    def search(self, query):
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=5))
                return "\n".join([f"- {r['title']}: {r['body']}" for r in results])
        except:
            return "Search unavailable"
    
    def run(self, country: str) -> str:
        """Analyzes macro health of an emerging market."""
        macro_query = f"{country} GDP growth inflation 2025 economic outlook"
        political_query = f"{country} political stability elections policy 2025"
        
        macro_data = self.search(macro_query)
        political_data = self.search(political_query)
        
        prompt = f"""
        Analyze the macro environment for **{country}**:
        
        **Economic Data**: {macro_data}
        **Political Context**: {political_data}
        
        Provide:
        1. Macro Health Score (0-100)
        2. Key Growth Drivers
        3. Major Risks (political, economic)
        4. Investment Outlook (Bullish/Neutral/Bearish)
        """
        
        return self.model.generate_content(prompt).text


class SectorRotationAnalyst(BaseAgent):
    """Identifies hot sectors in emerging markets."""
    
    def __init__(self):
        super().__init__("Sector Rotation Analyst", "Sector Specialist")
    
    def search(self, query):
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=5))
                return "\n".join([f"- {r['title']}: {r['body']}" for r in results])
        except:
            return "Search unavailable"
    
    def run(self, country: str) -> str:
        """Identifies top sectors in an emerging market."""
        sector_query = f"{country} top performing sectors 2025 technology manufacturing commodities"
        
        sector_data = self.search(sector_query)
        
        prompt = f"""
        Analyze sector opportunities in **{country}**:
        
        **Sector Data**: {sector_data}
        
        Identify:
        1. Top 3 Performing Sectors
        2. Growth Catalysts for each
        3. Sector-specific risks
        """
        
        return self.model.generate_content(prompt).text


class EmergingMarketsEditor(BaseAgent):
    """Synthesizes emerging markets analysis into final report."""
    
    def __init__(self):
        super().__init__("EM Editor", "Report Writer")
    
    def run(self, countries_data: dict) -> str:
        """Creates comprehensive emerging markets report."""
        
        # Prepare country summaries
        country_sections = ""
        for country, data in countries_data.items():
            country_sections += f"\n### {country}\n{data['macro']}\n{data['sectors']}\n\n"
        
        prompt = f"""
        Create a **Comprehensive Emerging Markets Research Report**:
        
        **Country Analyses**:
        {country_sections}
        
        **Output Structure**:
        
        # Emerging Markets Outlook - {{date}}
        
        ## 1. Executive Summary
        - Top 3 Markets to Watch (ranked by opportunity)
        - Key Global Risks for Emerging Markets
        - Currency & Commodity Outlook
        
        ## 2. Country-by-Country Deep Dive
        {{Insert detailed analysis for each country}}
        
        ## 3. Comparative Analysis
        - Best Risk/Reward Markets
        - Correlation with Global Growth
        
        ## 4. Sector Opportunities
        - Cross-market sector themes
        - Where to find alpha
        
        ## 5. Investment Strategy
        - Recommended allocation across emerging markets
        - Key risks to monitor actively
        - Hedge strategies (currency, political risk)
        
        ## 6. Financial Terms Glossary
        Define ALL complex financial and macro-economic terms used (at least 15-20 terms):
        - **GDP (Gross Domestic Product)**: [Clear explanation]
        - **CAGR**: [Clear explanation]
        - **FII/DII**: [Clear explanation]
        - **Currency Devaluation**: [Clear explanation]
        - **Current Account Deficit**: [Clear explanation]
        - **PMI (Purchasing Managers Index)**: [Clear explanation]
        - **Sovereign Risk**: [Clear explanation]
        - **Capital Flight**: [Clear explanation]
        (Include all other terms used)
        
        **CRITICAL REQUIREMENTS**:
        - Minimum 2500 words (excluding glossary)
        - Provide exhaustive country-by-country analysis with specific GDP numbers, inflation rates, etc.
        - Include actual policy names, central bank actions, and dates
        - Compare countries with data tables where possible
        - The glossary must explain EVERY technical term used
        """
        
        return self.model.generate_content(prompt).text
