"""
Skill registry.

Skills live in `skills/<name>/SKILL.md` and open with a YAML front matter block:

    ---
    name: news_extractor
    description: Extract NSE tickers, catalyst and sentiment from headlines
    tools: [gemini, rss]
    ---

Only the front matter is parsed at startup, so the catalogue stays cheap. The
full instruction body is read on demand, when an orchestrator actually decides
to run that skill.
"""
import os
import re
from functools import lru_cache

SKILLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skills"
)

FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


class Skill:
    def __init__(self, key: str, path: str, meta: dict):
        self.key = key
        self.path = path
        self.name = meta.get("name", key)
        self.description = meta.get("description", "")
        self.tools = meta.get("tools", [])

    def body(self) -> str:
        """Reads the full instruction text (everything after the front matter)."""
        with open(self.path, "r", encoding="utf-8") as f:
            raw = f.read()
        return FRONT_MATTER_RE.sub("", raw, count=1).strip()

    def __repr__(self):
        return f"<Skill {self.key}>"


def _parse_front_matter(raw: str) -> dict:
    """
    Minimal YAML front matter reader: flat `key: value` pairs, inline lists and
    folded `>` blocks. Avoids a PyYAML dependency for a fixed, simple schema.
    """
    m = FRONT_MATTER_RE.match(raw)
    if not m:
        return {}

    meta: dict = {}
    key = None
    for line in m.group(1).splitlines():
        if not line.strip():
            continue
        if line.startswith((" ", "\t")) and key:
            meta[key] = (str(meta.get(key, "")) + " " + line.strip()).strip()
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value in (">", "|", ">-", "|-"):
            meta[key] = ""
        elif value.startswith("[") and value.endswith("]"):
            meta[key] = [v.strip() for v in value[1:-1].split(",") if v.strip()]
        else:
            meta[key] = value
    return meta


@lru_cache(maxsize=1)
def list_skills() -> dict:
    """Returns {key: Skill} built from front matter only."""
    found: dict = {}
    if not os.path.isdir(SKILLS_DIR):
        return found

    for entry in sorted(os.listdir(SKILLS_DIR)):
        path = os.path.join(SKILLS_DIR, entry, "SKILL.md")
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                head = f.read(4096)
        except OSError:
            continue
        meta = _parse_front_matter(head)
        key = meta.get("name", entry)
        found[key] = Skill(key, path, meta)
    return found


def get_skill(name: str) -> Skill | None:
    skills = list_skills()
    if name in skills:
        return skills[name]
    for skill in skills.values():
        if skill.key.replace("-", "_") == name.replace("-", "_"):
            return skill
    return None


def load_skill_body(name: str, default: str = "") -> str:
    """Full instruction text for a skill, or `default` when it is missing."""
    skill = get_skill(name)
    if not skill:
        return default
    try:
        return skill.body()
    except OSError:
        return default


def catalog() -> str:
    """One line per skill, cheap enough to keep in an orchestrator prompt."""
    lines = []
    for skill in list_skills().values():
        tools = ", ".join(skill.tools) if isinstance(skill.tools, list) else skill.tools
        lines.append(f"- {skill.key}: {skill.description} (tools: {tools})")
    return "\n".join(lines)
