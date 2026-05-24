# tests/test_report.py
from vibe_insights import report


def _sessions():
    return [
        {"session_id": "a", "account": "personal", "machine": "dunder",
         "repo": "vibe-insights", "branch": "main", "title": "Build the engine",
         "last_ts": "2026-05-23T10:00:00+00:00", "human_tokens": 1200},
        {"session_id": "b", "account": "personal", "machine": "neb",
         "repo": "Sanduhr", "branch": "main", "title": "Token tab",
         "last_ts": "2026-05-22T10:00:00+00:00", "human_tokens": 800},
    ]


def test_coverage_groups_by_account_machine():
    rows = report.coverage(_sessions())
    by_machine = {r["machine"]: r for r in rows}
    assert by_machine["dunder"]["sessions"] == 1
    assert by_machine["dunder"]["human_tokens"] == 1200
    assert by_machine["neb"]["repos"] == 1


def test_where_was_i_orders_by_last_ts_desc():
    rows = report.where_was_i(_sessions(), limit=10)
    assert [r["repo"] for r in rows] == ["vibe-insights", "Sanduhr"]
    assert rows[0]["title"] == "Build the engine"


def test_render_markdown_contains_sections():
    md = report.render_markdown(_sessions())
    assert "# vibe-insights" in md
    assert "Coverage" in md
    assert "Where was I" in md
    assert "vibe-insights" in md


def test_render_markdown_escapes_pipes_in_titles():
    sessions = [{"session_id": "a", "account": "personal", "machine": "m",
                 "repo": "r", "branch": "main", "title": "fix a|b parser",
                 "last_ts": "2026-05-23T10:00:00+00:00", "human_tokens": 5}]
    md = report.render_markdown(sessions)
    # the raw pipe must be escaped so it doesn't break the table row
    assert "a\\|b" in md
    assert "fix a|b parser" not in md


def test_render_html_escapes_coverage_cells():
    sessions = [{"session_id": "a", "account": "personal", "machine": "<script>",
                 "repo": "r", "branch": "main", "title": "t",
                 "last_ts": "2026-05-23T10:00:00+00:00", "human_tokens": 5}]
    html_out = report.render_html(sessions)
    assert "<script>" not in html_out
    assert "&lt;script&gt;" in html_out


def test_render_html_embeds_narrative():
    sessions = [{"session_id": "a", "account": "personal", "machine": "m",
                 "repo": "r", "branch": "main", "title": "t",
                 "last_ts": "2026-05-23T12:00:00+00:00", "human_tokens": 5}]
    nh = "<h2>How you work</h2><p>You ship in bursts.</p>"
    out = report.render_html(sessions, narrative_html=nh)
    assert "You ship in bursts." in out
    assert "narrative" in out  # the hero section class
    # absent when not provided
    assert "You ship in bursts." not in report.render_html(sessions)


def test_render_markdown_includes_digest_sections():
    from vibe_insights import analytics
    sessions = [
        {"session_id": "a", "account": "personal", "machine": "dunder",
         "repo": "ROROROblox", "branch": "feat/x", "title": "ship it",
         "last_ts": "2026-05-23T12:00:00+00:00", "human_tokens": 1000,
         "tokens_input": 100, "tokens_output": 900, "tokens_cache_read": 5000,
         "tokens_cache_creation": 50, "models": ["claude-opus-4-7"]},
    ]
    digest = analytics.build_digest(sessions)
    md = report.render_markdown(sessions, digest=digest)
    assert "## Token & cost" in md
    assert "## Trends" in md
    assert "## Pick this back up" in md
    assert "ROROROblox" in md
    # without digest, those sections are absent
    md2 = report.render_markdown(sessions)
    assert "## Token & cost" not in md2


