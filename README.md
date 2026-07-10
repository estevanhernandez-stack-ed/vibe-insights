<p align="center"><img src="assets/brand/icon.svg" width="120" alt="vibe-insights mark"></p>

<p align="center">
  <img alt="Vibe Insights — deep retrospective for your Claude Code work" src="https://626labs.dev/assets/brand/plugins/vibe-insights-banner-1500x500.png" />
</p>

# Vibe Insights

**The deep retrospective for your Claude Code work — coverage, where-was-I recall, token/cost with the cache reveal, how you actually work, ranked open threads, and a synthesized narrative read. Across your full history and every machine you code on. No telemetry, all local.**

[![stable](https://img.shields.io/github/v/tag/estevanhernandez-stack-ed/vibe-insights?label=stable&color=17d4fa)](https://github.com/estevanhernandez-stack-ed/vibe-insights/tags)

## What it does

A deterministic Python engine reads your Claude Code session transcripts — across all your machines and full history — and produces one branded report:

- **Coverage** — sessions / repos / token burn, split by source × machine.
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
- **Personal by default.** Every `~/.claude*` directory discovered on your machine is treated as a personal source and included in your synced-eligible index. You control what stays local via the `advanced` block — no config required to get started.
- **Cross-machine via per-machine indexes.** Each machine emits a tiny `index.json` under `synced/`; sync that folder (e.g., Syncthing) and the report merges every machine. Token math can be shared with **Sanduhr** via the optional [`cc-logs`](https://github.com/estevanhernandez-stack-ed/cc-logs) package, so burn numbers stay aligned across tools when it's installed.

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

vibe-insights --init   # discover sources, review config
vibe-insights          # scan + build the report
```

As a plugin, the `/vibe-insights` skill orchestrates the run, synthesizes the narrative, and (optionally) pulls your decisions from a file or MCP.

## Privacy & multiple sources (advanced)

Out of the box, everything is personal. Every `~/.claude*` source discovered at `--init` time lands in your synced-eligible index. Nothing is sent anywhere — "sync" means you mirror the `synced/` folder yourself (Syncthing, rsync, iCloud, whatever you choose).

When you need to wall off employer sessions or an entire source directory, the `advanced` block gives you two levers:

### Mark a whole source as private

Add it to `advanced.sources` with `"private": true`:

```json
"advanced": {
  "sources": [
    { "path": "~/.claude", "private": false },
    { "path": "~/.claude-work", "private": true }
  ]
}
```

A private source is indexed in `index.private.local.json` — visible in your own local report, but never written to `synced/` and never merged cross-machine.

### Mark individual repos as private

Use `advanced.private_repos` for repos that live inside an otherwise-personal source but belong to an employer or client:

```json
"advanced": {
  "private_repos": ["owner/employer-repo", "acme-corp/backend"]
}
```

Sessions for those repos are kept in `index.private.local.json` and stay local-only.

### Privacy helpers

```bash
vibe-insights --privacy                        # list all sources + repos and their privacy status
vibe-insights --make-private owner/repo        # wall a repo
vibe-insights --make-private-source ~/.claude-work  # wall an entire source directory
```

After a scan where nothing is private yet, a non-blocking nudge prints — something like: `Privacy: all N source(s) are personal (synced-eligible). Keep any local-only? One line — add "private_repos": ["owner/repo"] to advanced in <config path>, or run \`vibe-insights --privacy\`.` It's informational — you can ignore it if you're fine with everything syncing.

### Back-compat note

Legacy configs using `homes` / `work_repos` keys are still read automatically — no migration required. The old `index.work.local.json` is still read alongside the new `index.private.local.json`. The new vocabulary (`source` / `private` / `private_repos`) is preferred in any new config you write.

## Part of the Vibe ecosystem

Part of the **[Vibe Plugins](https://github.com/estevanhernandez-stack-ed/vibe-plugins)** marketplace from [626 Labs](https://626labs.dev) — foundations and process pillars for AI-assisted creation.

```text
/plugin marketplace add estevanhernandez-stack-ed/vibe-plugins
```

## License

MIT — *Imagine Something Else.*