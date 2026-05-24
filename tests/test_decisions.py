import json
from pathlib import Path

from vibe_insights import decisions


def test_none_source_returns_empty(tmp_path):
    assert decisions.load_decisions({"source": "none"}, tmp_path) == []
    assert decisions.load_decisions(None, tmp_path) == []


def test_file_jsonl(tmp_path):
    f = tmp_path / "d.jsonl"
    f.write_text(
        json.dumps({"timestamp": "2026-05-20T10:00:00", "title": "Older", "body": "b"}) + "\n"
        + json.dumps({"timestamp": "2026-05-22T10:00:00", "title": "Newer",
                      "project_tag": "P", "link": "x.md"}) + "\n"
        + "{bad json}\n",
        encoding="utf-8")
    out = decisions.load_decisions({"source": "file", "path": str(f)}, tmp_path)
    assert [d["title"] for d in out] == ["Newer", "Older"]  # newest first, bad line skipped
    assert out[0]["project_tag"] == "P" and out[0]["link"] == "x.md"


def test_file_markdown_vibe_wrap_format(tmp_path):
    f = tmp_path / "decisions.md"
    f.write_text(
        "# Decisions\n\n"
        "## 2026-05-22\n\n"
        "### 14:05 — Picked SQLite over JSON\n\n"
        "Faster queries.\n\n"
        "## 2026-05-21\n\n"
        "### 09:30 — Walled work from personal\n\n"
        "Confidentiality boundary.\n",
        encoding="utf-8")
    out = decisions.load_decisions({"source": "file", "path": str(f)}, tmp_path)
    assert [d["title"] for d in out] == ["Picked SQLite over JSON", "Walled work from personal"]
    assert out[0]["timestamp"].startswith("2026-05-22T14:05")
    assert "Faster queries." in out[0]["body"]


def test_mcp_source_reads_cache(tmp_path):
    (tmp_path / "decisions.cache.json").write_text(
        json.dumps([{"timestamp": "2026-05-23T10:00:00", "title": "From MCP",
                     "project_tag": "proj-1"}]), encoding="utf-8")
    out = decisions.load_decisions({"source": "mcp"}, tmp_path)
    assert len(out) == 1 and out[0]["title"] == "From MCP"


def test_missing_or_bad_never_raises(tmp_path):
    assert decisions.load_decisions({"source": "file", "path": str(tmp_path / "nope.jsonl")}, tmp_path) == []
    assert decisions.load_decisions({"source": "mcp"}, tmp_path) == []  # no cache file
