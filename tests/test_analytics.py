from vibe_insights import analytics


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
