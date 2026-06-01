# tests/test_scan.py
import json
from pathlib import Path

import cc_logs
from vibe_insights import scan


def _write_session(home, root_name, project, sid, lines):
    d = Path(home) / root_name / "projects" / project
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{sid}.jsonl"
    f.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
    return f


def _assistant(sid, ts, inp, out, cwd):
    return {"type": "assistant", "sessionId": sid, "timestamp": ts, "cwd": cwd,
            "message": {"model": "claude-opus-4-7",
                        "usage": {"input_tokens": inp, "output_tokens": out}}}


def test_private_source_walls_from_personal(tmp_path):
    _write_session(tmp_path, ".claude-work", "projA", "w1",
                   [_assistant("w1", "2026-05-20T10:00:00Z", 50, 5, "C:/work/A")])
    _write_session(tmp_path, ".claude-personal", "projB", "p1",
                   [_assistant("p1", "2026-05-21T10:00:00Z", 80, 8, "C:/me/B")])
    sources = [
        {"path": str(tmp_path / ".claude-work"), "private": True},
        {"path": str(tmp_path / ".claude-personal"), "private": False},
    ]
    records = scan.build_records(sources, machine="m")
    out = tmp_path / "data"
    counts = scan.write_indexes(records, out, "m")
    personal = json.loads((out / "synced" / "m" / "index.json").read_text())["sessions"]
    private = json.loads((out / "index.private.local.json").read_text())["sessions"]
    assert counts == {"personal": 1, "private": 1}
    assert [s["session_id"] for s in personal] == ["p1"]
    assert all(s["account"] == "personal" for s in personal)
    assert [s["session_id"] for s in private] == ["w1"]
    assert not (out / "synced" / "m" / "index.private.local.json").exists()


def test_private_repos_reclassify_by_repo(tmp_path):
    _write_session(tmp_path, ".claude", "proj", "s_personal",
                   [_assistant("s_personal", "2026-05-20T12:00:00Z", 10, 1, "C:/x/my-hub")])
    _write_session(tmp_path, ".claude", "proj2", "s_priv",
                   [_assistant("s_priv", "2026-05-20T12:00:00Z", 10, 1, "C:/x/employer-api")])
    sources = [{"path": str(tmp_path / ".claude"), "private": False}]
    recs = scan.build_records(sources, machine="m", private_repos=["employer-api"])
    by_id = {r.session_id: r for r in recs.values()}
    assert by_id["s_personal"].walled is False and by_id["s_personal"].account == "personal"
    assert by_id["s_priv"].walled is True and by_id["s_priv"].account == "private"


def test_default_source_is_personal(tmp_path):
    _write_session(tmp_path, ".claude", "proj", "s1",
                   [_assistant("s1", "2026-05-20T12:00:00Z", 10, 1, "C:/x/anything")])
    sources = [{"path": str(tmp_path / ".claude"), "private": False}]
    recs = scan.build_records(sources, machine="m")
    # THE FIX: a lone ~/.claude is personal now, not walled work.
    assert list(recs.values())[0].walled is False
    assert list(recs.values())[0].account == "personal"


def test_personal_burn_reconciles_with_cc_logs(tmp_path, monkeypatch):
    # Only a personal home exists -> cc_logs (which scans .claude + .claude-personal)
    # sees exactly the same data as vibe-insights' personal index.
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    _write_session(tmp_path, ".claude-personal", "projB", "pers1",
                   [_assistant("pers1", "2026-05-21T10:00:00Z", 80, 8, "C:/me/B"),
                    _assistant("pers1", "2026-05-21T10:05:00Z", 20, 2, "C:/me/B")])
    sources = [{"path": str(tmp_path / ".claude-personal"), "private": False}]
    records = scan.build_records(sources, machine="m")
    vi_total = sum(r.human_tokens for r in records.values())

    from datetime import datetime, timezone
    cc_total = sum(cc_logs.tokens_since(datetime(2000, 1, 1, tzinfo=timezone.utc)).values())
    assert vi_total == cc_total == 110


def test_subagent_tokens_fold_into_parent(tmp_path):
    import json
    base = tmp_path / ".claude-personal" / "projects" / "C--repo"
    base.mkdir(parents=True)
    (base / "sess.jsonl").write_text(json.dumps(
        {"type": "assistant", "sessionId": "sess", "timestamp": "2026-05-21T10:00:00Z",
         "cwd": "C:/repo", "message": {"model": "claude-opus-4-7",
         "usage": {"input_tokens": 80, "output_tokens": 8}}}) + "\n", encoding="utf-8")
    sub = base / "sess" / "subagents"
    sub.mkdir(parents=True)
    (sub / "agent-1.jsonl").write_text(json.dumps(
        {"type": "assistant", "sessionId": "sess", "timestamp": "2026-05-21T10:01:00Z",
         "message": {"model": "claude-opus-4-7",
         "usage": {"input_tokens": 20, "output_tokens": 2}}}) + "\n", encoding="utf-8")
    sources = [{"path": str(tmp_path / ".claude-personal"), "private": False}]
    records = scan.build_records(sources, machine="m")
    assert len(records) == 1                       # subagent folds into parent, not a new session
    assert records["sess"].human_tokens == 110     # (80+8) + (20+2)
