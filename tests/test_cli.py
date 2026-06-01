# tests/test_cli.py
import json
from pathlib import Path

from vibe_insights import cli
from vibe_insights import config as config_mod


def _write_session(home, root, project, sid, lines):
    d = Path(home) / root / "projects" / project
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{sid}.jsonl").write_text(
        "\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")


def test_run_produces_index_and_reports(tmp_path):
    _write_session(tmp_path, ".claude-personal", "P", "s1",
                   [{"type": "assistant", "sessionId": "s1",
                     "timestamp": "2026-05-23T10:00:00Z", "cwd": "C:/me/P",
                     "message": {"model": "claude-opus-4-7",
                                 "usage": {"input_tokens": 10, "output_tokens": 2}}}])
    cfg = {"machine": "testbox", "dataDir": str(tmp_path / "data"),
           "sources": [{"path": str(tmp_path / ".claude-personal"), "private": False}],
           "private_repos": []}
    result = cli.run(cfg)
    assert (Path(cfg["dataDir"]) / "synced" / "testbox" / "index.json").exists()
    assert Path(result["reports"]["md"]).exists()
    assert result["counts"]["personal"] == 1


def test_render_only_embeds_existing_narrative(tmp_path):
    import json
    # seed an index, digest, and a narrative.html, then render-only
    data = tmp_path / "data"
    (data / "synced" / "m").mkdir(parents=True)
    (data / "synced" / "m" / "index.json").write_text(json.dumps({"sessions": [
        {"session_id": "a", "account": "personal", "machine": "m", "repo": "r",
         "branch": "main", "title": "t", "last_ts": "2026-05-23T12:00:00+00:00",
         "human_tokens": 5}]}), encoding="utf-8")
    (data / "digest.json").write_text(json.dumps({
        "token_cost": {"sessions": 1, "burn": 5, "input": 1, "output": 4,
                       "cache_read": 9, "cache_creation": 0, "cache_read_share": 90.0,
                       "output_share": 80.0, "top_repos_by_burn": [], "model_session_counts": {}},
        "trends": {"by_day": {}, "recent_days": [], "recent_burn": 0,
                   "baseline_avg_per_day": 0, "recent_avg_per_day": 0, "acceleration_multiple": None},
        "pick_back_up": []}), encoding="utf-8")
    (data / "reports").mkdir()
    (data / "reports" / "narrative.html").write_text("<p>seeded read</p>", encoding="utf-8")
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"machine": "m", "dataDir": str(data), "homes": []}), encoding="utf-8")

    from vibe_insights import cli
    rc = cli.main(["--render-only", "--config", str(cfg_path)])
    assert rc == 0
    html = (data / "reports" / "insights.html").read_text(encoding="utf-8")
    assert "seeded read" in html


def test_run_includes_work_in_report(tmp_path):
    import json
    # one personal repo session + one employer repo session, both in a work-labeled home
    _write_session(tmp_path, ".claude", "p", "personal1",
                   [{"type": "assistant", "sessionId": "personal1", "timestamp": "2026-05-23T12:00:00Z",
                     "cwd": "C:/x/626labs-hub", "message": {"model": "m",
                     "usage": {"input_tokens": 5, "output_tokens": 1}}}])
    _write_session(tmp_path, ".claude", "w", "work1",
                   [{"type": "assistant", "sessionId": "work1", "timestamp": "2026-05-23T12:00:00Z",
                     "cwd": "C:/x/pricescout-react", "message": {"model": "m",
                     "usage": {"input_tokens": 5, "output_tokens": 1}}}])
    cfg = {"machine": "m", "dataDir": str(tmp_path / "data"),
           "private_repos": ["pricescout-react"],
           "sources": [{"path": str(tmp_path / ".claude"), "private": True}]}
    result = cli.run(cfg)
    # personal index synced; work index local
    data = tmp_path / "data"
    personal = json.loads((data / "synced" / "m" / "index.json").read_text())["sessions"]
    work = json.loads((data / "index.private.local.json").read_text())["sessions"]
    assert [s["session_id"] for s in personal] == ["personal1"]
    assert [s["session_id"] for s in work] == ["work1"]
    # BOTH appear in the report's accounts (work is viewable, not hidden)
    md = (data / "reports" / "insights.md").read_text()
    assert "work" in md and "personal" in md
    assert result["counts"] == {"personal": 1, "private": 1}


