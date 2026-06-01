# Vibe Insights Generalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make vibe-insights work great for any user with zero config (everything personal by default) while keeping work-walling and multi-surface as opt-in power — and reframe the vocabulary from `home/work-walled/account` to `source/private/private_repos`.

**Architecture:** Add a `normalize_config()` adapter in `config.py` that reads either the new schema (core + `advanced.sources`/`private_repos`) or the legacy schema (`homes`/`work_repos`) and emits one canonical internal dict (`sources` = `[{path, private}]`, `private_repos`). The scan/CLI consume the canonical form. The hardcoded `.claude`-is-work heuristic is deleted; discovery defaults every source to personal. The local-only index file is renamed `index.private.local.json` with dual-read back-compat. A non-blocking privacy nudge and a `--privacy` helper make opt-in walling discoverable and one-step.

**Tech Stack:** Python 3, pytest (tmp_path / monkeypatch), `cc_logs` (optional dep, vendored fallback in `cclogs.py`). Tests live in `tests/`, source in `src/vibe_insights/`. Run tests with `python -m pytest`.

**Internal vocabulary note:** The user-facing reframe is `home→source`, `work-walled→private`. Internally we keep the `SessionRecord.walled` boolean as the wall flag and rename the `account` field's *values* from `"work"` → `"private"` (kept `"personal"` as-is). The canonical config keys are `sources` and `private_repos`.

---

## File structure

- `src/vibe_insights/config.py` — schema, discovery, normalization, back-compat. Most change here.
- `src/vibe_insights/scan.py` — `build_records` signature change, `is_private_repo` rename, account-value rename, index file rename + `read_local_private_index` helper.
- `src/vibe_insights/records.py` — `account` field doc/value comment.
- `src/vibe_insights/cli.py` — consume canonical config, dual-read helper at all sites, `--init` writes new schema, privacy nudge, `--privacy`/`--make-private*` flags.
- `src/vibe_insights/report.py` — replace `"work"` display vocabulary with `"private"`; drop hardcoded "work walled" meta.
- `tests/test_config.py`, `tests/test_scan.py`, `tests/test_cli.py` — updated + new tests.
- `README.md`, `skills/vibe-insights/SKILL.md`, `docs/privacy-and-sources.md` — docs reframe.

---

## Phase 1 — Config layer

### Task 1: Default discovery to personal (delete the work heuristic)

**Files:**
- Modify: `src/vibe_insights/config.py:16-30` (`discover_homes` → `discover_sources`)
- Test: `tests/test_config.py`

- [ ] **Step 1: Replace the failing test** — open `tests/test_config.py`, replace `test_discover_homes_labels_work_and_personal` with:

```python
def test_discover_sources_defaults_all_personal(tmp_path):
    _make_home(tmp_path, ".claude")
    _make_home(tmp_path, ".claude-personal")
    _make_home(tmp_path, ".claude-server-commander", with_projects=False)
    sources = config.discover_sources(home=tmp_path)
    by_path = {Path(s["path"]).name: s for s in sources}
    # No more ".claude == work" — every discovered source is personal by default.
    assert by_path[".claude"]["private"] is False
    assert by_path[".claude-personal"]["private"] is False
    # no projects/ dir => not a source
    assert ".claude-server-commander" not in by_path
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_config.py::test_discover_sources_defaults_all_personal -v`
Expected: FAIL — `AttributeError: module 'vibe_insights.config' has no attribute 'discover_sources'`

- [ ] **Step 3: Implement** — in `config.py`, replace `discover_homes` with:

```python
def discover_sources(home: Path = None) -> list[dict]:
    """Every `.claude*` dir with a `projects/` subdir is a source, all
    personal (synced-eligible) by default. Walling is opt-in via the
    `private` flag or `private_repos` — never inferred from the dir name."""
    home = Path(home) if home else Path.home()
    sources = []
    for child in sorted(home.iterdir()):
        if not child.is_dir() or not child.name.startswith(".claude"):
            continue
        if not (child / "projects").is_dir():
            continue
        sources.append({"path": str(child), "private": False})
    return sources
```

Also update the module docstring (lines 1-6) to drop the "`.claude` is the work seat" wording:

```python
"""Topology: which Claude Code sources exist on this machine.

A source is any `~/.claude*` dir containing `projects/`. Discovery marks
every source personal (synced-eligible); walling is opt-in. The emitted
config is meant to be human-reviewed before use.
"""
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_config.py::test_discover_sources_defaults_all_personal -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/vibe_insights/config.py tests/test_config.py
git commit -m "feat(config): discover_sources defaults all sources personal (delete .claude=work heuristic)"
```

### Task 2: `build_config` emits the new schema (core + advanced block)

**Files:**
- Modify: `src/vibe_insights/config.py:33-43` (`build_config`)
- Test: `tests/test_config.py`

- [ ] **Step 1: Replace the failing tests** — replace `test_build_config_shape`, `test_build_config_includes_work_repos_key` with:

