"""Vendored Claude Code session-log primitives.

vibe-insights runs fully standalone on these four functions. When the shared
`cc-logs` package is installed, scan.py prefers it instead, so token-burn and
timestamp semantics stay identical with other tools that share it (e.g.
Sanduhr). Either way the contract is the same: iter_raw_events, parse_iso,
project_display_name, discover_under.

Source: extracted from the cc-logs package (MIT, same author). If the upstream
parsing contract changes, keep these in sync.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional


def discover_under(root) -> list:
    """All session JSONL files under a single CC root, recursively.

    Top-level sessions live at <root>/projects/<encoded-cwd>/<uuid>.jsonl;
    subagent transcripts nest deeper. A recursive walk captures both. A
    missing projects/ dir yields []. Sorted for deterministic output."""
    projects = Path(root) / "projects"
    if not projects.is_dir():
        return []
    return sorted(projects.rglob("*.jsonl"))


def parse_iso(s: Optional[str]) -> Optional[datetime]:
    """Permissive ISO-8601 parser. Returns None on bad input rather than
    raising, so one malformed timestamp doesn't kill the aggregation."""
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, AttributeError, TypeError):
        return None


def iter_raw_events(path) -> Iterator[dict]:
    """Stream every well-formed JSON line in a session log as a dict. A single
    malformed/partial line (common at the tail of a live file) is skipped, not
    fatal. The shared low-level primitive; typed iterators build on it."""
    try:
        f = open(path, encoding="utf-8", errors="replace")
    except OSError:
        return
    try:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
    finally:
        f.close()


def project_display_name(cwd: str) -> str:
    """Friendly basename out of a cwd path for display. Handles both forward
    and backslash separators (e.g. a Windows path -> the final segment)."""
    if not cwd:
        return ""
    parts = cwd.replace("\\", "/").rstrip("/").split("/")
    last = parts[-1] if parts else cwd
    return last or cwd
