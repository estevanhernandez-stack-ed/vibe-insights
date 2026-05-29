<!-- Five-field format per item; /build relies on all five fields.
     Spec ref points at the approved design spec (superpowers path), since this
     run adopted Cart mid-stream over an existing combined spec. -->

# Build Checklist — vibe-insights Phase 2 (close the two thin lenses)

> **Spec:** `docs/superpowers/specs/2026-05-24-vibe-insights-phase2-design.md`
> (serves as combined spec + PRD for this run). Branch: `feat/phase2-thin-lenses`.

## Build Preferences

- **Build mode:** Autonomous (experienced builder; shape pre-approved).
- **Comprehension checks:** N/A (autonomous mode).
- **Git:** Commit after each item — conventional commits, e.g. `feat(analytics): tool_mix aggregator (step 1)`. End commit bodies with the Co-Authored-By trailer.
- **Verification:** Yes. Superpowers discipline woven in — **TDD (test-first)** on every aggregator (items 1-5), and **verification-before-completion** (run `pytest` + the real-index check) before any item is marked done. Checkpoint after item 5 (analytics complete) and item 7 (render + SKILL).
- **Check-in cadence:** N/A (autonomous).
- **Code review:** Superpowers `requesting-code-review` pass after item 7, before the final gate.

## Checklist

- [x] **1. `tool_mix` aggregator (TDD)**
  Spec ref: `design.md > Lens 1 > tool_mix(sessions)`
  What to build: Add `tool_mix(sessions)` to `analytics.py` — sum each session's `tool_counts` into a ranked `tools` list (top 12, desc), plus `web_search` / `web_fetch` totals. Mirror the `languages()` shape and cap. Write the tests first.
  Acceptance: Tests cover ranking order, top-12 cap, web-tool sums, and empty input. Returns the documented dict shape.
  Verify: `pytest tests/test_analytics.py -k tool_mix` passes.

- [x] **2. `delegation` aggregator (TDD)**
  Spec ref: `design.md > Lens 1 > delegation(sessions)`
  What to build: Add `delegation(sessions)` — `agent_calls` = sum of `tool_counts["Agent"]`; `haiku_sessions` = count of sessions where any `models` string contains "haiku" (case-insensitive). Tests first.
  Acceptance: Tests cover Agent-call sum, Haiku count with case-insensitivity, multi-model sessions, and no-model sessions.
  Verify: `pytest tests/test_analytics.py -k delegation` passes.

- [x] **3. `by_machine` aggregator (TDD)**
  Spec ref: `design.md > Lens 1 > by_machine(sessions)`
  What to build: Add `by_machine(sessions)` — group by `machine` only into `{machine, sessions, assistant_msgs, burn, repos}`, sorted by `assistant_msgs` desc. `burn` uses `human_tokens`; `repos` is distinct-repo count. Tests first.
  Acceptance: Tests cover grouping, `assistant_msgs` rollup, sort order, distinct-repo count, single-machine case.
  Verify: `pytest tests/test_analytics.py -k by_machine` passes.

- [x] **4. `pick_back_up` rework + `prune_candidates` (TDD)**
  Spec ref: `design.md > Lens 3 > rework pick_back_up`
  What to build: Extend `pick_back_up` so each record carries `age_days`, `empty_title`, `resume_signal`, `unfinished_score` (`resume+3, empty_title+2, recency=max(0, 3 - age_days//7)`). Exclude prune candidates and sort by `unfinished_score` desc then `last_ts` desc. Add `prune_candidates(sessions)` (or shared helper) for `age_days >= 21 AND not resume_signal AND not empty_title`. Preserve existing fields (`repo, branch, machine, title, last_ts`) for back-compat. Tests first.
  Acceptance: Tests cover per-signal scoring, sort-by-score, dedupe by `(repo, branch, machine)`, back-compat fields present, prune inclusion rule, mutual exclusion (score 0 ⟺ prune), and unparseable-`last_ts` handling.
  Verify: `pytest tests/test_analytics.py -k "pick_back_up or prune"` passes.

