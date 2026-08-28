"""
Episode instrumentation — observation only.

Writes UUID episodes and insert-only agent_predictions. Does not score,
route, or change weights. Existing signal_log writes stay on the caller.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta

from agents.prediction_format import UNKNOWN_PREDICTION, decision_from_editor, dumps
from agents.skill_loader import skill_version_label
from turso_db import get_db_smart

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "quantum_data.db"
)

AGENT_VERSION_COUNCIL = "council-v1"
AGENT_VERSION_QUANTUM = "quantum-v1"
COUNCIL_HORIZON_DAYS = 30
COUNCIL_HORIZON = "30d"
QUANTUM_HORIZON_DAYS = {"week": 7, "year": 30, "5years": 90}
QUANTUM_TOP_N = 10

_TABLES_READY = False


def _db():
    return get_db_smart(DB_PATH)


def ensure_episode_tables():
    global _TABLES_READY
    conn = _db()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS episodes (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                ticker TEXT NOT NULL,
                run_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                horizon_days INTEGER,
                horizon TEXT,
                regime TEXT,
                evaluation_due_at TEXT,
                evaluated_at TEXT,
                final_decision TEXT,
                entry_price REAL,
                signals_json TEXT,
                data_snapshot_json TEXT,
                actual_return REAL,
                benchmark_return REAL,
                alpha REAL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_predictions (
                id TEXT PRIMARY KEY,
                episode_id TEXT NOT NULL,
                agent_name TEXT NOT NULL,
                agent_version TEXT,
                skill_version TEXT,
                thesis TEXT,
                confidence REAL,
                prediction_direction TEXT,
                recommendation TEXT,
                horizon_days INTEGER,
                evidence_json TEXT,
                risks_json TEXT,
                key_assumption TEXT,
                reasoning_summary TEXT,
                raw_output TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS episode_horizon_outcomes (
                id TEXT PRIMARY KEY,
                episode_id TEXT NOT NULL,
                horizon_days INTEGER NOT NULL,
                status TEXT NOT NULL,
                entry_price REAL,
                exit_price REAL,
                entry_date TEXT,
                exit_date TEXT,
                absolute_return REAL,
                nifty_return REAL,
                relative_return REAL,
                max_gain REAL,
                max_drawdown REAL,
                evaluated_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_outcomes (
                id TEXT PRIMARY KEY,
                episode_id TEXT NOT NULL,
                agent TEXT NOT NULL,
                horizon_days INTEGER NOT NULL,
                actual_return REAL,
                relative_return REAL,
                prediction_correct INTEGER,
                decision_quality TEXT,
                confidence_calibration REAL,
                failure_type TEXT,
                evaluated_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS lessons (
                id TEXT PRIMARY KEY,
                agent TEXT,
                event_type TEXT,
                regime TEXT,
                horizon TEXT,
                lesson TEXT,
                evidence TEXT,
                sample_size INTEGER,
                validated INTEGER
            )
        """)
        _migrate_episode_columns(conn)
        for sql in (
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_horizon_outcomes_ep_hz "
            "ON episode_horizon_outcomes(episode_id, horizon_days)",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_outcomes_ep_ag_hz "
            "ON agent_outcomes(episode_id, agent, horizon_days)",
        ):
            try:
                conn.execute(sql)
            except Exception:
                pass
        conn.commit()
        _TABLES_READY = True
    except Exception as exc:
        logger.debug("episode table setup skipped: %s", exc)
    finally:
        conn.close()


def _migrate_episode_columns(conn):
    """Add columns to existing tables. Never drop or overwrite prediction fields."""
    for table, column, typ in (
        ("episodes", "event_id", "TEXT"),
        ("episodes", "entry_date", "TEXT"),
        ("episodes", "event_type", "TEXT"),
        ("agent_predictions", "recommendation", "TEXT"),
    ):
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {typ}")
        except Exception:
            pass