def test_run_attaches_decisions_from_file(tmp_path):
    import json
    _write_session(tmp_path, ".claude-personal", "P", "s1",
                   [{"type": "assistant", "sessionId": "s1", "timestamp": "2026-05-23T12:00:00Z",
                     "cwd": "C:/me/P", "message": {"model": "m",
                     "usage": {"input_tokens": 5, "output_tokens": 1}}}])
    dec = tmp_path / "decisions.jsonl"
    dec.write_text(json.dumps({"timestamp": "2026-05-22T10:00:00", "title": "Chose repo-based wall"}) + "\n",
                   encoding="utf-8")
    cfg = {"machine": "m", "dataDir": str(tmp_path / "data"),
           "sources": [{"path": str(tmp_path / ".claude-personal"), "private": False}],
           "private_repos": [], "decisions": {"source": "file", "path": str(dec)}}
    cli.run(cfg)
    digest = json.loads((tmp_path / "data" / "digest.json").read_text())
    assert any(d["title"] == "Chose repo-based wall" for d in digest.get("decisions", []))
    md = (tmp_path / "data" / "reports" / "insights.md").read_text()
    assert "Chose repo-based wall" in md


def test_run_writes_digest_json(tmp_path):
    import json
    _write_session(tmp_path, ".claude-personal", "P", "s1",
                   [{"type": "assistant", "sessionId": "s1",
                     "timestamp": "2026-05-23T12:00:00Z", "cwd": "C:/me/P",
                     "gitBranch": "feat/y",
                     "message": {"model": "claude-opus-4-7",
                                 "usage": {"input_tokens": 10, "output_tokens": 2}}}])
    cfg = {"machine": "testbox", "dataDir": str(tmp_path / "data"),
           "sources": [{"path": str(tmp_path / ".claude-personal"), "private": False}],
           "private_repos": []}
    cli.run(cfg)
    digest_path = tmp_path / "data" / "digest.json"
    assert digest_path.exists()
    d = json.loads(digest_path.read_text())
    assert "token_cost" in d and "pick_back_up" in d


def test_emit_tagging_input(tmp_path):
    import json
    _write_session(tmp_path, ".claude-personal", "C--repo", "s1",
                   [{"type": "user", "sessionId": "s1", "timestamp": "2026-05-23T12:00:00Z",
                     "cwd": "C:/repo", "message": {"content": "do the thing"}},
                    {"type": "assistant", "sessionId": "s1", "timestamp": "2026-05-23T12:01:00Z",
                     "cwd": "C:/repo", "message": {"model": "m",
                     "usage": {"input_tokens": 5, "output_tokens": 1},
                     "content": [{"type": "text", "text": "did it"}]}}])
    data = tmp_path / "data"
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"machine": "m", "dataDir": str(data), "work_repos": [],
        "homes": [{"path": str(tmp_path / ".claude-personal"), "account": "personal", "walled": False}]}),
        encoding="utf-8")
    # build the index first so report_set has the session
    from vibe_insights import cli
    cli.main(["--config", str(cfg_path)])
    rc = cli.main(["--emit-tagging-input", "--config", str(cfg_path)])
    assert rc == 0
    todo = json.loads((data / "tagging_input.json").read_text())
    assert len(todo) == 1
    assert todo[0]["session_id"] == "s1"
    assert "do the thing" in todo[0]["sample"]


