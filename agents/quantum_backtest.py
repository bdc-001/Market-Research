"""
QuanTum Backtest Engine

Walk-forward backtesting of the factor scoring model.
At each rebalance date, scores all stocks using only data available up to
that date (no look-ahead bias), picks the top N, and measures forward returns.

Outputs
-------
- CAGR (model vs Nifty50 benchmark)
- Sharpe ratio (annualized)
- Max drawdown
- Hit rate (% of picks with positive forward return)
- Average alpha per pick
- Win/loss ratio
- Monthly return series
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import NamedTuple


class BacktestResult(NamedTuple):
    cagr_model: float
    cagr_benchmark: float
    sharpe_ratio: float
    max_drawdown: float
    hit_rate: float
    avg_alpha: float
    win_loss_ratio: float
    total_picks: int
    total_months: int
    monthly_returns: pd.DataFrame  # columns: date, model_return, benchmark_return


def _annualized_sharpe(returns: pd.Series, rf_annual: float = 0.06) -> float:
    """Annualized Sharpe from monthly returns. rf_annual = risk-free rate."""
    rf_monthly = (1 + rf_annual) ** (1 / 12) - 1
    excess = returns - rf_monthly
    if excess.std() == 0:
        return 0.0
    return float((excess.mean() / excess.std()) * np.sqrt(12))


def _max_drawdown(cumulative: pd.Series) -> float:
    """Maximum drawdown from a cumulative return series."""
    peak = cumulative.cummax()
    dd = (cumulative - peak) / peak
    return float(dd.min())


def _cagr(cumulative_return: float, years: float) -> float:
    if years <= 0 or cumulative_return <= -1:
        return 0.0
    return float((1 + cumulative_return) ** (1 / years) - 1)


def run_backtest(
    tickers: list[str],
    horizon: str = "year",
    lookback_months: int = 12,
    top_n: int = 5,
    hold_months: int = 1,
) -> BacktestResult | None:
    """
    Walk-forward backtest.

    Downloads 3 years of monthly data for all tickers + Nifty50 benchmark.
    Every `hold_months`, re-scores and picks top_n stocks.
    Measures equal-weight portfolio returns vs benchmark.
    """
    from agents.quantum_scorer import FactorScorer

    end_date = datetime.today()
    start_date = end_date - timedelta(days=365 * 3)

    # Fetch monthly data for all tickers
    syms = [f"{t}.NS" for t in tickers]
    benchmark_sym = "^NSEI"

    try:
        prices = yf.download(
            syms + [benchmark_sym],
            start=start_date.strftime("%Y-%m-%d"),
            end=end_date.strftime("%Y-%m-%d"),
            interval="1mo",
            progress=False,
            auto_adjust=True,
            group_by="ticker",
        )
    except Exception:
        return None

    if prices.empty:
        return None

    # Extract monthly close prices into a clean DataFrame
    close_data = {}
    for t in tickers:
        sym = f"{t}.NS"
        try:
            col = prices[sym]["Close"].squeeze()
            if isinstance(col, pd.Series) and not col.dropna().empty:
                close_data[t] = col
        except Exception:
            continue

    try:
        bench_close = prices[benchmark_sym]["Close"].squeeze()
    except Exception:
        return None

    if len(close_data) < 10:
        return None

    close_df = pd.DataFrame(close_data)
    close_df = close_df.dropna(how="all")

    # Monthly returns
    returns_df = close_df.pct_change().dropna(how="all")
    bench_returns = bench_close.pct_change().dropna()

    # Align dates
    common_dates = returns_df.index.intersection(bench_returns.index)
    if len(common_dates) < 6:
        return None

    returns_df = returns_df.loc[common_dates]
    bench_returns = bench_returns.loc[common_dates]

    scorer = FactorScorer()

    model_monthly = []
    bench_monthly = []
    pick_results = []  # (date, ticker, forward_return, benchmark_forward)
    dates_used = []

    # Walk forward: at each month, score using trailing data, pick top_n
    rebalance_dates = list(common_dates[lookback_months:-hold_months])

    for i, date in enumerate(rebalance_dates):
        if i % hold_months != 0:
            continue

        # Build a snapshot DataFrame from trailing data (simulating live scoring)
        snapshot_rows = []
        for t in close_data:
            try:
                trail = close_df[t].loc[:date].dropna()
                if len(trail) < 6:
                    continue

                c = float(trail.iloc[-1])
                r1 = float(trail.iloc[-1] / trail.iloc[-2] - 1) if len(trail) >= 2 else 0
                r3 = float(trail.iloc[-1] / trail.iloc[-4] - 1) if len(trail) >= 4 else 0
                r6 = float(trail.iloc[-1] / trail.iloc[-7] - 1) if len(trail) >= 7 else 0
                r12 = float(trail.iloc[-1] / trail.iloc[-13] - 1) if len(trail) >= 13 else 0

                snapshot_rows.append({
                    "ticker": t,
                    "close": c,
                    "return_1m": r1,
                    "return_3m": r3,
                    "return_6m": r6,
                    "return_12m": r12,
                    "volatility_20d": float(trail.pct_change().dropna().tail(6).std() * np.sqrt(12)),
                    # Fundamentals not available historically via yfinance monthly;
                    # use current values as proxy (acknowledged limitation)
                    "pe_ratio": None,
                    "pb_ratio": None,
                    "roe": None,
                    "debt_equity": None,
                    "profit_margin": None,
                    "earnings_yield": None,
                    "dividend_yield": None,
                    "rsi": 50.0,  # placeholder for monthly data
                    "sma50": None,
                    "sma200": None,
                    "macd": 0.0,
                    "macd_signal": 0.0,
                    "volume_ratio": 1.0,
                    "market_cap": None,
                })
            except Exception:
                continue

        if len(snapshot_rows) < 10:
            continue

        snap_df = pd.DataFrame(snapshot_rows)
        scored = scorer.score(snap_df, horizon)
        top_picks = scored.head(top_n)["ticker"].tolist()

        # Measure forward return (next hold_months)
        fwd_idx = list(common_dates).index(date)
        fwd_end = min(fwd_idx + hold_months, len(common_dates) - 1)

        if fwd_end <= fwd_idx:
            continue

        portfolio_return = 0.0
        valid_picks = 0
        for t in top_picks:
            if t in returns_df.columns:
                fwd_rets = returns_df[t].iloc[fwd_idx + 1 : fwd_end + 1]
                cum = float((1 + fwd_rets).prod() - 1)
                portfolio_return += cum
                valid_picks += 1

                bench_fwd = float((1 + bench_returns.iloc[fwd_idx + 1 : fwd_end + 1]).prod() - 1)
                pick_results.append((date, t, cum, bench_fwd))

        if valid_picks > 0:
            portfolio_return /= valid_picks
            bench_period = float(
                (1 + bench_returns.iloc[fwd_idx + 1 : fwd_end + 1]).prod() - 1
            )
            model_monthly.append(portfolio_return)
            bench_monthly.append(bench_period)
            dates_used.append(date)

    if len(model_monthly) < 3:
        return None

    model_series = pd.Series(model_monthly)
    bench_series = pd.Series(bench_monthly)

    # Cumulative returns
    model_cum = (1 + model_series).cumprod()
    bench_cum = (1 + bench_series).cumprod()

    total_years = len(model_monthly) / 12.0

    # Hit rate: % of individual picks that beat the benchmark
    hits = sum(1 for _, _, ret, bret in pick_results if ret > bret)
    total_picks = len(pick_results)
    hit_rate = hits / total_picks if total_picks > 0 else 0

    # Win/loss ratio
    wins = [r - b for _, _, r, b in pick_results if r > b]
    losses = [b - r for _, _, r, b in pick_results if r <= b]
    avg_win = np.mean(wins) if wins else 0
    avg_loss = np.mean(losses) if losses else 1
    wl_ratio = avg_win / avg_loss if avg_loss > 0 else 0

    # Average alpha
    alphas = [r - b for _, _, r, b in pick_results]
    avg_alpha = float(np.mean(alphas)) if alphas else 0

    monthly_df = pd.DataFrame({
        "date": dates_used,
        "model_return": model_monthly,
        "benchmark_return": bench_monthly,
    })

    return BacktestResult(
        cagr_model=_cagr(float(model_cum.iloc[-1] - 1), total_years),
        cagr_benchmark=_cagr(float(bench_cum.iloc[-1] - 1), total_years),
        sharpe_ratio=_annualized_sharpe(model_series),
        max_drawdown=_max_drawdown(model_cum),
        hit_rate=hit_rate,
        avg_alpha=avg_alpha,
        win_loss_ratio=wl_ratio,
        total_picks=total_picks,
        total_months=len(model_monthly),
        monthly_returns=monthly_df,
    )
