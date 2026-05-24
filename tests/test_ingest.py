# tests/test_ingest.py
from vibe_insights.scan import ingest_event


def _records():
    return {}


def test_assistant_event_accumulates_tokens_tools_model():
    recs = _records()
    ev = {
        "type": "assistant", "sessionId": "s1", "timestamp": "2026-05-23T10:00:00Z",
        "cwd": "C:\\Users\\estev\\Projects\\Sanduhr", "gitBranch": "main",
        "message": {
            "model": "claude-opus-4-7",
            "usage": {"input_tokens": 100, "output_tokens": 20,
                      "cache_creation_input_tokens": 5, "cache_read_input_tokens": 7,
                      "server_tool_use": {"web_search_requests": 2, "web_fetch_requests": 1}},
            "content": [
                {"type": "text", "text": "hi"},
                {"type": "tool_use", "name": "Bash"},
                {"type": "tool_use", "name": "Bash"},
                {"type": "tool_use", "name": "Read"},
            ],
        },
    }
    ingest_event(recs, ev, account="personal", machine="m", walled=False, default_sid="s1")
    r = recs["s1"]
    assert r.tokens_input == 100 and r.tokens_output == 20
    assert r.tokens_cache_creation == 5 and r.tokens_cache_read == 7
    assert r.web_search == 2 and r.web_fetch == 1
    assert r.assistant_msgs == 1
    assert r.tool_counts == {"Bash": 2, "Read": 1}
    assert r.models == ["claude-opus-4-7"]
    assert r.repo == "Sanduhr" and r.branch == "main"
    assert r.human_tokens == 120


def test_ai_title_and_user_events():
    recs = _records()
    ingest_event(recs, {"type": "ai-title", "sessionId": "s1", "aiTitle": "Fix the bug"},
                 account="personal", machine="m", walled=False, default_sid="s1")
    ingest_event(recs, {"type": "user", "sessionId": "s1", "timestamp": "2026-05-23T09:00:00Z"},
                 account="personal", machine="m", walled=False, default_sid="s1")
    r = recs["s1"]
    assert r.title == "Fix the bug"
    assert r.user_msgs == 1


def test_missing_session_id_falls_back_to_default():
    recs = _records()
    ingest_event(recs, {"type": "user"}, account="personal", machine="m",
                 walled=False, default_sid="fallback")
    assert "fallback" in recs


def test_captures_file_extensions_and_tool_errors():
    recs = {}
    # assistant edits two files -> extensions; a tool_use we don't care about ignored
    ingest_event(recs, {
        "type": "assistant", "sessionId": "s1", "timestamp": "2026-05-23T10:00:00Z",
        "message": {"model": "m", "usage": {"input_tokens": 1, "output_tokens": 1},
            "content": [
                {"type": "tool_use", "name": "Edit", "input": {"file_path": "C:/x/a.py"}},
                {"type": "tool_use", "name": "Write", "input": {"file_path": "C:/x/b.ts"}},
                {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}},
            ]}}, account="personal", machine="m", walled=False, default_sid="s1")
    # a tool_result error comes back in a user event
    ingest_event(recs, {
        "type": "user", "sessionId": "s1", "timestamp": "2026-05-23T10:01:00Z",
        "message": {"content": [
            {"type": "tool_result", "is_error": True, "content": "boom"},
            {"type": "tool_result", "content": "ok"},
        ]}}, account="personal", machine="m", walled=False, default_sid="s1")
    r = recs["s1"]
    assert r.file_exts == {"py": 1, "ts": 1}
    assert r.tool_errors == 1


def test_response_time_buckets():
    recs = {}
    base = "2026-05-23T10:00:00Z"
    # assistant at 10:00:00, user replies at 10:00:30 -> <1m
    ingest_event(recs, {"type": "assistant", "sessionId": "s1", "timestamp": "2026-05-23T10:00:00Z",
                        "message": {"model": "m", "usage": {"input_tokens": 1, "output_tokens": 1}}},
                 account="personal", machine="m", walled=False, default_sid="s1")
    ingest_event(recs, {"type": "user", "sessionId": "s1", "timestamp": "2026-05-23T10:00:30Z",
                        "message": {"content": "hi"}},
                 account="personal", machine="m", walled=False, default_sid="s1")
    # assistant at 10:01, user replies at 10:11 -> 5-30m
    ingest_event(recs, {"type": "assistant", "sessionId": "s1", "timestamp": "2026-05-23T10:01:00Z",
                        "message": {"model": "m", "usage": {"input_tokens": 1, "output_tokens": 1}}},
                 account="personal", machine="m", walled=False, default_sid="s1")
    ingest_event(recs, {"type": "user", "sessionId": "s1", "timestamp": "2026-05-23T10:11:00Z",
                        "message": {"content": "next"}},
                 account="personal", machine="m", walled=False, default_sid="s1")
    r = recs["s1"]
    assert r.response_buckets.get("<1m") == 1
    assert r.response_buckets.get("5-30m") == 1
    # the transient last-assistant tracker must NOT serialize
    assert "_last_asst_ts" not in r.to_dict()
