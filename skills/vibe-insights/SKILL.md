---
name: vibe-insights
description: Cross-machine retrospective insights for Claude Code. Run when the user says "/vibe-insights", "where was I", "what was I working on", or wants coverage / token-burn / recall across their sources and machines. Personal by default; private sources and repos stay local-only.
---

# vibe-insights

Run the deterministic engine, synthesize the narrative read from its digest, then
surface the report. Never print the full report inline — write to files and
summarize (output-ceiling discipline).

## Steps

1. **Ensure config.** If `~/.vibe-insights/config.json` is missing, run
   `vibe-insights --init`, show the discovered sources, and ask the user to confirm
   the config. Every discovered `~/.claude*` source is personal by default —
   no walling is required to get started. Config also carries an optional `advanced`
   block (`advanced.sources` with per-source `private` flags, `advanced.private_repos`
   for individual repos to keep local-only) and a `decisions` block
   (`{"source": "none"|"file"|"mcp"}`). After a scan where nothing is private, a
   non-blocking nudge prints reminding the user that `--privacy` exists — it's
   informational, not an error.

2. **Decisions (MCP-agnostic — only the skill ever touches MCP; implements the [family decision-log convention](https://github.com/estevanhernandez-stack-ed/vibe-plugins/blob/main/docs/conventions/decision-log-backend.md)).** Read
   `config.decisions.source`:
   - `none` / `file` → do nothing; the engine reads it directly.
   - `mcp` → fetch from the user's configured decisions MCP, map each to the
     canonical shape `{timestamp, title, body, project_tag, link}`, and write the
     list to `~/.vibe-insights/decisions.cache.json` BEFORE running the engine (the
     engine reads that cache; it never calls MCP itself).
     - For **626Labs**: `mcp__626labs-cloud__manage_decisions` action `getUnified`
       (requires a `projectId`). For a **cross-project** view, iterate the project IDs
       in `config.decisions.projects` (or `manage_projects list` → the active ones),
       `getUnified` each, merge, sort newest-first. Map `decision`→`title`,
       `rationale`→`body`, created→`timestamp`, the project name→`project_tag`. The
       report's Decisions section shows `project_tag`, so cross-project reads cleanly.
     - For **another user's MCP**: call their decisions tool and map to the same
       canonical shape. The engine is identical regardless of source.

3. **Run the engine.** `vibe-insights` (or `python -m vibe_insights.cli`). It
   writes per-machine personal indexes under `synced/`, the local-only
   `index.private.local.json` (for any private sources or repos), `digest.json`,
   and the deterministic report (`reports/insights.{md,html}` — Coverage, Where was
   I, Token & cost, Trends, Pick this back up, Decisions).

4. **Synthesize the narrative.** Read `~/.vibe-insights/digest.json` and write a
   2–4 paragraph "How you actually work" read. Ground every claim in digest numbers
   — name the gravity-well repo (top of `token_cost.top_repos_by_burn`), the
   acceleration (`trends.acceleration_multiple`), the cache story
   (`token_cost.cache_read` vs `input`, `cache_read_share`), the output-heaviness
   (`output_share`), the build-debug loop shape (`tool_mix.tools` — the lead tools,
   in order), the delegation habit (`delegation.agent_calls` Agent calls +
   `delegation.haiku_sessions` sessions touching Haiku), the workhorse machine
   (`by_machine` — which box carries the work and by how much; the ratio of the
   top-two `assistant_msgs`), and the open threads. For the threads, **reason over
   the computed `pick_back_up[].unfinished_score`** (highest = most likely genuinely
   unfinished — name the top 1–2) and **call out `prune_candidates`** as the
   shipped-or-abandoned set worth a prune pass. Don't re-derive "looks unfinished"
   from titles by hand — the engine already scored it; explain the score.
   Punchline-first, specific numbers, no hedging. Don't restate the tables — read
   what they *mean*.

   Write it as a **trusted HTML fragment** to `~/.vibe-insights/reports/narrative.html`
   using only `<h2>/<h3>/<p>/<strong>/<ol>/<li>/<code>` (it's styled by the report's
   `.narrative` CSS). Optionally also write a `.md` copy. Then run
   `vibe-insights --render-only` to re-render `insights.html` with the narrative as
   its hero (no re-scan).

5. **Report only:** the narrative inline (tight — the highlights, not the whole
   file), then the single `insights.html` path (narrative + all sections in one
   branded page) and `insights.md`, plus a one-line coverage stat (personal vs private,
   across N machines). Never dump the full report inline.

6. **The privacy boundary.** Private sources and private repos ARE included and
   labeled in the local report (so all your sessions are viewable locally), but
   the private shard (`index.private.local.json`) is **local-only**: it never syncs
   cross-machine (only `synced/` replicates) and never gets pushed to git. Don't
   publish private session content to external or public surfaces.

## Operating doctrine

Family procedure layer — full anatomy per move in the [canonical doctrine](https://github.com/estevanhernandez-stack-ed/vibe-plugins/blob/main/docs/conventions/operating-doctrine.md).

```
Operating doctrine digest — operating-doctrine v1.0.0 (2026-07-06):
1. Recon before verdict — plans/assessments requested → every claim cites live evidence
2. Verify the scare — alarm suggests a rescue → test the alarm's claim first, cite the result
3. Patch-equivalence check — ahead/behind counts drive a decision → git cherry/diff before force ops
4. Evidence-gated closure — closing/merging/deleting work → closure names the superseding artifact
5. Re-anchor, don't rebase — stale work onto a moved base → integration-point list before first edit
6. Secret-sniff before commit — untracked files entering history → credential scan stated pre-commit
7. Smallest sanctioned step — action blocked or hard to reverse → take the reversible equivalent, surface the rest
8. Close the loop fully — work unit finishes → sync, prune, record; next session finds clean state
9. Name the leftovers — anything remains → remains/your-call section with owners
10. Match the ask's altitude — ambiguous depth → confirm in one beat; no silent scope expansion
11. Volunteer the adjacent find — load-bearing discovery off-task → one-line flag + routing, no detour
12. Contradiction stop — evidence contradicts a prior conclusion → name it, re-verify, reconcile before proceeding
```

### Domain overlay — vibe-insights' load-bearing moves

- **1. Recon before verdict — recall answers come from the engine, never from model memory.** "Where was I" resolves from the live scan's digest; every recall claim cites the session it came from (date, source, repo). A model's remembered impression of prior sessions is not a source.
- **12. Contradiction stop — when the numbers contradict the user's memory, name the mechanism.** "I definitely worked on X last week" vs an empty scan means: source not mounted, privacy wall excluding it, or view mismatch — say which, with evidence, before concluding the work didn't happen. Canonical instance: the burn view bundles subagent transcripts, so per-model attribution disputes resolve against raw transcripts, not burn totals.

*Provenance: operating-doctrine v1.0.0 (2026-07-06).*

## Voice

If `config.voice` is set, write the narrative read, the Next-moves copy, AND the
Build Story in that voice (default is neutral analytic prose):
- `coder` — the CODER VOICE SYNTHESIS in `~/.claude/CLAUDE.md` (punchline-first,
  specific numbers, em-dashes, the dichotomy moves).
- `smart-brevity` — axiom-led, tight, published-article feel.
- `oscar` — the `oscar` skill (patient, faintly-exasperated explainer).

## Build Story (optional)

Turn a project's history into a grounded build-in-public devlog:

1. `vibe-insights --story-input <repo> [--repo-path <path>]` writes
   `~/.vibe-insights/story-input.md` — the spine: scoped session timeline + that
   project's decisions + the repo's git commit log.
2. Draft the story from the spine in `config.voice`. Lead with the arc; name the
   momentous hurdles (look for `bugfix`/pivot decisions); ground every beat in the
   spine's real timestamps + numbers; never invent.
3. **Offer a riff pass.** Show the draft (or its shape) and invite the user to riff
   — change the angle, add or cut beats, shift emphasis, adjust the voice. The build
   story is collaborative; it's *their* story. Iterate on their notes before
   finalizing. Don't treat the first draft as done.
4. Write to `<repo>/docs/build-story-<date>.md` (long-form → file), then a
   2-sentence summary + the path in chat (output-ceiling discipline).