```python
def test_build_config_new_schema(tmp_path):
    _make_home(tmp_path, ".claude-personal")
    cfg = config.build_config(home=tmp_path, machine="testbox",
                              data_dir=tmp_path / ".vibe-insights")
    assert cfg["machine"] == "testbox"
    assert cfg["dataDir"].endswith(".vibe-insights")
    assert cfg["advanced"]["sources"] == [
        {"path": str(tmp_path / ".claude-personal"), "private": False}
    ]
    assert cfg["advanced"]["private_repos"] == []
    # legacy keys are gone from freshly-built config
    assert "homes" not in cfg and "work_repos" not in cfg
```

(Leave `test_build_config_includes_decisions_default` and `test_build_config_includes_voice_default` as-is — those keys are unchanged.)

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_config.py::test_build_config_new_schema -v`
Expected: FAIL — `KeyError: 'advanced'`

- [ ] **Step 3: Implement** — replace `build_config`:

```python
def build_config(home: Path = None, machine: str = None,
                 data_dir: Path = None) -> dict:
    data_dir = Path(data_dir) if data_dir else (Path.home() / ".vibe-insights")
    return {
        "machine": machine or default_machine(),
        "dataDir": str(data_dir),
        "decisions": {"source": "none"},
        "voice": None,
        "advanced": {
            "sources": discover_sources(home),
            "private_repos": [],
        },
    }
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_config.py::test_build_config_new_schema tests/test_config.py::test_build_config_includes_decisions_default tests/test_config.py::test_build_config_includes_voice_default -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/vibe_insights/config.py tests/test_config.py
git commit -m "feat(config): build_config emits core + advanced block schema"
```

### Task 3: `normalize_config` — one canonical internal form from new OR legacy

**Files:**
- Modify: `src/vibe_insights/config.py` (add `normalize_config`)
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing tests** — append to `tests/test_config.py`:

```python
def test_normalize_new_schema_passthrough():
    cfg = {"machine": "m", "dataDir": "/d",
           "decisions": {"source": "none"}, "voice": None,
           "advanced": {"sources": [{"path": "/h/.claude-work", "private": True}],
                        "private_repos": ["employer/api"]}}
    norm = config.normalize_config(cfg)
    assert norm["sources"] == [{"path": "/h/.claude-work", "private": True}]
    assert norm["private_repos"] == ["employer/api"]
    assert norm["machine"] == "m" and norm["dataDir"] == "/d"


def test_normalize_legacy_schema_maps_walled_to_private():
    legacy = {"machine": "m", "dataDir": "/d",
              "homes": [{"path": "/h/.claude", "account": "work", "walled": True},
                        {"path": "/h/.claude-personal", "account": "personal", "walled": False}],
              "work_repos": ["employer/api"],
              "decisions": {"source": "none"}, "voice": None}
    norm = config.normalize_config(legacy)
    assert norm["sources"] == [{"path": "/h/.claude", "private": True},
                               {"path": "/h/.claude-personal", "private": False}]
    assert norm["private_repos"] == ["employer/api"]


