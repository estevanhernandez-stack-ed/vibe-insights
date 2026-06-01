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
        "decisions": {"source": "none"},
        "voice": None,
        "advanced": {
            "sources": discover_sources(home),
            "private_repos": [],
        },
    }


def normalize_config(cfg: dict) -> dict:
    """Return a canonical internal config from either the new schema
    (core + `advanced.sources`/`private_repos`) or the legacy schema
    (`homes` with `account`/`walled`, top-level `work_repos`). Downstream
    code consumes only `sources` (list of {path, private}) + `private_repos`."""
    adv = cfg.get("advanced") or {}
    if adv.get("sources") is not None:
        sources = [{"path": s["path"], "private": bool(s.get("private", False))}
                   for s in adv["sources"]]
    elif cfg.get("homes") is not None:  # legacy: walled -> private
        sources = [{"path": h["path"], "private": bool(h.get("walled", False))}
                   for h in cfg["homes"]]
    else:  # no sources declared -> discover, all personal
        sources = discover_sources()
    private_repos = adv.get("private_repos")
    if private_repos is None:
        private_repos = cfg.get("work_repos", [])  # legacy
    return {
        "machine": cfg.get("machine") or default_machine(),
        "dataDir": cfg.get("dataDir") or str(Path.home() / ".vibe-insights"),
        "sources": sources,
        "private_repos": list(private_repos),
        "decisions": cfg.get("decisions") or {"source": "none"},
        "voice": cfg.get("voice"),
    }


def load_config(config_path: Path) -> dict:
    with open(config_path, encoding="utf-8") as f:
        return normalize_config(json.load(f))


def write_config(config_path: Path, cfg: dict) -> None:
    Path(config_path).parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def init_config(config_path: Path, rediscover: bool = False, home: Path = None) -> dict:
    """Config to write on --init. Fresh discovery (all personal) when no config
    exists. When a config exists, PRESERVE the user's privacy edits — per-source
    `private` flags, `private_repos`, and core fields — and fold in any newly
    discovered sources as personal (so --init is sticky, not destructive).
    `rediscover=True` re-scans the source list fresh (all personal) but still
    keeps core fields + private_repos."""
    if not Path(config_path).exists():
        return build_config(home=home)
    with open(config_path, encoding="utf-8") as f:
        norm = normalize_config(json.load(f))
    discovered = discover_sources(home)
    if rediscover:
        sources = discovered
    else:
        existing_private = {s["path"]: s["private"] for s in norm["sources"]}
        discovered_paths = {s["path"] for s in discovered}
        sources = [{"path": s["path"], "private": existing_private.get(s["path"], False)}
                   for s in discovered]
        # keep configured sources discovery didn't see (e.g. dir temporarily absent)
        for s in norm["sources"]:
            if s["path"] not in discovered_paths:
                sources.append({"path": s["path"], "private": s["private"]})
    return {
        "machine": norm["machine"], "dataDir": norm["dataDir"],
        "decisions": norm["decisions"], "voice": norm["voice"],
        "advanced": {"sources": sources, "private_repos": norm["private_repos"]},
    }


def set_private(config_path: Path, repo: str = None, source: str = None) -> dict:
    """Mark a repo (added to advanced.private_repos) or a source (its private
    flag set True) as local-only. Writes the new-schema `advanced` block,
    migrating a legacy file on the way. Returns the written config."""
    with open(config_path, encoding="utf-8") as f:
        raw = json.load(f)
    norm = normalize_config(raw)
    out = {
        "machine": norm["machine"], "dataDir": norm["dataDir"],
        "decisions": norm["decisions"], "voice": norm["voice"],
        "advanced": {"sources": norm["sources"], "private_repos": norm["private_repos"]},
    }
    if repo and repo not in out["advanced"]["private_repos"]:
        out["advanced"]["private_repos"].append(repo)
    if source:
        for s in out["advanced"]["sources"]:
            if s["path"] == source:
                s["private"] = True
    write_config(config_path, out)
    return out
