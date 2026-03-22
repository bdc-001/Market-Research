"""
QuanTum Engine Orchestrator (v7) — Full Pipeline + Entry Timing + Alpha Management

Pipeline:
  Phase 1:  Market Regime Detection (BULL/BEAR/SIDEWAYS -> dynamic weights)
  Phase 2:  News Scanner (deep impact: sentiment + surprise + event + reaction)
  Phase 3:  Data Collection (price, technicals, fundamentals)
  Phase 4:  Institutional Flow Tracking (REAL delivery % from NSE + OBV)
  Phase 5:  Earnings Revision Factor (yfinance + Gemini-extracted from news)
  Phase 6:  Factor Scoring (9 factors, sector-relative momentum, regime-adjusted)
  Phase 7:  Entry Timing Engine (pullback, volume, vol-compression, RSI stability)
  Phase 8:  Portfolio Construction (risk-adjusted sizing, sector caps)
  Phase 9:  Alpha Management (decay tracking, exit signals, live performance)
  Phase 10: Report Generation + PDF
"""
import pandas as pd
import sqlite3
from datetime import datetime
import os

from agents.quantum_regime import RegimeDetector
from agents.quantum_news_scanner import NewsScanner
from agents.quantum_data_collector import DataCollectorAgent, NIFTY_UNIVERSE, get_db
from agents.quantum_flow import FlowTracker
from agents.quantum_earnings import EarningsRevisionTracker
from agents.quantum_scorer import FactorScorer
from agents.quantum_portfolio import PortfolioConstructor
from agents.quantum_entry_engine import EntryTimingEngine
from agents.quantum_decay import AlphaDecayModel
from agents.quantum_performance import PerformanceTracker
from agents.quantum_synthesizer import QuantumSynthesizer


