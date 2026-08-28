"""
QuanTum Engine Orchestrator (v7) — Full Pipeline + Entry Timing + Alpha Management

Pipeline:
  Phase 0:  Memory restore + verification of past signals (learning loop)
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
  Phase 11: Weight learning + critic (writes back into the next run)
"""
import pandas as pd
import sqlite3
from datetime import datetime
import os
import uuid

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
from agents.quantum_learning import (
    SignalVerifier, WeightLearner, ensure_learning_tables,
)
from agents.quantum_critic import CriticAgent
from agents import memory
from agents.episode_store import (
    attach_verified_signal_log_outcomes,
    write_quantum_topn,
)
from agents.agent_trace import TraceLog, df_brief, news_brief

# Long-horizon universe size when the caller asks for a fast run.
FAST_UNIVERSE_SIZE = 30


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
        self.verifier = SignalVerifier()
        self.learner = WeightLearner()
        self.critic = CriticAgent()

    def run(
        self,
        tickers=None,
        run_backtest: bool = False,
        progress_callback=None,
        fast: bool = False,
        step_callback=None,
    ) -> dict:
        """
        Runs the full pipeline.

        fast=True trims the long-horizon universe so a phone-triggered run
        finishes in a few minutes. Weekly picks are unaffected because they come
        from the news scanner either way; annual and 5-year picks are drawn from
        a smaller universe and the report says so.
        """
        if tickers is None:
            tickers = list(dict.fromkeys(NIFTY_UNIVERSE))
        if fast:
            tickers = tickers[:FAST_UNIVERSE_SIZE]

        def update(msg):
            if progress_callback:
                progress_callback(msg)
            else:
                print(f"  {msg}")

        trace = TraceLog(
            "quantum",
            f"QuanTum · {'Fast' if fast else 'Full'}",
            on_event=step_callback,
        )

        # -- Phase 0: Learning memory ----------------------------------------
        # Restore rules first: a fresh container has an empty rules file but the
        # database still holds everything learned so far.
        ensure_learning_tables()
        restored = memory.restore_rules()
        if restored:
            update(f"Restored {restored} learned rules from memory")

        update("Phase 0 -- Verifying past signals...")
        trace.begin("verify")
        verification = self.verifier.run(progress_callback=update)
        try:
            attached = attach_verified_signal_log_outcomes()
            if attached:
                update(f"Copied {attached} existing signal outcomes onto episodes")
        except Exception:
            pass

        trace.add(
            step_id="verify",
            name="Signal verifier",
            kind="python",
            receives_from=["signal_log"],
            sends_to=["Weight learner (later)"],
            received="Unverified rows in signal_log whose window has elapsed",
            passed=str(verification),
            note="Does not change scores. Copies existing outcomes onto matching episodes.",
        )

        # -- Phase 1: Market Regime Detection --------------------------------
        update("Phase 1/10 -- Regime Detection...")
        trace.begin("regime")
        regime_data = self.regime_detector.detect(progress_callback=update)
        regime = regime_data["regime"]
        update(f"Regime: {regime}")
        trace.add(
            step_id="regime",
            name="Regime detector",
            kind="python",
            receives_from=["Nifty, VIX, breadth"],
            sends_to=["Factor scorer", "Portfolio"],
            received="Nifty 50, India VIX, large-cap breadth",
            passed=str({
                k: regime_data.get(k)
                for k in ("regime", "nifty", "vix", "signals")
            }),
        )

        # -- Phase 2: News Discovery (deep impact) --------------------------
        update("Phase 2/10 -- News Scanner (deep impact scoring)...")
        trace.begin("news")
        news_data, headlines = self.news_scanner.run(progress_callback=update)
        news_tickers = [item["symbol"] for item in news_data]
        update(f"Discovered {len(news_tickers)} tickers from {len(headlines)} headlines")
        trace.add(
            step_id="news",
            name="News scanner",
            kind="gemini",
            receives_from=["RSS headlines"],
            sends_to=["Data collector", "Factor scorer (week)"],
            received=f"{len(headlines)} headlines from ET / Moneycontrol / Mint / BS / NDTV",
            passed=news_brief(news_data),
            note="Gemini extracts tickers; Python measures price reaction.",
        )

        # -- Phase 3: Data Collection ----------------------------------------
        all_tickers = list(dict.fromkeys(news_tickers + tickers))
        update(f"Phase 3/10 -- Data Collector: {len(all_tickers)} stocks...")
        trace.begin("prices")
        df = self.data_agent.run(tickers=all_tickers, progress_callback=None)

        if df.empty:
            empty = TraceLog("quantum", "QuanTum (failed)").as_dict()
            return {"error": "Failed to fetch market data.", "trace": empty}

        update(f"Data collected for {len(df)} stocks")
        trace.add(
            step_id="prices",
            name="Data collector",
            kind="python",
            receives_from=["News tickers", "Nifty universe"],
            sends_to=["Flow", "Earnings", "Factor scorer"],
            received=f"{len(all_tickers)} symbols",
            passed=df_brief(df, ["ticker", "close", "rsi", "pe_ratio", "roe"], n=10),
        )

        weekly_set = set(news_tickers)
        df_weekly = df[df["ticker"].isin(weekly_set)].copy()
        df_longterm = df[df["ticker"].isin(set(tickers))].copy()

        if df_weekly.empty:
            update("Warning: no news tickers had valid data, using full universe for weekly")
            df_weekly = df.copy()
            news_data = []

        # -- Phase 4: Institutional Flow (REAL delivery % from NSE) ----------
        update("Phase 4/10 -- Institutional Flow Tracking (NSE delivery %)...")
        trace.begin("flow")
        flow_weekly = self.flow_tracker.compute_flow_scores(df_weekly, progress_callback=update)
        flow_longterm = self.flow_tracker.compute_flow_scores(df_longterm, progress_callback=update)
        trace.add(
            step_id="flow",
            name="Flow tracker",
            kind="python",
            receives_from=["Data collector", "NSE bhavcopy"],
            sends_to=["Factor scorer"],
            received=f"weekly {len(df_weekly)} names, long-term {len(df_longterm)} names",
            passed=df_brief(flow_weekly, n=8),
        )

        # -- Phase 5: Earnings Revisions (multi-source) ---------------------
        update("Phase 5/10 -- Earnings Revision Factor (yfinance + news)...")
        trace.begin("earnings")
        earnings_weekly = self.earnings_tracker.compute_scores(
            df_weekly, headlines=headlines, progress_callback=update
        )
        earnings_longterm = self.earnings_tracker.compute_scores(
            df_longterm, headlines=headlines, progress_callback=update
        )
        trace.add(
            step_id="earnings",
            name="Earnings revisions",
            kind="python",
            receives_from=["yfinance", "headlines"],
            sends_to=["Factor scorer"],
            received=f"{len(headlines)} headlines + price/fundamental frame",
            passed=df_brief(earnings_weekly, n=8),
        )

        # -- Phase 6: Factor Scoring (sector-relative, regime-adjusted) ------
        update("Phase 6/10 -- Factor Scoring (sector-relative, regime-adjusted)...")
        trace.begin("scores")

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
        trace.add(
            step_id="scores",
            name="Factor scorer",
            kind="python",
            receives_from=["Prices", "News", "Flow", "Earnings", "Regime weights"],
            sends_to=["Entry engine", "Portfolio"],
            received=f"week weights {week_weights}\nyear weights {year_weights}",
            passed=(
                "WEEK\n" + df_brief(week_scored) +
                "\n\nYEAR\n" + df_brief(year_scored) +
                "\n\n5Y\n" + df_brief(fiveyear_scored)
            ),
        )

        # -- Phase 7: Entry Timing Engine (execution alpha) -----------------
        update("Phase 7/10 -- Entry Timing Engine (execution alpha)...")
        trace.begin("entry")
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
        trace.add(
            step_id="entry",
            name="Entry engine",
            kind="python",
            receives_from=["Factor scorer"],
            sends_to=["Portfolio", "Report"],
            received="Scored names + OHLCV for pullback / volume / vol-compression / RSI",
            passed=(
                "WEEK\n" + df_brief(entry_week) +
                "\n\nYEAR\n" + df_brief(entry_year)
            ),
            note="entry_allowed when entry_score >= 70. Signal and entry are separate.",
        )

        # -- Phase 8: Portfolio Construction ----------------------------------
        update("Phase 8/10 -- Portfolio Construction...")
        trace.begin("portfolio")
        week_portfolio = self.portfolio.construct(week_scored, regime, top_n=7)
        year_portfolio = self.portfolio.construct(year_scored, regime, top_n=10)
        fiveyear_portfolio = self.portfolio.construct(fiveyear_scored, regime, top_n=10)
        trace.add(
            step_id="portfolio",
            name="Portfolio constructor",
            kind="python",
            receives_from=["Scored + entry", "Regime"],
            sends_to=["Report", "Performance"],
            received=f"regime={regime}; caps 20% stock / 30% sector",
            passed=(
                "WEEK\n" + df_brief(week_portfolio) +
                "\n\nYEAR\n" + df_brief(year_portfolio) +
                "\n\n5Y\n" + df_brief(fiveyear_portfolio)
            ),
        )

        # -- Phase 9: Alpha Management (decay + performance) -----------------
        update("Phase 9/10 -- Alpha Management (decay + exit + performance)...")
        trace.begin("decay")

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
        trace.add(
            step_id="decay",
            name="Alpha decay",
            kind="python",
            receives_from=["Prior active_positions", "Current scores"],
            sends_to=["Report"],
            received=str(decay_summary),
            passed=str(decay_results[:8]) if decay_results else "(none)",
        )

        # Log signals to signal_log for performance tracking and learning
        self._log_signals(week_scored, "week", regime)
        self._log_signals(year_scored, "year", regime)
        self._log_signals(fiveyear_scored, "5years", regime)

        try:
            run_id = str(uuid.uuid4())
            news_by_symbol = {
                item.get("symbol"): item for item in (news_data or []) if item.get("symbol")
            }
            write_quantum_topn(week_scored, "week", regime, run_id, news_by_symbol, week_portfolio)
            write_quantum_topn(year_scored, "year", regime, run_id, {}, year_portfolio)
            write_quantum_topn(fiveyear_scored, "5years", regime, run_id, {}, fiveyear_portfolio)
        except Exception:
            pass

        # Record portfolio snapshots for daily tracking
        self.performance.record_portfolio(week_portfolio, "week", progress_callback=update)
        self.performance.record_portfolio(year_portfolio, "year", progress_callback=update)
        self.performance.record_portfolio(fiveyear_portfolio, "5years", progress_callback=update)

        # Live performance
        perf_metrics = self.performance.compute_performance(progress_callback=update)

        # -- Phase 10: Report ------------------------------------------------
        update("Phase 10/10 -- Generating report...")
        trace.begin("report")

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
        trace.add(
            step_id="report",
            name="Synthesizer",
            kind="python",
            receives_from=["Scores", "Entry", "Portfolio", "Decay", "Regime"],
            sends_to=["UI markdown / PDF"],
            received="All prior stage outputs",
            passed=report[:2500],
        )

        # -- Phase 11: Learning ------------------------------------------------
        # Runs last so a failure here cannot cost the user their report.
        update("Phase 11 -- Learning from verified outcomes...")
        for horizon, weights in (("week", week_weights), ("year", year_weights),
                                 ("5years", fiveyear_weights)):
            try:
                self.learner.run(
                    self.regime_detector.base_weights(regime, horizon),
                    horizon, regime, progress_callback=update,
                )
            except Exception as exc:
                update(f"Weight learning skipped for {horizon}: {exc}")

        trace.begin("critic")
        critique = self.critic.run(
            week_picks=week_scored, verification=verification,
            regime=regime, progress_callback=update,
        )
        critic_text = ""
        if isinstance(critique, dict):
            critic_text = str(critique)
        elif critique:
            critic_text = str(critique)
        trace.add(
            step_id="critic",
            name="Critic",
            kind="gemini",
            receives_from=["Picks", "Verified outcomes", "Existing rules"],
            sends_to=["memory/learned_rules.md"],
            received=f"regime={regime} verification={verification}",
            passed=critic_text or "(no new rules)",
        )

        return {
            "report": report,
            "report_path": report_path,
            "verification": verification,
            "critique": critique,
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
            "trace": trace.as_dict(),
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

    def _log_signals(self, scored: pd.DataFrame, horizon: str, regime: str = ""):
        """
        Records the top picks with every factor score, which is what the weight
        learner later correlates against realised alpha.
        """
        try:
            ensure_learning_tables()
            conn = get_db()
            today = datetime.today().strftime("%Y-%m-%d")
            for _, row in scored.head(10).iterrows():
                conn.execute(
                    """INSERT OR REPLACE INTO signal_log
                       (date, ticker, horizon, composite_score,
                        value_rank, quality_rank, momentum_rank,
                        technical_rank, volatility_rank,
                        sector_growth_rank, news_catalyst_rank,
                        flow_rank, earnings_rev_rank, regime,
                        factor_agreement, conviction, close_at_signal)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (today, row["ticker"], horizon, row["composite_score"],
                     row["value_score"], row["quality_score"],
                     row["momentum_score"], row["technical_score"],
                     row["volatility_score"],
                     row.get("sector_growth_score"), row.get("news_catalyst_score"),
                     row.get("flow_score"), row.get("earnings_rev_score"), regime,
                     int(row["factor_agreement"]),
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
