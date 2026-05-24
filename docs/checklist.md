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

- [ ] **8. Documentation & security verification**
  Spec ref: `design.md > all sections` + `design.md > Validation`
  What to build: Confirm `README.md` reflects the new lenses (what the report now produces). Confirm `docs/` artifacts (design spec, checklist) are current with what shipped. Run the full `pytest` suite. Run the **real-index validation** — `vibe-insights` against the local index — and confirm the report auto-produces the tool-mix line, delegation signal, machine comparison, and ranked/pruned open-threads (the prototype's read, generated). Secrets scan: no tokens/keys committed; `.gitignore` sane (no `config.json`, no `.vibe-insights/` data). Dependency audit (`pip audit` or `python -m pip_audit` against `pyproject.toml`); address criticals.
  Acceptance: Full suite green. Real-index run shows all four lenses populated. README + docs current. No secrets in the diff. Dependency audit clean or findings documented.
  Verify: `pytest` all green; `git log -p` on the branch shows no secrets; real `insights.html` renders the new sections end to end.

## Sequencing rationale

Items 1-4 are independent aggregators built test-first; 4 also carries the shared scoring helper for prune. Item 5 wires them into the digest (depends on 1-4) — the analytics checkpoint. Item 6 renders over the digest keys (depends on 5). Item 7 updates the narrative contract (depends on the keys existing). Item 8 is the always-final doc/security gate, plus the real-index validation that proves the prototype's read is now automatic.
