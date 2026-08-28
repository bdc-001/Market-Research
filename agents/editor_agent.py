from .common import BaseAgent
from .editor_canonical import enforce


class EditorAgent(BaseAgent):
    """
    The Judge: synthesizes specialist views into a memo.
    Structured JSON is canonical. Python then forces the Verdict line
    to match final_decision so the UI and the episode store cannot diverge.
    """

    def __init__(self):
        super().__init__("The Editor", "Portfolio Manager")

    def run(
        self,
        ticker: str,
        research_data: str,
        market_data: str,
        quant_verdict: str,
        bull_case: str,
        bear_case: str,
        technical_outlook: str,
        evidence_index: str = "",
    ) -> str:
        prompt = f"""
Role: Partner synthesizing a memo for {ticker}.
You will output a markdown memo AND a JSON prediction appendix.

The JSON final_decision is the only allowed verdict. The Executive Summary
**Verdict** line MUST be exactly one of: Buy / Watch / Avoid / Hold
matching that JSON field. Do not write "Avoid (Watchlist)" if the JSON is watch.
Do not invent numbers that are not in the inputs. Cite evidence IDs when present.

Two separate, non-interchangeable calls (report both, never merge them):
- 30-DAY SIGNAL: prediction_direction (positive/negative/flat) over horizon_days=30.
  This is a short-term price call. It is NOT the Verdict.
- 1-3Y INVESTMENT STANCE: final_decision + investment_horizon="1-3y".
  This is the long-term thesis that drives **Verdict**.

Use ONLY the canonical latest_close from the evidence header as the as-of price.
Never mix in a second vendor quote.

Evidence index (facts already gathered in Python):
{evidence_index}

Analyst inputs:
1. Historian: {research_data}
2. Scout: {market_data}
3. Quant: {quant_verdict}
4. Bull: {bull_case}
5. Bear: {bear_case}
6. Chartist: {technical_outlook}

Write the memo as:

# Investment Analysis: {ticker}

## 1. Executive Summary
- **Verdict**: Buy | Watch | Avoid | Hold
- **Investment Horizon**: 1-3 Years
- **30-Day Signal**: Positive | Negative | Flat (short-term, separate from the verdict)
- **The Bottom Line**: 3-4 sentences. Compounder vs trap, with IDs/numbers.

## 2. Business & Moat Analysis
## 3. Financial Health (The Physics)
## 4. Management Quality
## 5. The Bull Case (Pros)
## 6. The Bear Case (Cons)
## 7. Sector Tailwinds vs Headwinds
## 8. Technical Entry Strategy
## 9. Final Valuation & Conclusion
Include a Buffett-Dalio score out of 100 only from supplied metrics; else null.
## 10. Financial Terms Glossary
Define terms you actually used.

Keep the memo detailed but do not pad. Phone-readable. Not investment advice.
"""
        self.complete(prompt)
        memo, canonical, _ = enforce(self.last_prose, self.last_parsed)
        self.last_prose = memo
        self.last_parsed = canonical
        return memo
