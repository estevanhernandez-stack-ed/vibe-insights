# Privacy & Sources — Advanced Guide

Everything you need to know about multi-source setups, the sync/private split, and keeping employer sessions local-only.

## The two axes

**Sync** and **private** are independent concepts.

| Axis | What it controls |
|---|---|
| **Sync** | Whether a source's index lands in `synced/` (eligible to merge across your machines if you replicate that folder yourself) |
| **Private** | Whether a source or repo is kept local-only — indexed in `index.private.local.json`, never written to `synced/`, never merged cross-machine |

"Synced" never means sent anywhere. Nothing leaves your machine unless you replicate `synced/` yourself via Syncthing, rsync, iCloud, or whatever you choose. Sync is just the label for the shareable shard.

Personal sources are synced-eligible by default. Marking something `private` pulls it out of `synced/` and into the local-only shard — it stays in your own report, it just doesn't travel.

## The `advanced` block

The core config keys (`machine`, `dataDir`, `decisions`, `voice`) cover the common case. The `advanced` block is opt-in and only needed when you have multiple sources or employer sessions to wall off.

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

### `advanced.sources`

A list of `{ "path": "...", "private": true|false }` objects. Each entry declares a source directory to scan and whether it's private.

- `"private": false` — synced-eligible. The source's index goes into `synced/` and merges cross-machine.
- `"private": true` — local-only. The source's index goes into `index.private.local.json`. Visible in your own report; never synced.

If you omit `advanced.sources` entirely, the engine auto-discovers all `~/.claude*` directories and treats them all as personal (synced-eligible).

### `advanced.private_repos`

A list of `"owner/repo"` identifiers. Sessions for these repos are kept in `index.private.local.json` regardless of which source they came from. Useful when a single `~/.claude` directory holds both personal and employer work.

```json
"advanced": {
  "private_repos": ["acme-corp/backend", "acme-corp/infra"]
}
```

You can combine both: wall the whole `~/.claude-work` source AND specific repos inside `~/.claude`:

```json
"advanced": {
  "sources": [
    { "path": "~/.claude", "private": false },
    { "path": "~/.claude-work", "private": true }
  ],
  "private_repos": ["acme-corp/backend"]
}
```

## CLI helpers

You don't need to hand-edit the JSON. Three commands handle the common cases:

```bash
# Show all discovered sources + repos with their current privacy status
vibe-insights --privacy

# Wall a specific repo
vibe-insights --make-private owner/employer-repo

# Wall an entire source directory
vibe-insights --make-private-source ~/.claude-work
```

`--make-private` and `--make-private-source` write directly to `config.json` and print a confirmation. Run `--privacy` afterward to verify the result.

After a scan where nothing is private yet, a non-blocking nudge prints — something like:

```
Privacy: all N source(s) are personal (synced-eligible). Keep any local-only? One line — add "private_repos": ["owner/repo"] to advanced in <config path>, or run `vibe-insights --privacy`.
```

It's informational — if everything you have is personal and synced is fine, you can ignore it.

## Multi-source worked example

Scenario: personal coding on `~/.claude`, employer work on `~/.claude-work`, one specific employer repo (`acme/auth-service`) inside `~/.claude`, and cross-machine sync via Syncthing.

```json
{
  "machine": "laptop-01",
  "dataDir": "~/.vibe-insights",
  "decisions": { "source": "mcp" },
  "voice": "coder",
  "advanced": {
    "sources": [
      { "path": "~/.claude", "private": false },
      { "path": "~/.claude-work", "private": true }
    ],
    "private_repos": ["acme/auth-service"]
  }
}
```

What this produces:

- `~/.claude` sessions (except `acme/auth-service`) → `synced/index.<machine>.json` → merges across all your machines
- `~/.claude-work` sessions → `index.private.local.json` → local only, visible in your report
- `acme/auth-service` sessions (from `~/.claude`) → `index.private.local.json` → local only
- Report shows all three groups, labeled; only the non-private group syncs

The second machine has its own `config.json` with `"machine": "desktop-02"` and the same `advanced` block. Syncthing replicates `synced/` in both directions. The report on either machine merges both machines' personal sessions.

## Back-compat: legacy `homes` / `work_repos`

If you have a config from before the generalization rewrite (using `homes` and `work_repos` keys), it still loads without any changes:

```json
{
  "machine": "my-machine",
  "homes": [
    { "path": "~/.claude", "account": "work", "walled": true },
    { "path": "~/.claude-personal", "account": "personal", "walled": false }
  ],
  "work_repos": ["acme/backend"]
}
```

The engine reads `homes` as `advanced.sources` (mapping `"walled": true` → `"private": true`) and `work_repos` as `advanced.private_repos`. The old `index.work.local.json` is also still read alongside the new `index.private.local.json`.

No migration is required. If you want to move to the new schema, `--init` will write a fresh config in the current format, or you can update manually using `advanced.sources` and `advanced.private_repos` as shown above.
