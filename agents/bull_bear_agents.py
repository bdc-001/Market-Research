from .common import BaseAgent, setup_gemini

class FinancialAgent(BaseAgent):
    """
    The Quant: Strictly analyzes the numbers. ROE, Growth, Debt.
    """
    def __init__(self):
        super().__init__("The Quant", "Financial Physicist")

    def run(self, ticker: str, research_data: str) -> str:
        prompt = f"""
        Analyze the Financial Physics for {ticker} using this context:
        {research_data}
        
        **Task**: Calculate/Estimate the key 'Buffett-Dalio' metrics:
        
        1. **Compounders Test**: Sales Growth (3y/5y) vs Profit Growth.
        2. **Capital Efficiency**: ROE > 15%? ROCE > 20%?
        3. **Balance Sheet**: Debt/Equity < 0.5? Working Capital Cycle improving?
        
        **Output**: A strict verdict on Financial Health (Exceptional / Good / Weak).
        """
        response = self.model.generate_content(prompt)
        return response.text

class BullAgent(BaseAgent):
    """
    The Optimist: Focuses on Moat & Growth. Why buy this stock?
    """
    def __init__(self):
        super().__init__("The Bull", "Growth Investor")

    def run(self, ticker: str, research_data: str) -> str:
        prompt = f"""
        You are a Bullish Fund Manager pitching {ticker} to an Investment Committee.
        Use this data: {research_data}
        
        **Your Case**:
        1. **The Moat**: Why can't competitors kill this business? (Brand? Network Effect? Monopoly?)
        2. **Growth Runway**: What is the Next Big Trigger? (e.g., Defence orders, EV shift)
        3. **Management Quality**: Evidence of integrity & good capital allocation.
        
        **Output**: 3 Strong Reasons to BUY immediately. Be persuasive but factual.
        """
        response = self.model.generate_content(prompt)
        return response.text

class BearAgent(BaseAgent):
    """
    The Skeptic: Focuses on Risks & overvaluation. Why avoid this stock?
    """
    def __init__(self):
        super().__init__("The Bear", "Short Seller")

    def run(self, ticker: str, research_data: str) -> str:
        prompt = f"""
        You are a Forensic Auditor / Short Seller analyzing {ticker}.
        Use this data: {research_data}
        
        **Your Case**:
        1. **Red Flags**: Any auditor resignations? High promoter pledging? Related Party transactions?
        2. **Valuation Trap**: Is the P/E justified? Is growth slowing down?
        3. **Competition**: Is a big player (Reliance/Tata) entering to disrupt them?
        
        **Output**: 3 Strong Reasons to SELL or AVOID. Be critical and ruthless.
        """
        response = self.model.generate_content(prompt)
        return response.text
