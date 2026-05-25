<p align="center">
  <img alt="Vibe Insights — cross-machine, work-walled Claude Code session analytics" src="https://626labs.dev/assets/brand/plugins/vibe-insights-banner-1500x500.png" />
</p>

# Vibe Insights

**Cross-machine, work-walled Claude Code session analytics — the verbose `/insights` you wish you had.**

[![stable](https://img.shields.io/github/v/tag/estevanhernandez-stack-ed/vibe-insights?label=stable&color=17d4fa)](https://github.com/estevanhernandez-stack-ed/vibe-insights/tags)

## What it does

A deterministic Python engine reads your Claude Code session transcripts — across *all* your machines and history, with the parts that are your employer's kept local — and produces one branded report:

- **Coverage** — sessions / repos / token burn, split by account (work vs personal) × machine.
- **Where was I** — most-recent sessions with titles, branches, machines (ADHD-brain recall).
- **Token & cost** — burn, output share, and the cache reveal (cache-read tokens vs fresh input).
- **Trends** — burn per day, recent-vs-baseline acceleration.
- **How you work** — your tool mix (the build-debug loop), delegation habit (subagent + Haiku usage), and a per-machine comparison (which box is the workhorse).
- **Pick this back up** — open feature branches you walked away from, ranked by how likely they are to be genuinely unfinished, plus a **prune candidates** list for branches that look shipped-or-abandoned.
- **Decisions** — your logged architectural decisions (MCP-agnostic: file or your dashboard).
- **Languages & signals** — what you edit, tool errors, multi-clauding (parallel sessions).
- **How it went** — per-session friction / satisfaction / outcome (LLM-tagged, cached).
- **A narrative read** — a synthesized "how you actually work" interpretation, grounded in the numbers.

## How it works

- **Engine is deterministic and offline.** It never calls an LLM or MCP — it reads local JSONL transcripts and a few local cache files. The narrative + decisions + per-session tags are produced by the `/vibe-insights` skill (where the LLM lives) and handed to the engine as files. That keeps the analytics reproducible and the tool marketplace-portable.
- **The wall is by repo, not by home.** Configure `work_repos`; those sessions are labeled `work`, kept **local-only** (never synced cross-machine, never pushed), but still visible in your own report. Personal sessions sync.
- **Cross-machine via per-machine indexes.** Each machine emits a tiny `index.json`; sync the `synced/` folder (e.g., Syncthing) and the report merges every machine. Token math can be shared with **Sanduhr** via the optional [`cc-logs`](https://github.com/estevanhernandez-stack-ed/cc-logs) package, so burn numbers stay aligned across tools when it's installed.

```bash
vibe-insights                # scan + build the report
vibe-insights --render-only  # re-render without re-scanning (after the narrative is written)
vibe-insights --emit-tagging-input   # emit sessions needing per-session tags
```

Reports land in `~/.vibe-insights/reports/insights.html`.

## Validated on

Proven on a live **195-session personal index** across two machines — the Phase 2 lenses (how-you-work, ranked open-threads) were validated end-to-end against real data before shipping.

## Install

**Stable (recommended) — as a Claude Code plugin via the marketplace:**

```text
/plugin marketplace add estevanhernandez-stack-ed/vibe-plugins
/plugin install vibe-insights@vibe-plugins
```

**Canary — track this repo's `main`:**

```text
/plugin install vibe-insights@estevanhernandez-stack-ed/vibe-insights
```

**Standalone engine (Python 3.11+):**

```bash
git clone https://github.com/estevanhernandez-stack-ed/vibe-insights
cd vibe-insights
python -m pip install -e .
# Optional: share token/parse definitions with Sanduhr et al. (pulls cc-logs)
python -m pip install -e ".[shared]"

python -m vibe_insights.cli --init   # discover config homes, review labels
python -m vibe_insights.cli          # scan + build the report
```

As a plugin, the `/vibe-insights` skill orchestrates the run, synthesizes the narrative, and (optionally) pulls your decisions from a file or MCP.

## Part of the Vibe ecosystem

Part of the **[Vibe Plugins](https://github.com/estevanhernandez-stack-ed/vibe-plugins)** marketplace from [626 Labs](https://626labs.dev) — foundations and process pillars for AI-assisted creation.

```text
/plugin marketplace add estevanhernandez-stack-ed/vibe-plugins
```

## License

MIT — *Imagine Something Else.*
