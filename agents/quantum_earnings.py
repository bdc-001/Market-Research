"""
QuanTum Earnings Revision Factor (v3) — Multi-Source Revision Engine

Sources:
  1. yfinance earnings_estimate: forward EPS estimates, growth rates
  2. yfinance get_earnings_dates: historical EPS surprise data
  3. yfinance revenue_estimate: revenue growth expectations
  4. Gemini news extraction: earnings surprise from headlines

Score components:
  1. Revision momentum: current vs year-ago EPS estimate growth (30%)
  2. Earnings surprise track record: avg surprise % last 4 quarters (25%)
  3. Earnings acceleration: improvement in growth rate (15%)
  4. Revenue growth quality: (10%)
  5. Analyst consensus: strong buy ratio (10%)
  6. News-sourced earnings surprise (10%)

SQLite table: earnings_revision (ticker, date, revision_score, surprise_score, final_score)

Weight in model: 15-25% depending on regime.
"""
import re
import json
import sqlite3
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
from agents.common import setup_gemini

import logging
logger = logging.getLogger(__name__)


def _pct_rank(series: pd.Series) -> pd.Series:
    return series.rank(pct=True, na_option="keep")


EARNINGS_EXTRACTION_PROMPT = """\
You are analyzing Indian stock market headlines to extract earnings-related data.

**Headlines:**
{headlines}

**Task:** For each stock with earnings/results/guidance mentioned, extract:
- symbol: NSE ticker
- earnings_surprise_pct: beat/miss magnitude (positive = beat, negative = miss, 0 if unclear)
- revenue_surprise_pct: revenue beat/miss (0 if unclear)
- guidance_change: "upgrade" | "downgrade" | "maintained" | "none"
- is_earnings_related: true if this headline is about earnings/results/guidance

Output ONLY valid JSON (no fences):
{{"stocks": [
  {{"symbol": "RELIANCE", "earnings_surprise_pct": 8.0, "revenue_surprise_pct": 3.5,
    "guidance_change": "upgrade", "is_earnings_related": true}}
]}}

Rules:
- Only include stocks with actual earnings/results/financial data mentions
- Use 0 for unclear surprise magnitudes, don't fabricate numbers
"""


