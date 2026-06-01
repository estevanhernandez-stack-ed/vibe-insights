# tests/test_config.py
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


def test_build_config_shape(tmp_path):
    _make_home(tmp_path, ".claude-personal")
    cfg = config.build_config(home=tmp_path, machine="testbox",
                              data_dir=tmp_path / ".vibe-insights")
    assert cfg["machine"] == "testbox"
    assert cfg["dataDir"].endswith(".vibe-insights")
    assert len(cfg["homes"]) == 1


def test_build_config_includes_work_repos_key(tmp_path):
    _make_home(tmp_path, ".claude-personal")
    cfg = config.build_config(home=tmp_path, machine="m", data_dir=tmp_path / ".vi")
    assert "work_repos" in cfg and cfg["work_repos"] == []


def test_build_config_includes_decisions_default(tmp_path):
    _make_home(tmp_path, ".claude-personal")
    cfg = config.build_config(home=tmp_path, machine="m", data_dir=tmp_path / ".vi")
    assert cfg["decisions"] == {"source": "none"}


def test_build_config_includes_voice_default(tmp_path):
    _make_home(tmp_path, ".claude-personal")
    cfg = config.build_config(home=tmp_path, machine="m", data_dir=tmp_path / ".vi")
    assert cfg["voice"] is None
