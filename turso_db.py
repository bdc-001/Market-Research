"""
turso_db.py — Drop-in sqlite3-compatible adapter for Turso via HTTP API.

Usage (identical to sqlite3):
    from turso_db import connect
    conn = connect()                   # uses env vars TURSO_URL + TURSO_TOKEN
    conn.execute("CREATE TABLE ...")
    conn.execute("INSERT ...", values)
    rows = conn.execute("SELECT ...").fetchall()
    conn.commit()   # no-op (Turso auto-commits)
    conn.close()    # no-op

Set environment variables (in .env or .streamlit/secrets.toml):
    TURSO_URL   = "libsql://your-db-name-org.turso.io"
    TURSO_TOKEN = "eyJh..."
"""

import os
import re
import json
import requests
import sqlite3
from typing import Any, Sequence


# ── Config ────────────────────────────────────────────────────────────────────

def _get_url() -> str:
    url = os.environ.get("TURSO_URL", "")
    if url.startswith("libsql://"):
        url = "https://" + url[len("libsql://"):]
    return url.rstrip("/")


def _get_token() -> str:
    return os.environ.get("TURSO_TOKEN", "")


# ── Cursor ────────────────────────────────────────────────────────────────────

class TursoCursor:
    def __init__(self, base_url: str, token: str):
        self._url = base_url
        self._token = token
        self._rows: list[tuple] = []
        self._description: list | None = None
        self.rowcount: int = -1
        self.lastrowid: int | None = None

    # Convert ? positional params to :p1, :p2 … (Turso uses named params)
    def _convert_sql(self, sql: str, params) -> tuple[str, dict]:
        if params is None:
            return sql, {}
        # Named params dict already
        if isinstance(params, dict):
            return sql, params
        # Positional ? params
        named: dict[str, Any] = {}
        idx = 0
        def replacer(m):
            nonlocal idx
            idx += 1
            key = f"p{idx}"
            named[key] = None  # placeholder, filled below
            return f":{key}"
        new_sql = re.sub(r"\?", replacer, sql)
        for i, v in enumerate(params, 1):
            named[f"p{i}"] = v
        return new_sql, named

    def _turso_value(self, v: Any) -> dict:
        if v is None:
            return {"type": "null", "value": None}
        if isinstance(v, bool):
            return {"type": "integer", "value": str(int(v))}
        if isinstance(v, int):
            return {"type": "integer", "value": str(v)}
        if isinstance(v, float):
            return {"type": "float", "value": v}
        return {"type": "text", "value": str(v)}

    def execute(self, sql: str, parameters=None):
        sql = sql.strip()
        new_sql, named = self._convert_sql(sql, parameters)

        # Build named_args list for Turso
        named_args = [{"name": k, "value": self._turso_value(v)}
                      for k, v in named.items()] if named else []

        payload = {
            "requests": [
                {
                    "type": "execute",
                    "stmt": {
                        "sql": new_sql,
                        **({"named_args": named_args} if named_args else {}),
                    }
                },
                {"type": "close"}
            ]
        }

        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

        resp = requests.post(
            f"{self._url}/v2/pipeline",
            headers=headers,
            json=payload,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        result = data["results"][0]
        if result.get("type") == "error":
            raise Exception(result["error"]["message"])

        rs = result.get("response", {}).get("result", {})
        cols = [c["name"] for c in rs.get("cols", [])]
        self._description = [(c, None, None, None, None, None, None) for c in cols]
        self._rows = [
            tuple(cell.get("value") for cell in row)
            for row in rs.get("rows", [])
        ]
        self.rowcount = rs.get("affected_row_count", -1)
        self.lastrowid = rs.get("last_insert_rowid")
        return self

    def executemany(self, sql: str, seq_of_params):
        for params in seq_of_params:
            self.execute(sql, params)
        return self

    def fetchall(self) -> list[tuple]:
        return self._rows

    def fetchone(self) -> tuple | None:
        return self._rows[0] if self._rows else None

    @property
    def description(self):
        return self._description

    def __iter__(self):
        return iter(self._rows)


# ── Connection ────────────────────────────────────────────────────────────────

class TursoConnection:
    def __init__(self, base_url: str, token: str):
        self._url = base_url
        self._token = token

    def cursor(self) -> TursoCursor:
        return TursoCursor(self._url, self._token)

    def execute(self, sql: str, parameters=None) -> TursoCursor:
        cur = self.cursor()
        cur.execute(sql, parameters)
        return cur

    def executemany(self, sql: str, seq_of_params):
        cur = self.cursor()
        cur.executemany(sql, seq_of_params)
        return cur

    def commit(self):
        pass  # Turso auto-commits each statement

    def close(self):
        pass  # HTTP connections are stateless

    # Context manager support
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# ── Public API ────────────────────────────────────────────────────────────────

def is_configured() -> bool:
    """Returns True if TURSO_URL and TURSO_TOKEN env vars are set."""
    return bool(_get_url() and _get_token())


def connect(url: str = "", token: str = "") -> TursoConnection:
    """
    Returns a Turso connection (uses env vars if url/token not given).
    Falls back to local sqlite3 if env vars are missing.
    """
    u = url or _get_url()
    t = token or _get_token()
    if not u or not t:
        raise EnvironmentError(
            "TURSO_URL and TURSO_TOKEN must be set. "
            "See .streamlit/secrets.toml or set environment variables."
        )
    return TursoConnection(u, t)


def get_db_smart(local_path: str) -> Any:
    """
    Returns a Turso connection if configured, otherwise a local sqlite3 connection.
    This is the main function to use — zero code changes needed in callers.
    """
    if is_configured():
        return connect()
    return sqlite3.connect(local_path)
