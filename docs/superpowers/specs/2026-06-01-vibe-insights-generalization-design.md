# Vibe Insights — Generalization Design (v0.3)

**Date:** 2026-06-01
**Status:** Approved design, pending spec review → implementation plan
**Author:** Estevan Hernandez + The Architect

## Context

Vibe Insights is a shipped Claude Code session-analytics plugin (solo repo `vibe-insights`, v0.2.2, pinned in the vibe-plugins marketplace). An audit of the codebase found it is **already ~80% author-agnostic** — session parsing, cross-machine index merge, all analytics, machine-ID-by-hostname, the `~/.vibe-insights/config.json` file, repo-based walling, optional `cc-logs` fallback, and the MCP-via-skill decisions overlay are all universal. No personal identifiers live in `src/` — only branding in README badges and install URLs.

The coupling to the author's setup is **one hardcoded heuristic** in `config.py:24`:

```python
account = "work" if child.name == ".claude" else "personal"
```

This encodes the author's exact shape (`~/.claude` = walled employer seat; every other `~/.claude-*` = personal/synced). It is auto-generated on `--init` and silently regenerated on re-run, so hand-edits to the config don't durably stick.

It does not merely limit multi-employer users — **it is backwards for the common case.** A user with only `~/.claude` (the default, most people) gets *every* session classified "work" → walled local-only → the cross-machine sync value prop silently never fires.

## Goal

Generalize so the single-home majority works great with zero config, while the author's work-walled / multi-surface model survives as opt-in power. Per the agreed direction, this is a **full reframe** (identity + vocabulary + onboarding + docs), not just an engine fix — using path "A + B's config block": reposition the value prop, retire insider vocabulary, default to personal, and tuck the power features behind an opt-in `advanced` config block.

## Non-goals

- No `profiles` rename / vocabulary overhaul that forces a config migration (rejected path C).
- No change to the underlying analytics, merge, parsing, or the security-wall mechanism itself (already universal and correct).
- No telemetry, ever. The reframe must not weaken the all-local, your-data posture.
- Marketplace `marketplace.json` description rewrite is a **downstream** edit that ships when the new version is promoted — out of scope for this repo's diff (noted in Rollout).

## Decisions (all confirmed)

