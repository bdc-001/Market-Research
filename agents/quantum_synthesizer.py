"""
QuanTum Synthesizer (v7) — Full Pipeline Report Generator

Sections:
  1. Market Regime (BULL/BEAR/SIDEWAYS with signals)
  2. Methodology (9 factors + entry timing, regime-adjusted weights)
  3. Weekly picks (news catalyst + technicals, prose + entry status)
  4. Entry timing dashboard (pullback, volume, vol-compression, RSI)
  5. Annual / 5-Year picks (factor tables + profiles + entry)
  6. Portfolio allocation (position weights, sector caps)
  7. Alpha decay & exit signals (signal validity, exit triggers)
  8. Live performance tracking (CAGR, Sharpe, drawdown, alpha)
  9. Risk metrics + disclaimer
"""

import pandas as pd
import numpy as np
from datetime import datetime


def _fmt_pct(val, decimals=1) -> str:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "N/A"
    return f"{val * 100:.{decimals}f}%"


def _fmt_num(val, decimals=1) -> str:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "N/A"
    return f"{val:.{decimals}f}"


def _fmt_inr(val) -> str:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "N/A"
    return f"Rs.{val:,.0f}"


def _fmt_mcap(val) -> str:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "N/A"
    cr = val / 1e7
    if cr >= 100000:
        return f"Rs.{cr / 100000:.1f}L Cr"
    return f"Rs.{cr:,.0f} Cr"


