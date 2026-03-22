"""
QuanTum Live Performance Tracking Engine

Tracks real portfolio performance with:
  1. Daily portfolio_history table (date, ticker, weight, price, portfolio_value)
  2. Daily return computation
  3. Annualized Sharpe ratio: mean(daily_returns) / std(daily_returns) * sqrt(252)
  4. Max drawdown: (current - peak) / peak
  5. Alpha vs Nifty 50: portfolio_return - nifty_return
  6. Hit rate: % of signals with positive alpha
  7. Win/loss ratio

Auto-generates performance report section for the QuanTum report.
"""
import sqlite3
import sys
import io
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from turso_db import get_db_smart
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

logging.getLogger("yfinance").setLevel(logging.CRITICAL)

logger = logging.getLogger(__name__)


class PerformanceTracker:

    def __init__(self, db_path: str = "quantum_data.db"):
        self.db_path = db_path
        self._ensure_tables()

    def _get_db(self) -> sqlite3.Connection:
        return get_db_smart(self.db_path)

    def _ensure_tables(self):
        try:
            conn = self._get_db()
            conn.execute("""CREATE TABLE IF NOT EXISTS portfolio_history (
                date TEXT,
                ticker TEXT,
                horizon TEXT,
                weight REAL,
                price REAL,
                portfolio_value REAL,
                benchmark_value REAL,
                PRIMARY KEY (date, ticker, horizon)
            )""")
            conn.execute("""CREATE TABLE IF NOT EXISTS daily_returns (
                date TEXT PRIMARY KEY,
                portfolio_return REAL,
                benchmark_return REAL,
                portfolio_value REAL,
                benchmark_value REAL,
                alpha REAL
            )""")
            conn.commit()
            conn.close()
        except Exception:
            pass

    def record_portfolio(
        self, portfolio: pd.DataFrame, horizon: str, progress_callback=None,
    ):
        """Record today's portfolio snapshot for tracking."""
        if portfolio is None or portfolio.empty:
            return

        today = datetime.today().strftime("%Y-%m-%d")
        conn = self._get_db()

        # Fetch current Nifty value
        nifty_val = self._get_nifty_current()

        for _, row in portfolio.iterrows():
            ticker = row.get("ticker", "?")
            if ticker == "CASH":
                continue
            weight = row.get("position_weight_pct", 0) / 100.0
            price = row.get("close") or row.get("current_price", 0)

            try:
                conn.execute(
                    """INSERT OR REPLACE INTO portfolio_history
                       (date, ticker, horizon, weight, price, portfolio_value, benchmark_value)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (today, ticker, horizon, weight, price, None, nifty_val),
                )
            except Exception:
                continue

        conn.commit()
        conn.close()

    def compute_performance(self, progress_callback=None) -> dict:
        """Compute live performance metrics from signal + portfolio history."""
        conn = self._get_db()

        # Read signal_log
        try:
            signals = pd.read_sql_query(
                """SELECT date, ticker, horizon, composite_score, conviction,
                          close_at_signal, actual_return, alpha, verified
                   FROM signal_log ORDER BY date""",
                conn,
            )
        except Exception:
            signals = pd.DataFrame()

        # Read portfolio history
        try:
            port_hist = pd.read_sql_query(
                "SELECT * FROM portfolio_history ORDER BY date",
                conn,
            )
        except Exception:
            port_hist = pd.DataFrame()

        conn.close()

        if signals.empty and port_hist.empty:
            return {"error": "No signal or portfolio history found"}

        if progress_callback:
            progress_callback(f"Analyzing {len(signals)} signals + {len(port_hist)} portfolio records...")

        # Update unverified signal returns
        if not signals.empty:
            unverified = signals[signals["verified"] != 1].copy()
            if not unverified.empty and progress_callback:
                progress_callback(f"Fetching prices for {len(unverified)} unverified signals...")
            signals = self._update_signal_returns(signals)

        # Compute daily portfolio returns from portfolio_history
        daily_metrics = self._compute_daily_returns(port_hist, progress_callback)

        # Compute signal-level metrics
        signal_metrics = self._compute_signal_metrics(signals)

        # Combine
        result = {
            "signal_count": len(signals),
            "date_range": {
                "start": str(signals["date"].min()) if not signals.empty else "N/A",
                "end": str(signals["date"].max()) if not signals.empty else "N/A",
            },
        }
        result.update(signal_metrics)

        # Overwrite with daily metrics if available (more accurate)
        if daily_metrics:
            result.update(daily_metrics)

        # Per-horizon breakdown
        if not signals.empty:
            for horizon in ["week", "year", "5years"]:
                h_signals = signals[signals["horizon"] == horizon]
                if len(h_signals) >= 3:
                    hm = self._compute_signal_metrics(h_signals)
                    result[f"{horizon}_metrics"] = hm

        # Persist updated returns
        self._persist_returns(signals)

        return result

    def _update_signal_returns(self, signals: pd.DataFrame) -> pd.DataFrame:
        """Fetch current prices and compute returns for all signals."""
        tickers = signals["ticker"].unique().tolist()
        symbols = [f"{t}.NS" for t in tickers]

        try:
            hist = yf.download(symbols, period="1y", interval="1d",
                               progress=False, auto_adjust=True, group_by="ticker")
        except Exception:
            return signals

        nifty = self._get_nifty_history()

        for idx, row in signals.iterrows():
            entry_price = row.get("close_at_signal")
            if pd.isna(entry_price) or entry_price <= 0:
                continue

            ticker = row["ticker"]
            sym = f"{ticker}.NS"

            try:
                if len(symbols) == 1:
                    close_series = hist["Close"].squeeze().dropna()
                else:
                    if sym not in hist.columns.get_level_values(0):
                        continue
                    close_series = hist[sym]["Close"].dropna()

                if close_series.empty:
                    continue

                current_price = float(close_series.iloc[-1])
                actual_return = (current_price / entry_price - 1) * 100

                # Nifty return over same period
                nifty_return = self._nifty_return_since(nifty, row["date"])
                alpha = actual_return - nifty_return

                signals.at[idx, "actual_return"] = round(actual_return, 2)
                signals.at[idx, "alpha"] = round(alpha, 2)
                signals.at[idx, "verified"] = 1

            except Exception:
                continue

        return signals

    def _compute_daily_returns(
        self, port_hist: pd.DataFrame, progress_callback=None,
    ) -> dict:
        """Compute daily portfolio returns from portfolio_history table."""
        if port_hist.empty:
            return {}

        dates = sorted(port_hist["date"].unique())
        if len(dates) < 2:
            return {}

        # Get current prices for all portfolio tickers
        tickers = port_hist["ticker"].unique().tolist()
        symbols = [f"{t}.NS" for t in tickers]

        try:
            start_date = dates[0]
            all_prices = yf.download(symbols, start=start_date, interval="1d",
                                     progress=False, auto_adjust=True, group_by="ticker")
            nifty = yf.download("^NSEI", start=start_date, interval="1d",
                                progress=False, auto_adjust=True)
        except Exception:
            return {}

        if all_prices.empty:
            return {}

        # Compute weighted portfolio value per day
        daily_port_returns = []
        daily_bench_returns = []

        nifty_close = nifty["Close"].squeeze() if "Close" in nifty.columns else pd.Series(dtype=float)

        for d in dates:
            day_holdings = port_hist[port_hist["date"] == d]
            port_val = 0
            for _, h in day_holdings.iterrows():
                ticker = h["ticker"]
                weight = h["weight"]
                entry_price = h["price"]
                sym = f"{ticker}.NS"

                try:
                    if len(symbols) == 1:
                        cs = all_prices["Close"].squeeze().dropna()
                    else:
                        cs = all_prices[sym]["Close"].dropna() if sym in all_prices.columns.get_level_values(0) else pd.Series(dtype=float)

                    dt = pd.Timestamp(d)
                    prices_after = cs[cs.index >= dt]
                    if not prices_after.empty and entry_price > 0:
                        current = float(prices_after.iloc[-1])
                        ret = (current / entry_price - 1)
                        port_val += weight * ret
                except Exception:
                    continue

            daily_port_returns.append(port_val * 100)

            # Benchmark return
            dt = pd.Timestamp(d)
            nifty_after = nifty_close[nifty_close.index >= dt]
            nifty_before = nifty_close[nifty_close.index <= dt]
            if not nifty_before.empty and not nifty_after.empty:
                bench_ret = (float(nifty_after.iloc[-1]) / float(nifty_before.iloc[-1]) - 1) * 100
            else:
                bench_ret = 0
            daily_bench_returns.append(bench_ret)

        port_returns = pd.Series(daily_port_returns)
        bench_returns = pd.Series(daily_bench_returns)

        if port_returns.empty or len(port_returns) < 2:
            return {}

        # Annualized Sharpe: mean(daily) / std(daily) * sqrt(252)
        # Using period returns as proxy for daily
        mean_ret = float(port_returns.mean())
        std_ret = float(port_returns.std())
        risk_free_daily = 6.0 / 252  # ~6% annual risk-free for India
        sharpe = (mean_ret - risk_free_daily) / std_ret * np.sqrt(252) if std_ret > 0 else 0

        # Max drawdown
        cum = (1 + port_returns / 100).cumprod()
        peak = cum.cummax()
        dd = (cum - peak) / peak * 100
        max_dd = float(dd.min())

        # Portfolio CAGR
        total_return = float(cum.iloc[-1])
        days = len(dates)
        years = days / 252 if days > 0 else 1
        cagr = (total_return ** (1 / years) - 1) * 100 if years > 0 else 0

        # Alpha
        avg_alpha = float((port_returns - bench_returns).mean())

        return {
            "cagr": round(cagr, 2),
            "sharpe": round(sharpe, 2),
            "max_drawdown_pct": round(max_dd, 2),
            "alpha": round(avg_alpha, 2),
            "avg_return": round(mean_ret, 2),
            "avg_benchmark": round(float(bench_returns.mean()), 2),
            "tracking_days": days,
        }

    def _compute_signal_metrics(self, signals: pd.DataFrame) -> dict:
        """Compute metrics from individual signal returns."""
        returns = signals["actual_return"].dropna() if not signals.empty else pd.Series(dtype=float)
        alphas = signals["alpha"].dropna() if not signals.empty else pd.Series(dtype=float)

        if returns.empty:
            return {
                "cagr": 0, "sharpe": 0, "max_drawdown_pct": 0,
                "alpha": 0, "hit_rate": 0, "avg_return": 0,
                "win_rate": 0, "avg_win": 0, "avg_loss": 0,
                "win_loss_ratio": 0, "avg_benchmark": 0, "total_signals": 0,
            }

        avg_return = float(returns.mean())
        std_return = float(returns.std()) if len(returns) > 1 else 1.0

        risk_free = 0.5  # monthly proxy
        sharpe = (avg_return - risk_free) / std_return if std_return > 0 else 0

        hit_rate = float((alphas > 0).sum() / len(alphas)) if len(alphas) > 0 else 0
        avg_alpha = float(alphas.mean()) if len(alphas) > 0 else 0

        cum_returns = (1 + returns / 100).cumprod()
        peak = cum_returns.cummax()
        drawdown = (cum_returns - peak) / peak * 100
        max_dd = float(drawdown.min()) if len(drawdown) > 0 else 0

        # CAGR
        if len(signals) >= 2 and not signals.empty:
            first = pd.Timestamp(signals["date"].min())
            last = pd.Timestamp(signals["date"].max())
            days = (last - first).days
            if days > 0:
                total = float(cum_returns.iloc[-1])
                yrs = days / 365.25
                cagr = (total ** (1 / yrs) - 1) * 100 if yrs > 0 else 0
            else:
                cagr = avg_return
        else:
            cagr = avg_return

        wins = returns[returns > 0]
        losses = returns[returns <= 0]
        win_rate = len(wins) / len(returns) if len(returns) > 0 else 0
        avg_win = float(wins.mean()) if len(wins) > 0 else 0
        avg_loss = float(losses.mean()) if len(losses) > 0 else 0
        wl_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else float("inf")

        return {
            "cagr": round(cagr, 2),
            "sharpe": round(sharpe, 2),
            "max_drawdown_pct": round(max_dd, 2),
            "alpha": round(avg_alpha, 2),
            "avg_return": round(avg_return, 2),
            "hit_rate": round(hit_rate, 4),
            "win_rate": round(win_rate, 4),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "win_loss_ratio": round(min(wl_ratio, 99.9), 2),
            "total_signals": len(returns),
            "avg_benchmark": 0,
        }

    def _get_nifty_history(self) -> pd.Series | None:
        try:
            nifty = yf.download("^NSEI", period="1y", interval="1d",
                                progress=False, auto_adjust=True)
            if "Close" in nifty.columns:
                return nifty["Close"].squeeze()
        except Exception:
            pass
        return None

    def _get_nifty_current(self) -> float | None:
        try:
            nifty = yf.download("^NSEI", period="5d", interval="1d",
                                progress=False, auto_adjust=True)
            if "Close" in nifty.columns:
                return float(nifty["Close"].squeeze().iloc[-1])
        except Exception:
            pass
        return None

    def _nifty_return_since(self, nifty: pd.Series | None, entry_date: str) -> float:
        if nifty is None or nifty.empty:
            return 0
        try:
            dt = pd.Timestamp(entry_date)
            before = nifty[nifty.index <= dt]
            after = nifty[nifty.index >= dt]
            if not before.empty and not after.empty:
                entry = float(before.iloc[-1])
                current = float(after.iloc[-1])
                return (current / entry - 1) * 100 if entry > 0 else 0
        except Exception:
            pass
        return 0

    def _persist_returns(self, signals: pd.DataFrame):
        if signals.empty:
            return
        try:
            conn = self._get_db()
            for _, row in signals.iterrows():
                if pd.notna(row.get("actual_return")):
                    conn.execute(
                        """UPDATE signal_log
                           SET actual_return=?, alpha=?, verified=1
                           WHERE date=? AND ticker=? AND horizon=?""",
                        (row["actual_return"], row.get("alpha", 0),
                         row["date"], row["ticker"], row["horizon"]),
                    )
            conn.commit()
            conn.close()
        except Exception:
            pass

    def format_report_section(self, metrics: dict) -> str:
        if "error" in metrics:
            return f"## Live Performance\n\n*{metrics['error']}*\n"

        def _s(key, default=0):
            v = metrics.get(key, default)
            return v if v is not None else default

        lines = [
            "## Live Performance Tracking\n",
            f"Tracking {_s('signal_count')} signals "
            f"({metrics.get('date_range', {}).get('start', '?')} to "
            f"{metrics.get('date_range', {}).get('end', '?')})\n",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Portfolio CAGR | {_s('cagr'):.1f}% |",
            f"| Sharpe Ratio | {_s('sharpe'):.2f} |",
            f"| Max Drawdown | {_s('max_drawdown_pct'):.1f}% |",
            f"| Alpha vs Nifty | {_s('alpha'):+.1f}% |",
            f"| Hit Rate | {_s('hit_rate'):.0%} |",
            f"| Win Rate | {_s('win_rate'):.0%} |",
            f"| Avg Win | +{_s('avg_win'):.1f}% |",
            f"| Avg Loss | {_s('avg_loss'):.1f}% |",
            f"| Win/Loss Ratio | {_s('win_loss_ratio'):.1f}x |",
        ]

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
