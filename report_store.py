"""
Cache of the most recent report for each pipeline.

A full QuanTum run takes minutes. Opening the app on a phone should not.
Every completed run is written here, and the UI renders the stored copy
immediately while the user decides whether to trigger a fresh run.

Backed by Turso when configured, otherwise a local SQLite file, so the cache
survives a Hugging Face Space restart.
"""
import json
import os
from datetime import datetime

from turso_db import get_db_smart

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quantum_data.db")


def _db():
    return get_db_smart(DB_PATH)


def _ensure_table():
    conn = _db()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cached_reports (
                kind TEXT PRIMARY KEY,
                created TEXT,
                mode TEXT,
                markdown TEXT,
                picks TEXT
            )
        """)
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def save_report(kind: str, markdown: str, picks: dict | None = None,
                mode: str = "") -> bool:
    """Stores a finished report. `picks` is a dict of horizon -> list of rows."""
    if not markdown:
        return False
    _ensure_table()
    conn = _db()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO cached_reports
               (kind, created, mode, markdown, picks) VALUES (?, ?, ?, ?, ?)""",
            (kind, datetime.now().strftime("%Y-%m-%d %H:%M"), mode, markdown,
             json.dumps(picks or {}, default=str)),
        )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def load_report(kind: str) -> dict | None:
    """Returns {created, mode, markdown, picks} for the last stored run."""
    _ensure_table()
    conn = _db()
    try:
        row = conn.execute(
            "SELECT created, mode, markdown, picks FROM cached_reports WHERE kind = ?",
            (kind,),
        ).fetchone()
    except Exception:
        return None
    finally:
        conn.close()

    if not row or not row[2]:
        return None

    try:
        picks = json.loads(row[3]) if row[3] else {}
    except (TypeError, ValueError):
        picks = {}

    return {"created": row[0], "mode": row[1], "markdown": row[2], "picks": picks}


def picks_to_records(df, columns: list[str], limit: int = 10) -> list[dict]:
    """Trims a scored DataFrame down to something worth caching."""
    if df is None or getattr(df, "empty", True):
        return []
    present = [c for c in columns if c in df.columns]
    return df.head(limit)[present].round(2).to_dict("records")
