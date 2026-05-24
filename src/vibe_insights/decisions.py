"""Decisions overlay — MCP-agnostic.

The engine only ever reads a LOCAL source: a file (markdown or jsonl) or a
skill-populated cache (`decisions.cache.json`, which the skill writes from
whatever MCP the user points at). The engine never calls MCP itself.
"""
import json
import re
from pathlib import Path

_DATE_RE = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})\s*$")
_ENTRY_RE = re.compile(r"^###\s+(\d{2}:\d{2})\s*[—-]\s*(.+?)\s*$")


def _canon(d: dict) -> dict:
    return {
        "timestamp": d.get("timestamp"),
        "title": d.get("title", ""),
        "body": d.get("body", ""),
        "project_tag": d.get("project_tag"),
        "link": d.get("link"),
    }


def _parse_jsonl(path: Path) -> list[dict]:
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(d, dict) and d.get("title"):
            out.append(_canon(d))
    return out


def _parse_md(path: Path) -> list[dict]:
    out: list[dict] = []
    cur_date = None
    cur: dict | None = None
    body: list[str] = []

    def flush():
        nonlocal cur, body
        if cur is not None:
            cur["body"] = "\n".join(body).strip()
            out.append(cur)
        cur, body = None, []

    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = _DATE_RE.match(line)
        if m:
            flush()
            cur_date = m.group(1)
            continue
        e = _ENTRY_RE.match(line)
        if e:
            flush()
            hhmm, title = e.group(1), e.group(2).strip()
            ts = f"{cur_date}T{hhmm}:00" if cur_date else None
            cur = {"timestamp": ts, "title": title, "body": "",
                   "project_tag": None, "link": None}
            continue
        if cur is not None:
            body.append(line)
    flush()
    return [_canon(d) for d in out]


def load_decisions(dcfg: dict | None, data_dir) -> list[dict]:
    """Return canonical decisions, newest-first. Never raises; missing or
    unreadable sources return []. The engine stays MCP-agnostic — `mcp` source
    just reads a skill-written cache file."""
    source = (dcfg or {}).get("source", "none")
    try:
        if source == "file":
            p = Path(dcfg.get("path", ""))
            if not p.is_file():
                return []
            out = _parse_jsonl(p) if p.suffix == ".jsonl" else _parse_md(p)
        elif source == "mcp":
            cache = Path(data_dir) / "decisions.cache.json"
            if not cache.is_file():
                return []
            raw = json.loads(cache.read_text(encoding="utf-8"))
            out = [_canon(d) for d in raw if isinstance(d, dict) and d.get("title")]
        else:
            return []
    except (OSError, json.JSONDecodeError):
        return []
    out.sort(key=lambda d: d.get("timestamp") or "", reverse=True)
    return out