- [x] **5. Wire new keys into `build_digest`**
  Spec ref: `design.md > Digest assembly (build_digest)`
  What to build: Add `tool_mix`, `delegation`, `by_machine`, and `prune_candidates` to the dict returned by `build_digest`. Leave existing keys and `at_a_glance` untouched.
  Acceptance: Test asserts all four new keys present in `build_digest` output and existing keys unchanged.
  Verify: `pytest tests/test_analytics.py` fully green. **Checkpoint:** analytics layer complete.

- [x] **6. Render both lenses — Markdown + HTML (`report.py`)**
  Spec ref: `design.md > Rendering (report.py)`
  What to build: Add a "How you work" section (md `_md_how_you_work` + branded HTML card): tool-mix table/bars, delegation line/tiles, per-machine comparison table. Enrich `_md_pick_back_up` and its HTML card with `Age` + `Score` columns and an appended "Prune candidates" table (omit when empty). Reuse existing CSS vocabulary (`.card/.kick/.tiles/.tile/.bars/tbl()`).
  Acceptance: Smoke test in `tests/test_report.py` — when the digest carries the new keys, the rendered md/html contain the new sections; empty prune list omits the table cleanly.
  Verify: `pytest tests/test_report.py` passes; eyeball `reports/insights.html` from a real run.

- [x] **7. Update SKILL narrative grounding**
  Spec ref: `design.md > SKILL (skills/vibe-insights/SKILL.md)`
  What to build: Extend SKILL step 4's grounding list with `tool_mix.tools`, `delegation.*`, `by_machine` (workhorse ratio of top-two `assistant_msgs`), and `pick_back_up[].unfinished_score` + `prune_candidates`. Narrative reasons over the computed score; it does not re-derive "looks unfinished."
  Acceptance: SKILL step 4 names every new digest field. No engine logic moved into the SKILL.
  Verify: Re-read SKILL step 4 — every new field is referenced. **Checkpoint + superpowers code-review pass** before the final gate.

