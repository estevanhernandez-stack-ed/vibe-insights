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


# --- Phase 2 step 6: How you work + open-threads lenses ---

def _how_you_work_digest():
    """Digest carrying the new Phase-2 keys: tool_mix, delegation, by_machine,
    plus enriched pick_back_up. Constructed directly so the render assertions
    don't depend on analytics' date math."""
    return {
        "token_cost": {"burn": 100, "input": 10, "output": 90, "output_share": 90.0,
                       "cache_read": 50, "cache_creation": 5, "cache_read_share": 80.0,
                       "top_repos_by_burn": [{"repo": "vibe-insights", "sessions": 2, "burn": 100}],
                       "model_session_counts": {"claude-opus-4-7": 2}},
        "trends": {"by_day": {"2026-05-23": {"sessions": 2, "burn": 100}},
                   "recent_avg_per_day": 100, "baseline_avg_per_day": 50,
                   "acceleration_multiple": 2.0},
        "tool_mix": {
            "tools": [{"tool": "Bash", "count": 8400}, {"tool": "Read", "count": 7300},
                      {"tool": "Edit", "count": 4100}],
            "web_search": 12, "web_fetch": 7,
        },
        "delegation": {"agent_calls": 397, "haiku_sessions": 31},
        "by_machine": [
            {"machine": "nebuchadnezzar", "sessions": 75, "assistant_msgs": 39284,
             "burn": 48900000, "repos": 14},
            {"machine": "dunder-mifflan", "sessions": 57, "assistant_msgs": 17090,
             "burn": 22100000, "repos": 9},
        ],
        "pick_back_up": [
            {"repo": "Celestia3", "branch": "feat/ephem", "machine": "neb",
             "title": "finish the engine", "last_ts": "2026-05-23T12:00:00+00:00",
             "age_days": 1, "empty_title": False, "resume_signal": True,
             "unfinished_score": 6},
        ],
        "prune_candidates": [
            {"repo": "OldThing", "branch": "feat/dead", "machine": "neb",
             "title": "shipped feature", "last_ts": "2026-03-01T12:00:00+00:00",
             "age_days": 84, "empty_title": False, "resume_signal": False,
             "unfinished_score": 0},
        ],
    }


def test_render_how_you_work_markdown():
    digest = _how_you_work_digest()
    md = report.render_markdown([], digest=digest)
    assert "## How you work" in md
    # tool-mix entries present
    assert "Bash" in md and "8,400" in md
    assert "Read" in md and "7,300" in md
    # delegation + web lines
    assert "397" in md and "31" in md  # agent calls + haiku sessions
    assert "12" in md and "7" in md    # web search + fetch
    # per-machine row data
    assert "nebuchadnezzar" in md and "39,284" in md
    assert "dunder-mifflan" in md and "17,090" in md


def test_render_how_you_work_html():
    digest = _how_you_work_digest()
    html = report.render_html([], digest=digest)
    assert "How you work" in html
    assert "Bash" in html and "8,400" in html
    assert "397" in html      # agent calls tile
    assert "nebuchadnezzar" in html and "39,284" in html


def test_render_pick_back_up_shows_age_and_score():
    digest = _how_you_work_digest()
    md = report.render_markdown([], digest=digest)
    # enriched columns in the pick-back-up table
    assert "Age (d)" in md
    assert "Score" in md
    assert "finish the engine" in md
    html = report.render_html([], digest=digest)
    assert "Age" in html and "Score" in html
    assert "finish the engine" in html


def test_render_prune_candidates_present_when_nonempty():
    digest = _how_you_work_digest()
    md = report.render_markdown([], digest=digest)
    assert "## Prune candidates" in md
    assert "OldThing" in md
    html = report.render_html([], digest=digest)
    assert "Prune candidates" in html
    assert "OldThing" in html


def test_render_prune_candidates_omitted_when_empty():
    digest = _how_you_work_digest()
    digest["prune_candidates"] = []
    md = report.render_markdown([], digest=digest)
    assert "## Prune candidates" not in md
    assert "OldThing" not in md
    html = report.render_html([], digest=digest)
    assert "Prune candidates" not in html
    assert "OldThing" not in html
    # pick-back-up still renders
    assert "Pick this back up" in html