def split_agent_calls(parsed: dict | None, agent_name: str = "") -> tuple:
    """
    Keep three questions separate. Never copy one field onto another.

    prediction_direction — was the agent right about price direction?
    recommendation — would the agent buy / watch / reject?
    episodes.final_decision — what did the Council Editor decide?
    """
    data = parsed or {}
    direction = data.get("prediction_direction")
    if direction is not None:
        direction = str(direction).lower().strip()
        if direction not in {"positive", "negative", "flat"}:
            direction = None
    rec = data.get("recommendation")
    if rec is None:
        rec = data.get("final_decision")
    if rec is not None:
        rec = str(rec).lower().replace(" ", "_").strip()
        rec = {
            "avoid": "reject",
            "sell": "reject",
            "hold": "watch",
            "strong_buy": "buy",
            "accumulate": "buy",
        }.get(rec, rec)
        if rec not in {"buy", "watch", "reject"}:
            rec = None
    return direction, rec


def _row_dict(cursor) -> dict | None:
    row = cursor.fetchone()
    if row is None:
        return None
    cols = [d[0] for d in (cursor.description or [])]
    return dict(zip(cols, row))


def _row_dicts(cursor) -> list[dict]:
    cols = [d[0] for d in (cursor.description or [])]
    return [dict(zip(cols, r)) for r in cursor.fetchall()]


def fetch_episode(episode_id: str) -> dict | None:
    ensure_episode_tables()
    conn = _db()
    try:
        return _row_dict(conn.execute(
            "SELECT * FROM episodes WHERE id = ?", (episode_id,),
        ))
    finally:
        conn.close()


def fetch_episode_by_ticker(ticker: str, source: str = "discovery_council") -> dict | None:
    ensure_episode_tables()
    conn = _db()
    try:
        return _row_dict(conn.execute(
            """SELECT * FROM episodes
               WHERE ticker = ? AND source = ?
               ORDER BY created_at ASC""",
            (ticker.upper().strip(), source),
        ))
    finally:
        conn.close()


def fetch_council_event_ids() -> set[str]:
    ensure_episode_tables()
    conn = _db()
    try:
        rows = conn.execute(
            "SELECT event_id FROM episodes WHERE source = 'discovery_council' AND event_id IS NOT NULL AND event_id != ''"
        ).fetchall()
        return {str(r[0]) for r in rows if r and r[0]}
    finally:
        conn.close()


def fetch_predictions(episode_id: str) -> list[dict]:
    ensure_episode_tables()
    conn = _db()
    try:
        return _row_dicts(conn.execute(
            """SELECT * FROM agent_predictions
               WHERE episode_id = ?
               ORDER BY created_at ASC""",
            (episode_id,),
        ))
    finally:
        conn.close()


def list_discovery_council_episodes() -> list[dict]:
    ensure_episode_tables()
    conn = _db()
    try:
        return _row_dicts(conn.execute(
            """SELECT * FROM episodes
               WHERE source = 'discovery_council'
               ORDER BY created_at ASC"""
        ))
    finally:
        conn.close()


def fetch_horizon_outcomes(episode_id: str) -> list[dict]:
    ensure_episode_tables()
    conn = _db()
    try:
        return _row_dicts(conn.execute(
            """SELECT * FROM episode_horizon_outcomes
               WHERE episode_id = ?
               ORDER BY horizon_days ASC""",
            (episode_id,),
        ))
    finally:
        conn.close()


def fetch_agent_outcomes(episode_id: str) -> list[dict]:
    ensure_episode_tables()
    conn = _db()
    try:
        return _row_dicts(conn.execute(
            """SELECT * FROM agent_outcomes
               WHERE episode_id = ?
               ORDER BY horizon_days ASC, agent ASC""",
            (episode_id,),
        ))
    finally:
        conn.close()


def patch_episode_identity(
    episode_id: str,
    *,
    event_id: str | None = None,
    entry_date: str | None = None,
    entry_price=None,
    final_decision: str | None = None,
    event_type: str | None = None,
) -> None:
    """Fill missing identity fields. Never overwrites a non-empty value."""
    ensure_episode_tables()
    row = fetch_episode(episode_id)
    if not row:
        return
    conn = _db()
    try:
        if event_id and not (row.get("event_id") or "").strip():
            conn.execute("UPDATE episodes SET event_id = ? WHERE id = ?", (event_id, episode_id))
        if entry_date and not (row.get("entry_date") or "").strip():
            conn.execute("UPDATE episodes SET entry_date = ? WHERE id = ?", (entry_date, episode_id))
        if entry_price is not None and row.get("entry_price") in (None, ""):
            conn.execute(
                "UPDATE episodes SET entry_price = ? WHERE id = ?",
                (_float_or_none(entry_price), episode_id),
            )
        if final_decision and not (row.get("final_decision") or "").strip():
            conn.execute(
                "UPDATE episodes SET final_decision = ? WHERE id = ?",
                (final_decision, episode_id),
            )
        if event_type and not (row.get("event_type") or "").strip():
            conn.execute(
                "UPDATE episodes SET event_type = ? WHERE id = ?",
                (event_type, episode_id),
            )
        conn.commit()
    finally:
        conn.close()