def test_render_includes_new_charts():
    from vibe_insights import analytics
    sessions = [{"session_id": "a", "account": "personal", "machine": "m", "repo": "r",
                 "branch": "main", "title": "t", "last_ts": "2026-05-23T12:00:00+00:00",
                 "first_ts": "2026-05-23T11:00:00+00:00", "human_tokens": 5,
                 "tokens_input": 1, "tokens_output": 4, "tokens_cache_read": 9,
                 "tokens_cache_creation": 0, "models": ["m"],
                 "file_exts": {"py": 3}, "tool_errors": 2}]
    digest = analytics.build_digest(sessions)
    md = report.render_markdown(sessions, digest=digest)
    assert "## Languages" in md and "Python" in md
    html = report.render_html(sessions, digest=digest)
    assert "Languages" in html and "Python" in html


def test_render_includes_tag_charts():
    from vibe_insights import analytics
    sessions = [{"session_id": "a", "account": "personal", "machine": "m", "repo": "r",
                 "branch": "main", "title": "t", "last_ts": "2026-05-23T12:00:00+00:00",
                 "first_ts": "2026-05-23T11:00:00+00:00", "human_tokens": 5,
                 "tokens_input": 1, "tokens_output": 4, "tokens_cache_read": 9,
                 "tokens_cache_creation": 0, "models": ["m"],
                 "tags": {"friction": "none", "satisfaction": "satisfied",
                          "outcome": "fully_achieved", "session_type": "feature"}}]
    digest = analytics.build_digest(sessions)
    md = report.render_markdown(sessions, digest=digest)
    assert "## How it went" in md and "fully_achieved" in md
    html = report.render_html(sessions, digest=digest)
    assert "How it went" in html


def test_render_includes_decisions_section():
    from vibe_insights import analytics
    sessions = [{"session_id": "a", "account": "personal", "machine": "m",
                 "repo": "r", "branch": "main", "title": "t",
                 "last_ts": "2026-05-23T12:00:00+00:00", "human_tokens": 5}]
    digest = analytics.build_digest(sessions)
    digest["decisions"] = [{"timestamp": "2026-05-22T14:00:00", "title": "Walled work by repo",
                            "project_tag": "vibe-insights", "link": "x.md"}]
    md = report.render_markdown(sessions, digest=digest)
    assert "## Decisions" in md
    assert "Walled work by repo" in md
    html = report.render_html(sessions, digest=digest)
    assert "Decisions" in html and "Walled work by repo" in html


def test_render_at_a_glance_and_next_moves():
    from vibe_insights import analytics
    sessions = [{"session_id": "a", "account": "personal", "machine": "m", "repo": "ROROROblox",
                 "branch": "feat/x", "title": "ship it", "last_ts": "2026-05-23T12:00:00+00:00",
                 "first_ts": "2026-05-23T11:00:00+00:00", "human_tokens": 1000,
                 "tokens_input": 100, "tokens_output": 900, "tokens_cache_read": 9, "tokens_cache_creation": 0,
                 "models": ["m"], "tags": {"friction": "env_tooling", "satisfaction": "satisfied",
                                            "outcome": "fully_achieved", "session_type": "feature"}}]
    digest = analytics.build_digest(sessions)
    html = report.render_html(sessions, digest=digest)
    assert "At a glance" in html
    assert "Next moves" in html
    md = report.render_markdown(sessions, digest=digest)
    assert "## At a glance" in md


def test_render_response_time():
    from vibe_insights import analytics
    sessions = [{"session_id": "a", "account": "personal", "machine": "m", "repo": "r",
                 "branch": "main", "title": "t", "last_ts": "2026-05-23T12:00:00+00:00",
                 "first_ts": "2026-05-23T11:00:00+00:00", "human_tokens": 5,
                 "tokens_input": 1, "tokens_output": 4, "tokens_cache_read": 9, "tokens_cache_creation": 0,
                 "models": ["m"], "response_buckets": {"<1m": 4, "5-30m": 1}}]
    digest = analytics.build_digest(sessions)
    md = report.render_markdown(sessions, digest=digest)
    assert "## Response time" in md
    html = report.render_html(sessions, digest=digest)
    assert "Response time" in html
