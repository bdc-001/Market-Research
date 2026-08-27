"""
Semantic memory for the agent ecosystem.

Two files make up the system prompt of every Gemini call:

  GEMINI.md                 static meta-prompt (role, output contracts)
  memory/learned_rules.md   imperative rules learned from past runs

Rules are mirrored into the database (Turso when configured) because the
Hugging Face Space filesystem is ephemeral: a restart wipes the local file but
not the remote table. `restore_rules()` re-materialises the file on boot.
"""
import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from turso_db import get_db_smart

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
META_PROMPT_PATH = os.path.join(PROJECT_ROOT, "GEMINI.md")
RULES_PATH = os.path.join(PROJECT_ROOT, "memory", "learned_rules.md")
DB_PATH = os.path.join(PROJECT_ROOT, "quantum_data.db")

RULES_START = "<!-- RULES:START -->"
RULES_END = "<!-- RULES:END -->"

# Hard cap so the system prompt cannot grow without bound.
MAX_RULES = 80

RULE_RE = re.compile(r"^Rule\s+\[?(\d+)\]?\s*-\s*([^:]+):\s*(.+)$")


# ── Database ──────────────────────────────────────────────────────────────────

def _db():
    return get_db_smart(DB_PATH)


def _ensure_table():
    try:
        conn = _db()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_rules (
                rule_number INTEGER PRIMARY KEY,
                category TEXT,
                body TEXT,
                created TEXT
            )
        """)
        conn.commit()
        conn.close()
    except Exception:
        pass


# ── File helpers ──────────────────────────────────────────────────────────────

def _read_rules_file() -> str:
    try:
        with open(RULES_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def _rules_block(text: str) -> str:
    if RULES_START in text and RULES_END in text:
        return text.split(RULES_START, 1)[1].split(RULES_END, 1)[0].strip()
    return text.strip()


def _write_rules_block(lines: list[str]):
    os.makedirs(os.path.dirname(RULES_PATH), exist_ok=True)
    header = (
        "# Learned Rules\n\n"
        "Rules are appended by the critic agent after each pipeline run. Newest rules\n"
        "win when two rules conflict. Do not edit by hand unless a rule is wrong.\n\n"
    )
    body = "\n".join(lines)
    with open(RULES_PATH, "w", encoding="utf-8") as f:
        f.write(f"{header}{RULES_START}\n{body}\n{RULES_END}\n")


def load_rules() -> list[str]:
    """Returns the rule lines currently in the local file."""
    block = _rules_block(_read_rules_file())
    return [ln.strip() for ln in block.splitlines() if ln.strip().startswith("Rule")]


def next_rule_number() -> int:
    numbers = []
    for line in load_rules():
        m = RULE_RE.match(line)
        if m:
            numbers.append(int(m.group(1)))
    return (max(numbers) + 1) if numbers else 1


# ── Public API ────────────────────────────────────────────────────────────────

def append_rules(new_rules: list[str]) -> list[str]:
    """
    Appends imperative rules to the local file and mirrors them to the database.

    Each entry may be a bare sentence or a fully formatted `Rule N - Cat: ...`
    line; numbering is normalised here so callers cannot collide.
    Returns the formatted lines that were actually written.
    """
    if not new_rules:
        return []

    existing = load_rules()
    existing_bodies = {_body_of(r).lower() for r in existing}
    number = next_rule_number()
    written = []

    for raw in new_rules:
        raw = (raw or "").strip()
        if not raw:
            continue
        category, body = _split_rule(raw)
        if body.lower() in existing_bodies:
            continue
        line = f"Rule [{number}] - {category}: {body}"
        written.append(line)
        existing_bodies.add(body.lower())
        number += 1

    if not written:
        return []

    combined = (existing + written)[-MAX_RULES:]
    _write_rules_block(combined)
    _persist(written)
    return written


def _split_rule(raw: str) -> tuple[str, str]:
    m = RULE_RE.match(raw)
    if m:
        return m.group(2).strip(), m.group(3).strip()
    if " - " in raw and ":" in raw.split(" - ", 1)[1]:
        head, rest = raw.split(" - ", 1)
        category, body = rest.split(":", 1)
        if len(category) < 40:
            return category.strip(), body.strip()
    return "General", raw


def _body_of(line: str) -> str:
    m = RULE_RE.match(line)
    return m.group(3).strip() if m else line.strip()


def _persist(lines: list[str]):
    _ensure_table()
    try:
        conn = _db()
        today = datetime.now().strftime("%Y-%m-%d %H:%M")
        for line in lines:
            m = RULE_RE.match(line)
            if not m:
                continue
            conn.execute(
                """INSERT OR REPLACE INTO agent_rules
                   (rule_number, category, body, created) VALUES (?, ?, ?, ?)""",
                (int(m.group(1)), m.group(2).strip(), m.group(3).strip(), today),
            )
        conn.commit()
        conn.close()
    except Exception:
        pass


def restore_rules() -> int:
    """
    Rebuilds the local rules file from the database when it is missing or empty.
    Called at pipeline start so a fresh container keeps what it has learned.
    Returns the number of rules restored.
    """
    if load_rules():
        return 0
    _ensure_table()
    try:
        conn = _db()
        rows = conn.execute(
            "SELECT rule_number, category, body FROM agent_rules ORDER BY rule_number"
        ).fetchall()
        conn.close()
    except Exception:
        return 0

    lines = [f"Rule [{r[0]}] - {r[1]}: {r[2]}" for r in rows if r and r[2]]
    if not lines:
        return 0
    _write_rules_block(lines[-MAX_RULES:])
    return len(lines)


def system_instruction() -> str:
    """The full prepended prompt: meta-prompt plus every learned rule."""
    try:
        with open(META_PROMPT_PATH, "r", encoding="utf-8") as f:
            meta = f.read()
    except FileNotFoundError:
        meta = "You are an equity research agent for the Indian market (NSE)."

    rules = load_rules()
    if not rules:
        return meta
    return meta + "\n\n## Active learned rules\n\n" + "\n".join(rules) + "\n"