def fill_missing_recommendations(episode_id: str, fallback: dict | None = None) -> int:
    """Set recommendation from parsed output. Never changes prediction_direction."""
    from agents.prediction_format import parse_dual_output

    ensure_episode_tables()
    preds = fetch_predictions(episode_id)
    n = 0
    conn = _db()
    try:
        for pred in preds:
            if (pred.get("recommendation") or "").strip():
                continue
            parsed = {}
            raw = pred.get("raw_output") or ""
            if raw:
                try:
                    _, parsed = parse_dual_output(raw)
                except Exception:
                    parsed = {}
            _, rec = split_agent_calls(parsed, pred.get("agent_name") or "")
            if not rec and fallback:
                rec = fallback.get(pred.get("agent_name") or "")
            if not rec:
                continue
            conn.execute(
                "UPDATE agent_predictions SET recommendation = ? WHERE id = ?",
                (rec, pred["id"]),
            )
            n += 1
        conn.commit()
    finally:
        conn.close()
    return n


def upsert_horizon_outcome(row: dict) -> None:
    ensure_episode_tables()
    conn = _db()
    try:
        existing = conn.execute(
            "SELECT id FROM episode_horizon_outcomes WHERE episode_id = ? AND horizon_days = ?",
            (row["episode_id"], int(row["horizon_days"])),
        ).fetchone()
        fields = (
            "status", "entry_price", "exit_price", "entry_date", "exit_date",
            "absolute_return", "nifty_return", "relative_return",
            "max_gain", "max_drawdown", "evaluated_at",
        )
        values = tuple(row.get(k) for k in fields)
        if existing:
            conn.execute(
                """UPDATE episode_horizon_outcomes SET
                   status=?, entry_price=?, exit_price=?, entry_date=?, exit_date=?,
                   absolute_return=?, nifty_return=?, relative_return=?,
                   max_gain=?, max_drawdown=?, evaluated_at=?
                   WHERE id=?""",
                values + (existing[0],),
            )
        else:
            conn.execute(
                """INSERT INTO episode_horizon_outcomes
                   (id, episode_id, horizon_days, status, entry_price, exit_price,
                    entry_date, exit_date, absolute_return, nifty_return,
                    relative_return, max_gain, max_drawdown, evaluated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (str(uuid.uuid4()), row["episode_id"], int(row["horizon_days"])) + values,
            )
        conn.commit()
    finally:
        conn.close()


def upsert_agent_outcome(row: dict) -> None:
    ensure_episode_tables()
    conn = _db()
    try:
        existing = conn.execute(
            "SELECT id FROM agent_outcomes WHERE episode_id = ? AND agent = ? AND horizon_days = ?",
            (row["episode_id"], row["agent"], int(row["horizon_days"])),
        ).fetchone()
        fields = (
            "actual_return", "relative_return", "prediction_correct",
            "decision_quality", "confidence_calibration", "failure_type",
            "evaluated_at",
        )
        values = tuple(row.get(k) for k in fields)
        if existing:
            conn.execute(
                """UPDATE agent_outcomes SET
                   actual_return=?, relative_return=?, prediction_correct=?,
                   decision_quality=?, confidence_calibration=?, failure_type=?,
                   evaluated_at=?
                   WHERE id=?""",
                values + (existing[0],),
            )
        else:
            conn.execute(
                """INSERT INTO agent_outcomes
                   (id, episode_id, agent, horizon_days, actual_return,
                    relative_return, prediction_correct, decision_quality,
                    confidence_calibration, failure_type, evaluated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (str(uuid.uuid4()), row["episode_id"], row["agent"],
                 int(row["horizon_days"])) + values,
            )
        conn.commit()
    finally:
        conn.close()


def insert_episode_if_missing(
    *,
    episode_id: str,
    source: str,
    ticker: str,
    run_id: str,
    horizon_days: int,
    horizon: str,
    regime: str,
    final_decision: str,
    entry_price,
    event_id: str,
    entry_date: str,
    signals: dict | None = None,
) -> bool:
    """Insert a known episode id only if it does not already exist. Returns True if inserted."""
    ensure_episode_tables()
    if fetch_episode(episode_id):
        return False
    created = _now()
    due = created + timedelta(days=int(horizon_days or 30))
    conn = _db()
    try:
        conn.execute(
            """INSERT INTO episodes
               (id, source, ticker, run_id, created_at, horizon_days, horizon,
                regime, evaluation_due_at, evaluated_at, final_decision,
                entry_price, signals_json, data_snapshot_json, event_id, entry_date)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?)""",
            (
                episode_id, source, ticker, run_id, _iso(created),
                int(horizon_days), horizon, regime or "", _iso(due),
                final_decision, _float_or_none(entry_price),
                dumps(signals or {}), dumps({}),
                event_id or "", entry_date or created.strftime("%Y-%m-%d"),
            ),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def insert_prediction_if_missing(episode_id: str, pred: dict) -> bool:
    """Insert one agent prediction if that agent has no row on this episode."""
    ensure_episode_tables()
    agent_name = pred.get("agent_name") or "unknown"
    conn = _db()
    try:
        existing = conn.execute(
            "SELECT id FROM agent_predictions WHERE episode_id = ? AND agent_name = ?",
            (episode_id, agent_name),
        ).fetchone()
        if existing:
            return False
        parsed = pred.get("parsed") or dict(UNKNOWN_PREDICTION)
        direction, recommendation = split_agent_calls(parsed, agent_name)
        if pred.get("recommendation"):
            recommendation = pred["recommendation"]
        if pred.get("prediction_direction"):
            direction = pred["prediction_direction"]
        conn.execute(
            """INSERT INTO agent_predictions
               (id, episode_id, agent_name, agent_version, skill_version,
                thesis, confidence, prediction_direction, recommendation,
                horizon_days, evidence_json, risks_json, key_assumption,
                reasoning_summary, raw_output, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()), episode_id, agent_name,
                pred.get("agent_version") or "",
                pred.get("skill_version") or "none",
                parsed.get("thesis") or pred.get("thesis") or "unknown",
                pred.get("confidence", parsed.get("confidence")),
                direction,
                recommendation,
                parsed.get("horizon_days") or 30,
                dumps({"ids": parsed.get("evidence_ids") or pred.get("evidence_ids") or []}),
                dumps(parsed.get("risks") or []),
                parsed.get("key_assumption") or "",
                parsed.get("reasoning_summary") or "",
                pred.get("raw_output") or "",
                _iso(_now()),
            ),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def _now() -> datetime:
    return datetime.now()


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def write_episode(
    *,
    source: str,
    ticker: str,
    run_id: str,
    horizon_days: int,
    horizon: str,
    regime: str = "",
    final_decision: str | None = None,
    entry_price=None,
    signals=None,
    snapshot=None,
    predictions: list[dict] | None = None,
    event_id: str = "",
    entry_date: str | None = None,
    event_type: str = "",
) -> str | None:
    """Insert one episode and its prediction rows. Returns episode id."""
    ensure_episode_tables()
    created = _now()
    episode_id = str(uuid.uuid4())
    due = created + timedelta(days=int(horizon_days or 30))
    conn = _db()
    try:
        conn.execute(
            """INSERT INTO episodes
               (id, source, ticker, run_id, created_at, horizon_days, horizon,
                regime, evaluation_due_at, evaluated_at, final_decision,
                entry_price, signals_json, data_snapshot_json, event_id, entry_date,
                event_type)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?)""",
            (
                episode_id, source, ticker, run_id, _iso(created),
                int(horizon_days), horizon, regime or "", _iso(due),
                final_decision, _float_or_none(entry_price),
                dumps(signals or {}), dumps(snapshot or {}),
                event_id or "", entry_date or created.strftime("%Y-%m-%d"),
                event_type or "",
            ),
        )
        created_s = _iso(created)
        for pred in predictions or []:
            parsed = pred.get("parsed") or dict(UNKNOWN_PREDICTION)
            agent_name = pred.get("agent_name") or "unknown"
            direction, recommendation = split_agent_calls(parsed, agent_name)
            conn.execute(
                """INSERT INTO agent_predictions
                   (id, episode_id, agent_name, agent_version, skill_version,
                    thesis, confidence, prediction_direction, recommendation,
                    horizon_days, evidence_json, risks_json, key_assumption,
                    reasoning_summary, raw_output, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4()), episode_id,
                    agent_name,
                    pred.get("agent_version") or "",
                    pred.get("skill_version") or "none",
                    parsed.get("thesis") or "unknown",
                    parsed.get("confidence"),
                    direction,
                    recommendation,
                    parsed.get("horizon_days") or horizon_days,
                    dumps({
                        "facts": parsed.get("evidence") or [],
                        "ids": parsed.get("evidence_ids") or [],
                        "invalid_ids": parsed.get("invalid_evidence_ids") or [],
                    }),
                    dumps(parsed.get("risks") or []),
                    parsed.get("key_assumption") or "",
                    parsed.get("reasoning_summary") or "",
                    pred.get("raw_output") or "",
                    created_s,
                ),
            )
        conn.commit()
        return episode_id
    except Exception as exc:
        logger.debug("episode write failed for %s %s: %s", source, ticker, exc)
        return None
    finally:
        conn.close()


