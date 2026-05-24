"""Topology: which config homes exist, and how each maps to an account.

Phase-1 heuristic: `.claude` is the work seat (walled); any other
`.claude*` dir that contains a `projects/` subdir is personal. The
emitted config.json is meant to be human-reviewed before use.
"""
import json
import socket
from pathlib import Path


def default_machine() -> str:
    return socket.gethostname().lower()


def discover_homes(home: Path = None) -> list[dict]:
    home = Path(home) if home else Path.home()
    homes = []
    for child in sorted(home.iterdir()):
        if not child.is_dir() or not child.name.startswith(".claude"):
            continue
        if not (child / "projects").is_dir():
            continue
        account = "work" if child.name == ".claude" else "personal"
        homes.append({
            "path": str(child),
            "account": account,
            "walled": account == "work",
        })
    return homes


def build_config(home: Path = None, machine: str = None,
                 data_dir: Path = None) -> dict:
    data_dir = Path(data_dir) if data_dir else (Path.home() / ".vibe-insights")
    return {
        "machine": machine or default_machine(),
        "dataDir": str(data_dir),
        "homes": discover_homes(home),
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