def test_run_repo_filter(tmp_path):
    import json
    _write_session(tmp_path, ".claude-personal", "A", "s1",
                   [{"type": "assistant", "sessionId": "s1", "timestamp": "2026-05-23T12:00:00Z",
                     "cwd": "C:/x/ROROROblox", "message": {"model": "m",
                     "usage": {"input_tokens": 5, "output_tokens": 1}}}])
    _write_session(tmp_path, ".claude-personal", "B", "s2",
                   [{"type": "assistant", "sessionId": "s2", "timestamp": "2026-05-23T12:00:00Z",
                     "cwd": "C:/x/Celestia3", "message": {"model": "m",
                     "usage": {"input_tokens": 5, "output_tokens": 1}}}])
    cfg = {"machine": "m", "dataDir": str(tmp_path / "data"), "private_repos": [],
           "sources": [{"path": str(tmp_path / ".claude-personal"), "private": False}]}
    result = cli.run(cfg, repo_filter="rororoblox")  # case-insensitive
    digest = json.loads((tmp_path / "data" / "digest.json").read_text())
    # only the ROROROblox session counts
    assert digest["token_cost"]["sessions"] == 1
    md = (tmp_path / "data" / "reports" / "insights.md").read_text()
    assert "ROROROblox" in md and "Celestia3" not in md


def test_story_input_writes_spine(tmp_path):
    import json
    _write_session(tmp_path, ".claude-personal", "Foo", "s1",
                   [{"type": "assistant", "sessionId": "s1", "timestamp": "2026-05-23T12:00:00Z",
                     "cwd": "C:/x/Foo", "message": {"model": "m",
                     "usage": {"input_tokens": 5, "output_tokens": 1}}}])
    data = tmp_path / "data"
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"machine": "m", "dataDir": str(data), "work_repos": [],
        "homes": [{"path": str(tmp_path / ".claude-personal"), "account": "personal", "walled": False}]}),
        encoding="utf-8")
    from vibe_insights import cli
    cli.main(["--config", str(cfg_path)])  # build the index first
    rc = cli.main(["--story-input", "Foo", "--config", str(cfg_path)])
    assert rc == 0
    spine = (data / "story-input.md").read_text(encoding="utf-8")
    assert "# Build story spine: Foo" in spine
    assert "## Session timeline" in spine


def test_run_merges_tag_cache(tmp_path):
    import json
    _write_session(tmp_path, ".claude-personal", "P", "s1",
                   [{"type": "assistant", "sessionId": "s1", "timestamp": "2026-05-23T12:00:00Z",
                     "cwd": "C:/me/P", "message": {"model": "m",
                     "usage": {"input_tokens": 5, "output_tokens": 1}}}])
    data = tmp_path / "data"
    data.mkdir()
    (data / "tags.cache.json").write_text(json.dumps({
        "s1": {"friction": "none", "satisfaction": "satisfied",
               "outcome": "fully_achieved", "session_type": "feature", "last_ts": "x"}}),
        encoding="utf-8")
    cfg = {"machine": "m", "dataDir": str(data), "private_repos": [],
           "sources": [{"path": str(tmp_path / ".claude-personal"), "private": False}]}
    cli.run(cfg)
    digest = json.loads((data / "digest.json").read_text())
    assert digest["tags"]["tagged"] == 1
    assert digest["tags"]["outcome"]["fully_achieved"] == 1


def test_run_personal_by_default_single_source(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    d = tmp_path / ".claude" / "projects" / "C--repo"
    d.mkdir(parents=True)
    (d / "s1.jsonl").write_text(json.dumps(
        {"type": "assistant", "sessionId": "s1", "timestamp": "2026-05-20T10:00:00Z",
         "cwd": "C:/repo", "message": {"model": "claude-opus-4-7",
         "usage": {"input_tokens": 10, "output_tokens": 1}}}) + "\n", encoding="utf-8")
    cfg = config_mod.normalize_config({"machine": "m", "dataDir": str(tmp_path / "data"),
                                       "decisions": {"source": "none"}, "voice": None})
    result = cli.run(cfg)
    assert result["counts"] == {"personal": 1, "private": 0}