class EarningsRevisionTracker:
    """
    Multi-source earnings revision scoring with:
    - yfinance estimates (forward EPS, surprise history, revenue)
    - Gemini news extraction for recent earnings events
    - SQLite persistence for revision tracking
    """

    def __init__(self, db_path: str = "quantum_data.db"):
        self.db_path = db_path
        self._gemini_model = None
        self._news_earnings: dict[str, dict] = {}
        self._ensure_table()

    def _ensure_table(self):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("""CREATE TABLE IF NOT EXISTS earnings_revision (
                ticker TEXT,
                date TEXT,
                revision_score REAL,
                surprise_score REAL,
                final_score REAL,
                eps_estimate REAL,
                eps_growth REAL,
                avg_surprise REAL,
                PRIMARY KEY (ticker, date)
            )""")
            conn.commit()
            conn.close()
        except Exception:
            pass

    def _get_gemini(self):
        if self._gemini_model is None:
            self._gemini_model = setup_gemini()
        return self._gemini_model

    def extract_earnings_from_news(
        self, headlines: list[dict], progress_callback=None,
    ) -> dict[str, dict]:
        if not headlines:
            return {}

        earnings_headlines = []
        earnings_keywords = [
            "result", "earnings", "profit", "revenue", "quarter", "Q1", "Q2",
            "Q3", "Q4", "PAT", "EBITDA", "guidance", "outlook", "beat", "miss",
            "net income", "operating", "margin", "EPS", "growth", "YoY",
        ]

        for h in headlines:
            text = (h.get("title", "") + " " + h.get("summary", "")).lower()
            if any(kw.lower() in text for kw in earnings_keywords):
                earnings_headlines.append(h)

        if not earnings_headlines:
            return {}

        if progress_callback:
            progress_callback(f"Extracting earnings data from {len(earnings_headlines)} headlines...")

        headline_text = "\n".join([
            f"- [{h['source']}] {h['title']}" +
            (f" -- {h.get('summary', '')[:120]}" if h.get("summary") else "")
            for h in earnings_headlines[:40]
        ])

        try:
            model = self._get_gemini()
            resp = model.generate_content(
                EARNINGS_EXTRACTION_PROMPT.format(headlines=headline_text)
            ).text.strip()
            resp = re.sub(r"```json|```", "", resp).strip()
            data = json.loads(resp)

            result = {}
            for s in data.get("stocks", []):
                sym = s.get("symbol", "").upper().strip()
                if sym and s.get("is_earnings_related"):
                    result[sym] = {
                        "earnings_surprise_pct": float(s.get("earnings_surprise_pct", 0)),
                        "revenue_surprise_pct": float(s.get("revenue_surprise_pct", 0)),
                        "guidance_change": s.get("guidance_change", "none"),
                    }

            if progress_callback:
                progress_callback(f"Found earnings data for {len(result)} stocks from news")
            return result

        except Exception as e:
            if progress_callback:
                progress_callback(f"Earnings extraction warning: {e}")
            return {}

    def compute_scores(
        self, df: pd.DataFrame, headlines: list[dict] | None = None,
        progress_callback=None,
    ) -> pd.Series:
        if progress_callback:
            progress_callback("Computing earnings revision signals (multi-source)...")

        # Extract earnings data from news if headlines provided
        if headlines and not self._news_earnings:
            self._news_earnings = self.extract_earnings_from_news(
                headlines, progress_callback=progress_callback
            )

        results = {}
        for _, row in df.iterrows():
            ticker = row["ticker"]
            news_data = self._news_earnings.get(ticker)
            score = self._score_single(ticker, row, news_data)
            results[ticker] = score

            # Persist to SQLite
            self._persist_score(ticker, score)

        raw = df["ticker"].map(results).fillna(50.0)
        return _pct_rank(raw).fillna(0.5) * 100

    def _score_single(
        self, ticker: str, row: pd.Series, news_data: dict | None = None,
    ) -> float:
        try:
            sym = f"{ticker}.NS"
            tk = yf.Ticker(sym)
            info = tk.info

            # ── 1. Revision Momentum (30%) ─────────────────────────────────
            # From earnings_estimate: compare current EPS growth vs expectations
            revision_score = 50.0
            eps_growth = None
            try:
                ee = tk.earnings_estimate
                if ee is not None and not ee.empty:
                    # Current year estimate growth
                    cy = ee.loc["0y"] if "0y" in ee.index else None
                    ny = ee.loc["+1y"] if "+1y" in ee.index else None

                    if cy is not None:
                        growth_0y = cy.get("growth")
                        if growth_0y is not None and not pd.isna(growth_0y):
                            eps_growth = growth_0y * 100
                            if eps_growth > 20:
                                revision_score = 100
                            elif eps_growth > 10:
                                revision_score = 80
                            elif eps_growth > 5:
                                revision_score = 65
                            elif eps_growth > 0:
                                revision_score = 50
                            elif eps_growth > -5:
                                revision_score = 35
                            else:
                                revision_score = 15

                    # Bonus: next year accelerating vs current year
                    if cy is not None and ny is not None:
                        g0 = cy.get("growth", 0) or 0
                        g1 = ny.get("growth", 0) or 0
                        if g1 > g0 and g1 > 0:
                            revision_score = min(100, revision_score + 10)
            except Exception:
                pass

            # ── 2. Earnings Surprise Track Record (25%) ────────────────────
            surprise_score = 50.0
            avg_surprise = None
            try:
                ed = tk.get_earnings_dates(limit=8)
                if ed is not None and not ed.empty:
                    surprises = ed["Surprise(%)"].dropna()
                    if len(surprises) >= 2:
                        # Last 4 quarters average surprise
                        recent = surprises.head(4)
                        avg_surprise = float(recent.mean())
                        positive_ratio = float((recent > 0).sum() / len(recent))

                        # Score based on consistency + magnitude
                        if avg_surprise > 10 and positive_ratio >= 0.75:
                            surprise_score = 100
                        elif avg_surprise > 5 and positive_ratio >= 0.5:
                            surprise_score = 85
                        elif avg_surprise > 0 and positive_ratio >= 0.5:
                            surprise_score = 70
                        elif avg_surprise > -5:
                            surprise_score = 45
                        else:
                            surprise_score = 20
            except Exception:
                pass

            # ── 3. Earnings Acceleration (15%) ─────────────────────────────
            accel_score = 50.0
            try:
                # Use income statement for historical earnings acceleration
                earnings_g = info.get("earningsGrowth")
                revenue_g = info.get("revenueGrowth")
                if earnings_g is not None:
                    eg_pct = earnings_g * 100
                    if eg_pct > 30:
                        accel_score = 100
                    elif eg_pct > 20:
                        accel_score = 85
                    elif eg_pct > 10:
                        accel_score = 70
                    elif eg_pct > 0:
                        accel_score = 55
                    elif eg_pct > -10:
                        accel_score = 35
                    else:
                        accel_score = 15
            except Exception:
                pass

            # ── 4. Revenue Growth Quality (10%) ────────────────────────────
            rg_score = 50.0
            try:
                re_est = tk.revenue_estimate
                if re_est is not None and not re_est.empty:
                    cy = re_est.loc["0y"] if "0y" in re_est.index else None
                    if cy is not None:
                        rg = cy.get("growth")
                        if rg is not None and not pd.isna(rg):
                            rg_pct = rg * 100
                            if rg_pct > 25:
                                rg_score = 100
                            elif rg_pct > 15:
                                rg_score = 80
                            elif rg_pct > 5:
                                rg_score = 60
                            elif rg_pct > 0:
                                rg_score = 45
                            else:
                                rg_score = 25
                else:
                    # Fallback to info
                    revenue_growth = info.get("revenueGrowth")
                    if revenue_growth is not None:
                        rg_pct = revenue_growth * 100
                        if rg_pct > 25:
                            rg_score = 100
                        elif rg_pct > 15:
                            rg_score = 80
                        elif rg_pct > 5:
                            rg_score = 60
                        elif rg_pct > 0:
                            rg_score = 45
                        else:
                            rg_score = 25
            except Exception:
                pass

            # ── 5. Analyst Consensus (10%) ─────────────────────────────────
            consensus_score = 50.0
            try:
                rec = tk.recommendations
                if rec is not None and not rec.empty:
                    latest = rec.iloc[0]
                    total = (latest.get("strongBuy", 0) + latest.get("buy", 0) +
                             latest.get("hold", 0) + latest.get("sell", 0) +
                             latest.get("strongSell", 0))
                    if total > 0:
                        buy_ratio = (latest.get("strongBuy", 0) + latest.get("buy", 0)) / total
                        if buy_ratio > 0.80:
                            consensus_score = 100
                        elif buy_ratio > 0.65:
                            consensus_score = 80
                        elif buy_ratio > 0.50:
                            consensus_score = 60
                        elif buy_ratio > 0.35:
                            consensus_score = 40
                        else:
                            consensus_score = 20
            except Exception:
                pass

            # ── 6. News-Sourced Earnings Surprise (10%) ────────────────────
            news_score = 50.0
            if news_data:
                eps_surprise = news_data.get("earnings_surprise_pct", 0)
                guidance = news_data.get("guidance_change", "none")

                if eps_surprise > 10:
                    news_score = 100
                elif eps_surprise > 5:
                    news_score = 80
                elif eps_surprise > 0:
                    news_score = 65
                elif eps_surprise > -5:
                    news_score = 40
                else:
                    news_score = 15

                if guidance == "upgrade":
                    news_score = min(100, news_score + 15)
                elif guidance == "downgrade":
                    news_score = max(0, news_score - 15)

            # ── Composite ──────────────────────────────────────────────────
            composite = (0.30 * revision_score +
                         0.25 * surprise_score +
                         0.15 * accel_score +
                         0.10 * rg_score +
                         0.10 * consensus_score +
                         0.10 * news_score)

            return max(0, min(100, composite))

        except Exception:
            return 50.0

    def _persist_score(self, ticker: str, score: float):
        try:
            conn = sqlite3.connect(self.db_path)
            today = datetime.today().strftime("%Y-%m-%d")
            conn.execute(
                """INSERT OR REPLACE INTO earnings_revision
                   (ticker, date, final_score)
                   VALUES (?, ?, ?)""",
                (ticker, today, score),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    def get_earnings_detail(self, ticker: str) -> dict:
        try:
            sym = f"{ticker}.NS"
            tk = yf.Ticker(sym)
            info = tk.info
            result = {
                "forward_pe": info.get("forwardPE"),
                "trailing_pe": info.get("trailingPE"),
                "earnings_growth": info.get("earningsGrowth"),
                "revenue_growth": info.get("revenueGrowth"),
                "target_mean": info.get("targetMeanPrice"),
                "target_high": info.get("targetHighPrice"),
                "recommendation": info.get("recommendationMean"),
                "num_analysts": info.get("numberOfAnalystOpinions"),
            }

            # Add surprise history
            try:
                ed = tk.get_earnings_dates(limit=4)
                if ed is not None and not ed.empty:
                    surprises = ed["Surprise(%)"].dropna()
                    if len(surprises) > 0:
                        result["avg_surprise_4q"] = round(float(surprises.mean()), 1)
                        result["latest_surprise"] = round(float(surprises.iloc[0]), 1)
            except Exception:
                pass

            # Add estimate growth
            try:
                ee = tk.earnings_estimate
                if ee is not None and "0y" in ee.index:
                    result["eps_growth_0y"] = ee.loc["0y"].get("growth")
            except Exception:
                pass

            # Add news data if available
            news = self._news_earnings.get(ticker)
            if news:
                result["news_earnings_surprise"] = news.get("earnings_surprise_pct")
                result["news_guidance"] = news.get("guidance_change")

            return result
        except Exception:
            return {}
