import json
from pathlib import Path
from vibe_insights import scan


def _write(home, root, project, sid, lines):
    d = Path(home) / root / "projects" / project
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{sid}.jsonl").write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")


def test_locate_session_files_skips_subagents(tmp_path):
    _write(tmp_path, ".claude-personal", "C--repo", "sessA", [{"type": "user", "sessionId": "sessA"}])
    sub = tmp_path / ".claude-personal" / "projects" / "C--repo" / "sessA" / "subagents"
    sub.mkdir(parents=True, exist_ok=True)
    (sub / "agent-1.jsonl").write_text('{"type":"assistant"}\n', encoding="utf-8")
    m = scan.locate_session_files([str(tmp_path / ".claude-personal")])
    assert "sessA" in m
    assert "agent-1" not in m


def test_sample_session_extracts_users_assistant_errors(tmp_path):
    f = tmp_path / "s.jsonl"
    f.write_text("\n".join(json.dumps(x) for x in [
        {"type": "user", "message": {"content": "Build the thing please"}},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "On it."},
                                                       {"type": "tool_use", "name": "Bash"}]}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "is_error": True, "content": "boom"}]}},
        {"type": "user", "message": {"content": "second prompt"}},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "Done now."}]}},
    ]) + "\n", encoding="utf-8")
    sample = scan.sample_session(f)
    assert "Build the thing please" in sample
    assert "Done now." in sample           # last assistant text
    assert "TOOL_ERRORS: 1" in sample
