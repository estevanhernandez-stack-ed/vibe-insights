"""Per-session tag cache (friction / satisfaction / outcome / session_type / intent).

Tags are produced by an LLM pass (the skill orchestrates it) and stored keyed by
session_id. The engine only reads + aggregates — it never calls an LLM.
Incremental: a session is re-tagged only when its last_ts changes."""
import json
from pathlib import Path


def load_cache(path) -> dict:
    p = Path(path)
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_cache(path, cache: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cache, indent=2), encoding="utf-8")


def untagged(sessions: list[dict], cache: dict) -> list[dict]:
    out = []
    for s in sessions:
        sid = s.get("session_id")
        if not sid:
            continue
        entry = cache.get(sid)
        if not isinstance(entry, dict) or entry.get("last_ts") != s.get("last_ts"):
            out.append(s)
    return out


def merge_into(sessions: list[dict], cache: dict) -> list[dict]:
    for s in sessions:
        t = cache.get(s.get("session_id"))
        if isinstance(t, dict):
            s["tags"] = t
    return sessions
