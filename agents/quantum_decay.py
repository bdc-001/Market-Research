"""
QuanTum Alpha Decay Engine — Signal Validity & Exit Intelligence

Exit conditions (exit if ANY true):
  1. Score drop > 25% from entry score
  2. Price falls below 50 DMA
  3. Earnings revision turns negative (score drops below 40)
  4. Holding period > max_days (weekly: 10d, annual: 180d)
  5. Stop-loss hit (5% below entry)
  6. Target hit (10% above entry for weekly, 20% for annual)

Expected return half-life model:
  expected_alpha(t) = initial_alpha * exp(-lambda * t)

Signal half-lives (days):
  news_catalyst:   3
  technical:       7
  momentum:       14
  flow:           21
  earnings_rev:   45
  quality/value:  90

Tracks active_positions table in SQLite.
"""
import sqlite3
import math
import sys
import io
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

logging.getLogger("yfinance").setLevel(logging.CRITICAL)

logger = logging.getLogger(__name__)


SIGNAL_HALF_LIVES = {
    "news_catalyst": 3,
    "technical": 7,
    "momentum": 14,
    "flow": 21,
    "earnings_revision": 45,
    "quality": 90,
    "value": 90,
    "sector_growth": 180,
    "volatility": 30,
}

MAX_HOLDING_DAYS = {
    "week": 10,
    "year": 180,
    "5years": 365 * 3,
}

STOP_LOSS_PCT = {"week": 5.0, "year": 8.0, "5years": 15.0}
TARGET_PCT = {"week": 10.0, "year": 20.0, "5years": 50.0}
SCORE_DROP_THRESHOLD = 0.25  # 25% score drop triggers exit