def write_council_episode(
    ticker: str,
    run_id: str,
    agents: dict,
    regime: str = "",
    evidence: dict | None = None,
) -> str | None:
    """
    `agents` maps agent_name -> object with last_raw / last_parsed
    (and optional last_snapshot on the technical agent).
    Observation only: stores the canonical editor decision and the evidence
    package snapshot. Does not change how the council decided.
    """
    editor = agents.get("editor")
    parsed_editor = getattr(editor, "last_parsed", None) or dict(UNKNOWN_PREDICTION)
    prose = getattr(editor, "last_prose", "") or ""
    thesis = parsed_editor.get("investment_thesis") or {}
    prediction = parsed_editor.get("prediction") or {}
    direction = prediction.get("direction") or parsed_editor.get("prediction_direction")
    thirty_day_decision = {
        "positive": "buy",
        "negative": "avoid",
        "flat": "watch",
    }.get(direction, "watch")

    technical = agents.get("technical")
    tech_snapshot = getattr(technical, "last_snapshot", None) or {}
    canonical = (evidence or {}).get("canonical") or {}
    entry_price = canonical.get("price") or tech_snapshot.get("price")

    predictions = []
    for name, agent in agents.items():
        predictions.append({
            "agent_name": name,
            "agent_version": AGENT_VERSION_COUNCIL,
            "skill_version": "none",
            "parsed": getattr(agent, "last_parsed", None) or dict(UNKNOWN_PREDICTION),
            "raw_output": getattr(agent, "last_raw", "") or "",
        })

    snapshot = {
        "technical": tech_snapshot,
        "evidence": evidence or {},
        "canonical_price": canonical,
        "canonical_decision": parsed_editor,
        "prediction": prediction,
        "investment_thesis": thesis,
        "memo_verdict": parsed_editor.get("final_decision") or decision_from_editor(parsed_editor, prose),
    }

    return write_episode(
        source="council",
        ticker=ticker,
        run_id=run_id,
        horizon_days=COUNCIL_HORIZON_DAYS,
        horizon=COUNCIL_HORIZON,
        regime=regime,
        final_decision=thirty_day_decision,
        entry_price=entry_price,
        signals=tech_snapshot,
        snapshot=snapshot,
        predictions=predictions,
    )