class QuantumEngineOrchestrator:

    def __init__(self):
        self.regime_detector = RegimeDetector()
        self.news_scanner = NewsScanner()
        self.data_agent = DataCollectorAgent()
        self.flow_tracker = FlowTracker()
        self.earnings_tracker = EarningsRevisionTracker()
        self.scorer = FactorScorer()
        self.entry_engine = EntryTimingEngine()
        self.portfolio = PortfolioConstructor()
        self.decay_model = AlphaDecayModel()
        self.performance = PerformanceTracker()
        self.synthesizer = QuantumSynthesizer()

    def run(
        self,
        tickers=None,
        run_backtest: bool = False,
        progress_callback=None,
    ) -> dict:
        if tickers is None:
            tickers = list(dict.fromkeys(NIFTY_UNIVERSE))

        def update(msg):
            if progress_callback:
                progress_callback(msg)
            else:
                print(f"  {msg}")

        # -- Phase 1: Market Regime Detection --------------------------------
        update("Phase 1/10 -- Regime Detection...")
        regime_data = self.regime_detector.detect(progress_callback=update)
        regime = regime_data["regime"]
        update(f"Regime: {regime}")

        # -- Phase 2: News Discovery (deep impact) --------------------------
        update("Phase 2/10 -- News Scanner (deep impact scoring)...")
        news_data, headlines = self.news_scanner.run(progress_callback=update)
        news_tickers = [item["symbol"] for item in news_data]
        update(f"Discovered {len(news_tickers)} tickers from {len(headlines)} headlines")

        # -- Phase 3: Data Collection ----------------------------------------
        all_tickers = list(dict.fromkeys(news_tickers + tickers))
        update(f"Phase 3/10 -- Data Collector: {len(all_tickers)} stocks...")
        df = self.data_agent.run(tickers=all_tickers, progress_callback=None)

        if df.empty:
            return {"error": "Failed to fetch market data."}

        update(f"Data collected for {len(df)} stocks")

        weekly_set = set(news_tickers)
        df_weekly = df[df["ticker"].isin(weekly_set)].copy()
        df_longterm = df[df["ticker"].isin(set(tickers))].copy()

        if df_weekly.empty:
            update("Warning: no news tickers had valid data, using full universe for weekly")
            df_weekly = df.copy()
            news_data = []

        # -- Phase 4: Institutional Flow (REAL delivery % from NSE) ----------
        update("Phase 4/10 -- Institutional Flow Tracking (NSE delivery %)...")
        flow_weekly = self.flow_tracker.compute_flow_scores(df_weekly, progress_callback=update)
        flow_longterm = self.flow_tracker.compute_flow_scores(df_longterm, progress_callback=update)

        # -- Phase 5: Earnings Revisions (multi-source) ---------------------
        update("Phase 5/10 -- Earnings Revision Factor (yfinance + news)...")
        earnings_weekly = self.earnings_tracker.compute_scores(
            df_weekly, headlines=headlines, progress_callback=update
        )
        earnings_longterm = self.earnings_tracker.compute_scores(
            df_longterm, headlines=headlines, progress_callback=update
        )

        # -- Phase 6: Factor Scoring (sector-relative, regime-adjusted) ------
        update("Phase 6/10 -- Factor Scoring (sector-relative, regime-adjusted)...")

        week_weights = self.regime_detector.get_weights(regime, "week")
        year_weights = self.regime_detector.get_weights(regime, "year")
        fiveyear_weights = self.regime_detector.get_weights(regime, "5years")

        week_scored = self.scorer.score(
            df_weekly, "week", news_data=news_data,
            flow_scores=flow_weekly, earnings_scores=earnings_weekly,
            weights=week_weights,
        )
        year_scored = self.scorer.score(
            df_longterm, "year",
            flow_scores=flow_longterm, earnings_scores=earnings_longterm,
            weights=year_weights,
        )
        fiveyear_scored = self.scorer.score(
            df_longterm, "5years",
            flow_scores=flow_longterm, earnings_scores=earnings_longterm,
            weights=fiveyear_weights,
        )

        self._log_top(update, week_scored, year_scored, fiveyear_scored)

        # -- Phase 7: Entry Timing Engine (execution alpha) -----------------
        update("Phase 7/10 -- Entry Timing Engine (execution alpha)...")
        entry_week = self.entry_engine.evaluate_entries(
            week_scored, horizon="week", progress_callback=update
        )
        entry_year = self.entry_engine.evaluate_entries(
            year_scored, horizon="year", progress_callback=update
        )
        entry_fiveyear = self.entry_engine.evaluate_entries(
            fiveyear_scored, horizon="5years", progress_callback=update
        )

        # Merge entry data into scored DataFrames
        week_scored = self._merge_entry(week_scored, entry_week)
        year_scored = self._merge_entry(year_scored, entry_year)
        fiveyear_scored = self._merge_entry(fiveyear_scored, entry_fiveyear)

        # -- Phase 8: Portfolio Construction ----------------------------------
        update("Phase 8/10 -- Portfolio Construction...")
        week_portfolio = self.portfolio.construct(week_scored, regime, top_n=7)
        year_portfolio = self.portfolio.construct(year_scored, regime, top_n=10)
        fiveyear_portfolio = self.portfolio.construct(fiveyear_scored, regime, top_n=10)

        # -- Phase 9: Alpha Management (decay + performance) -----------------
        update("Phase 9/10 -- Alpha Management (decay + exit + performance)...")

        self.decay_model.register_signals(week_scored, "week", top_n=7)
        self.decay_model.register_signals(year_scored, "year", top_n=10)
        self.decay_model.register_signals(fiveyear_scored, "5years", top_n=10)

        # Build current scores map for score-drop detection
        current_scores = {}
        for scored_df in [week_scored, year_scored, fiveyear_scored]:
            for _, row in scored_df.iterrows():
                current_scores[row["ticker"]] = row["composite_score"]

        decay_results = self.decay_model.compute_decay(
            current_scores=current_scores, progress_callback=update,
        )
        decay_summary = self.decay_model.get_active_summary()

        exit_count = sum(1 for d in decay_results if d["should_exit"])
        if exit_count > 0:
            update(f"Exit signals triggered for {exit_count} positions")
        update(f"Active positions: {decay_summary['active_positions']}")

        # Log signals to signal_log for performance tracking
        self._log_signals(week_scored, "week")
        self._log_signals(year_scored, "year")
        self._log_signals(fiveyear_scored, "5years")

        # Record portfolio snapshots for daily tracking
        self.performance.record_portfolio(week_portfolio, "week", progress_callback=update)
        self.performance.record_portfolio(year_portfolio, "year", progress_callback=update)
        self.performance.record_portfolio(fiveyear_portfolio, "5years", progress_callback=update)

        # Live performance
        perf_metrics = self.performance.compute_performance(progress_callback=update)

        # -- Phase 10: Report ------------------------------------------------
        update("Phase 10/10 -- Generating report...")

        signal_accuracy = self._check_past_accuracy()

        report = self.synthesizer.generate_report(
            week_scored=week_scored,
            year_scored=year_scored,
            fiveyear_scored=fiveyear_scored,
            regime_data=regime_data,
            week_weights=week_weights,
            year_weights=year_weights,
            fiveyear_weights=fiveyear_weights,
            week_portfolio=week_portfolio,
            year_portfolio=year_portfolio,
            fiveyear_portfolio=fiveyear_portfolio,
            news_data=news_data,
            headlines=headlines,
            backtest_result=None,
            signal_accuracy=signal_accuracy,
            entry_week=entry_week,
            entry_year=entry_year,
            entry_fiveyear=entry_fiveyear,
            decay_results=decay_results,
            decay_summary=decay_summary,
            perf_metrics=perf_metrics,
        )

        os.makedirs("reports", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        report_path = f"reports/QuanTum_v7_{timestamp}.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)

        update(f"Report saved: {report_path}")

        return {
            "report": report,
            "report_path": report_path,
            "week_picks": week_scored.head(10),
            "year_picks": year_scored.head(10),
            "fiveyear_picks": fiveyear_scored.head(10),
            "week_portfolio": week_portfolio,
            "year_portfolio": year_portfolio,
            "fiveyear_portfolio": fiveyear_portfolio,
            "entry_week": entry_week,
            "entry_year": entry_year,
            "entry_fiveyear": entry_fiveyear,
            "regime": regime_data,
            "news_data": news_data,
            "decay_results": decay_results,
            "decay_summary": decay_summary,
            "perf_metrics": perf_metrics,
            "df": week_scored,
        }

    def _merge_entry(self, scored: pd.DataFrame, entry: pd.DataFrame) -> pd.DataFrame:
        """Merge entry timing columns into scored DataFrame."""
        if entry.empty:
            return scored
        merge_cols = ["ticker", "entry_score", "entry_allowed", "entry_status",
                      "pullback_score", "volume_score", "vol_compression_score", "rsi_score",
                      "pullback_note", "volume_note", "vol_compression_note", "rsi_note"]
        available = [c for c in merge_cols if c in entry.columns]
        return scored.merge(entry[available], on="ticker", how="left")

    def _log_top(self, update, week, year, fiveyear):
        parts = []
        for label, s in [("Week", week), ("Year", year), ("5Yr", fiveyear)]:
            if not s.empty:
                parts.append(f"{label}: {s.iloc[0]['ticker']} ({s.iloc[0]['composite_score']:.1f})")
        update("Scoring complete -- " + " | ".join(parts))

    def _log_signals(self, scored: pd.DataFrame, horizon: str):
        try:
            conn = get_db()
            today = datetime.today().strftime("%Y-%m-%d")
            for _, row in scored.head(10).iterrows():
                conn.execute(
                    """INSERT OR REPLACE INTO signal_log
                       (date, ticker, horizon, composite_score,
                        value_rank, quality_rank, momentum_rank,
                        technical_rank, volatility_rank,
                        factor_agreement, conviction, close_at_signal)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (today, row["ticker"], horizon, row["composite_score"],
                     row["value_score"], row["quality_score"],
                     row["momentum_score"], row["technical_score"],
                     row["volatility_score"], int(row["factor_agreement"]),
                     row["conviction"], row["close"]),
                )
            conn.commit()
            conn.close()
        except Exception:
            pass

    def _check_past_accuracy(self) -> dict | None:
        try:
            conn = get_db()
            agg = conn.execute(
                """SELECT COUNT(*), SUM(CASE WHEN alpha > 0 THEN 1 ELSE 0 END),
                          AVG(alpha), AVG(actual_return)
                   FROM signal_log WHERE verified = 1"""
            ).fetchone()
            conn.close()
            if agg and agg[0] > 0:
                return {
                    "Total Verified Signals": agg[0],
                    "Signals Beating Benchmark": agg[1],
                    "Hit Rate": agg[1] / agg[0],
                    "Average Alpha": agg[2] or 0,
                    "Average Return": agg[3] or 0,
                }
        except Exception:
            pass
        return None
