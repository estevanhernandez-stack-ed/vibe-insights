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
    assert counts == {"personal": 1, "private": 1, "retained": 0}
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


def test_write_indexes_uses_private_filename(tmp_path):
    sources = [{"path": str(tmp_path / ".claude-work"), "private": True}]
    _write_session(tmp_path, ".claude-work", "p", "w1",
                   [_assistant("w1", "2026-05-20T10:00:00Z", 1, 1, "C:/w/A")])
    recs = scan.build_records(sources, machine="m")
    counts = scan.write_indexes(recs, tmp_path / "data", "m")
    assert counts == {"personal": 0, "private": 1, "retained": 0}
    assert (tmp_path / "data" / "index.private.local.json").exists()
    assert not (tmp_path / "data" / "index.work.local.json").exists()


def test_read_local_private_index_prefers_new_falls_back_to_legacy(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    (d / "index.work.local.json").write_text(
        json.dumps({"sessions": [{"session_id": "legacy"}]}), encoding="utf-8")
    assert [s["session_id"] for s in scan.read_local_private_index(d)] == ["legacy"]
    (d / "index.private.local.json").write_text(
        json.dumps({"sessions": [{"session_id": "fresh"}]}), encoding="utf-8")
    assert [s["session_id"] for s in scan.read_local_private_index(d)] == ["fresh"]


def test_read_local_private_index_missing_returns_empty(tmp_path):
    assert scan.read_local_private_index(tmp_path) == []


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


def test_burn_by_day_spreads_usage_across_active_days(tmp_path):
    # One session resumed across three months must not book everything to last_ts.
    lines = [
        _assistant("long", "2026-06-26T19:00:00Z", 100, 900, "C:/x/app"),
        _assistant("long", "2026-07-15T10:00:00Z", 10, 40, "C:/x/app"),
        _assistant("long", "2026-09-14T21:00:00Z", 1, 9, "C:/x/app"),
    ]
    _write_session(tmp_path, ".claude", "proj", "long", lines)
    recs = scan.build_records([{"path": str(tmp_path / ".claude"), "private": False}], machine="m")
    rec = recs["long"]
    assert rec.burn_by_day == {"2026-06-26": 1000, "2026-07-15": 50, "2026-09-14": 10}
    assert sum(rec.burn_by_day.values()) == rec.human_tokens
    assert rec.to_dict()["burn_by_day"] == rec.burn_by_day


def test_write_indexes_accumulates_sessions_gone_from_disk(tmp_path):
    out = tmp_path / "data"
    src = [{"path": str(tmp_path / ".claude"), "private": False}]
    _write_session(tmp_path, ".claude", "proj", "old",
                   [_assistant("old", "2026-02-01T10:00:00Z", 10, 1, "C:/x/a")])
    scan.write_indexes(scan.build_records(src, machine="m"), out, "m")
    # cleanup purges the old transcript; a new session appears
    (tmp_path / ".claude" / "projects" / "proj" / "old.jsonl").unlink()
    _write_session(tmp_path, ".claude", "proj", "new",
                   [_assistant("new", "2026-09-01T10:00:00Z", 20, 2, "C:/x/a")])
    counts = scan.write_indexes(scan.build_records(src, machine="m"), out, "m")
    idx = {s["session_id"]: s for s in
           json.loads((out / "synced" / "m" / "index.json").read_text())["sessions"]}
    assert set(idx) == {"old", "new"}
    assert idx["old"]["human_tokens"] == 11 and idx["old"].get("retained") is True
    assert idx["new"]["human_tokens"] == 22 and not idx["new"].get("retained")
    assert counts == {"personal": 2, "private": 0, "retained": 1}


def test_write_indexes_fresh_record_replaces_retained(tmp_path):
    out = tmp_path / "data"
    src = [{"path": str(tmp_path / ".claude"), "private": False}]
    f = _write_session(tmp_path, ".claude", "proj", "s",
                       [_assistant("s", "2026-09-01T10:00:00Z", 10, 1, "C:/x/a")])
    scan.write_indexes(scan.build_records(src, machine="m"), out, "m")
    f.write_text(f.read_text() + json.dumps(_assistant("s", "2026-09-02T10:00:00Z", 5, 5, "C:/x/a")) + "\n")
    scan.write_indexes(scan.build_records(src, machine="m"), out, "m")
    idx = json.loads((out / "synced" / "m" / "index.json").read_text())["sessions"]
    assert len(idx) == 1 and idx[0]["human_tokens"] == 21 and not idx[0].get("retained")


def test_write_indexes_accumulate_off_drops_gone_sessions(tmp_path):
    out = tmp_path / "data"
    src = [{"path": str(tmp_path / ".claude"), "private": False}]
    _write_session(tmp_path, ".claude", "proj", "old",
                   [_assistant("old", "2026-02-01T10:00:00Z", 10, 1, "C:/x/a")])
    scan.write_indexes(scan.build_records(src, machine="m"), out, "m")
    (tmp_path / ".claude" / "projects" / "proj" / "old.jsonl").unlink()
    scan.write_indexes(scan.build_records(src, machine="m"), out, "m", accumulate=False)
    idx = json.loads((out / "synced" / "m" / "index.json").read_text())["sessions"]
    assert idx == []