def write_quantum_topn(
    scored,
    horizon: str,
    regime: str,
    run_id: str,
    news_by_symbol: dict | None = None,
    portfolio=None,
) -> int:
    """One episode per top-N ticker. Same N as signal_log. Does not touch signal_log."""
    if scored is None or getattr(scored, "empty", True):
        return 0

    news_by_symbol = news_by_symbol or {}
    news_skill = skill_version_label("news_extractor")
    horizon_days = QUANTUM_HORIZON_DAYS.get(horizon, 30)
    written = 0

    from agents.quantum_portfolio import audit_constraints
    audit = audit_constraints(portfolio)

    try:
        rows = scored.head(QUANTUM_TOP_N)
    except Exception:
        return 0

    for _, row in rows.iterrows():
        ticker = str(row.get("ticker") or "")
        if not ticker:
            continue
        news_item = news_by_symbol.get(ticker)
        predictions = _quantum_predictions(row, news_item, horizon_days, news_skill)
        allowed = _truthy(row.get("entry_allowed"))
        decision = "buy" if allowed else "watch"
        signals = _row_subset(row, [
            "rsi", "sma50", "sma200", "macd", "macd_signal",
            "composite_score", "factor_agreement", "conviction",
            "entry_allowed", "entry_score", "entry_status",
            "news_catalyst", "event_type",
        ])
        snapshot = _row_subset(row, [
            "close", "pe_ratio", "pb_ratio", "roe", "debt_equity",
            "profit_margin", "rsi", "sma50", "sma200", "macd",
            "return_1m", "return_3m", "return_6m", "return_12m",
            "volatility_20d", "volume_ratio", "market_cap",
            "earnings_yield", "dividend_yield",
            "value_score", "quality_score", "momentum_score",
            "technical_score", "volatility_score", "sector_growth_score",
            "news_catalyst_score", "flow_score", "earnings_rev_score",
            "composite_score", "conviction",
        ])
        sector = str(row.get("sector") or "")
        ticker_violations = [
            v for v in audit.get("violations") or []
            if v.get("ticker") == ticker or v.get("sector") == sector
        ]
        snapshot["portfolio"] = {
            "stock_cap_pct": audit.get("stock_cap_pct"),
            "sector_cap_pct": audit.get("sector_cap_pct"),
            "weight_pct": (audit.get("weights") or {}).get(ticker),
            "sector": sector,
            "sector_weight_pct": (audit.get("sector_weights") or {}).get(sector),
            "constraint_violations": ticker_violations,
            "run_constraint_violations": audit.get("violations") or [],
        }
        eid = write_episode(
            source="quantum",
            ticker=ticker,
            run_id=run_id,
            horizon_days=horizon_days,
            horizon=horizon,
            regime=regime or "",
            final_decision=decision,
            entry_price=row.get("close"),
            signals=signals,
            snapshot=snapshot,
            predictions=predictions,
        )
        if eid:
            written += 1
    return written


