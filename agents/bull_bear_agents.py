from .common import BaseAgent


class FinancialAgent(BaseAgent):
    """The Quant: scores supplied financial evidence. Does not fetch data."""

    def __init__(self):
        super().__init__("The Quant", "Financial Physicist")

    def run(self, ticker: str, evidence_text: str = "") -> str:
        prompt = f"""
Analyze the Financial Physics for {ticker} using ONLY this evidence package.
Cite evidence IDs. Never invent a metric. If ROE/ROCE/debt is missing, say null.

{evidence_text}

Task — Buffett-Dalio tests using supplied numbers only:
1. Compounders: sales vs profit growth (use annual/quarterly revenue and net income IDs).
2. Capital efficiency: ROE > 15%? (ROCE if an ID exists; otherwise null).
3. Balance sheet: Debt/Equity, FCF, cash vs debt.

Output: Financial Health = Exceptional / Good / Weak / Insufficient, with IDs.
"""
        return self.complete(prompt)


_DEBATE_CONTRACT = """
You and your counterpart receive THE SAME evidence package.
Disagreement must be interpretation of the same IDs, not missing-data philosophy.
For each of your 3 points use this shape:
- Claim:
- Evidence IDs:
- Interpretation:
- Assumption:
- Risk:
In the JSON appendix, put those IDs in evidence_ids.
Do not argue from training-data "structural moat" unless an ID supports it.
"""


class BullAgent(BaseAgent):
    def __init__(self):
        super().__init__("The Bull", "Growth Investor")

    def run(self, ticker: str, evidence_text: str = "") -> str:
        prompt = f"""
You are a bullish fund manager pitching {ticker}.
{_DEBATE_CONTRACT}

{evidence_text}

Output: 3 reasons to BUY, each tied to evidence IDs.
"""
        return self.complete(prompt)


class BearAgent(BaseAgent):
    def __init__(self):
        super().__init__("The Bear", "Short Seller")

    def run(self, ticker: str, evidence_text: str = "") -> str:
        prompt = f"""
You are a forensic auditor / short seller analyzing {ticker}.
{_DEBATE_CONTRACT}

{evidence_text}

Output: 3 reasons to AVOID, each tied to the SAME evidence IDs the bull sees.
If valuation IDs exist, use them. Do not treat "package exists" as a red flag
by itself.
"""
        return self.complete(prompt)