- [x] **8. Documentation & security verification**
  Spec ref: `design.md > all sections` + `design.md > Validation`
  What to build: Confirm `README.md` reflects the new lenses (what the report now produces). Confirm `docs/` artifacts (design spec, checklist) are current with what shipped. Run the full `pytest` suite. Run the **real-index validation** — `vibe-insights` against the local index — and confirm the report auto-produces the tool-mix line, delegation signal, machine comparison, and ranked/pruned open-threads (the prototype's read, generated). Secrets scan: no tokens/keys committed; `.gitignore` sane (no `config.json`, no `.vibe-insights/` data). Dependency audit (`pip audit` or `python -m pip_audit` against `pyproject.toml`); address criticals.
  Acceptance: Full suite green. Real-index run shows all four lenses populated. README + docs current. No secrets in the diff. Dependency audit clean or findings documented.
  Verify: `pytest` all green; `git log -p` on the branch shows no secrets; real `insights.html` renders the new sections end to end.

## Sequencing rationale

Items 1-4 are independent aggregators built test-first; 4 also carries the shared scoring helper for prune. Item 5 wires them into the digest (depends on 1-4) — the analytics checkpoint. Item 6 renders over the digest keys (depends on 5). Item 7 updates the narrative contract (depends on the keys existing). Item 8 is the always-final doc/security gate, plus the real-index validation that proves the prototype's read is now automatic.

## Iteration 1 — resume-keyword tune-up

Polish pass after v0.2.0 shipped. Real-index validation showed `resume_signal`
fired on nearly every branch (substring match including the over-common `fix`),
so `prune_candidates` never surfaced. Make the signal meaningful.

- [x] **I1.1 Two-tier word-boundary resume keywords (TDD)**
  Spec ref: `design.md > Lens 3` (refines the `resume_signal` definition)
  What to build: Replace the flat substring `_RESUME_KEYWORDS` with a curated
  strong-intent set — `continue, wip, todo, finish, incomplete, unfinished,
  "in progress", "left off", "pick up", smoke, draft` — matched on word
  boundaries (compiled `\b(...)\b` regex, case-insensitive). Drop `fix` and
  `complete` (too common / ambiguous). Update `_enrich_branch` to use the regex.
  Tests first.
  Acceptance: `fix`-only and `complete`-only titles no longer set `resume_signal`;
  `continue/wip/smoke/"in progress"/"left off"/"pick up"/draft` do; word-boundary
  false-positives excluded (`prefix`, `fixture`, `smoker`, `finished`); `unfinished`
  matches. Existing score/prune tests updated to the new keyword semantics; full
  suite green.
  Verify: `python -m pytest -q` all green.

- [x] **I1.2 Real-index re-validation** — ranking now leads with real resume threads (continue/smoke); `prune_candidates` correctly 0 (no feature branch is ≥21d in the current index; oldest is 20d). Invariant holds on real data.
  Spec ref: `design.md > Validation`
  What to build: Run the engine against the live personal index; confirm
  `prune_candidates` now surfaces stale no-signal branches and `pick_back_up`
  still leads with the genuine resume threads (continue/wip/smoke), and the
  score==0 ⟺ prune invariant still holds on real data.
  Verify: validation output shows non-trivial prune set (if stale branches exist)
  and a sane ranking; invariant assertion passes.

## Iteration 2 — wire the Web line

The "Web" line read 0/0. Root cause (verified): `scan.py` populates
`web_search`/`web_fetch` only from `usage.server_tool_use` (the Anthropic API
server-side web tool), which is 0 in normal Claude Code use. The real web
activity is the **client-side** `WebSearch`/`WebFetch` tools — confirmed present
in the live index (sessions run 1-9 searches; work shard up to 56) but only
counted in `tool_counts`, never mirrored to the dedicated fields.

- [x] **I2.1 Count client web tools into the web fields (TDD)**
  Spec ref: `scan.py > ingest_event` (assistant tool_use loop)
  What to build: In `ingest_event`'s `tool_use` loop, increment `rec.web_search`
  for `name == "WebSearch"` and `rec.web_fetch` for `name == "WebFetch"`, on top
  of the existing `server_tool_use` accounting. The fields become *total* web
  activity (client + the ~0 server); the tools stay in `tool_counts` too (the
  ranking view). Tests first.
  Acceptance: an assistant event with WebSearch/WebFetch tool_use blocks folds
  into `web_search`/`web_fetch` AND `tool_counts`; the existing server_tool_use
  test still passes; combined client+server sums correctly. Full suite green.
  Verify: `python -m pytest -q` all green.

- [x] **I2.2 Real-index re-validation** — re-scan surfaced web_search=322 / web_fetch=306 on this machine's personal shard (was 0/0). Fix confirmed on real data.
  Spec ref: `design.md > Validation`
  What to build: Re-scan the live index (the engine re-scans every run) and
  confirm the "Web" line now reports non-zero search/fetch totals matching the
  client tool usage.
  Verify: validation shows web_search/web_fetch > 0 on the real personal index.

## Iteration 3 — active runtime + tag-cache timestamp drift

Two engine gaps surfaced during a 2026-05-29 session comparing Opus 4.8 / ultracode
work against the prior window. Both ship in the distributed engine, so fix here.

1. **No active-runtime metric.** The only per-session time fields are `first_ts` /
   `last_ts`, whose delta is the session's *open window* — it includes overnight idle
   and concurrent overlap (the real index reads as >24 h/day when summed), so it is
   useless as "runtime." There is no active-time signal at all. It must be computed
   at scan time on each machine: raw `.jsonl` logs never cross machines (only
   `synced/` indexes do), so active time cannot be derived downstream from the index
   alone — it has to be baked into the record. (Today this required a manual one-off:
   computing active time per session on each machine and dropping a
   `synced/<machine>/active_times.json` for the other to read. That stopgap is what
   this iteration makes native.)
2. **Tag-cache staleness false-positives.** `tagging.untagged()` decides "needs
   re-tag" by a raw **string** compare of `last_ts` (cache vs index). After a
   re-merge the index re-serializes timestamps in a different format (local `-05:00`
   → `+00:00` UTC), so already-judged sessions get re-flagged en masse. In this run
   **71 of 74** re-flagged sessions were the *same instant* in a different string —
   pure format drift, not real change. Every re-merge otherwise forces a full,
   needless re-tag pass.

- [ ] **I3.1 `active_minutes` at scan time (TDD)**
  Spec ref: `scan.py > ingest_event` + `records.py` (new record field)
  What to build: Track each session's event timestamps during scan; compute
  `active_minutes` = sum of gaps between consecutive events, counting only gaps
  `<= IDLE_THRESHOLD_MIN` (module constant, default 5). Store on the record. Idle
  gaps and the cross-session overlap problem are excluded by construction. Tests
  first.
  Acceptance: a session with two close events plus one long gap counts only the close
  gap; single-event sessions = 0; threshold is a named constant; field present on
  every record. Full suite green.
  Verify: `python -m pytest -q` all green.

- [ ] **I3.2 Active-time rollups + render (TDD)**
  Spec ref: `analytics.py > by_machine` + `report.py > How you work`
  What to build: Add `active_hours` to `by_machine`, plus a `burn_per_active_hour`
  density figure (`human_tokens` / active hours). Surface an "Active time" line in
  the md/HTML report. Depends on I3.1. Tests first.
  Acceptance: rollups sum per machine; density = burn / active-hours; report renders
  the line; zero/empty active time degrades cleanly. Suite green.
  Verify: `python -m pytest -q`; eyeball `reports/insights.html` from a real run.

- [ ] **I3.3 Compare `last_ts` as an instant, not a string (TDD)**
  Spec ref: `tagging.py > untagged()`
  What to build: Parse both cached and current `last_ts` to a normalized UTC instant
  and compare with a small tolerance (< 1 s) instead of `!=` on the raw strings. A
  session is "needs re-tag" only when the instant genuinely advances. Optionally
  canonicalize stored `last_ts` to UTC ISO going forward. Tests first.
  Acceptance: same-instant-different-format does NOT re-flag; a genuinely advanced
  `last_ts` does; unparseable `last_ts` falls back to current (re-flag) behavior.
  Suite green.
  Verify: `python -m pytest -q` all green.

- [ ] **I3.4 Real-index re-validation**
  Spec ref: `design.md > Validation`
  What to build: Re-scan the live index; confirm `active_minutes` is populated and
  the report's "Active time" line + density read are sane (active time well below the
  open-window span). Confirm a re-merge no longer mass-re-flags the tag cache —
  `--emit-tagging-input` after a re-merge returns only genuinely new + genuinely
  advanced sessions, not the whole tagged set.
  Verify: active-time line non-trivial and < span; post-re-merge tagging-input count
  reflects real change only.