def attach_verified_signal_log_outcomes() -> int:
    """
    Copy already-verified signal_log outcomes onto matching unevaluated
    quantum episodes. Does not recompute returns or change windows.
    """
    ensure_episode_tables()
    conn = _db()
    attached = 0
    now = _iso(_now())
    try:
        episodes = conn.execute(
            """SELECT id, ticker, horizon, created_at FROM episodes
               WHERE source = 'quantum' AND evaluated_at IS NULL"""
        ).fetchall()
        for eid, ticker, horizon, created_at in episodes or []:
            day = str(created_at)[:10]
            row = conn.execute(
                """SELECT actual_return, benchmark_return, alpha, verification_date
                   FROM signal_log
                   WHERE ticker = ? AND horizon = ? AND date = ? AND verified = 1
                   ORDER BY id DESC LIMIT 1""",
                (ticker, horizon, day),
            ).fetchone()
            if not row:
                continue
            evaluated = row[3] or now
            conn.execute(
                """UPDATE episodes
                   SET actual_return = ?, benchmark_return = ?, alpha = ?,
                       evaluated_at = ?
                   WHERE id = ? AND evaluated_at IS NULL""",
                (row[0], row[1], row[2], evaluated, eid),
            )
            attached += 1
        conn.commit()
    except Exception as exc:
        logger.debug("episode outcome attach skipped: %s", exc)
    finally:
        conn.close()
    return attached


