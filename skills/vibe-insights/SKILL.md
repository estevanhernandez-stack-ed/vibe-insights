---
name: vibe-insights
description: Cross-home, cross-machine retrospective insights for Claude Code. Run when the user says "/vibe-insights", "where was I", "what was I working on", or wants coverage / token-burn / recall across their config homes and machines. Walls work (employer) sessions from personal.
---

# vibe-insights

Run the deterministic engine, synthesize the narrative read from its digest, then
surface the report. Never print the full report inline — write to files and
summarize (output-ceiling discipline).

## Steps

1. **Ensure config.** If `~/.vibe-insights/config.json` is missing, run
   `vibe-insights --init`, show the discovered homes + account labels, and ask the
   user to confirm the mapping. Config also carries `work_repos` (employer repos →
   labeled work, kept local-only) and a `decisions` block
   (`{"source": "none"|"file"|"mcp"}`).

2. **Decisions (MCP-agnostic — only the skill ever touches MCP).** Read
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
   `index.work.local.json`, `digest.json`, and the deterministic report
   (`reports/insights.{md,html}` — Coverage, Where was I, Token & cost, Trends,
   Pick this back up, Decisions).

4. **Synthesize the narrative.** Read `~/.vibe-insights/digest.json` and write a
   2–4 paragraph "How you actually work" read. Ground every claim in digest numbers
   — name the gravity-well repo (top of `token_cost.top_repos_by_burn`), the
   acceleration (`trends.acceleration_multiple`), the cache story
   (`token_cost.cache_read` vs `input`, `cache_read_share`), the output-heaviness
   (`output_share`), and the top 1–2 `pick_back_up` threads. Punchline-first,
   specific numbers, no hedging. Don't restate the tables — read what they *mean*.

   Write it as a **trusted HTML fragment** to `~/.vibe-insights/reports/narrative.html`
   using only `<h2>/<h3>/<p>/<strong>/<ol>/<li>/<code>` (it's styled by the report's
   `.narrative` CSS). Optionally also write a `.md` copy. Then run
   `vibe-insights --render-only` to re-render `insights.html` with the narrative as
   its hero (no re-scan).

5. **Report only:** the narrative inline (tight — the highlights, not the whole
   file), then the single `insights.html` path (narrative + all sections in one
   branded page) and `insights.md`, plus a one-line coverage stat (personal vs work,
   across N machines). Never dump the full report inline.

6. **The boundary.** Work sessions ARE included and labeled in the local report (so
   all your work is viewable), but the work shard (`index.work.local.json`) is
   **local-only**: it never syncs cross-machine (only `synced/` replicates) and never
   gets pushed to git. Don't publish work content to external/public surfaces.

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