1. **Default behavior:** everything personal (synced-eligible) by default; walling is opt-in.
2. **Opt-in walling:** keep BOTH mechanisms — whole-source walling and repo-level walling — but nothing walls unless explicitly declared.
3. **Scope:** full reframe (path A + B's config block).
4. **Naming approved:** `home → source`, `account → dropped`, `work-walled/walled → private (local-only)`, `work_repos → private_repos`, `surface → folded into source`, `synced` kept.
5. **Privacy must be discoverable + easy** (load-bearing constraint): a user who never considered local-only walling gets one apparent, zero-friction beat to opt in; the opt-in itself is a single obvious action; it never blocks the default flow.
6. **On-disk rename:** `index.work.local.json → index.private.local.json`; read both; leave a code comment noting the back-compat + that downstream consumers get fixed when they surface.
7. **Privacy helper command** (`vibe-insights privacy`): in scope for this version (not a fast-follow).

## The reframe (identity + vocabulary)

**New value prop** (leads README / SKILL / eventually marketplace):

> The deep retrospective for your Claude Code work — coverage, where-was-I recall, token/cost with the cache reveal, how you actually work, ranked open threads, and a synthesized narrative read. Across your full history and every machine you code on. No telemetry, all local. Optionally keep chosen repos or machines local-only.

**Vocabulary mapping:**

| Today (insider) | Reframed | Why |
|---|---|---|
| `home` (`.claude*` dir) | **source** | "Where your sessions live." Nobody has "homes." |
| `account` (work/personal) | *(dropped)* | Replaced by one privacy flag. |
| `work-walled` / `walled` | **private** (local-only) | It's "don't let this leave the machine," not always "work." |
| `work_repos` | **private_repos** | Honest name; old key still read. |
| `surface` / `multi-surface` | folded into **source** | One concept, not three. |
| `synced` | **synced** (kept) | Already clear. |

**Two axes, stated plainly:**
- **Sync** — personal sessions land in a synced-eligible index so they merge across *your* machines if you sync the folder yourself. Nothing is sent anywhere.
- **Private** — a source or repo marked private is kept local-only, never written to the synced index. Opt-in exclusion.

Default: **every source is personal (synced-eligible) unless marked private.**

## Default behavior change

- **Delete** the hardcoded `account = "work" if child.name == ".claude"` line (`config.py:24`). This is the entire author-coupling.
- **No `advanced` block in config** → discover every `.claude*` source, mark all personal/synced-eligible. Zero-config; fixes the single-home majority.
- **`advanced.sources` present** → it is authoritative and **sticky**: discovery never overwrites user edits. (Today `--init` clobbers them; that bug is fixed — discovery only populates `advanced.sources` when absent or when explicitly re-run with a `--rediscover` flag.)
- The wall-enforcement split is unchanged: private → `index.private.local.json` (outside `synced/`), personal → `synced/<machine>/index.json`.

## Config schema

Flat core (everyone) + opt-in `advanced` block (omitted for simple users):

```jsonc
{
  // core — present for everyone, all sensible defaults
  "machine": "laptop-01",        // optional; defaults to the system hostname
  "dataDir": "~/.vibe-insights",
  "decisions": { "source": "none" },
  "voice": null,

  // advanced — omit entirely and everything Just Works
  "advanced": {
    "sources": [
      { "path": "~/.claude",      "private": false },
      { "path": "~/.claude-work", "private": true  }   // one-line opt-in
    ],
    "private_repos": ["owner/repo-a"]                    // refine within a personal source
  }
}
```

- Flipping `"private": true` on a source, or adding a repo to `private_repos`, is the entire walling action (satisfies "easy").
- `private_repos` walls matching sessions to local-only regardless of source. **Matching semantics are unchanged from today's `work_repos`** — case-insensitive match against the repo identifier the engine already records per session (`scan.py` `is_work_repo`). The `owner/repo` form in the examples is illustrative; the implementation matches whatever string the engine stores, so behavior is identical to the current `work_repos` for users migrating.

## Back-compat & migration

- The loader transparently reads the **old schema**: top-level `homes` (with `account`/`walled`) and top-level `work_repos`. Map `walled → private`, `work_repos → private_repos`, drop `account`. The author's current config and every existing v0.2.2 install keep working untouched.
- On the next config write, *optionally* emit the new shape (one-time silent upgrade with an explanatory comment). No forced migration.

## On-disk file rename

- Write the local-only index as **`index.private.local.json`**.
- On load, read **both** `index.private.local.json` and the legacy `index.work.local.json`.
- Leave a code comment at the read/write sites noting the rename, the back-compat dual-read, and that downstream consumers (sibling tools reading the old filename) are fixed when/if they surface — not preemptively hunted.

## Onboarding & the privacy nudge

1. **Zero-config works.** `/vibe-insights` with no config discovers sources, treats all personal, prints the report. No setup gate.
2. **The "take a second" beat** — a non-blocking privacy nudge, shown proactively (first-run output + a standing report-header line) so even a user who never considered walling sees it once:
   > *N sources, M repos — all personal (synced-eligible). Keep any local-only? One line: add `"private_repos": ["owner/repo"]` to `~/.vibe-insights/config.json` — or run `vibe-insights privacy`.*
   
   Louder when multiple sources are detected (the power case); a quiet one-liner for single-source users; always present at least once. Never blocks report generation.
3. **`vibe-insights privacy` helper command** (in scope): lists detected sources + repos and lets the user mark any private with a single interaction. Supports both an interactive list and flag forms (e.g. `vibe-insights privacy --repo owner/repo`, `vibe-insights privacy --source ~/.claude-work`). Writes the `advanced` block (sticky). This is the "maximally easy" path for users who took the second.

## Docs reframe

- **README** — lead with the universal value prop; "work-walled" leaves the headline; a separate **"Privacy & multiple sources (advanced)"** section holds the power features, with the author's setup as the worked example.
- **SKILL.md** — first-run path never mentions walling; new vocabulary throughout; emits the privacy nudge.
- **`docs/privacy-and-sources.md`** — dedicated advanced doc (the B-block home).
- **CLAUDE.md / AGENTS.md** (plugin-local) — update any old vocabulary if present.

## Testing

| Test | Proves |
|---|---|
| Single `~/.claude`, no config | Everything personal/synced, report generates, nothing walled — the headline fix |
| Legacy config (`homes`/`account`/`walled`, `work_repos`) | Reads transparently, same classification — existing setups unbroken |
| New `advanced.sources` w/ `private:true` + `private_repos` | Walls correctly |
| Re-run discovery / `--init` | Does not clobber `advanced.sources` edits — sticky config |
| File rename | Writes `index.private.local.json`, reads both old + new |
| Privacy nudge | Appears once on first-run / report, non-blocking |
| `vibe-insights privacy` | Lists sources/repos; flag + interactive forms write the `advanced` block correctly |

## Rollout / downstream follow-ups

- Ship as a **minor version** (v0.3.0) on the `vibe-insights` solo repo.
- After tagging, promote in `vibe-plugins/marketplace.json` (ref bump) — separate, deliberate step per the marketplace promotion flow.
- Rewrite the `marketplace.json` plugin **description** to the new value prop at promotion time (downstream; not in this repo's diff).
- Update the README badges/install URLs unchanged (branding is fine as-is).

## Open questions

None outstanding — all design decisions confirmed during brainstorming.