class QuantumSynthesizer:

    def generate_report(
        self,
        week_scored: pd.DataFrame,
        year_scored: pd.DataFrame,
        fiveyear_scored: pd.DataFrame,
        regime_data: dict | None = None,
        week_weights: dict | None = None,
        year_weights: dict | None = None,
        fiveyear_weights: dict | None = None,
        week_portfolio: pd.DataFrame | None = None,
        year_portfolio: pd.DataFrame | None = None,
        fiveyear_portfolio: pd.DataFrame | None = None,
        news_data: list[dict] | None = None,
        headlines: list[dict] | None = None,
        backtest_result=None,
        signal_accuracy: dict | None = None,
        entry_week: pd.DataFrame | None = None,
        entry_year: pd.DataFrame | None = None,
        entry_fiveyear: pd.DataFrame | None = None,
        decay_results: list[dict] | None = None,
        decay_summary: dict | None = None,
        perf_metrics: dict | None = None,
    ) -> str:
        now = datetime.now()
        date_str = now.strftime("%d %b %Y, %H:%M")

        regime = regime_data.get("regime", "SIDEWAYS") if regime_data else "SIDEWAYS"
        news_count = len(news_data) if news_data else 0
        headline_count = len(headlines) if headlines else 0

        sections = []

        # ── Title ─────────────────────────────────────────────────────────
        sections.append(
            f"# QuanTum Engine v7 — Multi-Layer Stock Intelligence\n"
            f"Generated: {date_str}\n"
            f"Market Regime: **{regime}**\n"
            f"Weekly universe: {len(week_scored)} stocks (from {headline_count} headlines)\n"
            f"Long-term universe: {len(year_scored)} NSE stocks\n"
        )

        # ── Actionable Summary (top of report) ──────────────────────────
        sections.append(self._actionable_summary(
            week_scored, year_scored, fiveyear_scored,
            entry_week, entry_year, entry_fiveyear,
            news_data, regime,
        ))

        # ── Regime ────────────────────────────────────────────────────────
        if regime_data:
            sections.append(self._regime_section(regime_data))

        # ── Methodology ───────────────────────────────────────────────────
        sections.append(self._methodology_section(
            regime, week_weights, year_weights, fiveyear_weights))

        # ── Accuracy ──────────────────────────────────────────────────────
        if signal_accuracy:
            sections.append(self._accuracy_section(signal_accuracy))

        # ── Weekly Picks ──────────────────────────────────────────────────
        sections.append(self._weekly_section(week_scored, news_data))

        # ── Weekly Entry Timing ──────────────────────────────────────────
        if entry_week is not None and not entry_week.empty:
            sections.append(self._entry_timing_section(entry_week, "Weekly Entry Timing"))

        # ── Weekly Portfolio ──────────────────────────────────────────────
        if week_portfolio is not None and not week_portfolio.empty:
            sections.append(self._portfolio_section(week_portfolio, "Weekly Portfolio Allocation", regime))

        # ── Annual ────────────────────────────────────────────────────────
        sections.append(self._longterm_section(
            year_scored, "year", "Annual Horizon (6-12 Months)"))

        # ── Annual Entry Timing ──────────────────────────────────────────
        if entry_year is not None and not entry_year.empty:
            sections.append(self._entry_timing_section(entry_year, "Annual Entry Timing"))

        if year_portfolio is not None and not year_portfolio.empty:
            sections.append(self._portfolio_section(year_portfolio, "Annual Portfolio Allocation", regime))

        # ── 5-Year ────────────────────────────────────────────────────────
        sections.append(self._longterm_section(
            fiveyear_scored, "5years", "5-Year Horizon (Structural)"))

        # ── 5-Year Entry Timing ──────────────────────────────────────────
        if entry_fiveyear is not None and not entry_fiveyear.empty:
            sections.append(self._entry_timing_section(entry_fiveyear, "5-Year Entry Timing"))

        if fiveyear_portfolio is not None and not fiveyear_portfolio.empty:
            sections.append(self._portfolio_section(fiveyear_portfolio, "5-Year Portfolio Allocation", regime))

        # ── Alpha Decay & Exit Signals ──────────────────────────────────
        if decay_results or decay_summary:
            sections.append(self._decay_section(decay_results, decay_summary))

        # ── Live Performance ───────────────────────────────────────────
        if perf_metrics and "error" not in perf_metrics:
            sections.append(self._performance_section(perf_metrics))

        # ── Risk + Disclaimer ────────────────────────────────────────────
        sections.append(self._risk_section(week_scored, year_scored, fiveyear_scored))
        sections.append(self._disclaimer())

        return "\n---\n\n".join(sections)

    # ── Actionable Summary ──────────────────────────────────────────────

    def _actionable_summary(
        self,
        week_scored: pd.DataFrame,
        year_scored: pd.DataFrame,
        fiveyear_scored: pd.DataFrame,
        entry_week: pd.DataFrame | None,
        entry_year: pd.DataFrame | None,
        entry_fiveyear: pd.DataFrame | None,
        news_data: list[dict] | None,
        regime: str,
    ) -> str:
        lines = [
            "## Actionable Now — Buy Decisions\n",
            "*Only stocks with optimal entry timing (score >= 70) are listed here. "
            "Signal is valid for all ranked stocks, but these have the right price, "
            "volume, volatility, and RSI conditions to enter today.*\n",
        ]

        catalyst_map = {}
        if news_data:
            for item in news_data:
                catalyst_map[item["symbol"]] = item.get("catalyst", "")

        has_any_actionable = False

        for label, horizon_tag, scored, entry_df in [
            ("Weekly (1-7 Days)", "week", week_scored, entry_week),
            ("Annual (6-12 Months)", "year", year_scored, entry_year),
            ("5-Year (Structural)", "5years", fiveyear_scored, entry_fiveyear),
        ]:
            actionable = self._get_actionable(scored, entry_df)

            if actionable.empty:
                wait_analysis = self._analyze_wait_reasons(scored, entry_df, horizon_tag)
                lines.append(f"### {label}\n")
                lines.append(f"**No stocks have optimal entry right now.**\n")
                lines.append(wait_analysis)
                lines.append("")
            else:
                has_any_actionable = True
                lines.append(f"### {label} — {len(actionable)} stocks ready\n")

                for i, (_, row) in enumerate(actionable.iterrows(), 1):
                    ticker = row["ticker"]
                    score = row.get("composite_score", 0)
                    entry_sc = row.get("entry_score", 0)
                    close = row.get("close", 0)
                    rsi = row.get("rsi", np.nan)
                    sma20 = row.get("sma20", np.nan)
                    conv = row.get("conviction", "")
                    sector = row.get("sector", "")

                    reasons = []
                    # Why signal is valid
                    flow = row.get("flow_score", np.nan)
                    earn = row.get("earnings_rev_score", np.nan)
                    if not pd.isna(flow) and flow > 70:
                        reasons.append(f"strong institutional flow ({flow:.0f}/100)")
                    if not pd.isna(earn) and earn > 70:
                        reasons.append(f"positive earnings revision ({earn:.0f}/100)")

                    catalyst = catalyst_map.get(ticker, "")
                    if catalyst:
                        reasons.append(f"catalyst: {catalyst[:80]}")

                    # Why entry is good now
                    entry_reasons = []
                    if not pd.isna(sma20) and sma20 > 0 and close > 0:
                        dist = (close - sma20) / sma20
                        if -0.02 <= dist <= 0.03:
                            entry_reasons.append(f"at 20DMA support ({dist:+.1%})")
                    if not pd.isna(rsi) and 50 <= rsi <= 65:
                        entry_reasons.append(f"RSI in sweet spot ({rsi:.0f})")

                    pullback_note = row.get("pullback_note", "")
                    vol_note = row.get("vol_compression_note", "")
                    if "compression" in str(vol_note).lower() or "tight" in str(vol_note).lower():
                        entry_reasons.append("volatility compressed (breakout setup)")

                    lines.append(
                        f"**{i}. {ticker}** ({sector}) — "
                        f"Signal {score:.0f}, Entry {entry_sc:.0f}, {conv}"
                    )
                    lines.append(f"   Price: Rs.{close:,.0f}")
                    if reasons:
                        lines.append(f"   Signal: {'; '.join(reasons)}")
                    if entry_reasons:
                        lines.append(f"   Entry: {'; '.join(entry_reasons)}")
                    lines.append("")

        if not has_any_actionable:
            lines.append(self._next_run_estimate(
                week_scored, year_scored, entry_week, entry_year, regime
            ))

        return "\n".join(lines)

    def _get_actionable(
        self, scored: pd.DataFrame, entry_df: pd.DataFrame | None
    ) -> pd.DataFrame:
        """Return scored stocks that have entry_allowed == True."""
        if entry_df is None or entry_df.empty:
            return pd.DataFrame()
        if "entry_allowed" not in scored.columns:
            return pd.DataFrame()
        actionable = scored[scored["entry_allowed"] == True].copy()
        return actionable.head(10)

    def _analyze_wait_reasons(
        self, scored: pd.DataFrame, entry_df: pd.DataFrame | None,
        horizon: str,
    ) -> str:
        """Analyze why nothing is actionable and what to watch for."""
        if entry_df is None or entry_df.empty:
            return "*Entry timing data unavailable.*"

        reasons = entry_df["entry_status"].value_counts()
        total = len(entry_df)

        parts = []
        for reason, count in reasons.head(3).items():
            pct = count / total * 100
            parts.append(f"{reason} ({count} stocks, {pct:.0f}%)")

        analysis = "**Why:** " + " | ".join(parts) + "\n"

        # Specific guidance based on dominant wait reason
        top_reason = reasons.index[0] if len(reasons) > 0 else ""
        if "pullback" in top_reason.lower() or "overextended" in top_reason.lower():
            analysis += (
                "**Watch for:** A 3-5% pullback toward 20DMA. "
                "Most stocks are extended above their moving average support.\n"
                f"**Re-run in:** 3-5 trading days, or after any market dip.\n"
            )
        elif "vol compression" in top_reason.lower():
            analysis += (
                "**Watch for:** Volatility to settle — 5-day vol dropping below "
                "70% of 30-day vol signals a breakout setup.\n"
                f"**Re-run in:** 5-7 trading days.\n"
            )
        elif "rsi" in top_reason.lower():
            analysis += (
                "**Watch for:** RSI cooling below 65. "
                "Many stocks are overbought and need consolidation.\n"
                f"**Re-run in:** 3-7 trading days.\n"
            )
        else:
            analysis += f"**Re-run in:** 3-5 trading days.\n"

        # Show closest-to-actionable stocks
        if "entry_score" in entry_df.columns:
            near = entry_df[entry_df["entry_allowed"] == False].nlargest(3, "entry_score")
            if not near.empty:
                close_list = ", ".join(
                    f"{r['ticker']} (entry {r['entry_score']:.0f})"
                    for _, r in near.iterrows()
                )
                analysis += f"**Closest to actionable:** {close_list}\n"

        return analysis

    def _next_run_estimate(
        self,
        week_scored: pd.DataFrame,
        year_scored: pd.DataFrame,
        entry_week: pd.DataFrame | None,
        entry_year: pd.DataFrame | None,
        regime: str,
    ) -> str:
        """Estimate when to re-generate the report."""
        lines = ["### When to Re-Run This Report\n"]

        if regime == "BEAR":
            lines.append(
                "Market is in **BEAR** regime. Quality and low-volatility stocks "
                "may reach entry points sooner. Re-run every **2-3 trading days**."
            )
        elif regime == "BULL":
            lines.append(
                "Market is in **BULL** regime. Pullbacks are shallow and brief. "
                "Re-run **daily** or after any intraday dip of 1-2%."
            )
        else:
            lines.append(
                "Market is **SIDEWAYS**. Stocks oscillate around moving averages. "
                "Re-run in **3-5 trading days**, or immediately after a "
                "market-wide pullback (Nifty drops 1-2% in a session)."
            )

        lines.extend([
            "",
            "**Quick triggers to re-run immediately:**",
            "- Nifty drops 1%+ intraday",
            "- India VIX spikes above 18 (creates entry dips)",
            "- Major earnings announcement from a top-ranked stock",
            "- Sector rotation news (budget, policy, RBI)",
        ])

        return "\n".join(lines)

    # ── Regime Section ────────────────────────────────────────────────────

    def _regime_section(self, rd: dict) -> str:
        lines = [
            f"## Market Regime: {rd['regime']}\n",
        ]

        if rd.get("nifty_close"):
            lines.append(f"- Nifty 50: {rd['nifty_close']:,.0f} "
                         f"(200 DMA: {rd.get('nifty_200dma', 0):,.0f}, "
                         f"{rd.get('pct_above_200dma', 0):+.1f}%)")
        if rd.get("breadth_pct") is not None:
            lines.append(f"- Market breadth: {rd['breadth_pct']:.0f}% of large-caps above 50 DMA")
        if rd.get("vix") is not None:
            lines.append(f"- India VIX: {rd['vix']:.1f}")

        lines.append("")
        for sig in rd.get("signals", []):
            lines.append(f"- {sig}")

        regime = rd["regime"]
        if regime == "BULL":
            lines.append("\n**Regime implication:** Favour momentum, earnings revisions, and flow. "
                         "Reduce defensive allocation.")
        elif regime == "BEAR":
            lines.append("\n**Regime implication:** Favour quality, low volatility, and defensive sectors. "
                         "10% cash reserve. Avoid pure momentum plays.")
        else:
            lines.append("\n**Regime implication:** Balanced allocation across factors. "
                         "5% cash reserve.")

        return "\n".join(lines)

    # ── Methodology ───────────────────────────────────────────────────────

    def _methodology_section(self, regime, ww, yw, fw) -> str:
        lines = [
            "## Methodology\n",
            "### 9-Factor Model with Sector-Relative Momentum + Regime-Adjusted Weights\n",
            "| Factor | Description | Week | Year | 5-Year |",
            "|--------|-------------|------|------|--------|",
        ]

        factors = [
            ("News Catalyst", "news_catalyst", "Deep impact: sentiment + surprise + event + reaction"),
            ("Technical", "technical", "RSI + MACD + trend alignment"),
            ("Momentum", "momentum", "60% sector-relative + 40% absolute (1m/3m/6m/12m)"),
            ("Flow", "flow", "NSE Bhavcopy delivery % (10d avg) + block deals + OBV"),
            ("Earnings Rev", "earnings_revision", "EPS estimates + 4Q surprise track + analyst consensus + news"),
            ("Volatility", "volatility", "Inverse 20-day annualized vol"),
            ("Value", "value", "Earnings yield + inverse P/B"),
            ("Quality", "quality", "ROE + leverage + margin (sector-corrected)"),
            ("Sector Growth", "sector_growth", "Structural industry tailwinds"),
        ]

        for label, key, desc in factors:
            w_wk = (ww or {}).get(key, 0)
            w_yr = (yw or {}).get(key, 0)
            w_5y = (fw or {}).get(key, 0)
            if w_wk == 0 and w_yr == 0 and w_5y == 0:
                continue
            lines.append(
                f"| {label} | {desc} | {w_wk:.0%} | {w_yr:.0%} | {w_5y:.0%} |"
            )

        lines.extend([
            "",
            f"*Weights adjusted for **{regime}** regime.*",
            "",
            "### Entry Timing Engine (Execution Alpha)\n",
            "Signals are filtered through an institutional-grade entry timing model:",
            "- **Pullback-to-Support (35%):** Enter near 20DMA support (-2% to +3%)",
            "- **Volume Confirmation (25%):** Require 1.5x+ avg volume for institutional participation",
            "- **Volatility Compression (25%):** 5d/30d vol ratio < 0.7 = breakout setup",
            "- **RSI Stability (15%):** Optimal zone RSI 50-65, avoid >75 or <40",
            "",
            "*Entry allowed when composite score >= 70. WAIT stocks have valid signals but suboptimal entry timing.*",
        ])

        return "\n".join(lines)

    # ── Weekly Section ────────────────────────────────────────────────────

    def _weekly_section(self, scored: pd.DataFrame, news_data: list[dict] | None) -> str:
        top = scored.head(7)
        lines = [
            "## Weekly Horizon (1-7 Days) — News-Driven\n",
            "*Stocks discovered from live headlines. Ranked by news impact + technical confirmation.*\n",
        ]

        catalyst_map = {}
        event_map = {}
        if news_data:
            for item in news_data:
                catalyst_map[item["symbol"]] = item.get("catalyst", "")
                event_map[item["symbol"]] = item.get("event_type", "")

        for i, (_, row) in enumerate(top.iterrows(), 1):
            ticker = row["ticker"]
            sector = row.get("sector", "")
            close = row.get("close", 0)
            rsi = row.get("rsi", np.nan)
            macd = row.get("macd", np.nan)
            macd_sig = row.get("macd_signal", np.nan)
            sma50 = row.get("sma50", np.nan)
            sma200 = row.get("sma200", np.nan)
            r1m = row.get("return_1m", np.nan)
            r3m = row.get("return_3m", np.nan)
            vol = row.get("volatility_20d", np.nan)
            vol_ratio = row.get("volume_ratio", np.nan)
            score = row["composite_score"]
            conv = row["conviction"]
            agree = row["factor_agreement"]
            flow = row.get("flow_score", np.nan)

            catalyst = row.get("news_catalyst", "") or catalyst_map.get(ticker, "")
            event = row.get("event_type", "") or event_map.get(ticker, "")
            event_label = event.replace("_", " ").title() if event else ""

            entry_status = row.get("entry_status", "")
            entry_sc = row.get("entry_score", np.nan)
            entry_tag = ""
            if entry_status and not pd.isna(entry_sc):
                entry_tag = f" | Entry: {entry_sc:.0f} ({entry_status})"

            parts = [f"### {i}. {ticker} ({sector}) — Score {score:.1f}, {conv}{entry_tag}\n"]

            if catalyst:
                prefix = f"**[{event_label}]** " if event_label else "**Catalyst:** "
                parts.append(f"{prefix}{catalyst}")
                parts.append("")

            trend_parts = [f"Trading at Rs.{close:,.0f}"]
            if not pd.isna(sma50):
                pct_50 = (close - sma50) / sma50 * 100
                trend_parts.append(f"{abs(pct_50):.1f}% {'above' if pct_50 > 0 else 'below'} 50 DMA")
            if not pd.isna(sma200):
                pct_200 = (close - sma200) / sma200 * 100
                trend_parts.append(f"{abs(pct_200):.1f}% {'above' if pct_200 > 0 else 'below'} 200 DMA")
            parts.append(", ".join(trend_parts) + ".")

            if not pd.isna(rsi):
                if 45 <= rsi <= 55:
                    rsi_read = "neutral zone"
                elif 55 < rsi <= 65:
                    rsi_read = "mildly bullish"
                elif 65 < rsi <= 75:
                    rsi_read = "strong momentum, nearing overbought"
                elif rsi > 75:
                    rsi_read = "overbought"
                elif 35 <= rsi < 45:
                    rsi_read = "recovering"
                else:
                    rsi_read = "oversold"
                parts.append(f"RSI {rsi:.1f} ({rsi_read}).")

            if not pd.isna(macd) and not pd.isna(macd_sig):
                if macd > macd_sig and macd > 0:
                    parts.append("MACD bullish.")
                elif macd > macd_sig:
                    parts.append("MACD early crossover.")
                elif abs(macd - macd_sig) < abs(macd_sig) * 0.1:
                    parts.append("MACD converging.")
                else:
                    parts.append("MACD bearish.")

            mom = []
            if not pd.isna(r1m):
                mom.append(f"1m: {r1m*100:+.1f}%")
            if not pd.isna(r3m):
                mom.append(f"3m: {r3m*100:+.1f}%")
            if mom:
                parts.append("Momentum: " + ", ".join(mom) + ".")

            if not pd.isna(flow) and flow > 70:
                parts.append(f"Flow score {flow:.0f}/100 (accumulation signal).")
            elif not pd.isna(flow) and flow < 30:
                parts.append(f"Flow score {flow:.0f}/100 (distribution signal).")

            if not pd.isna(vol_ratio) and vol_ratio >= 1.5:
                parts.append(f"Volume {vol_ratio:.1f}x average.")

            if not pd.isna(vol):
                parts.append(f"Vol: {vol*100:.1f}%.")

            lines.append(" ".join(parts))
            lines.append("")

        return "\n".join(lines)

    # ── Long-term Section ─────────────────────────────────────────────────

    def _longterm_section(self, scored: pd.DataFrame, horizon: str, title: str) -> str:
        top = scored.head(10)
        lines = [
            f"## {title}\n",
            "### Top 10 Rankings\n",
            "| # | Ticker | Sector | Score | Conv | Flow | EarnRev |",
            "|---|--------|--------|-------|------|------|---------|",
        ]

        for i, (_, row) in enumerate(top.iterrows(), 1):
            sector = row.get("sector", "?")
            flow = row.get("flow_score", 0)
            earn = row.get("earnings_rev_score", 0)
            lines.append(
                f"| {i} | {row['ticker']} | {sector} "
                f"| {row['composite_score']:.1f} "
                f"| {row['conviction']} "
                f"| {flow:.0f} | {earn:.0f} |"
            )

        if "sector" in top.columns:
            sc = top["sector"].value_counts()
            lines.append("\n**Sectors:** " + ", ".join(f"{s} ({c})" for s, c in sc.items()))

        lines.extend([
            "\n### Factor Breakdown (Top 5)\n",
            "| Ticker | Val | Qual | Mom | Tech | Vol | SectGr | Flow | Earn |",
            "|--------|-----|------|-----|------|-----|--------|------|------|",
        ])
        for _, row in top.head(5).iterrows():
            lines.append(
                f"| {row['ticker']} "
                f"| {row['value_score']:.0f} | {row['quality_score']:.0f} "
                f"| {row['momentum_score']:.0f} | {row['technical_score']:.0f} "
                f"| {row['volatility_score']:.0f} | {row.get('sector_growth_score', 0):.0f} "
                f"| {row.get('flow_score', 0):.0f} | {row.get('earnings_rev_score', 0):.0f} |"
            )

        lines.append("\n### Stock Profiles\n")
        for i, (_, row) in enumerate(top.head(5).iterrows(), 1):
            roe_val = row.get("roe", np.nan)
            if not pd.isna(roe_val) and abs(roe_val) < 1:
                roe_val = roe_val * 100
            sector = row.get("sector", "")

            lines.append(f"**{i}. {row['ticker']}** ({sector})")
            lines.extend([
                "",
                "| Metric | Value | Metric | Value |",
                "|--------|-------|--------|-------|",
                f"| Price | {_fmt_inr(row.get('close'))} | Mkt Cap | {_fmt_mcap(row.get('market_cap'))} |",
                f"| P/E | {_fmt_num(row.get('pe_ratio'))} | P/B | {_fmt_num(row.get('pb_ratio'))} |",
                f"| ROE | {_fmt_num(roe_val)}% | D/E | {_fmt_num(row.get('debt_equity'))} |",
                f"| 6m Ret | {_fmt_pct(row.get('return_6m'))} | 12m Ret | {_fmt_pct(row.get('return_12m'))} |",
                f"| Flow | {row.get('flow_score', 0):.0f}/100 | EarnRev | {row.get('earnings_rev_score', 0):.0f}/100 |",
                "",
            ])

        return "\n".join(lines)

    # ── Entry Timing Section ──────────────────────────────────────────────

    def _entry_timing_section(self, entry_df: pd.DataFrame, title: str) -> str:
        lines = [
            f"## {title}\n",
            "*Entry score = 0.35 x Pullback + 0.25 x Volume + 0.25 x Vol Compression + 0.15 x RSI.*\n",
            "*Enter when score >= 70. Signal remains valid; WAIT stocks should be entered on pullback.*\n",
        ]

        # Split into ENTER and WAIT groups
        enters = entry_df[entry_df["entry_allowed"] == True]
        waits = entry_df[entry_df["entry_allowed"] == False]

        if not enters.empty:
            lines.extend([
                f"### Ready to Enter ({len(enters)} stocks)\n",
                "| Ticker | Entry Score | Status | Pullback | Volume | VolComp | RSI |",
                "|--------|------------|--------|----------|--------|---------|-----|",
            ])
            for _, row in enters.iterrows():
                lines.append(
                    f"| {row['ticker']} "
                    f"| {row['entry_score']:.0f} "
                    f"| {row['entry_status']} "
                    f"| {row['pullback_score']:.0f} "
                    f"| {row['volume_score']:.0f} "
                    f"| {row['vol_compression_score']:.0f} "
                    f"| {row['rsi_score']:.0f} |"
                )
            lines.append("")

        if not waits.empty:
            show_n = min(15, len(waits))
            remaining = len(waits) - show_n
            lines.extend([
                f"### Wait for Better Entry ({len(waits)} stocks)\n",
                "| Ticker | Entry Score | Status | Pullback | Volume | VolComp | RSI |",
                "|--------|------------|--------|----------|--------|---------|-----|",
            ])
            for _, row in waits.head(show_n).iterrows():
                lines.append(
                    f"| {row['ticker']} "
                    f"| {row['entry_score']:.0f} "
                    f"| {row['entry_status']} "
                    f"| {row['pullback_score']:.0f} "
                    f"| {row['volume_score']:.0f} "
                    f"| {row['vol_compression_score']:.0f} "
                    f"| {row['rsi_score']:.0f} |"
                )
            if remaining > 0:
                lines.append(f"\n*...and {remaining} more stocks waiting for optimal entry.*")
            lines.append("")

        # Entry notes for WAIT stocks
        if not waits.empty:
            lines.append("**Entry triggers for WAIT stocks:**\n")
            for _, row in waits.head(5).iterrows():
                notes = []
                if row["pullback_score"] < 50:
                    notes.append(f"pullback needed ({row.get('pullback_note', '')})")
                if row["volume_score"] < 50:
                    notes.append(f"wait for volume ({row.get('volume_note', '')})")
                if row["vol_compression_score"] < 50:
                    notes.append(f"vol not compressed ({row.get('vol_compression_note', '')})")
                if row["rsi_score"] < 50:
                    notes.append(f"RSI issue ({row.get('rsi_note', '')})")
                if notes:
                    lines.append(f"- **{row['ticker']}:** {'; '.join(notes)}")
            lines.append("")

        return "\n".join(lines)

    # ── Portfolio Section ─────────────────────────────────────────────────

    def _portfolio_section(self, portfolio: pd.DataFrame, title: str, regime: str) -> str:
        lines = [
            f"## {title}\n",
            f"*Regime: {regime} — risk-adjusted position sizing with sector caps (30%), single-stock cap (20%)*\n",
            "| Ticker | Sector | Score | Weight |",
            "|--------|--------|-------|--------|",
        ]

        for _, row in portfolio.iterrows():
            ticker = row.get("ticker", "?")
            sector = row.get("sector", "")
            score = row.get("composite_score", 0)
            weight = row.get("position_weight_pct", 0)

            if ticker == "CASH":
                lines.append(f"| CASH | Reserve | - | {weight:.1f}% |")
            else:
                lines.append(f"| {ticker} | {sector} | {score:.1f} | {weight:.1f}% |")

        return "\n".join(lines)

    # ── Alpha Decay Section ──────────────────────────────────────────────

    def _decay_section(self, decay_results: list[dict] | None, summary: dict | None) -> str:
        lines = [
            "## Alpha Decay & Exit Signals\n",
            "Signal strength decays exponentially. Each factor has a half-life: "
            "news (3d), technical (7d), momentum (14d), flow (21d), "
            "earnings (45d), quality/value (90d).\n",
        ]

        if summary:
            lines.extend([
                f"Active positions: **{summary.get('active_positions', 0)}**\n",
            ])
            if summary.get("total_exited", 0) > 0:
                avg_pnl = summary.get("avg_pnl") or 0
                avg_win = summary.get("avg_win") or 0
                avg_loss = summary.get("avg_loss") or 0
                hit_rate = summary.get("hit_rate") or 0
                lines.extend([
                    "### Exit Statistics\n",
                    "| Metric | Value |",
                    "|--------|-------|",
                    f"| Total Exited | {summary['total_exited']} |",
                    f"| Win Rate | {hit_rate:.0%} |",
                    f"| Avg P&L | {avg_pnl:+.1f}% |",
                    f"| Avg Win | {avg_win:+.1f}% |",
                    f"| Avg Loss | {avg_loss:.1f}% |",
                    "",
                ])

        if decay_results:
            exits = [d for d in decay_results if d["should_exit"]]
            actives = [d for d in decay_results if not d["should_exit"]]

            if exits:
                lines.extend([
                    "### Exit Signals Triggered\n",
                    "| Ticker | Days | P&L | Signal | Reason |",
                    "|--------|------|-----|--------|--------|",
                ])
                for d in exits[:10]:
                    lines.append(
                        f"| {d['ticker']} | {d['days_held']}d "
                        f"| {d['pnl_pct']:+.1f}% "
                        f"| {d['signal_strength']:.0f}% "
                        f"| {d['exit_reason']} |"
                    )
                lines.append("")

            if actives:
                lines.extend([
                    "### Active Positions (Signal Decay)\n",
                    "| Ticker | Days | P&L | Strength | Factor | Half-Life |",
                    "|--------|------|-----|----------|--------|-----------|",
                ])
                for d in sorted(actives, key=lambda x: x["signal_strength"])[:15]:
                    lines.append(
                        f"| {d['ticker']} | {d['days_held']}d "
                        f"| {d['pnl_pct']:+.1f}% "
                        f"| {d['signal_strength']:.0f}% "
                        f"| {d['dominant_factor']} "
                        f"| {d['half_life']}d |"
                    )
                lines.append("")

        return "\n".join(lines)

    # ── Live Performance Section ───────────────────────────────────────

    def _performance_section(self, metrics: dict) -> str:
        def _safe(key, default=0):
            v = metrics.get(key, default)
            return v if v is not None else default

        lines = [
            "## Live Performance Tracking\n",
            f"Tracking **{_safe('signal_count')}** signals "
            f"({metrics.get('date_range', {}).get('start', '?')} to "
            f"{metrics.get('date_range', {}).get('end', '?')})\n",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Portfolio CAGR | {_safe('cagr'):.1f}% |",
            f"| Sharpe Ratio | {_safe('sharpe'):.2f} |",
            f"| Max Drawdown | {_safe('max_drawdown_pct'):.1f}% |",
            f"| Alpha vs Nifty | {_safe('alpha'):+.1f}% |",
            f"| Hit Rate (alpha>0) | {_safe('hit_rate'):.0%} |",
            f"| Win Rate | {_safe('win_rate'):.0%} |",
            f"| Avg Win | +{_safe('avg_win'):.1f}% |",
            f"| Avg Loss | {_safe('avg_loss'):.1f}% |",
            f"| Win/Loss Ratio | {_safe('win_loss_ratio'):.1f}x |",
        ]

        # Per-horizon breakdown
        for horizon, label in [("week", "Weekly"), ("year", "Annual"), ("5years", "5-Year")]:
            hm = metrics.get(f"{horizon}_metrics")
            if hm:
                lines.append(
                    f"\n**{label}:** Sharpe {hm.get('sharpe', 0):.2f}, "
                    f"Alpha {hm.get('alpha', 0):+.1f}%, "
                    f"Hit {hm.get('hit_rate', 0):.0%} "
                    f"({hm.get('total_signals', 0)} signals)"
                )

        return "\n".join(lines)

    # ── Accuracy / Risk / Disclaimer ──────────────────────────────────────

    def _accuracy_section(self, acc: dict) -> str:
        lines = ["## Signal Accuracy\n", "| Metric | Value |", "|--------|-------|"]
        for k, v in acc.items():
            val = f"{v:.1%}" if isinstance(v, float) else str(v)
            lines.append(f"| {k} | {val} |")
        return "\n".join(lines)

    def _risk_section(self, week_df, year_df, fiveyear_df) -> str:
        lines = ["## Risk Metrics\n"]

        for label, df in [("Week", week_df), ("Year", year_df), ("5-Year", fiveyear_df)]:
            top5 = df.head(5)
            if top5.empty:
                continue
            avg_vol = top5["volatility_20d"].mean() if "volatility_20d" in top5.columns else np.nan
            lines.extend([
                f"**{label}:** Avg vol {_fmt_pct(avg_vol)}, "
                f"Avg D/E {_fmt_num(top5.get('debt_equity', pd.Series()).mean())}",
                "",
            ])

        lines.extend([
            "### Limitations\n",
            "1. Weekly picks depend on RSS feed quality and Gemini accuracy.",
            "2. NSE delivery API may be rate-limited; falls back to volume proxies when unavailable.",
            "3. Quarterly earnings data depends on yfinance availability; Gemini extraction supplements.",
            "4. Regime detection uses Nifty 50 breadth sample (30 stocks), not full index.",
            "5. No transaction costs in performance estimates.",
            "6. Alpha decay half-lives are estimated; actual decay varies by market conditions.",
            "7. Entry timing uses EOD data; intraday entry windows may differ.",
        ])
        return "\n".join(lines)

    def _disclaimer(self) -> str:
        return (
            "## Disclaimer\n\n"
            "This report is generated by a quantitative model for informational purposes only. "
            "It is not investment advice. All investment carries risk of capital loss. "
            "Consult a SEBI-registered advisor before acting. Past performance does not "
            "guarantee future results."
        )
