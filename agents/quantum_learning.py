"""
QuanTum Learning Layer — closes the loop between picks and outcomes.

SignalVerifier   Fills in what actually happened to past picks: forward return,
                 benchmark return over the same window, and the alpha between
                 them. Runs at the start of every pipeline.

WeightLearner    Measures each factor's information coefficient (rank
                 correlation between the factor score and subsequent alpha) and
                 nudges the factor weights toward what has been working. The
                 update is shrunk and capped so a thin sample cannot wreck a
                 model that is otherwise sound.

Weights live in the `learned_weights` table and are read by
RegimeDetector.get_weights. When the table is empty the hardcoded regime
weights are used unchanged, so a fresh install behaves exactly as before.
"""
import os
import sys
import logging
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from turso_db import get_db_smart

logging.getLogger("yfinance").setLevel(logging.CRITICAL)
logger = logging.getLogger(__name__)

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "quantum_data.db"
)

BENCHMARK = "^NSEI"

# Calendar days after which a signal is scored. Year and 5-year horizons are
# judged on a proxy window: waiting a full year before learning anything would
# make the loop useless.
VERIFY_WINDOW_DAYS = {"week": 7, "year": 30, "5years": 90}

# Factor name in the weights dict -> column in signal_log.
FACTOR_COLUMNS = {
    "value": "value_rank",
    "quality": "quality_rank",
    "momentum": "momentum_rank",
    "technical": "technical_rank",
    "volatility": "volatility_rank",
    "sector_growth": "sector_growth_rank",
    "news_catalyst": "news_catalyst_rank",
    "flow": "flow_rank",
    "earnings_revision": "earnings_rev_rank",
}

# Learning hyper-parameters.
MIN_SAMPLES = 30       # verified signals needed before weights move at all
LEARNING_RATE = 0.30   # share of the new IC-implied weights in the blend
MAX_WEIGHT = 0.40      # no single factor may dominate
MIN_IC_SAMPLES = 8     # per-factor minimum before its IC is trusted


def _db():
    return get_db_smart(DB_PATH)


