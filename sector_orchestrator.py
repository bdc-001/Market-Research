"""
Sector Orchestrator - Multi-Agent Sector Analysis
Uses Research Agents + Financial Agent + Editor for comprehensive industry reports.
"""
from agents.research_agent import ResearchAgent, MarketScout
from agents.bull_bear_agents import FinancialAgent
from agents.common import setup_gemini

class SectorOrchestrator:
    def __init__(self):
        print("🏭 Initializing Sector Analysis Council...")
        self.researcher = ResearchAgent()
        self.scout = MarketScout()
        self.quant = FinancialAgent()
        self.model = setup_gemini()

    def run_sector_analysis(self, sector: str, progress_callback=None):
        """
        Comprehensive Sector Report using Multi-Agent approach.
        """
        
        def update(msg):
            if progress_callback:
                progress_callback(msg)
            else:
                print(f"🔄 {msg}")

        # Phase 1: Macro Research
        update("🕵️ Research Agent: Analyzing Industry Trends & Government Policies...")
        industry_context = f"{sector} industry india 2025 growth drivers government policies PLI scheme"
        macro_data = self.researcher.run(industry_context)
        
        # Phase 2: Market Intelligence
        update("📰 Market Scout: Tracking Institutional Movements & Key Players...")
        institutional_query = f"{sector} india institutional investors FII DII positioning major stocks 2025"
        institutional_data = self.scout.run(institutional_query)
        
        # Phase 3: Stock Screening
        update("📈 Financial Agent: Screening Top Stocks in Sector...")
        screening_prompt = f"""
        Identify the Top 10 publicly listed companies in **{sector}** (Indian Market).
        
        For each, provide:
        - Company Name & Ticker
        - Market Cap (Approx)
        - ROE & Debt/Equity
        - Recent Performance Highlight
        
        Output as a comparison table.
        """
        stock_comparison = self.model.generate_content(screening_prompt).text
        
        # Phase 4: Synthesis
        update("⚖️ Editor: Synthesizing Comprehensive Sector Report...")
        synthesis_prompt = f"""
        Create a **Comprehensive Sector Analysis Report** for **{sector}**.
        
        **Use these inputs from your analyst team**:
        
        1. **Macro & Policy Context**: {macro_data}
        2. **Institutional Positioning**: {institutional_data}
        3. **Stock Comparison**: {stock_comparison}
        
        **Output Structure** (Strictly follow):
        
        # Sector Report: {sector}
        
        ## 1. Executive Summary
        - Industry CAGR (2025-2030)
        - Key Growth Drivers
        - Investment Verdict (Attractive / Neutral / Avoid)
        
        ## 2. Industry Overview
        - Market Size & Growth Trajectory
        - Key Sub-Segments
        - Global vs. India Positioning
        
        ## 3. Government Policies & Tailwinds
        - PLI Schemes & Subsidies
        - Import Restrictions / Protections
        - Infrastructure Spending
        
        ## 4. Top 10 Stocks - Comparative Analysis
        (Insert the stock comparison table here)
        
        ### Financial Health Comparison
        - Which stocks have the best ROE/ROCE?
        - Debt profiles comparison
        
        ## 5. Institutional Investor Positioning
        - Are FIIs/DIIs increasing stakes?
        - Recent Mutual Fund inflows into this sector
        - Major block deals or insider buying
        
        ## 6. Competitive Landscape
        - Who dominates the market?
        - Emerging players to watch
        - Threat from imports/MNCs
        
        ## 7. Risks & Headwinds
        - Regulatory risks
        - Commodity price exposure
        - Competitive intensity
        
        ## 8. Investment Strategy
        - Best entry points (sectoral rotation)
        - Top 3 stock picks with detailed rationale
        - Time horizon recommendation (short/medium/long term)
        - Portfolio allocation suggestions
        
        ## 9. Financial Terms Glossary
        Define ALL complex financial and sector-specific terms used (at least 15-20 terms):
        - **CAGR (Compound Annual Growth Rate)**: [Clear explanation]
        - **PLI (Production Linked Incentive)**: [Clear explanation]
        - **FII/DII**: [Clear explanation]
        - **ROE/ROCE**: [Clear explanation]
        - **Market Cap**: [Clear explanation]
        - **Block Deals**: [Clear explanation]
        - **EV/EBITDA**: [Clear explanation]
        (Include all other sector-specific and financial terms used)
        
        **CRITICAL REQUIREMENTS**:
        - Minimum 2500 words (excluding glossary)
        - Provide exhaustive detail with specific data points, percentages, and dates
        - Include actual company names, policy names, and numbers
        - Analyze multi-year trends (3-5 years)
        - The glossary must explain EVERY technical term used in the report
        """
        
        final_report = self.model.generate_content(synthesis_prompt).text
        
        update("✅ Sector Analysis Complete!")
        return final_report
