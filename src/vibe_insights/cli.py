"""CLI entry: `vibe-insights` runs scan then report.

Usage:
    vibe-insights --init        # discover sources, write config.json (review it!)
    vibe-insights               # scan + report using config.json
"""
import argparse
import json
import sys
from pathlib import Path

from . import analytics as analytics_mod
from . import config as config_mod
from . import decisions as decisions_mod
from . import merge as merge_mod
from . import report as report_mod
from . import scan as scan_mod
from . import story as story_mod
from . import tagging as tagging_mod

DEFAULT_CONFIG = Path.home() / ".vibe-insights" / "config.json"


def run(cfg: dict, repo_filter: str | None = None) -> dict:
    machine = cfg["machine"]
    records = scan_mod.build_records(cfg["sources"], machine=machine,
                                     private_repos=cfg.get("private_repos", []))
    counts = scan_mod.write_indexes(records, cfg["dataDir"], machine)
    merged = merge_mod.load_merged(Path(cfg["dataDir"]) / "synced")
    private_local = scan_mod.read_local_private_index(cfg["dataDir"])
    report_set = merged + private_local
    if repo_filter:
        rf = repo_filter.strip().lower()
        report_set = [s for s in report_set if (s.get("repo") or "").lower() == rf]
    tags_cache = tagging_mod.load_cache(Path(cfg["dataDir"]) / "tags.cache.json")
    tagging_mod.merge_into(report_set, tags_cache)
    digest = analytics_mod.build_digest(report_set)
    decs = decisions_mod.load_decisions(cfg.get("decisions"), cfg["dataDir"])
    digest["decisions"] = decs[:20]
    scan_mod._atomic_write_json(Path(cfg["dataDir"]) / "digest.json", digest)
    narr_path = Path(cfg["dataDir"]) / "reports" / "narrative.html"
    narrative_html = narr_path.read_text(encoding="utf-8") if narr_path.exists() else ""
    reports = report_mod.write_reports(report_set, cfg["dataDir"], digest=digest,
                                       narrative_html=narrative_html)
    return {"counts": counts, "reports": reports,
            "merged_sessions": len(report_set), "digest": str(Path(cfg["dataDir"]) / "digest.json")}


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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="vibe-insights")
    parser.add_argument("--init", action="store_true",
                        help="discover sources and write config.json for review")
    parser.add_argument("--render-only", action="store_true",
                        help="re-render reports from existing index + digest + narrative, no re-scan")
    parser.add_argument("--emit-tagging-input", action="store_true",
                        help="write tagging_input.json (untagged sessions + content samples) for the tagging pass")
    parser.add_argument("--limit", type=int, default=0,
                        help="cap sessions emitted for tagging")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--repo", default=None,
                        help="scope the report to a single repo (by name, case-insensitive)")
    parser.add_argument("--privacy", action="store_true",
                        help="show which sources/repos are personal vs private, and how to wall")
    parser.add_argument("--make-private", metavar="REPO", default=None,
                        help="mark a repo local-only (adds to advanced.private_repos)")
    parser.add_argument("--make-private-source", metavar="PATH", default=None,
                        help="mark a source local-only (sets its private flag)")
    parser.add_argument("--story-input", default=None, metavar="REPO",
                        help="emit a build-story spine (sessions+decisions+commits) for a repo")
    parser.add_argument("--repo-path", default=None,
                        help="explicit repo path for --story-input git log (else inferred from sessions)")
    args = parser.parse_args(argv)
    config_path = Path(args.config)

    if args.story_input:
        if not config_path.exists():
            print(f"No config at {config_path}.", file=sys.stderr)
            return 1
        cfg = config_mod.load_config(config_path)
        data_dir = Path(cfg["dataDir"])
        report_set = merge_mod.load_merged(data_dir / "synced") + scan_mod.read_local_private_index(data_dir)
        rf = args.story_input.strip().lower()
        scoped = [s for s in report_set if (s.get("repo") or "").lower() == rf]
        all_decs = decisions_mod.load_decisions(cfg.get("decisions"), data_dir)
        decs = [d for d in all_decs if (d.get("project_tag") or "").lower() == rf] or all_decs
        spine = story_mod.build_story_input(args.story_input, scoped, decs,
                                            repo_path=args.repo_path)
        out_path = data_dir / "story-input.md"
        out_path.write_text(spine, encoding="utf-8")
        print(f"Wrote build-story spine ({len(scoped)} sessions, {len(decs)} decisions) -> {out_path}")
        return 0

    if args.emit_tagging_input:
        if not config_path.exists():
            print(f"No config at {config_path}.", file=sys.stderr)
            return 1
        cfg = config_mod.load_config(config_path)
        data_dir = Path(cfg["dataDir"])
        report_set = merge_mod.load_merged(data_dir / "synced") + scan_mod.read_local_private_index(data_dir)
        cache = tagging_mod.load_cache(data_dir / "tags.cache.json")
        todo = tagging_mod.untagged(report_set, cache)
        if args.limit:
            todo = todo[:args.limit]
        files = scan_mod.locate_session_files([s["path"] for s in cfg["sources"]])
        out = []
        for s in todo:
            sid = s.get("session_id")
            p = files.get(sid)
            out.append({
                "session_id": sid, "repo": s.get("repo", ""), "title": s.get("title", ""),
                "machine": s.get("machine", ""), "account": s.get("account", ""),
                "last_ts": s.get("last_ts", ""),
                "sample": scan_mod.sample_session(p) if p else "",
            })
        scan_mod._atomic_write_json(data_dir / "tagging_input.json", out)
        print(f"Wrote {len(out)} sessions needing tags -> {data_dir / 'tagging_input.json'}")
        return 0

    if args.render_only:
        if not config_path.exists():
            print(f"No config at {config_path}.", file=sys.stderr)
            return 1
        cfg = config_mod.load_config(config_path)
        data_dir = Path(cfg["dataDir"])
        report_set = merge_mod.load_merged(data_dir / "synced") + scan_mod.read_local_private_index(data_dir)
        digest = None
        dpath = data_dir / "digest.json"
        if dpath.exists():
            digest = json.loads(dpath.read_text(encoding="utf-8"))
        npath = data_dir / "reports" / "narrative.html"
        narrative_html = npath.read_text(encoding="utf-8") if npath.exists() else ""
        reports = report_mod.write_reports(report_set, cfg["dataDir"], digest=digest,
                                           narrative_html=narrative_html)
        print(f"Re-rendered: {reports['html']}")
        return 0

    if args.init:
        cfg = config_mod.build_config()
        config_mod.write_config(config_path, cfg)
        print(f"Wrote {config_path}")
        print(json.dumps(cfg, indent=2))
        print("All sources are personal (synced-eligible) by default. To keep any "
              "local-only, set \"private\": true on a source or add repos to "
              "advanced.private_repos — then run `vibe-insights`.")
        return 0

    if args.make_private or args.make_private_source:
        if not config_path.exists():
            print(f"No config at {config_path}. Run `vibe-insights --init` first.", file=sys.stderr)
            return 1
        config_mod.set_private(config_path, repo=args.make_private,
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

    if not config_path.exists():
        print(f"No config at {config_path}. Run `vibe-insights --init` first, "
              f"or just run `vibe-insights` to use auto-discovered personal sources.",
              file=sys.stderr)
        return 1

    cfg = config_mod.load_config(config_path)
    result = run(cfg, repo_filter=args.repo)
    c = result["counts"]
    if args.repo:
        print(f"Scoped to repo: {args.repo}")
    print(f"Indexed {c['personal']} personal"
          + (f" + {c['private']} private (local-only)" if c.get("private") else "")
          + f" sessions on {cfg['machine']}.")
    print(f"Report covers {result['merged_sessions']} sessions across machines "
          f"(personal merged + this machine's private).")
    print(f"Report: {result['reports']['html']}")
    print(f"Markdown: {result['reports']['md']}")
    nudge = privacy_nudge(cfg)
    if nudge:
        print(nudge)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
