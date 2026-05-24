from datetime import datetime, timedelta, timezone

from vibe_insights import analytics


def _ts_days_ago(n: int) -> str:
    """ISO timestamp n days before real now (tz-aware) — stable vs analytics' now."""
    return (datetime.now(timezone.utc) - timedelta(days=n)).isoformat()


def _s(**kw):
    base = dict(session_id="x", account="personal", machine="m", repo="r",
                branch="main", title="t", last_ts="2026-05-20T12:00:00+00:00",
                tokens_input=0, tokens_output=0, tokens_cache_read=0,
                tokens_cache_creation=0, human_tokens=0, models=[])
    base.update(kw)
    return base


def test_token_cost_basic():
    sessions = [
        _s(tokens_input=10, tokens_output=90, tokens_cache_read=900,
           human_tokens=100, repo="A", models=["claude-opus-4-7"]),
        _s(tokens_input=10, tokens_output=10, tokens_cache_read=100,
           human_tokens=20, repo="B", models=["claude-haiku-4-5"]),
    ]
    tc = analytics.token_cost(sessions)
    assert tc["burn"] == 120
    assert tc["output"] == 100
    assert tc["cache_read"] == 1000
    assert tc["cache_read_share"] == 98.0   # 1000 / (20 + 1000)
    assert tc["top_repos_by_burn"][0]["repo"] == "A"
    assert tc["top_repos_by_burn"][0]["sessions"] == 1
    assert tc["model_session_counts"]["claude-opus-4-7"] == 1


def test_trends_acceleration():
    sessions = [
        _s(last_ts="2026-05-01T12:00:00+00:00", human_tokens=100),
        _s(last_ts="2026-05-02T12:00:00+00:00", human_tokens=100),
        _s(last_ts="2026-05-10T12:00:00+00:00", human_tokens=1000),
        _s(last_ts="2026-05-11T12:00:00+00:00", human_tokens=1000),
    ]
    tr = analytics.trends(sessions)
    assert tr["recent_days"] == ["2026-05-10", "2026-05-11"]
    assert tr["acceleration_multiple"] == 10.0   # recent avg 1000 / baseline avg 100


def test_pick_back_up_feature_branches_dedup():
    sessions = [
        _s(repo="A", branch="feat/x", last_ts="2026-05-10T12:00:00+00:00", title="newer"),
        _s(repo="A", branch="feat/x", last_ts="2026-05-01T12:00:00+00:00", title="older"),
        _s(repo="B", branch="main", last_ts="2026-05-09T12:00:00+00:00"),
    ]
    pb = analytics.pick_back_up(sessions)
    assert len(pb) == 1
    assert pb[0]["repo"] == "A" and pb[0]["branch"] == "feat/x"
    assert pb[0]["title"] == "newer"


def test_build_digest_shape():
    d = analytics.build_digest([_s(human_tokens=5)])
    assert set(d) >= {"generated_at", "token_cost", "trends", "pick_back_up"}


def test_build_digest_includes_phase2_keys():
    d = analytics.build_digest([
        _s(human_tokens=5, tool_counts={"Bash": 3, "Agent": 1}, web_search=1,
           models=["claude-haiku-4-5"], assistant_msgs=4, machine="m1",
           branch="feat/x", title="wip", last_ts=_ts_days_ago(2)),
    ])
    # new keys present
    for k in ("tool_mix", "delegation", "by_machine", "prune_candidates"):
        assert k in d
    # existing keys still present and untouched in shape
    for k in ("generated_at", "token_cost", "trends", "pick_back_up",
              "languages", "tool_errors", "parallel", "tags",
              "response_dist", "glance"):
        assert k in d
    # spot-check the new aggregates are populated, not placeholders
    assert d["tool_mix"]["tools"][0]["tool"] == "Bash"
    assert d["delegation"]["agent_calls"] == 1
    assert d["delegation"]["haiku_sessions"] == 1
    assert d["by_machine"][0]["machine"] == "m1"
    assert isinstance(d["prune_candidates"], list)


def test_languages_aggregates_and_maps():
    sessions = [{"file_exts": {"py": 3, "ts": 1}}, {"file_exts": {"py": 2, "md": 5}}]
    langs = analytics.languages(sessions)
    # returns list of {language, count} sorted desc; py mapped to Python
    top = {d["language"]: d["count"] for d in langs}
    assert top["Python"] == 5
    assert top["Markdown"] == 5
    assert top["TypeScript"] == 1


def test_tool_error_total():
    assert analytics.tool_error_total([{"tool_errors": 2}, {"tool_errors": 3}, {}]) == 5