def _quantum_predictions(row, news_item, horizon_days: int, news_skill: str) -> list[dict]:
    score = _float_or_none(row.get("composite_score")) or 0.0
    if score > 60:
        thesis, direction = "bullish", "positive"
    elif score < 40:
        thesis, direction = "bearish", "negative"
    else:
        thesis, direction = "neutral", "flat"

    factor_parsed = {
        "thesis": thesis,
        "confidence": max(0.0, min(1.0, score / 100.0)),
        "prediction_direction": direction,
        "horizon_days": horizon_days,
        "evidence": [f"composite_score={score:.1f}"],
        "risks": [],
        "key_assumption": f"conviction={row.get('conviction')}",
        "reasoning_summary": (
            f"Factor composite {score:.1f} with agreement "
            f"{row.get('factor_agreement')}."
        ),
        "final_decision": None,
    }
    factor_raw = dumps(_row_subset(row, [
        "ticker", "composite_score", "value_score", "quality_score",
        "momentum_score", "technical_score", "volatility_score",
        "sector_growth_score", "news_catalyst_score", "flow_score",
        "earnings_rev_score", "factor_agreement", "conviction",
    ]))

    allowed = _truthy(row.get("entry_allowed"))
    entry_parsed = {
        "thesis": "bullish" if allowed else "neutral",
        "confidence": _float_or_none(row.get("entry_score")),
        "prediction_direction": "positive" if allowed else "flat",
        "horizon_days": horizon_days,
        "evidence": [str(row.get("entry_status") or "")],
        "risks": [],
        "key_assumption": "entry_allowed maps to buy vs watch",
        "reasoning_summary": (
            "Entry allowed." if allowed else "Entry not allowed; watch."
        ),
        "final_decision": "buy" if allowed else "watch",
    }
    if entry_parsed["confidence"] is not None:
        entry_parsed["confidence"] = max(0.0, min(1.0, float(entry_parsed["confidence"]) / 100.0))

    entry_raw = dumps(_row_subset(row, [
        "ticker", "entry_allowed", "entry_score", "entry_status",
        "pullback_score", "volume_score", "vol_compression_score", "rsi_score",
    ]))

    preds = [
        {
            "agent_name": "factor_scorer",
            "agent_version": AGENT_VERSION_QUANTUM,
            "skill_version": "none",
            "parsed": factor_parsed,
            "raw_output": factor_raw,
        },
        {
            "agent_name": "entry_engine",
            "agent_version": AGENT_VERSION_QUANTUM,
            "skill_version": "none",
            "parsed": entry_parsed,
            "raw_output": entry_raw,
        },
    ]

    if news_item:
        sent = _float_or_none(news_item.get("sentiment")) or 0.0
        if sent > 0.2:
            n_thesis, n_dir = "bullish", "positive"
        elif sent < -0.2:
            n_thesis, n_dir = "bearish", "negative"
        else:
            n_thesis, n_dir = "neutral", "flat"
        preds.insert(0, {
            "agent_name": "news_scanner",
            "agent_version": AGENT_VERSION_QUANTUM,
            "skill_version": news_skill,
            "parsed": {
                "thesis": n_thesis,
                "confidence": max(0.0, min(1.0, abs(sent))),
                "prediction_direction": n_dir,
                "horizon_days": horizon_days,
                "evidence": [str(news_item.get("catalyst") or "")],
                "risks": [],
                "key_assumption": f"event_type={news_item.get('event_type')}",
                "reasoning_summary": (
                    f"News sentiment {sent:.2f} for "
                    f"{news_item.get('event_type') or 'unspecified'} event."
                ),
                "final_decision": None,
            },
            "raw_output": dumps(news_item),
        })
    return preds


def _row_subset(row, columns: list[str]) -> dict:
    out = {}
    for col in columns:
        try:
            if col in row.index:
                out[col] = row[col]
        except Exception:
            continue
    return out


def _float_or_none(value):
    if value is None:
        return None
    try:
        if hasattr(value, "item"):
            value = value.item()
        number = float(value)
        if number != number:
            return None
        return number
    except (TypeError, ValueError):
        return None


def _truthy(value) -> bool:
    if value is None:
        return False
    try:
        if hasattr(value, "item"):
            value = value.item()
    except Exception:
        pass
    if isinstance(value, float) and value != value:
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "allowed"}
    return bool(value)


AGENT_VERSION_DISCOVERY = "discovery-v1"
DISCOVERY_HORIZON = "30d"