- [ ] **I3.5 Scope build-story decisions to the repo (TDD)**
  Spec ref: `cli.py > --story-input` decisions filter + `story.py`
  What to build: The story-input spine attaches the *full* decision log to every repo.
  The filter (`[d for d in all_decs if project_tag matches repo] or all_decs`) never
  matches, because project tags are display names ("Vibe Plugins") while the repo arg is
  a slug ("vibe-plugins"), so it always falls through to the global `or all_decs`. Match
  on a normalized form (slugify the tag, or maintain a repo→tag map), and when a repo
  genuinely has zero tagged decisions, label the fallback in the spine so the drafter
  knows the decisions aren't repo-scoped. Tests first.
  Acceptance: a repo with tagged decisions gets only its own; display-name-vs-slug
  mismatch still matches; a zero-match repo gets an explicitly-labeled global fallback,
  not a silent one. (Found 2026-05-29 generating per-repo build stories — every repo's
  spine carried the same 34 decisions.)
  Verify: `python -m pytest -q`; re-run `--story-input vibe-plugins` and confirm the
  Decisions section is vibe-plugins-only.

## Iteration 4 — split the work boundary by field, not by session

Policy refinement from the builder (2026-05-29): the current wall is stricter than
needed. Today work sessions are *fully* local-only — the work shard never syncs, never
aggregates cross-machine, never renders beyond the local report. The builder is fine
seeing **how he works on work** (burn, active time, velocity, friction, session shape)
across machines and in any rollup. What must never leave a machine or be published is
the **content** — anything describing *what* the work is about. So the boundary should
cut by field, not drop the whole session.

