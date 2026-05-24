# vibe-insights Phase 2 — close the two thin lenses

**Date:** 2026-05-24
**Status:** Design approved, pending implementation plan
**Repo:** `vibe-insights` (solo) · branch `feat/phase2-thin-lenses`

## Context

The `insights-deep-2026-05-23.md` prototype is a hand-written read of four lenses
over the merged personal session set. Its closing line proposed "baking these four
lenses into the engine so `/vibe-insights` produces this automatically every run."

A code audit corrected that framing: **two of the four lenses already ship.**

| Lens | State today |
|---|---|
| Trends (step-change, acceleration) | Done — `analytics.trends()` |
| Token / cache intelligence | Done — `analytics.token_cost()` |
| How you actually work | **Thin** — has top-repos + model counts, but no tool-mix, no delegation signal, no per-machine message-volume comparison |
| Open threads (pick this back up) | **Thin** — lists feature branches newest-first, but no unfinished-likelihood ranking and no prune-candidate flagging |

The two thin lenses are computable from data the engine **already ingests** —
`tool_counts`, `assistant_msgs`, and `models` are present on every `SessionRecord`
(see `records.py`) but never aggregated. No ingest-layer work is required.

## Goals

1. Enrich Lens 1 ("How you actually work") with three deterministic aggregators:
   tool mix, delegation signal, per-machine comparison.
2. Rework Lens 3 ("Open threads") to rank feature branches by a deterministic
   `unfinished_score` and surface a separate `prune_candidates` list.
3. Render both lenses in the Markdown and HTML reports.
4. Update the SKILL so the narrative grounds in the new digest fields instead of
   re-deriving them.
5. Cover all new logic with tests.

## Non-goals (explicitly out of scope)

- **No ingest changes.** `records.py`, `cclogs.py`, `scan.py`, `merge.py` untouched.
- **No new per-session signals** (dollar cost, diff churn, commit counts) — that was
  the rejected "extend ingest" scope.
- **No git cross-referencing** for prune detection. Prune candidacy is a pure
  age + keyword heuristic over the index; the engine does not shell into each repo.
- **No new CLI flags.** `cli.py` and `config.py` unchanged.
- **No marketplace ref-bump.** Promotion to stable in `vibe-plugins` is a separate,
  later, deliberate step once the work is validated.

## Design

Principle held throughout: **deterministic aggregation in `analytics.py`, rendering
in `report.py`, narrative synthesis stays in the SKILL.** This matches the engine's
existing grain — every other lens already follows it.

### Lens 1 — "How you actually work"

Three new aggregators in `analytics.py`, all assembled into the digest by
`build_digest`.

#### `tool_mix(sessions) -> dict`

Sums `tool_counts` across all sessions into a ranked list, plus web-tool totals.

```python
{
  "tools": [{"tool": "Bash", "count": 8400}, {"tool": "Read", "count": 7300}, ...],  # top 12, desc
  "web_search": <int>,   # sum of s["web_search"]
  "web_fetch": <int>,    # sum of s["web_fetch"]
}
```

Mirrors the existing `languages()` aggregator's shape and top-N cap (12).

#### `delegation(sessions) -> dict`

The subagent / model-delegation story.

```python
{
  "agent_calls": <int>,      # sum of tool_counts.get("Agent", 0)
  "haiku_sessions": <int>,   # count of sessions where any model string contains "haiku" (case-insensitive)
}
```