def test_normalize_no_advanced_discovers_personal(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    _make_home(tmp_path, ".claude")
    cfg = {"machine": "m", "dataDir": "/d", "decisions": {"source": "none"}, "voice": None}
    norm = config.normalize_config(cfg)
    assert norm["sources"] == [{"path": str(tmp_path / ".claude"), "private": False}]
    assert norm["private_repos"] == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_config.py -k normalize -v`
Expected: FAIL — `AttributeError: ... has no attribute 'normalize_config'`

- [ ] **Step 3: Implement** — add to `config.py`:

```python
def normalize_config(cfg: dict) -> dict:
    """Return a canonical internal config from either the new schema
    (core + `advanced.sources`/`private_repos`) or the legacy schema
    (`homes` with `account`/`walled`, top-level `work_repos`). Downstream
    code consumes only `sources` (list of {path, private}) + `private_repos`."""
    adv = cfg.get("advanced") or {}
    if adv.get("sources") is not None:
        sources = [{"path": s["path"], "private": bool(s.get("private", False))}
                   for s in adv["sources"]]
    elif cfg.get("homes") is not None:  # legacy: walled -> private
        sources = [{"path": h["path"], "private": bool(h.get("walled", False))}
                   for h in cfg["homes"]]
    else:  # no sources declared -> discover, all personal
        sources = discover_sources()
    private_repos = adv.get("private_repos")
    if private_repos is None:
        private_repos = cfg.get("work_repos", [])  # legacy
    return {
        "machine": cfg.get("machine") or default_machine(),
        "dataDir": cfg.get("dataDir") or str(Path.home() / ".vibe-insights"),
        "sources": sources,
        "private_repos": list(private_repos),
        "decisions": cfg.get("decisions") or {"source": "none"},
        "voice": cfg.get("voice"),
    }
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_config.py -k normalize -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/vibe_insights/config.py tests/test_config.py
git commit -m "feat(config): normalize_config adapts new + legacy schema to canonical form"
```

### Task 4: `load_config` returns the normalized form

**Files:**
- Modify: `src/vibe_insights/config.py:46-48` (`load_config`)
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test** — append:

```python
def test_load_config_returns_normalized(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({
        "machine": "m", "dataDir": "/d",
        "homes": [{"path": "/h/.claude", "account": "work", "walled": True}],
        "work_repos": ["e/r"], "decisions": {"source": "none"}, "voice": None,
    }), encoding="utf-8")
    cfg = config.load_config(p)
    assert cfg["sources"] == [{"path": "/h/.claude", "private": True}]
    assert cfg["private_repos"] == ["e/r"]
```

(Add `import json` at the top of `tests/test_config.py` if not present.)

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_config.py::test_load_config_returns_normalized -v`
Expected: FAIL — `KeyError: 'sources'`

- [ ] **Step 3: Implement** — change `load_config`:

```python
def load_config(config_path: Path) -> dict:
    with open(config_path, encoding="utf-8") as f:
        return normalize_config(json.load(f))
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS (all config tests)

- [ ] **Step 5: Commit**

```bash
git add src/vibe_insights/config.py tests/test_config.py
git commit -m "feat(config): load_config returns normalized canonical form"
```

---

## Phase 2 — Scan + records

### Task 5: `build_records` takes sources + private_repos; account value `work`→`private`

**Files:**
- Modify: `src/vibe_insights/scan.py:161-187` (`is_work_repo`, `build_records`)
- Modify: `src/vibe_insights/records.py:11` (account comment)
- Test: `tests/test_scan.py`

- [ ] **Step 1: Replace the failing tests** — in `tests/test_scan.py`, replace `test_scan_walls_work_from_personal`, `test_work_repos_reclassifies_by_repo`, `test_empty_work_repos_keeps_home_classification` with:

```python
def test_private_source_walls_from_personal(tmp_path):
    _write_session(tmp_path, ".claude-work", "projA", "w1",
                   [_assistant("w1", "2026-05-20T10:00:00Z", 50, 5, "C:/work/A")])
    _write_session(tmp_path, ".claude-personal", "projB", "p1",
                   [_assistant("p1", "2026-05-21T10:00:00Z", 80, 8, "C:/me/B")])
    sources = [
        {"path": str(tmp_path / ".claude-work"), "private": True},
        {"path": str(tmp_path / ".claude-personal"), "private": False},
    ]
    records = scan.build_records(sources, machine="m")
    out = tmp_path / "data"
    counts = scan.write_indexes(records, out, "m")
    personal = json.loads((out / "synced" / "m" / "index.json").read_text())["sessions"]
    private = json.loads((out / "index.private.local.json").read_text())["sessions"]
    assert counts == {"personal": 1, "private": 1}
    assert [s["session_id"] for s in personal] == ["p1"]
    assert all(s["account"] == "personal" for s in personal)
    assert [s["session_id"] for s in private] == ["w1"]
    assert not (out / "synced" / "m" / "index.private.local.json").exists()


def test_private_repos_reclassify_by_repo(tmp_path):
    _write_session(tmp_path, ".claude", "proj", "s_personal",
                   [_assistant("s_personal", "2026-05-20T12:00:00Z", 10, 1, "C:/x/my-hub")])
    _write_session(tmp_path, ".claude", "proj2", "s_priv",
                   [_assistant("s_priv", "2026-05-20T12:00:00Z", 10, 1, "C:/x/employer-api")])
    sources = [{"path": str(tmp_path / ".claude"), "private": False}]
    recs = scan.build_records(sources, machine="m", private_repos=["employer-api"])
    by_id = {r.session_id: r for r in recs.values()}
    assert by_id["s_personal"].walled is False and by_id["s_personal"].account == "personal"
    assert by_id["s_priv"].walled is True and by_id["s_priv"].account == "private"


def test_default_source_is_personal(tmp_path):
    _write_session(tmp_path, ".claude", "proj", "s1",
                   [_assistant("s1", "2026-05-20T12:00:00Z", 10, 1, "C:/x/anything")])
    sources = [{"path": str(tmp_path / ".claude"), "private": False}]
    recs = scan.build_records(sources, machine="m")
    # THE FIX: a lone ~/.claude is personal now, not walled work.
    assert list(recs.values())[0].walled is False
    assert list(recs.values())[0].account == "personal"
```

Also update `test_personal_burn_reconciles_with_cc_logs` and `test_subagent_tokens_fold_into_parent`: change their `homes = [{"path": ..., "account": "personal", "walled": False}]` literals to `sources = [{"path": ..., "private": False}]` and pass `sources` to `build_records`.

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_scan.py -v`
Expected: FAIL — `build_records` still expects `homes` dicts with `account`/`walled`; `index.private.local.json` not written.

- [ ] **Step 3: Implement** — in `scan.py` replace `is_work_repo` + `build_records`:

```python
def is_private_repo(repo: str, private_repos) -> bool:
    if not repo or not private_repos:
        return False
    r = repo.strip().lower()
    return any(r == str(w).strip().lower() for w in private_repos)


def build_records(sources: list[dict], machine: str, private_repos=()) -> dict:
    """Walk every source's logs (recursively, incl. subagent transcripts) and
    fold into records by session id. Subagent events carry the parent
    sessionId, so their burn folds into the parent automatically.

    Each source's `private` flag sets the initial wall. When private_repos is
    provided, records are then reclassified by repo name: a session whose repo
    matches a private_repos entry is private (local-only); all others personal."""
    records: dict = {}
    for src in sources:
        private = bool(src.get("private", False))
        account = "private" if private else "personal"
        for f in discover_under(Path(src["path"])):
            for ev in iter_raw_events(f):
                ingest_event(records, ev, account=account, machine=machine,
                             walled=private, default_sid=f.stem)
    if private_repos:
        for rec in records.values():
            rec.walled = is_private_repo(rec.repo, private_repos)
            rec.account = "private" if rec.walled else "personal"
    return records
```

In `records.py:11`, update the field comment:

```python
    account: str            # "personal" | "private"
```

- [ ] **Step 4: Run to verify it passes** (write_indexes file rename is Task 6 — this step will still fail on the `index.private.local.json` assertion until then; run only the non-index tests now)

Run: `python -m pytest tests/test_scan.py::test_private_repos_reclassify_by_repo tests/test_scan.py::test_default_source_is_personal -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/vibe_insights/scan.py src/vibe_insights/records.py tests/test_scan.py
git commit -m "feat(scan): build_records takes sources+private_repos; account value work->private"
```

### Task 6: Rename local index to `index.private.local.json` (write + dual-read)

**Files:**
- Modify: `src/vibe_insights/scan.py:204-216` (`write_indexes`) + add `read_local_private_index`
- Test: `tests/test_scan.py`

- [ ] **Step 1: Write the failing tests** — append to `tests/test_scan.py`:

```python
def test_write_indexes_uses_private_filename(tmp_path):
    sources = [{"path": str(tmp_path / ".claude-work"), "private": True}]
    _write_session(tmp_path, ".claude-work", "p", "w1",
                   [_assistant("w1", "2026-05-20T10:00:00Z", 1, 1, "C:/w/A")])
    recs = scan.build_records(sources, machine="m")
    counts = scan.write_indexes(recs, tmp_path / "data", "m")
    assert counts == {"personal": 0, "private": 1}
    assert (tmp_path / "data" / "index.private.local.json").exists()
    assert not (tmp_path / "data" / "index.work.local.json").exists()


def test_read_local_private_index_prefers_new_falls_back_to_legacy(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    # legacy only
    (d / "index.work.local.json").write_text(
        json.dumps({"sessions": [{"session_id": "legacy"}]}), encoding="utf-8")
    assert [s["session_id"] for s in scan.read_local_private_index(d)] == ["legacy"]
    # new present -> wins
    (d / "index.private.local.json").write_text(
        json.dumps({"sessions": [{"session_id": "fresh"}]}), encoding="utf-8")
    assert [s["session_id"] for s in scan.read_local_private_index(d)] == ["fresh"]


def test_read_local_private_index_missing_returns_empty(tmp_path):
    assert scan.read_local_private_index(tmp_path) == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_scan.py -k "private_filename or read_local_private" -v`
Expected: FAIL — counts key is `work` not `private`; `read_local_private_index` undefined.

- [ ] **Step 3: Implement** — replace `write_indexes` and add the reader:

```python
# Local-only index filename. Renamed from index.work.local.json in v0.3 to
# match the "private" vocabulary. read_local_private_index() dual-reads both
# so existing data keeps working. Downstream consumers reading the old name
# get fixed when/if they surface — not preemptively hunted.
PRIVATE_INDEX = "index.private.local.json"
LEGACY_PRIVATE_INDEX = "index.work.local.json"


def write_indexes(records: dict, data_dir: Path, machine: str) -> dict:
    """Personal -> <data_dir>/synced/<machine>/index.json (the only thing that
    syncs across machines). Private -> <data_dir>/index.private.local.json
    (OUTSIDE synced/, so local-only data never enters the synced folder)."""
    data_dir = Path(data_dir)
    personal = [r.to_dict() for r in records.values() if not r.walled]
    private = [r.to_dict() for r in records.values() if r.walled]
    _atomic_write_json(data_dir / "synced" / machine / "index.json",
                       {"sessions": personal})
    if private:
        _atomic_write_json(data_dir / PRIVATE_INDEX, {"sessions": private})
    return {"personal": len(personal), "private": len(private)}


def read_local_private_index(data_dir: Path) -> list[dict]:
    """Read this machine's local-only session shard. Prefers the new
    index.private.local.json; falls back to the legacy index.work.local.json.
    Never raises — missing/unreadable returns []."""
    data_dir = Path(data_dir)
    for name in (PRIVATE_INDEX, LEGACY_PRIVATE_INDEX):
        p = data_dir / name
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8")).get("sessions", [])
            except (OSError, json.JSONDecodeError):
                return []
    return []
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_scan.py -v`
Expected: PASS (all scan tests, including `test_private_source_walls_from_personal`)

- [ ] **Step 5: Commit**

```bash
git add src/vibe_insights/scan.py tests/test_scan.py
git commit -m "feat(scan): rename local index to index.private.local.json with dual-read back-compat"
```

---

## Phase 3 — CLI

### Task 7: `run()` + all read sites consume canonical config and the dual-read helper

**Files:**
- Modify: `src/vibe_insights/cli.py` (`run` line 24-53; the `--story-input`, `--emit-tagging-input`, `--render-only` blocks)
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test** — append to `tests/test_cli.py` (mirror existing helpers there; if a `_write_session` helper isn't present, import from a shared place or inline it as in `tests/test_scan.py`):

```python
def test_run_personal_by_default_single_source(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    # one ~/.claude, no advanced block -> everything personal, report generates
    d = tmp_path / ".claude" / "projects" / "C--repo"
    d.mkdir(parents=True)
    (d / "s1.jsonl").write_text(json.dumps(
        {"type": "assistant", "sessionId": "s1", "timestamp": "2026-05-20T10:00:00Z",
         "cwd": "C:/repo", "message": {"model": "claude-opus-4-7",
         "usage": {"input_tokens": 10, "output_tokens": 1}}}) + "\n", encoding="utf-8")
    cfg = config_mod.normalize_config({"machine": "m", "dataDir": str(tmp_path / "data"),
                                       "decisions": {"source": "none"}, "voice": None})
    result = cli.run(cfg)
    assert result["counts"] == {"personal": 1, "private": 0}
```

(Use whatever import aliases `tests/test_cli.py` already uses — e.g. `from vibe_insights import cli, config as config_mod`.)

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_cli.py::test_run_personal_by_default_single_source -v`
Expected: FAIL — `run` reads `cfg["homes"]` / `cfg["work_repos"]` (KeyError) and `index.work.local.json`.

- [ ] **Step 3: Implement** — in `cli.py`:

(a) Replace the body of `run()` lines 25-38 so it uses canonical keys + the helper:

```python
    machine = cfg["machine"]
    records = scan_mod.build_records(cfg["sources"], machine=machine,
                                     private_repos=cfg.get("private_repos", []))
    counts = scan_mod.write_indexes(records, cfg["dataDir"], machine)
    merged = merge_mod.load_merged(Path(cfg["dataDir"]) / "synced")
    private_local = scan_mod.read_local_private_index(cfg["dataDir"])
    report_set = merged + private_local
```

(Delete the old inline `work_local = []` / `wpath = ... index.work.local.json` block at lines 30-37.)

(b) In the `--story-input` block (lines 83-90) replace the inline work-local read with:

```python
        report_set = merge_mod.load_merged(data_dir / "synced") + scan_mod.read_local_private_index(data_dir)
```

(c) In the `--emit-tagging-input` block (lines 109-116) replace likewise:

```python
        report_set = merge_mod.load_merged(data_dir / "synced") + scan_mod.read_local_private_index(data_dir)
```

and change `files = scan_mod.locate_session_files([h["path"] for h in cfg["homes"]])` (line 121) to:

```python
        files = scan_mod.locate_session_files([s["path"] for s in cfg["sources"]])
```

(d) In the `--render-only` block (lines 143-150) replace likewise:

```python
        report_set = merge_mod.load_merged(data_dir / "synced") + scan_mod.read_local_private_index(data_dir)
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_cli.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/vibe_insights/cli.py tests/test_cli.py
git commit -m "feat(cli): consume canonical config (sources/private_repos) + dual-read helper at all sites"
```

### Task 8: `--init` writes the new schema with private-aware review copy

**Files:**
- Modify: `src/vibe_insights/cli.py:162-168` (the `args.init` block) and lines 170-173 (no-config message)
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test** — append:

```python
def test_init_writes_advanced_sources(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    (tmp_path / ".claude" / "projects").mkdir(parents=True)
    cfgpath = tmp_path / "config.json"
    rc = cli.main(["--init", "--config", str(cfgpath)])
    assert rc == 0
    raw = json.loads(cfgpath.read_text(encoding="utf-8"))
    assert raw["advanced"]["sources"] == [
        {"path": str(tmp_path / ".claude"), "private": False}]
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_cli.py::test_init_writes_advanced_sources -v`
Expected: FAIL — `build_config` output already changed in Task 2, but the printed review copy still says "homes + account labels"; assert may pass on shape but verify the message line. (If shape passes, proceed; the copy fix below is still required.)

- [ ] **Step 3: Implement** — replace the `args.init` block:

```python
    if args.init:
        cfg = config_mod.build_config()
        config_mod.write_config(config_path, cfg)
        print(f"Wrote {config_path}")
        print(json.dumps(cfg, indent=2))
        print("All sources are personal (synced-eligible) by default. To keep any "
              "local-only, set \"private\": true on a source or add repos to "
              "advanced.private_repos — then run `vibe-insights`.")
        return 0
```

And update the no-config hint (line 171):

```python
        print(f"No config at {config_path}. Run `vibe-insights --init` first, "
              f"or just run `vibe-insights` to use auto-discovered personal sources.",
              file=sys.stderr)
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_cli.py::test_init_writes_advanced_sources -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/vibe_insights/cli.py tests/test_cli.py
git commit -m "feat(cli): --init writes new schema with private-aware review copy"
```

### Task 9: Privacy nudge — apparent on every run, non-blocking

**Files:**
- Modify: `src/vibe_insights/cli.py` (add `privacy_nudge`, print it in the default-run block lines 176-187)
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test** — append:

```python
def test_privacy_nudge_shown_when_nothing_private(capsys, tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    d = tmp_path / ".claude" / "projects" / "C--repo"
    d.mkdir(parents=True)
    (d / "s1.jsonl").write_text(json.dumps(
        {"type": "assistant", "sessionId": "s1", "timestamp": "2026-05-20T10:00:00Z",
         "cwd": "C:/repo", "message": {"model": "x", "usage": {"input_tokens": 1, "output_tokens": 1}}}) + "\n",
        encoding="utf-8")
    cfgpath = tmp_path / "config.json"
    cli.main(["--init", "--config", str(cfgpath)])
    cli.main(["--config", str(cfgpath)])
    out = capsys.readouterr().out
    assert "local-only" in out and "private_repos" in out


def test_privacy_nudge_absent_when_something_private(capsys, tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    d = tmp_path / ".claude" / "projects" / "C--repo"
    d.mkdir(parents=True)
    (d / "s1.jsonl").write_text(json.dumps(
        {"type": "assistant", "sessionId": "s1", "timestamp": "2026-05-20T10:00:00Z",
         "cwd": "C:/repo", "message": {"model": "x", "usage": {"input_tokens": 1, "output_tokens": 1}}}) + "\n",
        encoding="utf-8")
    cfgpath = tmp_path / "config.json"
    cfgpath.write_text(json.dumps({"machine": "m", "dataDir": str(tmp_path / "data"),
        "decisions": {"source": "none"}, "voice": None,
        "advanced": {"sources": [{"path": str(tmp_path / ".claude"), "private": False}],
                     "private_repos": ["something"]}}), encoding="utf-8")
    cli.main(["--config", str(cfgpath)])
    out = capsys.readouterr().out
    assert "private_repos" not in out  # already using privacy -> no nudge
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_cli.py -k privacy_nudge -v`
Expected: FAIL — no nudge printed.

- [ ] **Step 3: Implement** — add to `cli.py` (above `main`):

```python
def privacy_nudge(cfg: dict) -> str | None:
    """A one-line, non-blocking hint shown when nothing is walled yet, so a
    user who never considered local-only sees it once. Returns None when the
    user already uses privacy (any private source or any private_repos)."""
    any_private = (bool(cfg.get("private_repos"))
                   or any(s.get("private") for s in cfg.get("sources", [])))
    if any_private:
        return None
    n = len(cfg.get("sources", []))
    return (f"Privacy: all {n} source(s) are personal (synced-eligible). "
            f"Keep any local-only? One line — add \"private_repos\": [\"owner/repo\"] "
            f"to advanced in {DEFAULT_CONFIG}, or run `vibe-insights --privacy`.")
```

Then in the default-run block, after the existing `print(f"Markdown: ...")` (line 186) and before `return 0`:

```python
    nudge = privacy_nudge(cfg)
    if nudge:
        print(nudge)
    return 0
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_cli.py -k privacy_nudge -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/vibe_insights/cli.py tests/test_cli.py
git commit -m "feat(cli): non-blocking privacy nudge when nothing is walled yet"
```

### Task 10: `--privacy` overview + `--make-private` / `--make-private-source` mutators

**Files:**
- Modify: `src/vibe_insights/cli.py` (argparse + a new handler block; add `set_private` to `config.py`)
- Test: `tests/test_cli.py`, `tests/test_config.py`

> **Design note:** Implemented as flags (`--privacy`, `--make-private REPO`, `--make-private-source PATH`) for consistency with the existing all-flag CLI, rather than an argparse subcommand. `vibe-insights --privacy` is the "list + how" view; the two mutators write the `advanced` block (sticky).

- [ ] **Step 1: Write the failing tests** —

`tests/test_config.py` (append):

```python
def test_set_private_repo_writes_advanced(tmp_path):
    p = tmp_path / "config.json"
    config.write_config(p, config.build_config(home=tmp_path, machine="m",
                                                data_dir=tmp_path / ".vi"))
    config.set_private(p, repo="owner/api")
    raw = json.loads(p.read_text(encoding="utf-8"))
    assert "owner/api" in raw["advanced"]["private_repos"]


def test_set_private_source_marks_private(tmp_path):
    _make_home(tmp_path, ".claude-work")
    p = tmp_path / "config.json"
    config.write_config(p, config.build_config(home=tmp_path, machine="m",
                                                data_dir=tmp_path / ".vi"))
    config.set_private(p, source=str(tmp_path / ".claude-work"))
    raw = json.loads(p.read_text(encoding="utf-8"))
    src = {s["path"]: s for s in raw["advanced"]["sources"]}
    assert src[str(tmp_path / ".claude-work")]["private"] is True
```

`tests/test_cli.py` (append):

```python
def test_privacy_flag_lists_sources(capsys, tmp_path):
    p = tmp_path / "config.json"
    config_mod.write_config(p, {"machine": "m", "dataDir": str(tmp_path),
        "decisions": {"source": "none"}, "voice": None,
        "advanced": {"sources": [{"path": "/h/.claude", "private": False}],
                     "private_repos": []}})
    rc = cli.main(["--privacy", "--config", str(p)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "/h/.claude" in out and "personal" in out
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_config.py -k set_private tests/test_cli.py::test_privacy_flag_lists_sources -v`
Expected: FAIL — `set_private` undefined; `--privacy` unknown arg.

- [ ] **Step 3: Implement** —

In `config.py` add (note: operates on the RAW file, preserving/creating the `advanced` block — not the normalized form):

```python
def set_private(config_path: Path, repo: str = None, source: str = None) -> dict:
    """Mark a repo (added to advanced.private_repos) or a source (its private
    flag set True) as local-only. Writes the new-schema `advanced` block,
    migrating a legacy file on the way. Returns the written config."""
    with open(config_path, encoding="utf-8") as f:
        raw = json.load(f)
    norm = normalize_config(raw)
    out = {
        "machine": norm["machine"], "dataDir": norm["dataDir"],
        "decisions": norm["decisions"], "voice": norm["voice"],
        "advanced": {"sources": norm["sources"], "private_repos": norm["private_repos"]},
    }
    if repo and repo not in out["advanced"]["private_repos"]:
        out["advanced"]["private_repos"].append(repo)
    if source:
        for s in out["advanced"]["sources"]:
            if s["path"] == source:
                s["private"] = True
    write_config(config_path, out)
    return out
```

In `cli.py` add three arguments (after the `--repo` arg, line 68):

```python
    parser.add_argument("--privacy", action="store_true",
                        help="show which sources/repos are personal vs private, and how to wall")
    parser.add_argument("--make-private", metavar="REPO", default=None,
                        help="mark a repo local-only (adds to advanced.private_repos)")
    parser.add_argument("--make-private-source", metavar="PATH", default=None,
                        help="mark a source local-only (sets its private flag)")
```

Add a handler block after the `args.init` block (before the no-config check, ~line 169):

```python
    if args.make_private or args.make_private_source:
        if not config_path.exists():
            print(f"No config at {config_path}. Run `vibe-insights --init` first.", file=sys.stderr)
            return 1
        out = config_mod.set_private(config_path, repo=args.make_private,
                                     source=args.make_private_source)
        target = args.make_private or args.make_private_source
        print(f"Marked private: {target}. Re-run `vibe-insights` to apply.")
        return 0

    if args.privacy:
        if not config_path.exists():
            print(f"No config at {config_path}. Run `vibe-insights --init` first.", file=sys.stderr)
            return 1
        cfg = config_mod.load_config(config_path)
        print("Sources:")
        for s in cfg["sources"]:
            print(f"  {'private (local-only)' if s['private'] else 'personal'}  {s['path']}")
        print(f"Private repos: {cfg['private_repos'] or '(none)'}")
        print("Wall a repo:   vibe-insights --make-private owner/repo")
        print("Wall a source: vibe-insights --make-private-source ~/.claude-work")
        return 0
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_config.py -k set_private tests/test_cli.py::test_privacy_flag_lists_sources -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/vibe_insights/cli.py src/vibe_insights/config.py tests/test_cli.py tests/test_config.py
git commit -m "feat(cli): --privacy overview + --make-private[-source] mutators"
```

---

## Phase 4 — Report display vocabulary

### Task 11: Replace `work` display vocabulary with `private` in the report

**Files:**
- Modify: `src/vibe_insights/report.py` (line 272-274 CSS `.tile.work`; line 298-299 `account == 'work'`; line 482 meta "work walled")
- Test: `tests/test_report.py`

- [ ] **Step 1: Write the failing test** — append to `tests/test_report.py`:

```python
def test_html_uses_private_vocabulary_not_work():
    sessions = [{"account": "private", "machine": "m", "repo": "r",
                 "human_tokens": 10, "last_ts": "2026-05-20T10:00:00"}]
    html = report.render_html(sessions, digest=None)
    assert "work walled" not in html
    # the private tile gets the accent class
    assert "tile private" in html
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_report.py::test_html_uses_private_vocabulary_not_work -v`
Expected: FAIL — html still emits `tile work` and "work walled".

- [ ] **Step 3: Implement** — in `report.py`:

(a) CSS (lines 272-274): rename the class selectors `.tile.work` → `.tile.private`:

```python
.tile.private{border-color:rgba(242,47,137,.40)}
.tile.private .tl{color:var(--mag)}
.tile.private .tn{color:var(--fg)}
```

(b) `cov_tiles` (line 298): change the conditional class:

```python
        f"<div class='tile{' private' if r['account'] == 'private' else ''}'>"
```

(c) meta line (line 482): drop the hardcoded "work walled":

```python
        f"<div class='meta'>{total} personal sessions &middot; {machines} machine(s)</div></header>"
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_report.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/vibe_insights/report.py tests/test_report.py
git commit -m "feat(report): private vocabulary in display; drop hardcoded 'work walled'"
```

### Task 12: Full suite green + CLI output wording

**Files:**
- Modify: `src/vibe_insights/cli.py:180-182` (the "X work (local-only)" print)
- Test: whole suite

- [ ] **Step 1: Update the run-summary wording** — in `cli.py` change lines 180-182:

```python
    print(f"Indexed {c['personal']} personal"
          + (f" + {c['private']} private (local-only)" if c.get("private") else "")
          + f" sessions on {cfg['machine']}.")
```

- [ ] **Step 2: Run the whole suite**

Run: `python -m pytest -q`
Expected: PASS — all tests green (config, scan, cli, report, plus the untouched analytics/merge/records/tagging/story/decisions/ingest/sample suites).

- [ ] **Step 3: Commit**

```bash
git add src/vibe_insights/cli.py
git commit -m "feat(cli): run summary uses 'private (local-only)' wording"
```

---

## Phase 5 — Docs reframe

### Task 13: README reframe

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Rewrite the headline + intro** so the universal value leads. Replace the current "cross-machine, work-walled" headline with the spec's value prop:

> The deep retrospective for your Claude Code work — coverage, where-was-I recall, token/cost with the cache reveal, how you actually work, ranked open threads, and a synthesized narrative read. Across your full history and every machine you code on. No telemetry, all local.

- [ ] **Step 2: Replace the "wall is by repo" section** with a **"Privacy & multiple sources (advanced)"** section that documents: personal-by-default; `advanced.sources` with `private: true`; `advanced.private_repos`; `--privacy` / `--make-private`; and the author's multi-source setup as the worked example. Use `source`/`private` vocabulary throughout; remove `home`/`work-walled`/`account`.

- [ ] **Step 3: Verify no stale vocabulary** —

Run: `grep -nri "work-walled\|work_repos\|\baccounts\?\b" README.md`
Expected: no hits except inside the back-compat note (which may mention the legacy `work_repos` key once).

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs(readme): reframe to universal value prop; privacy/sources as advanced"
```

### Task 14: SKILL.md reframe

**Files:**
- Modify: `skills/vibe-insights/SKILL.md`

- [ ] **Step 1: Read the file**, then update so the first-run/orchestration path never assumes walling, uses `source`/`private` vocabulary, and surfaces the privacy nudge. Keep the MCP-decisions cache mechanics unchanged.

- [ ] **Step 2: Verify no stale vocabulary** —

Run: `grep -nri "work-walled\|work seat\|\bwalled\b" skills/vibe-insights/SKILL.md`
Expected: no hits (or only inside an explicit back-compat aside).

- [ ] **Step 3: Commit**

```bash
git add skills/vibe-insights/SKILL.md
git commit -m "docs(skill): reframe orchestration to source/private vocabulary + nudge"
```

### Task 15: New advanced doc + example config

**Files:**
- Create: `docs/privacy-and-sources.md`
- Modify: `config.example.json`

- [ ] **Step 1: Write `docs/privacy-and-sources.md`** covering: the two axes (sync vs private), the `advanced` block schema, both walling mechanisms, the `--privacy`/`--make-private` helpers, legacy back-compat (old `homes`/`work_repos` still read; `index.work.local.json` still read), and the multi-source worked example.

- [ ] **Step 2: Update `config.example.json`** to the new schema:

```json
{
  "machine": "laptop-01",
  "dataDir": "~/.vibe-insights",
  "decisions": { "source": "none" },
  "voice": null,
  "advanced": {
    "sources": [
      { "path": "~/.claude", "private": false },
      { "path": "~/.claude-work", "private": true }
    ],
    "private_repos": ["owner/employer-repo"]
  }
}
```

- [ ] **Step 3: Commit**

```bash
git add docs/privacy-and-sources.md config.example.json
git commit -m "docs: add privacy-and-sources advanced guide + new-schema example config"
```

---

## Out of scope (per spec)

- Marketplace `marketplace.json` description rewrite — happens at promotion time in the `vibe-plugins` repo, not here.
- Renaming internal `SessionRecord.walled` field or restructuring analytics/merge — untouched; only the `account` *values* and display strings change.
- Tagging/decisions/story mechanics — unchanged except the dual-read helper they now call.

## Definition of done

- `python -m pytest -q` green.
- A single `~/.claude` with no config produces a report with all sessions personal (the headline fix).
- A legacy config (`homes`/`work_repos`) loads and classifies identically to before (back-compat).
- `index.private.local.json` is written; both it and the legacy name are read.
- `vibe-insights --privacy` lists sources/repos; `--make-private[-source]` writes the `advanced` block.
- The privacy nudge appears when nothing is walled, and is silent once the user opts in.
- No `work-walled`/`home`/`account` vocabulary remains in README/SKILL/report user-facing surfaces (legacy keys mentioned only in back-compat notes).
