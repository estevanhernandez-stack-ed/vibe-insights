import json
from pathlib import Path

from vibe_insights import merge


def _write_machine_index(synced, machine, sessions):
    d = synced / machine
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.json").write_text(json.dumps({"sessions": sessions}), encoding="utf-8")


def test_load_merged_unions_across_machines(tmp_path):
    synced = tmp_path / "synced"
    _write_machine_index(synced, "dunder", [
        {"session_id": "a", "account": "personal", "machine": "dunder",
         "assistant_msgs": 3, "human_tokens": 100}])
    _write_machine_index(synced, "neb", [
        {"session_id": "b", "account": "personal", "machine": "neb",
         "assistant_msgs": 5, "human_tokens": 200}])
    merged = merge.load_merged(synced)
    ids = sorted(s["session_id"] for s in merged)
    assert ids == ["a", "b"]


def test_load_merged_dedups_keeping_richer_record(tmp_path):
    synced = tmp_path / "synced"
    _write_machine_index(synced, "dunder", [
        {"session_id": "x", "account": "personal", "machine": "dunder",
         "assistant_msgs": 2, "human_tokens": 50}])
    _write_machine_index(synced, "neb", [
        {"session_id": "x", "account": "personal", "machine": "neb",
         "assistant_msgs": 9, "human_tokens": 400}])
    merged = merge.load_merged(synced)
    assert len(merged) == 1
    assert merged[0]["assistant_msgs"] == 9  # richer record wins


def test_load_merged_missing_dir_is_empty(tmp_path):
    assert merge.load_merged(tmp_path / "nope") == []
