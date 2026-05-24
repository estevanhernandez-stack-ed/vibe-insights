# tests/test_records.py
from datetime import datetime, timezone

from vibe_insights.records import SessionRecord


def test_human_tokens_is_input_plus_output():
    r = SessionRecord(session_id="s", account="personal", machine="m", walled=False)
    r.tokens_input = 100
    r.tokens_output = 40
    r.tokens_cache_read = 9999
    assert r.human_tokens == 140


def test_to_dict_serializes_timestamps_and_human_tokens():
    r = SessionRecord(session_id="s", account="personal", machine="m", walled=False)
    r.first_ts = datetime(2026, 5, 1, tzinfo=timezone.utc)
    r.last_ts = datetime(2026, 5, 2, tzinfo=timezone.utc)
    r.tokens_input, r.tokens_output = 10, 5
    d = r.to_dict()
    assert d["first_ts"] == "2026-05-01T00:00:00+00:00"
    assert d["last_ts"] == "2026-05-02T00:00:00+00:00"
    assert d["human_tokens"] == 15
    assert d["account"] == "personal"
