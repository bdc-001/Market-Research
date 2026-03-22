from .common import BaseAgent, setup_gemini

class EditorAgent(BaseAgent):
    """
    The Judge: Synthesizes all agent inputs into the Final Reliable Report.
    """
    def __init__(self):
        super().__init__("The Editor", "Portfolio Manager")

    def run(self, ticker: str, research_data: str, market_data: str, quant_verdict: str, bull_case: str, bear_case: str, technical_outlook: str) -> str:
        prompt = f"""
        **Role**: You are a Partner at a top-tier Investment Firm (Buffett-Dalio Strategy).
        **Objective**: Synthesize a definitive Investment Memo for **{ticker}**.
        
        **Inputs from your Analyst Team**:
        
        1. **Research (Historian)**: {research_data}
        2. **Market News (News Hound)**: {market_data}
        3. **Financials (Quant)**: {quant_verdict}
        4. **Bull Case (Optimist)**: {bull_case}
        5. **Bear Case (Skeptic)**: {bear_case}
        6. **Technical Analysis (Chartist)**: {technical_outlook}
        
        **Output Task**: Write a professional Markdown report structured EXACTLY as follows:
        
        # Investment Analysis: {ticker}
        
        ## 1. Executive Summary
        - **Verdict**: (Strong Buy / Accumulate / Hold / Avoid)
        - **Target Horizon**: (1-3 Years)
        - **The Bottom Line**: A comprehensive 3-4 sentence summary of why this is a Compounder or a Trap.
        
        ## 2. Business & Moat Analysis
        - **Revenue Engine**: Detailed breakdown of revenue streams with percentages
        - **The Moat**: Is it durable? What makes it defensible? (Provide specific evidence)
        - **Business Model**: How exactly do they make money?
        
        ## 3. Financial Health (The Physics)
        - **Quality Score**: Comprehensive assessment with supporting metrics
        - **Key Metrics**: 
          - ROE trends (5-year analysis)
          - Operating margins vs. industry average
          - Debt/Equity ratio and interest coverage
          - Working capital efficiency
        - **Cash Flow Analysis**: FCF trends and conversion rates
        
        ## 4. Management Quality
        - **Skin in the Game**: Promoter holding percentage and recent changes
        - **Capital Allocation**: 
          - Dividend policy and payout ratios
          - Past acquisitions (good or bad?)
          - Share buyback history
        - **Track Record**: Evidence of integrity and execution
        
        ## 5. The Bull Case (Pros)
        {bull_case}
        **Additional Analysis**: Expand on each point with data and examples
        
        ## 6. The Bear Case (Cons)
        {bear_case}
        **Risk Mitigation**: How serious are these risks? Can they be managed?
        
        ## 7. Sector Tailwinds vs Headwinds
        - **Industry Growth**: Detailed sector CAGR and drivers
        - **Government Policies**: Impact of PLI, subsidies, regulations
        - **Competitive Landscape**: Market share dynamics
        
        ## 8. Technical Entry Strategy
        - **Trend Analysis**: {technical_outlook}
        - **Actionable Advice**: Specific price levels for entry/exit
        - **Risk/Reward**: Expected move vs. downside protection
        
        ## 9. Final Valuation & Conclusion
        - **Current Valuation**: P/E, P/B, EV/EBITDA vs. historical averages
        - **Intrinsic Value Estimate**: DCF or similar method summary
        - **Buffett-Dalio Score**: Assign a score out of 100 based on:
          - Quality (40 points): ROE, Moat, Management
          - Valuation (30 points): Price vs. Intrinsic Value
          - Growth (30 points): Revenue/Profit trajectory
        - **Final Word**: Comprehensive 4-5 sentence closing argument
        
        ## 10. Financial Terms Glossary
        Define ALL complex financial terms used in this report (at least 15-20 terms):
        - **ROE (Return on Equity)**: [Clear explanation]
        - **ROCE (Return on Capital Employed)**: [Clear explanation]
        - **P/E Ratio**: [Clear explanation]
        - **EV/EBITDA**: [Clear explanation]
        - **Free Cash Flow (FCF)**: [Clear explanation]
        - **Moat**: [Clear explanation]
        - **CAPE Ratio**: [Clear explanation]
        - **DCF (Discounted Cash Flow)**: [Clear explanation]
        (Include all other terms used)
        
        **CRITICAL REQUIREMENTS**:
        - Minimum 2500 words (excluding glossary)
        - Be exhaustively detailed - include specific numbers, dates, and examples
        - Avoid generic statements - cite actual data points
        - Analyze trends over 3-5 year periods
        - The glossary must define EVERY technical term used
        """
        
        return self.model.generate_content(prompt).text