def write_discovery_episodes(cards: list[dict], run_id: str, horizon_days: int = 30) -> int:
    """Observation only. Does not change Discovery weights."""
    written = 0
    skill = skill_version_label("filing_extractor")
    for card in cards:
        ticker = str(card.get("ticker") or "")
        if not ticker:
            continue
        muted = card.get("muted_reaction")
        decision = "watch"
        stage = card.get("stage") or ""
        if stage == "opportunity_candidate":
            decision = "watch"
        predictions = [{
            "agent_name": "catalyst_hunter",
            "agent_version": AGENT_VERSION_DISCOVERY,
            "skill_version": skill,
            "parsed": {
                "thesis": "bullish" if (card.get("sentiment") or 0) >= 0 else "bearish",
                "confidence": None,
                "prediction_direction": "positive" if (card.get("sentiment") or 0) >= 0 else "negative",
                "horizon_days": horizon_days,
                "evidence": [card.get("catalyst") or card.get("subject") or ""],
                "risks": card.get("risks") or [],
                "key_assumption": (
                    f"event_type={card.get('event_type')} "
                    f"scarcity={card.get('components', {}).get('scarcity')}"
                ),
                "reasoning_summary": card.get("why_it_matters") or "",
                "final_decision": decision,
            },
            "raw_output": dumps({
                "event_type": card.get("event_type"),
                "source": card.get("source"),
                "components": card.get("components"),
                "weights": card.get("weights"),
                "opportunity_score": card.get("opportunity_score"),
            }),
        }]
        eid = write_episode(
            source="discovery",
            ticker=ticker,
            run_id=run_id,
            horizon_days=horizon_days,
            horizon=DISCOVERY_HORIZON,
            regime="discovery_phase_a",
            final_decision=decision,
            entry_price=card.get("last_price") or card.get("last_close"),
            signals={
                "event_type": card.get("event_type"),
                "opportunity_score": card.get("opportunity_score"),
                "muted_reaction": muted,
                "analyst_n": card.get("analyst_n"),
            },
            snapshot={
                "card_type": "hidden_catalyst",
                "mcap_cr": card.get("mcap_cr"),
                "adv_inr": card.get("adv_inr") or card.get("liquidity_inr"),
                "amount_inr_cr": card.get("amount_inr_cr"),
                "components": card.get("components"),
                "weights_frozen": True,
                "phase_a_active": card.get("phase_a_active"),
                "source": card.get("source"),
                "subject": card.get("subject"),
            },
            predictions=predictions,
        )
        if eid:
            written += 1
    return written


def write_discovery_council_episode(
    ticker: str,
    run_id: str,
    agents: dict,
    *,
    event_id: str = "",
    source_id: str = "",
    evidence: dict | None = None,
    editor_decision: str | None = None,
    horizon_days: int = 30,
    entry_date: str | None = None,
    event_type: str = "",
) -> str | None:
    """
    First complete Discovery learning episode: pack → council → editor.
    Observation only. Does not retune Discovery or QuanTum.
    """
    editor = agents.get("editor")
    parsed_editor = getattr(editor, "last_parsed", None) or dict(UNKNOWN_PREDICTION)
    technical = agents.get("technical")
    tech_snapshot = getattr(technical, "last_snapshot", None) or {}
    canonical = (evidence or {}).get("canonical") or {}
    entry_price = canonical.get("price") or tech_snapshot.get("price")
    decision = str(editor_decision or parsed_editor.get("final_decision") or "watch").lower()
    if decision not in {"buy", "watch", "reject"}:
        decision = "watch"

    predictions = []
    for name, agent in agents.items():
        predictions.append({
            "agent_name": name,
            "agent_version": "discovery-council-v1",
            "skill_version": "none",
            "parsed": getattr(agent, "last_parsed", None) or dict(UNKNOWN_PREDICTION),
            "raw_output": getattr(agent, "last_raw", "") or "",
        })

    bull = agents.get("bull")
    bear = agents.get("bear")
    snapshot = {
        "event_id": event_id,
        "source_id": source_id,
        "evidence": evidence or {},
        "canonical_price": canonical,
        "technical": tech_snapshot,
        "bull_thesis": getattr(bull, "last_prose", "") or "",
        "bear_thesis": getattr(bear, "last_prose", "") or "",
        "editor_decision": parsed_editor,
        "editor_prose": getattr(editor, "last_prose", "") or "",
    }
    return write_episode(
        source="discovery_council",
        ticker=ticker,
        run_id=run_id,
        horizon_days=horizon_days,
        horizon="30d",
        regime="discovery_phase_c",
        final_decision=decision,
        entry_price=entry_price,
        event_id=event_id,
        entry_date=entry_date,
        event_type=event_type,
        signals={
            "event_id": event_id,
            "source_id": source_id,
            "event_type": event_type,
            "catalyst_valid": parsed_editor.get("catalyst_valid"),
            "economic_materiality": parsed_editor.get("economic_materiality"),
            "asymmetry": parsed_editor.get("asymmetry"),
        },
        snapshot=snapshot,
        predictions=predictions,
    )