- **Metric / shape fields — safe to sync, aggregate, and render:** `tokens_*`,
  `active_minutes`, `tool_counts`, `models`, `first_ts` / `last_ts`, user/assistant
  msg counts, web counts, `session_type`, and the `friction` / `satisfaction` /
  `outcome` tags. The account=work flag itself is fine (so work vs personal stays
  distinguishable in rollups).
- **Content fields — stay local, redacted from anything that crosses or publishes:**
  `title`, the tag `intent`, `repo`, `branch`, `cwd` — anything that names or
  describes the work. (These may still show in the *local* report on the machine that
  owns them; the redaction applies only to what syncs or gets published.)

- [ ] **I4.1 Single source of truth for content vs metric fields**
  Spec ref: `records.py` (field classification) + `config.py`
  What to build: Declare which record fields are "content" in one place (a constant
  set or per-field flag). Everything not classified content is metric/shape. Tests
  assert the classification covers every record field (no field silently
  unclassified).
  Verify: `python -m pytest -q` green; adding a new record field without classifying
  it fails a test.

- [ ] **I4.2 Redacted work export the sync layer may carry (TDD)**
  Spec ref: `scan.py` / write path + `merge.py`
  What to build: Alongside the local-only full work shard (`index.work.local.json`,
  content intact, stays put), emit a **redacted** work projection that sync is allowed
  to carry: metric fields only, with `repo`/`branch` replaced by a stable opaque id
  (e.g. `work-repo-<hash>` so per-repo rollups still group without naming the repo),
  and `title`/`intent`/`cwd` dropped. Tests first.
  Acceptance: the redacted export contains zero content fields; the opaque repo id is
  stable across runs for the same repo; the full local work shard is unchanged.
  Verify: `python -m pytest -q` green; diff a redacted export — no titles, no repo
  names, no branches, no cwd.

- [ ] **I4.3 Let work shape into rollups + report; update the SKILL boundary**
  Spec ref: `analytics.py`, `report.py`, `skills/vibe-insights/SKILL.md` (step 6)
  What to build: Allow redacted work metrics into the cross-machine rollups and the
  "how you work" lenses (burn, active time, friction, by-machine), while work content
  stays off every synced/published surface. Rewrite SKILL step 6 from "work shard is
  fully local-only" to the metric/content split: work *shape* is included and may
  cross; work *descriptions* never leave the owning machine or get published.
  Acceptance: rollups can include work shape; no work title/intent/repo/branch/cwd
  appears in any synced or published artifact; SKILL step 6 states the new rule.
  Verify: real-index run shows work shape in the rollups; grep synced/ + any published
  output for known work repo names / titles — zero hits.

- [ ] **I4.4 Boundary validation gate**
  Spec ref: `design.md > Validation`
  What to build: A test/scan that fails if any content field leaks into a synced or
  published surface. Run it against the live data.
  Verify: leak scan clean on real data; redacted work export carries shape only.
