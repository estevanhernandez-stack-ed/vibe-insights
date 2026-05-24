from vibe_insights import story


def test_infer_repo_path():
    sessions = [{"cwd": "C:/x/Foo"}, {"cwd": "C:/x/Foo"}, {"cwd": "C:/y/Bar"}]
    assert story.infer_repo_path(sessions) == "C:/x/Foo"


def test_build_story_input_shape():
    sessions = [
        {"title": "Start it", "last_ts": "2026-05-23T10:00:00+00:00", "machine": "m", "cwd": "C:/x/Foo"},
        {"title": "Ship it", "last_ts": "2026-05-23T12:00:00+00:00", "machine": "m", "cwd": "C:/x/Foo"},
    ]
    decisions = [{"timestamp": "2026-05-23T11:00:00", "title": "Chose X over Y"}]
    out = story.build_story_input("Foo", sessions, decisions, repo_path="C:/nonexistent-xyz")
    assert "# Build story spine: Foo" in out
    assert "## Session timeline" in out
    assert "Start it" in out and "Ship it" in out
    assert "## Decisions" in out and "Chose X over Y" in out
    assert "## Commits" in out  # section present even if git log empty (bad path)
    # timeline is chronological
    assert out.index("Start it") < out.index("Ship it")