`opus`/`sonnet` session counts already exist via `token_cost.model_session_counts`;
`delegation` adds only the two signals the prototype called out ("397 Agent calls
+ 31 sessions touching Haiku").

#### `by_machine(sessions) -> list[dict]`

The "workhorse" comparison. Groups by `machine` only (not account+machine like
`coverage()`), and crucially includes `assistant_msgs`, which `coverage()` drops.

```python
[
  {"machine": "nebuchadnezzar", "sessions": 75, "assistant_msgs": 39284,
   "burn": 48900000, "repos": <int>},
  {"machine": "dunder-mifflan", "sessions": 57, "assistant_msgs": 17090,
   "burn": <int>, "repos": <int>},
]  # sorted by assistant_msgs desc
```

Work-wall note: work sessions are included and labeled in the local report (same as
the rest of the engine); the work shard stays local-only. `by_machine` aggregates
whatever sessions it is handed — the walling happens upstream, not here.

### Lens 3 — "Open threads" (rework `pick_back_up`)

`pick_back_up(sessions, limit=15)` keeps its existing public fields
(`repo, branch, machine, title, last_ts`) so current consumers — the report
renderers and `at_a_glance` / next-moves (which read the top 2) — keep working.
It gains deterministic signals and a new sort order.

Per unique `(repo, branch, machine)` feature branch (most-recent session wins):

| Signal | Definition |
|---|---|
| `age_days` | `(now - last_ts).days`; sessions with unparseable `last_ts` treated as very old |
| `empty_title` | `not title.strip()` — a dangling fix left open |
| `resume_signal` | title matches (case-insensitive) any of: `continue`, `complete`, `finish`, `wip`, `smoke`, `fix`, `todo`, `left off`, `pick up` |
| `unfinished_score` | `resume(+3) + empty_title(+2) + recency` where `recency = max(0, 3 - age_days // 7)` |

`recency` yields 3 (<7d), 2 (<14d), 1 (<21d), 0 (>=21d). Newer branches score as
more likely still-live.

**Output changes:**
- A new top-level digest key `prune_candidates`: feature branches where
  `age_days >= 21 AND not resume_signal AND not empty_title` — the "shipped-or-
  abandoned, worth a prune pass" set. Same record shape.
- `pick_back_up` **excludes prune candidates**, and is **sorted by
  `unfinished_score` desc, then `last_ts` desc** (was pure recency). Each remaining
  record carries the four new fields.

The two lists never overlap, by construction. The prune rule's `age_days >= 21`
is exactly where the recency term reaches 0, so a branch is a prune candidate
**iff** its `unfinished_score == 0` (no resume keyword, not an empty-title fix, and
old enough that recency contributes nothing). Every non-prune branch therefore has
`unfinished_score >= 1` and stays in `pick_back_up`.

### Rendering (`report.py`)

**Markdown** — two additions:
- `_md_how_you_work(tool_mix, delegation, by_machine)` → a "How you work" section:
  tool-mix table, a delegation line (`Agent calls: N · Haiku sessions: N`), and a
  per-machine comparison table.
- `_md_pick_back_up` gains `Age` and `Score` columns; a new `_md_prune_candidates`
  renders a "Prune candidates" mini-table (omitted when empty).

**HTML** — matching branded cards using the existing CSS vocabulary
(`.card`, `.kick`, `.tiles`, `.tile`, `.bars`, `tbl()`): a "How you work" card
(tool-mix bars + delegation tiles + machine table) and the enriched
"Pick this back up" card with an appended prune-candidates table.

### SKILL (`skills/vibe-insights/SKILL.md`)

Step 4 ("Synthesize the narrative") grounding list gains:
- `tool_mix.tools` — the build-debug loop shape (lead tools).
- `delegation.agent_calls` / `delegation.haiku_sessions` — the "delegates heavily"
  read.
- `by_machine` — which machine is the workhorse and by how much (ratio of top two
  `assistant_msgs`).
- `pick_back_up[].unfinished_score` and `prune_candidates` — reason over the
  computed score; name the top thread(s) and call out the prune set rather than
  re-deriving "looks unfinished."

### Digest assembly (`build_digest`)

Adds keys: `tool_mix`, `delegation`, `by_machine`, `prune_candidates`. Existing keys
unchanged. `at_a_glance` is unaffected (it reads `token_cost`, `trends`, `tags`).

## Testing

`tests/test_analytics.py` (following existing fixture patterns):
- `tool_mix`: ranking order, top-12 cap, web-tool sums, empty input.
- `delegation`: Agent-call sum, Haiku session count (case-insensitivity, sessions
  with multiple models, no-model sessions).
- `by_machine`: grouping, `assistant_msgs` rollup, sort order, single-machine case.
- `pick_back_up`: score computation per signal, sort-by-score, dedupe by
  `(repo, branch, machine)`, backward-compatible fields present.
- `prune_candidates`: inclusion rule, mutual exclusion with `pick_back_up`,
  unparseable-`last_ts` handling.

If render regressions are a risk, add a smoke assertion in `tests/test_report.py`
that the new sections appear when the digest carries the new keys.

## Blast radius

| File | Change |
|---|---|
| `src/vibe_insights/analytics.py` | 3 new aggregators + `pick_back_up` rework + `build_digest` keys |
| `src/vibe_insights/report.py` | new md + html sections; enriched pick-back-up |
| `skills/vibe-insights/SKILL.md` | narrative-grounding additions (step 4) |
| `tests/test_analytics.py` (+ maybe `tests/test_report.py`) | new coverage |

Untouched: `records.py`, `cclogs.py`, `scan.py`, `merge.py`, `cli.py`,
`config.py`, `decisions.py`, `tagging.py`, `story.py`.

## Validation

Run the full engine against the real local index (`vibe-insights`), confirm the
report now produces the tool-mix line, delegation signal, machine comparison, and
ranked/pruned open-threads — i.e. the prototype's read, generated automatically.
Real-index validation is the bar (the family norm: every plugin proven against real
data before it ships).
