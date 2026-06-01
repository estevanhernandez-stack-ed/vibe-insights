"""Topology: which Claude Code sources exist on this machine.

A source is any `~/.claude*` dir containing `projects/`. Discovery marks
every source personal (synced-eligible); walling is opt-in. The emitted
config is meant to be human-reviewed before use.
"""
import json
import socket
from pathlib import Path


def default_machine() -> str:
    return socket.gethostname().lower()


def discover_sources(home: Path = None) -> list[dict]:
    """Every `.claude*` dir with a `projects/` subdir is a source, all
    personal (synced-eligible) by default. Walling is opt-in via the
    `private` flag or `private_repos` — never inferred from the dir name."""
    home = Path(home) if home else Path.home()
    sources = []
    for child in sorted(home.iterdir()):
        if not child.is_dir() or not child.name.startswith(".claude"):
            continue
        if not (child / "projects").is_dir():
            continue
        sources.append({"path": str(child), "private": False})
    return sources


def build_config(home: Path = None, machine: str = None,
                 data_dir: Path = None) -> dict:
    data_dir = Path(data_dir) if data_dir else (Path.home() / ".vibe-insights")
    return {
        "machine": machine or default_machine(),
        "dataDir": str(data_dir),
        "homes": discover_sources(home),
        "work_repos": [],
        "decisions": {"source": "none"},
        "voice": None,
    }


def load_config(config_path: Path) -> dict:
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


def write_config(config_path: Path, cfg: dict) -> None:
    Path(config_path).parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
