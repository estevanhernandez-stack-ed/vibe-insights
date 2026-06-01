# tests/test_config.py
import json
from pathlib import Path

from vibe_insights import config


def _make_home(tmp_path, name, with_projects=True):
    d = tmp_path / name
    (d / "projects").mkdir(parents=True) if with_projects else d.mkdir()
    return d


def test_discover_sources_defaults_all_personal(tmp_path):
    _make_home(tmp_path, ".claude")
    _make_home(tmp_path, ".claude-personal")
    _make_home(tmp_path, ".claude-server-commander", with_projects=False)
    sources = config.discover_sources(home=tmp_path)
    by_path = {Path(s["path"]).name: s for s in sources}
    # No more ".claude == work" — every discovered source is personal by default.
    assert by_path[".claude"]["private"] is False
    assert by_path[".claude-personal"]["private"] is False
    # no projects/ dir => not a source
    assert ".claude-server-commander" not in by_path


def test_build_config_new_schema(tmp_path):
    _make_home(tmp_path, ".claude-personal")
    cfg = config.build_config(home=tmp_path, machine="testbox",
                              data_dir=tmp_path / ".vibe-insights")
    assert cfg["machine"] == "testbox"
    assert cfg["dataDir"].endswith(".vibe-insights")
    assert cfg["advanced"]["sources"] == [
        {"path": str(tmp_path / ".claude-personal"), "private": False}
    ]
    assert cfg["advanced"]["private_repos"] == []
    # legacy keys are gone from freshly-built config
    assert "homes" not in cfg and "work_repos" not in cfg


def test_build_config_includes_decisions_default(tmp_path):
    _make_home(tmp_path, ".claude-personal")
    cfg = config.build_config(home=tmp_path, machine="m", data_dir=tmp_path / ".vi")
    assert cfg["decisions"] == {"source": "none"}


def test_build_config_includes_voice_default(tmp_path):
    _make_home(tmp_path, ".claude-personal")
    cfg = config.build_config(home=tmp_path, machine="m", data_dir=tmp_path / ".vi")
    assert cfg["voice"] is None


def test_normalize_new_schema_passthrough():
    cfg = {"machine": "m", "dataDir": "/d",
           "decisions": {"source": "none"}, "voice": None,
           "advanced": {"sources": [{"path": "/h/.claude-work", "private": True}],
                        "private_repos": ["employer/api"]}}
    norm = config.normalize_config(cfg)
    assert norm["sources"] == [{"path": "/h/.claude-work", "private": True}]
    assert norm["private_repos"] == ["employer/api"]
    assert norm["machine"] == "m" and norm["dataDir"] == "/d"


def test_normalize_legacy_schema_maps_walled_to_private():
    legacy = {"machine": "m", "dataDir": "/d",
              "homes": [{"path": "/h/.claude", "account": "work", "walled": True},
                        {"path": "/h/.claude-personal", "account": "personal", "walled": False}],
              "work_repos": ["employer/api"],
              "decisions": {"source": "none"}, "voice": None}
    norm = config.normalize_config(legacy)
    assert norm["sources"] == [{"path": "/h/.claude", "private": True},
                               {"path": "/h/.claude-personal", "private": False}]
    assert norm["private_repos"] == ["employer/api"]


def test_normalize_no_advanced_discovers_personal(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    _make_home(tmp_path, ".claude")
    cfg = {"machine": "m", "dataDir": "/d", "decisions": {"source": "none"}, "voice": None}
    norm = config.normalize_config(cfg)
    assert norm["sources"] == [{"path": str(tmp_path / ".claude"), "private": False}]
    assert norm["private_repos"] == []


def test_load_config_returns_normalized(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({
        "machine": "m", "dataDir": "/d",
        "homes": [{"path": "/h/.claude", "account": "work", "walled": True}],
        "work_repos": ["e/r"], "decisions": {"source": "none"}, "voice": None,
    }), encoding="utf-8")
    cfg = config.load_config(p)
    assert cfg["sources"] == [{"path": "/h/.claude", "private": True}]
    assert cfg["private_repos"] == ["e/r"]


def test_set_private_repo_writes_advanced(tmp_path):
    p = tmp_path / "config.json"
    config.write_config(p, config.build_config(home=tmp_path, machine="m",
                                                data_dir=tmp_path / ".vi"))
    config.set_private(p, repo="owner/api")
    raw = json.loads(p.read_text(encoding="utf-8"))
    assert "owner/api" in raw["advanced"]["private_repos"]


def test_set_private_source_marks_private(tmp_path):
    _make_home(tmp_path, ".claude-work")
    p = tmp_path / "config.json"
    config.write_config(p, config.build_config(home=tmp_path, machine="m",
                                                data_dir=tmp_path / ".vi"))
    config.set_private(p, source=str(tmp_path / ".claude-work"))
    raw = json.loads(p.read_text(encoding="utf-8"))
    src = {s["path"]: s for s in raw["advanced"]["sources"]}
    assert src[str(tmp_path / ".claude-work")]["private"] is True