class AlphaDecayModel:

    def __init__(self, db_path: str = "quantum_data.db"):
        self.db_path = db_path
        self._ensure_table()

    def _get_db(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _ensure_table(self):
        try:
            conn = self._get_db()
            conn.execute("""CREATE TABLE IF NOT EXISTS active_positions (
                ticker TEXT,
                horizon TEXT,
                entry_date TEXT,
                entry_price REAL,
                entry_score REAL,
                dominant_factor TEXT,
                stop_loss REAL,
                target_price REAL,
                status TEXT DEFAULT 'active',
                exit_date TEXT,
                exit_price REAL,
                exit_reason TEXT,
                pnl_pct REAL,
                PRIMARY KEY (ticker, horizon, entry_date)
            )""")
            # Migrate old tables missing newer columns
            existing = {
                r[1] for r in conn.execute("PRAGMA table_info(active_positions)").fetchall()
            }
            for col, ctype, default in [
                ("entry_score", "REAL", "0"),
                ("dominant_factor", "TEXT", "'momentum'"),
                ("stop_loss", "REAL", "0"),
                ("target_price", "REAL", "0"),
            ]:
                if col not in existing:
                    conn.execute(
                        f"ALTER TABLE active_positions ADD COLUMN {col} {ctype} DEFAULT {default}"
                    )
            conn.commit()
            conn.close()
        except Exception:
            pass

    def register_signals(
        self, scored: pd.DataFrame, horizon: str, top_n: int = 10,
    ) -> list[dict]:
        conn = self._get_db()
        today = datetime.today().strftime("%Y-%m-%d")
        registered = []

        sl_pct = STOP_LOSS_PCT.get(horizon, 5.0)
        tgt_pct = TARGET_PCT.get(horizon, 10.0)

        for _, row in scored.head(top_n).iterrows():
            ticker = row["ticker"]
            close = row.get("close", 0)
            score = row.get("composite_score", 0)

            # Determine dominant factor
            factor_scores = {
                "news_catalyst": row.get("news_catalyst_score", 0),
                "technical": row.get("technical_score", 0),
                "momentum": row.get("momentum_score", 0),
                "flow": row.get("flow_score", 0),
                "earnings_revision": row.get("earnings_rev_score", 0),
                "quality": row.get("quality_score", 0),
                "value": row.get("value_score", 0),
            }
            dominant = max(factor_scores, key=factor_scores.get)

            stop_loss = close * (1 - sl_pct / 100)
            target = close * (1 + tgt_pct / 100)

            try:
                conn.execute(
                    """INSERT OR IGNORE INTO active_positions
                       (ticker, horizon, entry_date, entry_price, entry_score,
                        dominant_factor, stop_loss, target_price, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                    (ticker, horizon, today, close, score, dominant, stop_loss, target),
                )
                registered.append({
                    "ticker": ticker, "entry_price": close,
                    "dominant_factor": dominant,
                    "half_life_days": SIGNAL_HALF_LIVES.get(dominant, 14),
                })
            except Exception:
                continue

        conn.commit()
        conn.close()
        return registered

    def compute_decay(
        self, current_scores: dict[str, float] | None = None,
        progress_callback=None,
    ) -> list[dict]:
        """
        For all active positions, compute signal decay and check exit conditions.

        current_scores: {ticker: current_composite_score} for score-drop detection
        """
        conn = self._get_db()

        try:
            actives = conn.execute(
                "SELECT * FROM active_positions WHERE status = 'active'"
            ).fetchall()
        except Exception:
            conn.close()
            return []

        if not actives:
            conn.close()
            return []

        cols = [desc[0] for desc in conn.execute(
            "SELECT * FROM active_positions LIMIT 1"
        ).description]

        if progress_callback:
            progress_callback(f"Checking decay for {len(actives)} active positions...")

        results = []
        today = datetime.today()

        # Batch fetch current prices + 50 DMA
        tickers = list(set(row[cols.index("ticker")] for row in actives if cols.index("ticker") < len(row)))
        symbols = [f"{t}.NS" for t in tickers]
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            price_data = yf.download(symbols, period="3mo", interval="1d",
                                     progress=False, auto_adjust=True, group_by="ticker")
        except Exception:
            price_data = None
        finally:
            sys.stderr = old_stderr

        for row in actives:
            pos = dict(zip(cols, row))
            ticker = pos.get("ticker", "")
            horizon = pos.get("horizon", "week")
            entry_date = datetime.strptime(pos.get("entry_date", today.strftime("%Y-%m-%d")), "%Y-%m-%d")
            entry_price = pos.get("entry_price") or 0
            entry_score = pos.get("entry_score") or 0
            dominant = pos.get("dominant_factor") or "momentum"
            stop_loss = pos.get("stop_loss") or 0
            target_price = pos.get("target_price") or 0

            days_held = (today - entry_date).days
            half_life = SIGNAL_HALF_LIVES.get(dominant, 14)
            max_days = MAX_HOLDING_DAYS.get(horizon, 180)

            # Exponential decay
            signal_strength = 100 * math.pow(0.5, days_held / half_life)

            # Get current price + 50 DMA
            current_price = entry_price
            sma_50 = None
            sym = f"{ticker}.NS"

            if price_data is not None:
                try:
                    if len(symbols) == 1:
                        close_series = price_data["Close"].squeeze().dropna()
                    else:
                        close_series = (
                            price_data[sym]["Close"].dropna()
                            if sym in price_data.columns.get_level_values(0)
                            else pd.Series(dtype=float)
                        )

                    if len(close_series) > 0:
                        current_price = float(close_series.iloc[-1])
                    if len(close_series) >= 50:
                        sma_50 = float(close_series.tail(50).mean())
                except Exception:
                    pass

            pnl_pct = (current_price / entry_price - 1) * 100 if entry_price > 0 else 0

            # ── Exit Conditions ────────────────────────────────────────────
            exit_signals = []

            # 1. Score drop > 25%
            if current_scores and ticker in current_scores:
                current_score = current_scores[ticker]
                if entry_score > 0:
                    score_drop = (entry_score - current_score) / entry_score
                    if score_drop > SCORE_DROP_THRESHOLD:
                        exit_signals.append(f"score_drop_{score_drop:.0%}")

            # 2. Price below 50 DMA
            if sma_50 is not None and current_price < sma_50:
                pct_below = (sma_50 - current_price) / sma_50 * 100
                if pct_below > 2:  # Must be meaningfully below (not noise)
                    exit_signals.append(f"below_50dma_{pct_below:.1f}%")

            # 3. Holding period exceeded
            if days_held > max_days:
                exit_signals.append(f"max_days_{days_held}d>{max_days}d")

            # 4. Stop-loss hit
            if current_price <= stop_loss:
                exit_signals.append("stop_loss")

            # 5. Target hit
            if current_price >= target_price:
                exit_signals.append("target_hit")

            # 6. Signal expired (strength < 10%)
            if signal_strength < 10:
                exit_signals.append("signal_expired")

            should_exit = len(exit_signals) > 0
            primary_exit = exit_signals[0] if exit_signals else None

            # Expected remaining alpha (half-life model)
            expected_alpha = signal_strength / 100 * pnl_pct if pnl_pct > 0 else 0

            result = {
                "ticker": ticker,
                "horizon": horizon,
                "entry_date": pos["entry_date"],
                "entry_price": entry_price,
                "entry_score": entry_score,
                "current_price": current_price,
                "pnl_pct": round(pnl_pct, 2),
                "days_held": days_held,
                "max_days": max_days,
                "dominant_factor": dominant,
                "half_life": half_life,
                "signal_strength": round(signal_strength, 1),
                "sma_50": round(sma_50, 2) if sma_50 else None,
                "expected_alpha": round(expected_alpha, 2),
                "exit_signals": exit_signals,
                "should_exit": should_exit,
                "exit_reason": primary_exit,
            }

            if should_exit:
                conn.execute(
                    """UPDATE active_positions
                       SET status='exited', exit_date=?, exit_price=?,
                           exit_reason=?, pnl_pct=?
                       WHERE ticker=? AND horizon=? AND entry_date=? AND status='active'""",
                    (today.strftime("%Y-%m-%d"), current_price,
                     ", ".join(exit_signals), round(pnl_pct, 2),
                     ticker, horizon, pos["entry_date"]),
                )

            results.append(result)

        conn.commit()
        conn.close()
        return results

    def get_active_summary(self) -> dict:
        conn = self._get_db()

        try:
            active_count = conn.execute(
                "SELECT COUNT(*) FROM active_positions WHERE status='active'"
            ).fetchone()[0]
        except Exception:
            active_count = 0

        try:
            stats = conn.execute(
                """SELECT COUNT(*),
                          SUM(CASE WHEN pnl_pct > 0 THEN 1 ELSE 0 END),
                          AVG(pnl_pct),
                          AVG(CASE WHEN pnl_pct > 0 THEN pnl_pct END),
                          AVG(CASE WHEN pnl_pct <= 0 THEN pnl_pct END)
                   FROM active_positions WHERE status='exited' AND pnl_pct IS NOT NULL"""
            ).fetchone()
        except Exception:
            stats = (0, 0, 0, 0, 0)

        try:
            exited = conn.execute(
                """SELECT ticker, horizon, entry_date, exit_date, pnl_pct, exit_reason
                   FROM active_positions WHERE status='exited'
                   ORDER BY exit_date DESC LIMIT 20"""
            ).fetchall()
        except Exception:
            exited = []

        conn.close()

        total_exited = stats[0] if stats else 0
        wins = stats[1] if stats else 0

        return {
            "active_positions": active_count,
            "total_exited": total_exited,
            "wins": wins,
            "hit_rate": (wins / total_exited) if total_exited > 0 else 0,
            "avg_pnl": stats[2] if stats and stats[2] is not None else 0,
            "avg_win": stats[3] if stats and stats[3] is not None else 0,
            "avg_loss": stats[4] if stats and stats[4] is not None else 0,
            "recent_exits": [
                {"ticker": r[0], "horizon": r[1], "entry": r[2],
                 "exit": r[3], "pnl": r[4], "reason": r[5]}
                for r in (exited or [])
            ],
        }