def ensure_learning_tables():
    """Creates the learning tables and back-fills columns on older databases."""
    conn = _db()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS learned_weights (
                horizon TEXT,
                regime TEXT,
                factor TEXT,
                weight REAL,
                samples INTEGER,
                updated TEXT,
                PRIMARY KEY (horizon, regime, factor)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS weight_history (
                date TEXT,
                horizon TEXT,
                regime TEXT,
                factor TEXT,
                weight REAL,
                ic REAL,
                samples INTEGER
            )
        """)
        # Columns added after the first version of signal_log shipped.
        for column in ("sector_growth_rank", "news_catalyst_rank",
                       "flow_rank", "earnings_rev_rank"):
            try:
                conn.execute(f"ALTER TABLE signal_log ADD COLUMN {column} REAL")
            except Exception:
                pass
        try:
            conn.execute("ALTER TABLE signal_log ADD COLUMN regime TEXT")
        except Exception:
            pass
        conn.commit()
    except Exception as exc:
        logger.debug("learning table setup skipped: %s", exc)
    finally:
        conn.close()


# ── Verification ──────────────────────────────────────────────────────────────

class SignalVerifier:
    """Scores past signals against what the stock and the index actually did."""

    def run(self, progress_callback=None) -> dict:
        def update(msg):
            if progress_callback:
                progress_callback(msg)

        ensure_learning_tables()
        pending = self._pending()
        if pending.empty:
            return {"verified": 0, "pending": 0}

        tickers = sorted(pending["ticker"].unique())
        start = pd.to_datetime(pending["date"]).min() - timedelta(days=5)
        update(f"Verifying {len(pending)} past signals across {len(tickers)} stocks...")

        prices = self._price_history(tickers, start)
        benchmark = self._benchmark_history(start)
        if benchmark is None or benchmark.empty:
            return {"verified": 0, "pending": len(pending)}

        rows = []
        for _, sig in pending.iterrows():
            outcome = self._score_signal(sig, prices, benchmark)
            if outcome:
                rows.append(outcome)

        self._write(rows)
        update(f"Verified {len(rows)} signals")
        return {"verified": len(rows), "pending": len(pending) - len(rows)}

    def _pending(self) -> pd.DataFrame:
        conn = _db()
        try:
            rows = conn.execute(
                """SELECT id, date, ticker, horizon, close_at_signal
                   FROM signal_log WHERE verified = 0"""
            ).fetchall()
        except Exception:
            return pd.DataFrame()
        finally:
            conn.close()

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=["id", "date", "ticker", "horizon", "close_at_signal"])
        df = df.dropna(subset=["close_at_signal"])
        df = df[df["close_at_signal"] > 0]
        today = pd.Timestamp.today().normalize()
        due = df["horizon"].map(VERIFY_WINDOW_DAYS).fillna(30)
        df["due_date"] = pd.to_datetime(df["date"]) + pd.to_timedelta(due, unit="D")
        return df[df["due_date"] <= today].reset_index(drop=True)

    def _price_history(self, tickers: list[str], start) -> dict:
        history = {}
        symbols = [f"{t}.NS" for t in tickers]
        try:
            raw = yf.download(
                symbols, start=start.strftime("%Y-%m-%d"),
                progress=False, auto_adjust=True, threads=True,
                group_by="ticker",
            )
        except Exception as exc:
            logger.debug("verifier price download failed: %s", exc)
            return history

        for ticker, symbol in zip(tickers, symbols):
            try:
                series = raw[symbol]["Close"] if len(symbols) > 1 else raw["Close"]
                series = series.dropna()
                if not series.empty:
                    history[ticker] = series
            except Exception:
                continue
        return history

    def _benchmark_history(self, start):
        try:
            raw = yf.download(
                BENCHMARK, start=start.strftime("%Y-%m-%d"),
                progress=False, auto_adjust=True,
            )
            series = raw["Close"].dropna()
            if isinstance(series, pd.DataFrame):
                series = series.iloc[:, 0]
            return series
        except Exception as exc:
            logger.debug("benchmark download failed: %s", exc)
            return None

    @staticmethod
    def _at(series: pd.Series, when: pd.Timestamp):
        """First close on or after `when`, or None when the series ends first."""
        if series is None or series.empty:
            return None
        idx = series.index
        if getattr(idx, "tz", None) is not None:
            when = when.tz_localize(idx.tz)
        after = series[idx >= when]
        return float(after.iloc[0]) if not after.empty else None

    def _score_signal(self, sig, prices, benchmark) -> dict | None:
        series = prices.get(sig["ticker"])
        if series is None:
            return None

        due = pd.Timestamp(sig["due_date"])
        signal_date = pd.Timestamp(sig["date"])

        exit_price = self._at(series, due)
        bench_entry = self._at(benchmark, signal_date)
        bench_exit = self._at(benchmark, due)
        if exit_price is None or not bench_entry or bench_exit is None:
            return None

        entry = float(sig["close_at_signal"])
        stock_return = (exit_price - entry) / entry * 100
        bench_return = (bench_exit - bench_entry) / bench_entry * 100

        return {
            "id": int(sig["id"]),
            "actual_return": round(stock_return, 2),
            "benchmark_return": round(bench_return, 2),
            "alpha": round(stock_return - bench_return, 2),
            "verification_date": datetime.today().strftime("%Y-%m-%d"),
        }

    def _write(self, rows: list[dict]):
        if not rows:
            return
        conn = _db()
        try:
            for r in rows:
                conn.execute(
                    """UPDATE signal_log
                       SET actual_return = ?, benchmark_return = ?, alpha = ?,
                           verified = 1, verification_date = ?
                       WHERE id = ?""",
                    (r["actual_return"], r["benchmark_return"], r["alpha"],
                     r["verification_date"], r["id"]),
                )
            conn.commit()
        except Exception as exc:
            logger.debug("verifier write failed: %s", exc)
        finally:
            conn.close()


# ── Weight learning ───────────────────────────────────────────────────────────

class WeightLearner:
    """Moves factor weights toward the factors that actually produced alpha."""

    def run(self, base_weights: dict, horizon: str, regime: str,
            progress_callback=None) -> dict:
        """
        Returns the weights to store for this horizon and regime. Falls back to
        `base_weights` whenever the evidence is too thin to act on.
        """
        def update(msg):
            if progress_callback:
                progress_callback(msg)

        ensure_learning_tables()
        history = self._verified(horizon)
        if len(history) < MIN_SAMPLES:
            return dict(base_weights)

        ics = self._information_coefficients(history)
        if not ics:
            return dict(base_weights)

        learned = self._blend(base_weights, ics)
        self._save(learned, ics, horizon, regime, len(history))

        moved = sorted(
            ((f, learned[f] - base_weights.get(f, 0.0)) for f in learned),
            key=lambda kv: abs(kv[1]), reverse=True,
        )[:2]
        detail = ", ".join(f"{f} {d:+.2f}" for f, d in moved if abs(d) >= 0.01)
        update(f"Learned weights for {horizon} from {len(history)} signals"
               + (f" ({detail})" if detail else " (no material change)"))
        return learned

    def _verified(self, horizon: str) -> pd.DataFrame:
        columns = ["alpha"] + list(FACTOR_COLUMNS.values())
        conn = _db()
        try:
            rows = conn.execute(
                f"""SELECT {', '.join(columns)} FROM signal_log
                    WHERE verified = 1 AND horizon = ? AND alpha IS NOT NULL""",
                (horizon,),
            ).fetchall()
        except Exception:
            return pd.DataFrame()
        finally:
            conn.close()

        if not rows:
            return pd.DataFrame()
        return pd.DataFrame(rows, columns=columns).apply(pd.to_numeric, errors="coerce")

    def _information_coefficients(self, history: pd.DataFrame) -> dict:
        """Spearman rank correlation of each factor score against realised alpha."""
        ics = {}
        alpha = history["alpha"]
        for factor, column in FACTOR_COLUMNS.items():
            if column not in history.columns:
                continue
            pair = history[[column, "alpha"]].dropna()
            if len(pair) < MIN_IC_SAMPLES or pair[column].nunique() < 3:
                continue
            ic = pair[column].rank().corr(pair["alpha"].rank())
            if pd.notna(ic):
                ics[factor] = float(ic)
        return ics if len(ics) >= 2 else {}

    def _blend(self, base_weights: dict, ics: dict) -> dict:
        """
        Converts positive ICs into a weight vector, then shrinks toward the
        existing weights. Factors the base model switched off for this horizon
        stay off: a zero weight is a modelling decision, not a gap to fill.
        """
        active = {f: w for f, w in base_weights.items() if w > 0}
        if not active:
            return dict(base_weights)

        positive = {f: max(ics.get(f, 0.0), 0.0) for f in active}
        total_ic = sum(positive.values())
        if total_ic <= 0:
            return dict(base_weights)

        implied = {f: v / total_ic for f, v in positive.items()}

        blended = {}
        for factor, weight in base_weights.items():
            if weight <= 0:
                blended[factor] = weight
                continue
            target = implied.get(factor, 0.0)
            value = (1 - LEARNING_RATE) * weight + LEARNING_RATE * target
            blended[factor] = min(max(value, 0.0), MAX_WEIGHT)

        # Renormalise the active factors back to the base total.
        base_total = sum(w for w in base_weights.values() if w > 0)
        new_total = sum(w for f, w in blended.items() if base_weights.get(f, 0) > 0)
        if new_total > 0 and base_total > 0:
            scale = base_total / new_total
            for factor in blended:
                if base_weights.get(factor, 0) > 0:
                    blended[factor] = round(blended[factor] * scale, 4)
        return blended

    def _save(self, weights: dict, ics: dict, horizon: str, regime: str, samples: int):
        conn = _db()
        today = datetime.today().strftime("%Y-%m-%d")
        try:
            for factor, weight in weights.items():
                conn.execute(
                    """INSERT OR REPLACE INTO learned_weights
                       (horizon, regime, factor, weight, samples, updated)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (horizon, regime, factor, float(weight), samples, today),
                )
                conn.execute(
                    """INSERT INTO weight_history
                       (date, horizon, regime, factor, weight, ic, samples)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (today, horizon, regime, factor, float(weight),
                     float(ics.get(factor, 0.0)), samples),
                )
            conn.commit()
        except Exception as exc:
            logger.debug("weight save failed: %s", exc)
        finally:
            conn.close()


def load_learned_weights(horizon: str, regime: str) -> dict | None:
    """Weights previously learned for this horizon and regime, if any."""
    conn = _db()
    try:
        rows = conn.execute(
            """SELECT factor, weight FROM learned_weights
               WHERE horizon = ? AND regime = ?""",
            (horizon, regime),
        ).fetchall()
    except Exception:
        return None
    finally:
        conn.close()

    weights = {r[0]: float(r[1]) for r in rows if r and r[1] is not None}
    return weights or None


def accuracy_summary(horizon: str | None = None) -> dict | None:
    """Hit rate and average alpha across verified signals."""
    conn = _db()
    try:
        if horizon:
            row = conn.execute(
                """SELECT COUNT(*), SUM(CASE WHEN alpha > 0 THEN 1 ELSE 0 END),
                          AVG(alpha), AVG(actual_return)
                   FROM signal_log WHERE verified = 1 AND horizon = ?""",
                (horizon,),
            ).fetchone()
        else:
            row = conn.execute(
                """SELECT COUNT(*), SUM(CASE WHEN alpha > 0 THEN 1 ELSE 0 END),
                          AVG(alpha), AVG(actual_return)
                   FROM signal_log WHERE verified = 1"""
            ).fetchone()
    except Exception:
        return None
    finally:
        conn.close()

    if not row or not row[0]:
        return None
    return {
        "samples": int(row[0]),
        "beat_benchmark": int(row[1] or 0),
        "hit_rate": (row[1] or 0) / row[0],
        "avg_alpha": row[2] or 0.0,
        "avg_return": row[3] or 0.0,
    }