def test_parallel_sessions_counts_overlap():
    # two overlap, one disjoint
    s = [
        {"session_id": "a", "first_ts": "2026-05-20T10:00:00+00:00", "last_ts": "2026-05-20T11:00:00+00:00"},
        {"session_id": "b", "first_ts": "2026-05-20T10:30:00+00:00", "last_ts": "2026-05-20T12:00:00+00:00"},
        {"session_id": "c", "first_ts": "2026-05-21T10:00:00+00:00", "last_ts": "2026-05-21T10:30:00+00:00"},
    ]
    p = analytics.parallel_sessions(s)
    assert p["overlapping"] == 2
    assert p["max_concurrent"] >= 2


def test_tag_distributions():
    sessions = [
        {"tags": {"friction": "none", "satisfaction": "satisfied", "outcome": "fully_achieved", "session_type": "feature"}},
        {"tags": {"friction": "buggy_code", "satisfaction": "likely_satisfied", "outcome": "mostly_achieved", "session_type": "feature"}},
        {},  # untagged
    ]
    td = analytics.tag_distributions(sessions)
    assert td["tagged"] == 2
    assert td["friction"]["none"] == 1 and td["friction"]["buggy_code"] == 1
    assert td["session_type"]["feature"] == 2


def test_at_a_glance():
    digest = {
        "token_cost": {"burn": 1000, "top_repos_by_burn": [{"repo": "ROROROblox", "burn": 400, "sessions": 5}]},
        "trends": {"acceleration_multiple": 6.4},
        "tags": {"tagged": 100, "friction": {"none": 60, "env_tooling": 30, "buggy_code": 10},
                 "satisfaction": {"satisfied": 70, "likely_satisfied": 28, "dissatisfied": 2}},
    }
    g = analytics.at_a_glance(digest)
    assert g["top_project"] == "ROROROblox"
    assert g["top_project_pct"] == 40.0
    assert g["dominant_friction"] == "env_tooling"   # top friction excluding 'none'
    assert g["positive_satisfaction_pct"] == 98.0     # (70+28)/100
    assert g["acceleration"] == 6.4


def test_response_distribution():
    sessions = [{"response_buckets": {"<1m": 3, "1-5m": 1}}, {"response_buckets": {"<1m": 2, ">30m": 1}}]
    rd = analytics.response_distribution(sessions)
    assert rd["<1m"] == 5 and rd["1-5m"] == 1 and rd[">30m"] == 1


# --- Item 1: tool_mix --------------------------------------------------------

def test_tool_mix_sums_and_ranks():
    sessions = [
        _s(tool_counts={"Bash": 5, "Read": 2}, web_search=1, web_fetch=0),
        _s(tool_counts={"Bash": 3, "Read": 4, "Edit": 1}, web_search=2, web_fetch=3),
    ]
    tm = analytics.tool_mix(sessions)
    tools = tm["tools"]
    # ranked desc by count: Bash=8, Read=6, Edit=1
    assert tools[0] == {"tool": "Bash", "count": 8}
    assert tools[1] == {"tool": "Read", "count": 6}
    assert tools[2] == {"tool": "Edit", "count": 1}
    assert tm["web_search"] == 3
    assert tm["web_fetch"] == 3


def test_tool_mix_top_12_cap():
    # 15 distinct tools -> only top 12 returned
    counts = {f"Tool{i:02d}": (20 - i) for i in range(15)}
    tm = analytics.tool_mix([_s(tool_counts=counts)])
    assert len(tm["tools"]) == 12
    # highest count first
    assert tm["tools"][0] == {"tool": "Tool00", "count": 20}
    # the 12th is Tool11 (count 9); Tool12..14 dropped
    assert tm["tools"][-1] == {"tool": "Tool11", "count": 9}


def test_tool_mix_empty_input():
    tm = analytics.tool_mix([])
    assert tm == {"tools": [], "web_search": 0, "web_fetch": 0}


def test_tool_mix_handles_missing_fields():
    tm = analytics.tool_mix([_s()])
    assert tm["tools"] == []
    assert tm["web_search"] == 0 and tm["web_fetch"] == 0


# --- Item 2: delegation ------------------------------------------------------

def test_delegation_agent_call_sum():
    sessions = [
        _s(tool_counts={"Agent": 5, "Bash": 2}),
        _s(tool_counts={"Agent": 3}),
        _s(tool_counts={"Bash": 9}),  # no Agent
    ]
    d = analytics.delegation(sessions)
    assert d["agent_calls"] == 8


def test_delegation_haiku_case_insensitive():
    sessions = [
        _s(models=["claude-HAIKU-4-5"]),
        _s(models=["claude-opus-4-7"]),
        _s(models=["Claude-Haiku"]),
    ]
    d = analytics.delegation(sessions)
    assert d["haiku_sessions"] == 2


