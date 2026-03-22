"""
Multi-Agent Orchestrator (The Council Coordinator)
"""
import time
from agents.research_agent import ResearchAgent, MarketScout
from agents.bull_bear_agents import FinancialAgent, BullAgent, BearAgent
from agents.technical_agent import TechnicalAgent
from agents.editor_agent import EditorAgent

class AgentOrchestrator:
    def __init__(self):
        print("🤖 Initializing Council of Investors...")
        self.researcher = ResearchAgent()
        self.scout = MarketScout()
        self.quant = FinancialAgent()
        self.bull = BullAgent()
        self.bear = BearAgent()
        self.chartist = TechnicalAgent()
        self.editor = EditorAgent()

    def run_analysis_pipeline(self, ticker: str, progress_callback=None):
        """
        Executes the full 7-Agent workflow for a given ticker.
        """
        
        def update_status(msg):
            if progress_callback:
                progress_callback(msg)
            else:
                print(f"🔄 {msg}")

        # Phase 1: Research (Parallelizable in theory, sequential for simplicity here to avoid rate limits)
        update_status("🕵️ Research Agent: Digging into Annual Reports...")
        research_data = self.researcher.run(ticker)
        
        update_status("📰 Market Scout: Scanning News & Sentiment...")
        market_data = self.scout.run(ticker)
        
        # Phase 2: Analysis (The Debate)
        update_status("📈 Financial Agent: Calculating ROE & Valuation...")
        quant_verdict = self.quant.run(ticker, research_data)
        
        update_status("🐂 Bull Agent: Arguments for Buying...")
        bull_case = self.bull.run(ticker, research_data)
        
        update_status("🐻 Bear Agent: Arguments for Selling...")
        bear_case = self.bear.run(ticker, research_data)
        
        update_status("📉 Technical Analyst: Examining Price Action...")
        technical_outlook = self.chartist.run(ticker)
        
        # Phase 3: Synthesis (The Verdict)
        update_status("⚖️ Editor Agent: Drafting Final Report...")
        final_report = self.editor.run(
            ticker, 
            research_data, 
            market_data, 
            quant_verdict, 
            bull_case, 
            bear_case, 
            technical_outlook
        )
        
        update_status("✅ Analysis Complete!")
        return final_report
