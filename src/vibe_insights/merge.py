"""Cross-machine merge: union per-machine personal indexes for one report."""
import json
from pathlib import Path


def load_merged(synced_dir) -> list[dict]:
    """Union personal sessions across all <synced_dir>/<machine>/index.json.

    Keyed by session_id (UUID, globally unique). On the rare duplicate id,
    keep the richer record (more assistant_msgs). Missing dir or unreadable
    files are skipped, never fatal."""
    synced_dir = Path(synced_dir)
    if not synced_dir.is_dir():
        return []
    merged: dict = {}
    for machine_dir in sorted(synced_dir.iterdir()):
        idx = machine_dir / "index.json"
        if not idx.is_file():
            continue
        try:
            data = json.loads(idx.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            continue
        for s in data.get("sessions", []):
            sid = s.get("session_id")
            if not sid:
                continue
            prev = merged.get(sid)
            if prev is None or s.get("assistant_msgs", 0) > prev.get("assistant_msgs", 0):
                merged[sid] = s
    return list(merged.values())
