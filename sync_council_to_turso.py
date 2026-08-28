"""
Copy Discovery Council episodes from local sqlite into Turso.

CLI sample runs used quantum_data.db because TURSO_* was not in the
process environment. Render reads Turso, so those rows never appeared.

Does not print secrets. Skips radar `discovery` rows; only `discovery_council`.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from agents.episode_store import ensure_episode_tables
from turso_db import connect, is_configured

ROOT = Path(__file__).resolve().parent
LOCAL_DB = ROOT / "quantum_data.db"
SOURCE = "discovery_council"
TABLES = (
    "episodes",
    "agent_predictions",
    "episode_horizon_outcomes",
    "agent_outcomes",
)


def _cols(conn, table: str) -> list[str]:
    try:
        return [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    except Exception:
        return []
    return [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def _copy_table(local, remote, table: str, episode_ids: list[str]) -> int:
    if not episode_ids:
        return 0
    local_cols = _cols(local, table)
    if not local_cols:
        return 0
    remote_cols = _cols(remote, table)
    cols = [c for c in local_cols if c in set(remote_cols)] if remote_cols else local_cols
    key = "id" if table == "episodes" else "episode_id"
    placeholders = ",".join("?" * len(episode_ids))
    rows = local.execute(
        f"SELECT {', '.join(cols)} FROM {table} WHERE {key} IN ({placeholders})",
        episode_ids,
    ).fetchall()
    inserted = 0
    marks = ",".join("?" * len(cols))
    sql = f"INSERT OR REPLACE INTO {table} ({', '.join(cols)}) VALUES ({marks})"
    for row in rows:
        remote.execute(sql, row)
        inserted += 1
    return inserted


def main() -> None:
    if not LOCAL_DB.exists():
        raise SystemExit("quantum_data.db not found")
    if not is_configured():
        raise SystemExit("Turso is not configured. Set TURSO_URL and TURSO_TOKEN.")

    local = sqlite3.connect(LOCAL_DB)
    episode_ids = [
        row[0]
        for row in local.execute(
            "SELECT id FROM episodes WHERE source = ? ORDER BY created_at",
            (SOURCE,),
        ).fetchall()
    ]
    tickers = [
        row[0]
        for row in local.execute(
            "SELECT ticker FROM episodes WHERE source = ? ORDER BY created_at",
            (SOURCE,),
        ).fetchall()
    ]
    print(f"local {SOURCE} episodes: {len(episode_ids)} {tickers}")

    ensure_episode_tables()
    remote = connect()
    copied = {table: _copy_table(local, remote, table, episode_ids) for table in TABLES}
    print("copied", copied)
    verify = remote.execute(
        "SELECT COUNT(*) FROM episodes WHERE source = ?",
        (SOURCE,),
    ).fetchone()
    print("turso discovery_council count:", verify[0] if verify else 0)
    local.close()
    remote.close()


if __name__ == "__main__":
    main()
