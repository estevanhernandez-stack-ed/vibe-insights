import json
from vibe_insights import tagging


def test_load_missing_is_empty(tmp_path):
    assert tagging.load_cache(tmp_path / "nope.json") == {}


def test_save_then_load_roundtrip(tmp_path):
    p = tmp_path / "tags.cache.json"
    tagging.save_cache(p, {"s1": {"friction": "none", "last_ts": "t"}})
    assert tagging.load_cache(p)["s1"]["friction"] == "none"


def test_untagged_detects_missing_and_changed(tmp_path):
    cache = {"s1": {"last_ts": "2026-05-20T10:00:00+00:00"}}
    sessions = [
        {"session_id": "s1", "last_ts": "2026-05-20T10:00:00+00:00"},  # cached, unchanged
        {"session_id": "s2", "last_ts": "2026-05-20T11:00:00+00:00"},  # missing
        {"session_id": "s1b", "last_ts": "X"},                          # missing
        {"session_id": "s1", "last_ts": "CHANGED"},                     # changed -> retag
    ]
    ut = tagging.untagged(sessions, cache)
    ids = [s["session_id"] for s in ut]
    assert "s2" in ids and "s1b" in ids
    assert ids.count("s1") == 1  # the changed-last_ts one


def test_merge_into_attaches_tags():
    cache = {"s1": {"friction": "buggy_code", "outcome": "mostly_achieved"}}
    sessions = [{"session_id": "s1"}, {"session_id": "s2"}]
    tagging.merge_into(sessions, cache)
    assert sessions[0]["tags"]["friction"] == "buggy_code"
    assert "tags" not in sessions[1]
