from .common import BaseAgent
from .technical_compute import compute_technical_snapshot, snapshot_is_valid


class TechnicalAgent(BaseAgent):
    """
    The Chartist: interprets a Python-computed technical snapshot.
    Never calculates indicators and never owns evidence IDs.
    """

    def __init__(self):
        super().__init__("Technical Analyst", "Chartist")

    def run(self, ticker: str, snapshot: dict | None = None, id_map: dict | None = None) -> str:
        snap = snapshot if snapshot is not None else compute_technical_snapshot(ticker)
        self.last_snapshot = snap
        if not snapshot_is_valid(snap):
            return self.record_failure(
                f"Technical snapshot invalid: {snap.get('error') or 'missing scalars'}"
            )

        labels = [
            "price", "sma20", "sma50", "sma200", "rsi", "macd", "macd_signal",
            "atr", "volume_vs_average", "high_52w", "low_52w",
            "support", "resistance", "trend", "cross",
        ]
        id_map = id_map or {}
        legend = "\n".join(
            f"- {label} → {id_map[label]}" if label in id_map else f"- {label}"
            for label in labels
        )

        prompt = f"""
Interpret these already-computed technical scalars for {ticker}.
Do not recalculate anything. Do not invent levels that are not listed.
Do not emit evidence_ids. Return evidence_labels using the names below.
Python maps those labels to IDs.

Canonical latest_close (the only price): {snap['price']}
SMA20: {snap['sma20']}
SMA50: {snap['sma50']}
SMA200: {snap.get('sma200')}
RSI(14): {snap.get('rsi')}
MACD: {snap.get('macd')}  signal: {snap.get('macd_signal')}
ATR: {snap.get('atr')}
Volume vs 20d average: {snap.get('volume_vs_average')}
52w high / low: {snap.get('high_52w')} / {snap.get('low_52w')}
Recent support / resistance: {snap.get('support')} / {snap.get('resistance')}
Trend: {snap.get('trend')}  MA cross: {snap.get('cross')}
Bars used: {snap.get('bars')}  as_of: {snap.get('as_of')}

Allowed evidence_labels:
{legend}

Task: 30-day entry strategy from these scalars only.
- Buy zone, hold/breakout, or sell area?
- Which listed support/resistance levels matter?
"""
        return self.complete(prompt)