def test_delegation_multi_model_counts_session_once():
    # a session listing both opus and haiku counts as ONE haiku session
    sessions = [
        _s(models=["claude-opus-4-7", "claude-haiku-4-5"]),
        _s(models=["claude-haiku-4-5", "claude-haiku-4-5"]),
    ]
    d = analytics.delegation(sessions)
    assert d["haiku_sessions"] == 2


def test_delegation_no_model_sessions():
    sessions = [_s(models=[]), _s()]  # _s default models=[]
    d = analytics.delegation(sessions)
    assert d == {"agent_calls": 0, "haiku_sessions": 0}


# --- Item 3: by_machine ------------------------------------------------------

def test_by_machine_groups_and_rolls_up():
    sessions = [
        _s(machine="neb", assistant_msgs=100, human_tokens=500, repo="A"),
        _s(machine="neb", assistant_msgs=200, human_tokens=300, repo="B"),
        _s(machine="neb", assistant_msgs=50, human_tokens=100, repo="A"),  # dup repo
        _s(machine="dun", assistant_msgs=70, human_tokens=900, repo="C"),
    ]
    bm = analytics.by_machine(sessions)
    # sorted by assistant_msgs desc -> neb (350) before dun (70)
    assert [m["machine"] for m in bm] == ["neb", "dun"]
    neb = bm[0]
    assert neb["sessions"] == 3
    assert neb["assistant_msgs"] == 350
    assert neb["burn"] == 900            # 500 + 300 + 100
    assert neb["repos"] == 2             # A, B distinct
    dun = bm[1]
    assert dun["sessions"] == 1
    assert dun["assistant_msgs"] == 70
    assert dun["burn"] == 900
    assert dun["repos"] == 1


def test_by_machine_single_machine():
    bm = analytics.by_machine([_s(machine="solo", assistant_msgs=5, human_tokens=10, repo="R")])
    assert len(bm) == 1
    assert bm[0] == {"machine": "solo", "sessions": 1, "assistant_msgs": 5,
                     "burn": 10, "repos": 1}


def test_by_machine_distinct_repos_ignores_empty():
    sessions = [
        _s(machine="m", repo="A", assistant_msgs=1, human_tokens=0),
        _s(machine="m", repo="", assistant_msgs=1, human_tokens=0),
        _s(machine="m", repo="A", assistant_msgs=1, human_tokens=0),
    ]
    bm = analytics.by_machine(sessions)
    assert bm[0]["repos"] == 1   # only "A"; empty repo not counted


def test_by_machine_empty_input():
    assert analytics.by_machine([]) == []


# --- Item 4: pick_back_up rework + prune_candidates --------------------------

def test_pick_back_up_back_compat_fields_present():
    sessions = [_s(repo="A", branch="feat/x", machine="m", title="wip thing",
                   last_ts=_ts_days_ago(2))]
    pb = analytics.pick_back_up(sessions)
    assert len(pb) == 1
    rec = pb[0]
    # existing fields preserved
    for k in ("repo", "branch", "machine", "title", "last_ts"):
        assert k in rec
    # new fields added
    for k in ("age_days", "empty_title", "resume_signal", "unfinished_score"):
        assert k in rec
    assert rec["repo"] == "A" and rec["branch"] == "feat/x"


def test_pick_back_up_score_resume_signal():
    # title with resume keyword, recent (<7d) -> resume(3) + recency(3) = 6
    s = _s(repo="A", branch="feat/x", title="continue the refactor",
           last_ts=_ts_days_ago(1))
    rec = analytics.pick_back_up([s])[0]
    assert rec["resume_signal"] is True
    assert rec["empty_title"] is False
    assert rec["age_days"] == 1
    assert rec["unfinished_score"] == 6   # 3 resume + 3 recency


def test_pick_back_up_score_empty_title():
    # empty title, recent (<7d) -> empty(2) + recency(3) = 5, no resume
    s = _s(repo="A", branch="feat/x", title="   ", last_ts=_ts_days_ago(3))
    rec = analytics.pick_back_up([s])[0]
    assert rec["empty_title"] is True
    assert rec["resume_signal"] is False
    assert rec["unfinished_score"] == 5   # 2 empty + 3 recency


def test_pick_back_up_recency_buckets():
    # recency = max(0, 3 - age_days // 7): 3 (<7d), 2 (<14d), 1 (<21d)
    # use a plain non-resume, non-empty title so score == recency
    def score(days):
        s = _s(repo="A", branch="feat/x", title="ship it", last_ts=_ts_days_ago(days))
        return analytics.pick_back_up([s])[0]["unfinished_score"]
    assert score(3) == 3
    assert score(10) == 2
    assert score(17) == 1


def test_pick_back_up_sort_by_score_then_recency():
    sessions = [
        # high score: resume + recent
        _s(repo="A", branch="feat/hi", title="finish the wip", last_ts=_ts_days_ago(1)),
        # mid score: plain recent (recency 3)
        _s(repo="B", branch="feat/mid", title="ship it", last_ts=_ts_days_ago(2)),
        # lower score: plain, 10d old (recency 2)
        _s(repo="C", branch="feat/lo", title="ship it", last_ts=_ts_days_ago(10)),
    ]
    pb = analytics.pick_back_up(sessions)
    assert [r["branch"] for r in pb] == ["feat/hi", "feat/mid", "feat/lo"]


def test_pick_back_up_dedupe_newest_wins():
    sessions = [
        _s(repo="A", branch="feat/x", title="newer", last_ts=_ts_days_ago(1)),
        _s(repo="A", branch="feat/x", title="older", last_ts=_ts_days_ago(9)),
    ]
    pb = analytics.pick_back_up(sessions)
    assert len(pb) == 1
    assert pb[0]["title"] == "newer"
    assert pb[0]["age_days"] == 1


def test_pick_back_up_excludes_prune_candidates():
    # old (>=21d), no resume keyword, non-empty title -> score 0 -> prune, not pick
    sessions = [
        _s(repo="A", branch="feat/old", title="shipped already", last_ts=_ts_days_ago(40)),
        _s(repo="B", branch="feat/live", title="wip", last_ts=_ts_days_ago(2)),
    ]
    pb = analytics.pick_back_up(sessions)
    assert [r["branch"] for r in pb] == ["feat/live"]


def test_prune_candidates_inclusion_rule():
    sessions = [
        # prune: old, no resume, non-empty title
        _s(repo="A", branch="feat/old", title="done deal", last_ts=_ts_days_ago(40)),
        # NOT prune: old but has resume keyword
        _s(repo="B", branch="feat/wip", title="wip cleanup", last_ts=_ts_days_ago(40)),
        # NOT prune: old but empty title
        _s(repo="C", branch="feat/empty", title="", last_ts=_ts_days_ago(40)),
        # NOT prune: recent
        _s(repo="D", branch="feat/new", title="ship it", last_ts=_ts_days_ago(2)),
    ]
    pc = analytics.prune_candidates(sessions)
    assert [r["branch"] for r in pc] == ["feat/old"]
    # prune records carry the signal fields too
    assert pc[0]["unfinished_score"] == 0
    assert pc[0]["resume_signal"] is False
    assert pc[0]["empty_title"] is False


def test_prune_and_pick_mutual_exclusion_invariant():
    # The invariant: a branch is a prune candidate IFF unfinished_score == 0,
    # and the two lists never overlap.
    sessions = [
        _s(repo="A", branch="feat/old", title="done deal", last_ts=_ts_days_ago(40)),
        _s(repo="B", branch="feat/wip", title="wip cleanup", last_ts=_ts_days_ago(40)),
        _s(repo="C", branch="feat/empty", title="", last_ts=_ts_days_ago(40)),
        _s(repo="D", branch="feat/new", title="ship it", last_ts=_ts_days_ago(2)),
        _s(repo="E", branch="main", title="ignored", last_ts=_ts_days_ago(1)),
    ]
    pb = analytics.pick_back_up(sessions)
    pc = analytics.prune_candidates(sessions)
    pb_keys = {(r["repo"], r["branch"], r["machine"]) for r in pb}
    pc_keys = {(r["repo"], r["branch"], r["machine"]) for r in pc}
    # no overlap
    assert pb_keys & pc_keys == set()
    # every prune candidate has score 0
    assert all(r["unfinished_score"] == 0 for r in pc)
    # every pick has score >= 1
    assert all(r["unfinished_score"] >= 1 for r in pb)
    # union covers all feature branches (main excluded)
    assert pb_keys | pc_keys == {
        ("A", "feat/old", "m"), ("B", "feat/wip", "m"),
        ("C", "feat/empty", "m"), ("D", "feat/new", "m"),
    }


def test_pick_back_up_unparseable_last_ts_is_old():
    # unparseable last_ts -> treated as very old -> recency 0; non-resume, non-empty
    # -> score 0 -> prune candidate, excluded from pick_back_up
    sessions = [_s(repo="A", branch="feat/x", title="ship it", last_ts="not-a-date")]
    pb = analytics.pick_back_up(sessions)
    pc = analytics.prune_candidates(sessions)
    assert pb == []
    assert len(pc) == 1
    assert pc[0]["age_days"] >= 10**6
    assert pc[0]["unfinished_score"] == 0


def test_pick_back_up_missing_last_ts_is_old_but_resume_kept():
    # missing last_ts (very old) but resume keyword -> score 3 -> stays in pick
    sessions = [_s(repo="A", branch="feat/x", title="finish this", last_ts="")]
    pb = analytics.pick_back_up(sessions)
    assert len(pb) == 1
    assert pb[0]["resume_signal"] is True
    assert pb[0]["unfinished_score"] == 3   # resume only, recency 0
