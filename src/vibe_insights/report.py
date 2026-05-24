"""Phase-1 lenses: coverage + where-was-i, rendered to Markdown and HTML."""
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


def _md_cell(value) -> str:
    """Sanitize a value for a Markdown table cell. Pipes and newlines (which
    can appear in AI-generated titles or odd branch names) break table rows."""
    return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def _md_token_cost(tc: dict) -> list[str]:
    out = ["", "## Token & cost", "",
           f"- Burn (input+output): {tc['burn']:,}  ({tc['output_share']}% output)",
           f"- Cache: read {tc['cache_read']:,} / creation {tc['cache_creation']:,}  "
           f"({tc['cache_read_share']}% of input-side served from cache)",
           "", "Top repos by burn:", "",
           "| Repo | Sessions | Burn |", "|---|---|---|"]
    for r in tc["top_repos_by_burn"]:
        out.append(f"| {_md_cell(r['repo'])} | {r['sessions']} | {r['burn']:,} |")
    if tc.get("model_session_counts"):
        models = ", ".join(f"{m} ({n})" for m, n in tc["model_session_counts"].items())
        out += ["", f"Models: {_md_cell(models)}"]
    return out


def _md_trends(tr: dict) -> list[str]:
    mult = tr.get("acceleration_multiple")
    accel = f" (~{mult}x baseline)" if mult else ""
    out = ["", "## Trends", "",
           f"- Recent avg {tr['recent_avg_per_day']:,}/day vs baseline "
           f"{tr['baseline_avg_per_day']:,}/day{accel}",
           "", "| Day | Sessions | Burn |", "|---|---|---|"]
    for d, v in list(tr["by_day"].items())[-14:]:
        out.append(f"| {d} | {v['sessions']} | {v['burn']:,} |")
    return out


def _md_pick_back_up(pb: list) -> list[str]:
    out = ["", "## Pick this back up", "",
           "| Repo | Branch | Title | Last activity | Machine |",
           "|---|---|---|---|---|"]
    if not pb:
        out.append("| _nothing on a feature branch_ |  |  |  |  |")
    for s in pb:
        out.append(f"| {_md_cell(s['repo'])} | {_md_cell(s['branch'])} "
                   f"| {_md_cell(s['title'])} | {_md_cell(s['last_ts'])} | {_md_cell(s['machine'])} |")
    return out


def _md_languages(langs: list, tool_errors: int, parallel: dict) -> list[str]:
    out = ["", "## Languages", "", "| Language | Edits |", "|---|---|"]
    for d in langs:
        out.append(f"| {_md_cell(d['language'])} | {d['count']} |")
    out += ["", f"- Tool errors encountered: {tool_errors}",
            f"- Parallel sessions (multi-clauding): {parallel.get('overlapping', 0)} "
            f"overlapping, up to {parallel.get('max_concurrent', 0)} at once"]
    return out


def _md_tags(tags: dict) -> list[str]:
    out = ["", "## How it went", "", f"_Tagged {tags.get('tagged', 0)} sessions._", ""]
    for label, key in (("Outcomes", "outcome"), ("Satisfaction", "satisfaction"),
                       ("Friction types", "friction"), ("Session types", "session_type")):
        dist = tags.get(key) or {}
        if not dist:
            continue
        out += [f"**{label}**", "", "| Value | Count |", "|---|---|"]
        for k, v in dist.items():
            out.append(f"| {_md_cell(k)} | {v} |")
        out.append("")
    return out


def _md_glance(glance: dict, pick_back_up: list) -> list[str]:
    accel = glance.get("acceleration")
    accel_txt = f"{accel}x baseline" if accel is not None else "N/A"
    lines = [
        "", "## At a glance", "",
        f"- Top project: **{glance.get('top_project', '—')}** ({glance.get('top_project_pct', 0)}% of burn)",
        f"- Dominant friction: **{glance.get('dominant_friction') or '—'}**",
        f"- Satisfaction: **{glance.get('positive_satisfaction_pct', 0)}% positive**",
        f"- Acceleration: **{accel_txt}**",
        "", "## Next moves", "",
    ]
    prompts = []
    for s in (pick_back_up or [])[:2]:
        prompts.append(f"Resume {s['repo']} @ {s['branch']}: {s['title']}")
    if glance.get("dominant_friction") == "env_tooling":
        prompts.append(
            "Add a 'Shell & Git Conventions' block to my CLAUDE.md — when to use PowerShell vs git-bash, "
            "prefer Edit over heredocs, branch before committing."
        )
    for p in prompts:
        lines += [f"```", p, "```", ""]
    return lines


def _md_response(dist: dict) -> list[str]:
    out = ["", "## Response time", "",
           "| Bucket | Count |", "|---|---|"]
    for k, v in dist.items():
        out.append(f"| {_md_cell(k)} | {v} |")
    return out


def _md_decisions(decs: list) -> list[str]:
    out = ["", "## Decisions", "",
           "| When | Decision | Project | Link |", "|---|---|---|---|"]
    if not decs:
        out.append("| _no decisions source configured_ |  |  |  |")
    for d in decs:
        when = (d.get("timestamp") or "")[:10]
        out.append(f"| {when} | {_md_cell(d.get('title',''))} "
                   f"| {_md_cell(d.get('project_tag') or '')} | {_md_cell(d.get('link') or '')} |")
    return out


def _html_table(headers: list, rows: list) -> str:
    import html
    head = "".join(f"<th>{html.escape(str(h))}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{html.escape(str(c))}</td>" for c in row) + "</tr>"
                   for row in rows)
    return f"<table border=1><tr>{head}</tr>{body}</table>"


def coverage(sessions: list[dict]) -> list[dict]:
    """Group sessions by (account, machine): counts, distinct repos, burn."""
    agg = defaultdict(lambda: {"sessions": 0, "repos": set(), "human_tokens": 0})
    for s in sessions:
        key = (s.get("account", "?"), s.get("machine", "?"))
        agg[key]["sessions"] += 1
        if s.get("repo"):
            agg[key]["repos"].add(s["repo"])
        agg[key]["human_tokens"] += int(s.get("human_tokens") or 0)
    rows = []
    for (account, machine), v in sorted(agg.items()):
        rows.append({"account": account, "machine": machine,
                     "sessions": v["sessions"], "repos": len(v["repos"]),
                     "human_tokens": v["human_tokens"]})
    return rows


def _last_ts_key(s: dict):
    raw = s.get("last_ts")
    if not raw:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def where_was_i(sessions: list[dict], limit: int = 15) -> list[dict]:
    """Most-recently-touched sessions first — the recall view."""
    return sorted(sessions, key=_last_ts_key, reverse=True)[:limit]


def render_markdown(sessions: list[dict], digest: dict | None = None, limit: int = 15) -> str:
    lines = ["# vibe-insights", "", "## Coverage", "",
             "| Account | Machine | Sessions | Repos | Burn (in+out) |",
             "|---|---|---|---|---|"]
    for r in coverage(sessions):
        lines.append(f"| {_md_cell(r['account'])} | {_md_cell(r['machine'])} "
                     f"| {r['sessions']} | {r['repos']} | {r['human_tokens']:,} |")
    lines += ["", "## Where was I", "",
              "| Repo | Branch | Title | Last activity | Machine |",
              "|---|---|---|---|---|"]
    for s in where_was_i(sessions, limit):
        lines.append(f"| {_md_cell(s.get('repo',''))} | {_md_cell(s.get('branch',''))} "
                     f"| {_md_cell(s.get('title',''))} | {_md_cell(s.get('last_ts',''))} "
                     f"| {_md_cell(s.get('machine',''))} |")
    if digest:
        if "glance" in digest:
            lines += _md_glance(digest["glance"], digest.get("pick_back_up", []))
        lines += _md_token_cost(digest["token_cost"])
        lines += _md_trends(digest["trends"])
        lines += _md_pick_back_up(digest["pick_back_up"])
        if "decisions" in digest:
            lines += _md_decisions(digest["decisions"])
        if "languages" in digest:
            lines += _md_languages(digest["languages"], digest.get("tool_errors", 0), digest.get("parallel", {}))
        if digest.get("tags", {}).get("tagged"):
            lines += _md_tags(digest["tags"])
        if digest.get("response_dist"):
            lines += _md_response(digest["response_dist"])
    return "\n".join(lines) + "\n"


_CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=JetBrains+Mono:wght@500;600&family=Inter:wght@400;500;600&display=swap');
:root{--navy:#0f1f31;--navy1:#192e44;--navy2:#223a54;--cyan:#17d4fa;--mag:#f22f89;--fg:#fff;--fg2:#c4cdda;--fg3:#8e9bad;--bd:rgba(255,255,255,.10);--grad:linear-gradient(135deg,#17d4fa,#f22f89);}
*{box-sizing:border-box}
body{margin:0;background:var(--navy);color:var(--fg);font-family:'Inter',system-ui,sans-serif;font-size:15px;line-height:1.5;-webkit-font-smoothing:antialiased;background-image:radial-gradient(60% 50% at 18% 0%,rgba(23,212,250,.10),transparent 60%),radial-gradient(50% 50% at 92% 8%,rgba(242,47,137,.10),transparent 60%);background-attachment:fixed}
.wrap{max-width:980px;margin:0 auto;padding:48px 24px 72px}
.hero{margin-bottom:28px}
.mark{font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:clamp(34px,5vw,52px);letter-spacing:-.03em;background:var(--grad);-webkit-background-clip:text;background-clip:text;color:transparent}
.mark span{-webkit-text-fill-color:var(--fg3);color:var(--fg3)}
.meta{font-family:'JetBrains Mono',monospace;font-size:12px;text-transform:uppercase;letter-spacing:.12em;color:var(--fg3);margin-top:10px}
.card{background:var(--navy1);border:1px solid var(--bd);border-radius:14px;padding:24px;margin:18px 0;box-shadow:inset 0 0 0 1px rgba(255,255,255,.03)}
.kick{font-family:'JetBrains Mono',monospace;font-size:11px;text-transform:uppercase;letter-spacing:.14em;color:var(--cyan);margin-bottom:16px}
h3{font-family:'Space Grotesk',sans-serif;font-size:18px;font-weight:600;margin:22px 0 10px;color:var(--fg)}
.lead{color:var(--fg2);font-size:16px;margin:0 0 18px}
.lead b{color:var(--fg);font-family:'JetBrains Mono',monospace}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px}
.tile{background:var(--navy2);border:1px solid var(--bd);border-radius:10px;padding:16px}
.tl{font-family:'JetBrains Mono',monospace;font-size:10px;text-transform:uppercase;letter-spacing:.12em;color:var(--fg3)}
.tn{font-family:'Space Grotesk',sans-serif;font-size:30px;font-weight:700;letter-spacing:-.02em;margin:8px 0 3px}
.ts{font-size:12px;color:var(--fg3)}
table{width:100%;border-collapse:collapse;font-size:14px}
th{font-family:'JetBrains Mono',monospace;font-size:10px;text-transform:uppercase;letter-spacing:.1em;color:var(--fg3);text-align:left;padding:9px 10px;border-bottom:1px solid var(--bd)}
td{padding:10px;border-bottom:1px solid rgba(255,255,255,.05);color:var(--fg2);vertical-align:top}
td.mono{font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--fg3);white-space:nowrap}
tbody tr:hover{background:rgba(23,212,250,.05)}
.bars{display:flex;align-items:flex-end;gap:6px;height:96px;padding:14px 0 4px}
.bar{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;gap:8px}
.bar span{width:100%;max-width:24px;background:var(--grad);border-radius:3px 3px 0 0;display:block}
.bar em{font-family:'JetBrains Mono',monospace;font-size:9px;color:var(--fg3);font-style:normal}
.foot{font-family:'JetBrains Mono',monospace;font-size:11px;text-transform:uppercase;letter-spacing:.16em;color:var(--fg3);text-align:center;margin-top:44px}
.bar-row{display:grid;grid-template-columns:140px 1fr 44px;align-items:center;gap:10px;margin:5px 0}
.bar-label{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--fg3);text-transform:uppercase;letter-spacing:.04em}
.bar-track{background:var(--navy2);border-radius:999px;height:10px;overflow:hidden}
.bar-fill{height:100%;background:var(--grad);border-radius:999px}
.bar-value{font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--fg2);text-align:right}
.prompt{background:var(--navy2);border:1px solid var(--bd);border-radius:8px;padding:12px 14px;margin:8px 0;font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--fg2);white-space:pre-wrap;line-height:1.5}
.narrative h2{font-family:'Space Grotesk',sans-serif;font-size:22px;font-weight:600;letter-spacing:-.01em;margin:0 0 14px;background:var(--grad);-webkit-background-clip:text;background-clip:text;color:transparent}
.narrative h3{font-size:16px;margin:20px 0 8px}
.narrative p{color:var(--fg2);font-size:16px;line-height:1.65;margin:0 0 14px}
.narrative b,.narrative strong{color:var(--fg)}
.narrative ol,.narrative ul{color:var(--fg2);line-height:1.6;padding-left:20px}
.narrative li{margin:6px 0}
.narrative code{font-family:'JetBrains Mono',monospace;font-size:13px;background:rgba(23,212,250,.10);color:#5ce6ff;padding:1px 5px;border-radius:4px}
.tile.work{border-color:rgba(242,47,137,.40)}
.tile.work .tl{color:var(--mag)}
.tile.work .tn{color:var(--fg)}
</style>"""


def render_html(sessions: list[dict], digest: dict | None = None, narrative_html: str = "", limit: int = 15) -> str:
    import html as _h

    def esc(v):
        return _h.escape(str(v))

    def tbl(headers, rows, mono=()):
        head = "".join(f"<th>{esc(h)}</th>" for h in headers)
        body = ""
        for row in rows:
            cells = "".join(
                f"<td class='mono'>{esc(c)}</td>" if i in mono else f"<td>{esc(c)}</td>"
                for i, c in enumerate(row))
            body += f"<tr>{cells}</tr>"
        return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"

    cov = coverage(sessions)
    machines = len({r["machine"] for r in cov})
    total = sum(r["sessions"] for r in cov)
    cov_tiles = "".join(
        f"<div class='tile{' work' if r['account'] == 'work' else ''}'>"
        f"<div class='tl'>{esc(r['machine'])} &middot; {esc(r['account'])}</div>"
        f"<div class='tn'>{r['sessions']}</div>"
        f"<div class='ts'>{r['repos']} repos &middot; {r['human_tokens']:,} burn</div></div>"
        for r in cov)
    recall_rows = [[s.get("repo", ""), s.get("branch", ""), s.get("title", ""),
                    (s.get("last_ts", "") or "")[:16].replace("T", " "), s.get("machine", "")]
                   for s in where_was_i(sessions, limit)]

    extra = ""
    if digest:
        tc = digest["token_cost"]
        tr = digest["trends"]
        pb = digest["pick_back_up"]

        # --- At-a-glance card (first) ---
        glance = digest.get("glance")
        if glance:
            accel = glance.get("acceleration")
            accel_txt = f"{accel}&times; baseline" if accel is not None else "N/A"
            glance_tiles = (
                f"<div class='tile'><div class='tl'>Top project</div>"
                f"<div class='tn'>{esc(glance.get('top_project') or '—')}</div>"
                f"<div class='ts'>{esc(str(glance.get('top_project_pct', 0)))}% of burn</div></div>"
                f"<div class='tile'><div class='tl'>Dominant friction</div>"
                f"<div class='tn' style='font-size:18px'>{esc(glance.get('dominant_friction') or '—')}</div></div>"
                f"<div class='tile'><div class='tl'>Satisfaction</div>"
                f"<div class='tn'>{esc(str(glance.get('positive_satisfaction_pct', 0)))}%</div>"
                f"<div class='ts'>positive</div></div>"
                f"<div class='tile'><div class='tl'>Acceleration</div>"
                f"<div class='tn' style='font-size:20px'>{accel_txt}</div></div>"
            )
            # Next-moves prompts
            prompts = []
            for s in pb[:2]:
                prompts.append(f"Resume {s['repo']} @ {s['branch']}: {s['title']}")
            if glance.get("dominant_friction") == "env_tooling":
                prompts.append(
                    "Add a 'Shell & Git Conventions' block to my CLAUDE.md — when to use PowerShell vs git-bash, "
                    "prefer Edit over heredocs, branch before committing."
                )
            prompts_html = "".join(f"<pre class='prompt'>{esc(p)}</pre>" for p in prompts)
            extra += (
                "<section class='card'><div class='kick'>At a glance</div>"
                f"<div class='tiles'>{glance_tiles}</div></section>"
                "<section class='card'><div class='kick'>Next moves</div>"
                f"{prompts_html}</section>"
            )

        stat = (
            f"<div class='tile'><div class='tl'>Burn (in+out)</div><div class='tn'>{tc['burn']:,}</div><div class='ts'>{tc['output_share']}% output</div></div>"
            f"<div class='tile'><div class='tl'>Cache reads</div><div class='tn'>{tc['cache_read']:,}</div><div class='ts'>{tc['cache_read_share']}% of input-side</div></div>"
            f"<div class='tile'><div class='tl'>Fresh input</div><div class='tn'>{tc['input']:,}</div><div class='ts'>the non-cached part</div></div>"
        )
        repo_rows = [[r["repo"], r["sessions"], f"{r['burn']:,}"] for r in tc["top_repos_by_burn"]]
        days = list(tr["by_day"].items())[-14:]
        maxb = max((v["burn"] for _, v in days), default=1) or 1
        bars = "".join(
            f"<div class='bar' title='{esc(d)}: {v['sessions']} sess, {v['burn']:,} burn'>"
            f"<span style='height:{max(3, round(v['burn'] / maxb * 64))}px'></span>"
            f"<em>{esc(d[5:])}</em></div>"
            for d, v in days)
        accel = tr.get("acceleration_multiple")
        accel_txt = f" &middot; recent days run ~{accel}&times; your average day" if accel else ""
        pb_rows = [[s["repo"], s["branch"], s["title"], (s["last_ts"] or "")[:10], s["machine"]] for s in pb]
        extra += (
            "<section class='card'><div class='kick'>Token &amp; cost</div>"
            f"<div class='tiles'>{stat}</div>"
            "<h3>Top repos by burn</h3>" + tbl(["Repo", "Sessions", "Burn"], repo_rows, {2}) + "</section>"
            "<section class='card'><div class='kick'>Trends</div>"
            f"<p class='lead'>Recent avg <b>{tr['recent_avg_per_day']:,}</b>/day vs baseline "
            f"<b>{tr['baseline_avg_per_day']:,}</b>/day{accel_txt}.</p>"
            f"<div class='bars'>{bars}</div></section>"
            "<section class='card'><div class='kick'>Pick this back up</div>"
            + tbl(["Repo", "Branch", "Title", "Last activity", "Machine"], pb_rows, {3}) + "</section>"
        )
        dec_html = ""
        if "decisions" in digest:
            dec_rows = [[(d.get("timestamp") or "")[:10], d.get("title", ""),
                         d.get("project_tag") or "", d.get("link") or ""]
                        for d in digest.get("decisions", [])]
            dec_html = (
                "<section class='card'><div class='kick'>Decisions</div>"
                + tbl(["When", "Decision", "Project", "Link"], dec_rows, {0})
                + "</section>"
            )
        extra += dec_html

        if "languages" in digest:
            lang_rows = [[d["language"], d["count"]] for d in digest.get("languages", [])]
            extra += (
                "<section class='card'><div class='kick'>Languages &amp; signals</div>"
                + _html_table(["Language", "Edits"], lang_rows)
                + f"<div class='tiles' style='margin-top:16px'>"
                  f"<div class='tile'><div class='tl'>Tool errors</div><div class='tn'>{digest.get('tool_errors', 0)}</div><div class='ts'>across all sessions</div></div>"
                  f"<div class='tile'><div class='tl'>Multi-clauding</div><div class='tn'>{digest.get('parallel', {}).get('max_concurrent', 0)}</div><div class='ts'>max parallel sessions</div></div>"
                  f"</div></section>"
            )

        def _bars(dist):
            if not dist:
                return "<p class='ts'>—</p>"
            mx = max(dist.values()) or 1
            rows = "".join(
                f"<div class='bar-row'><div class='bar-label'>{esc(k)}</div>"
                f"<div class='bar-track'><div class='bar-fill' style='width:{v/mx*100:.0f}%'></div></div>"
                f"<div class='bar-value'>{v}</div></div>"
                for k, v in dist.items())
            return rows

        tags = digest.get("tags", {})
        if tags.get("tagged"):
            extra += ("<section class='card'><div class='kick'>How it went</div>"
                      f"<p class='ts'>Tagged {tags['tagged']} sessions.</p>"
                      "<h3>Outcomes</h3>" + _bars(tags.get("outcome", {}))
                      + "<h3>Satisfaction</h3>" + _bars(tags.get("satisfaction", {}))
                      + "<h3>Friction types</h3>" + _bars(tags.get("friction", {}))
                      + "<h3>Session types</h3>" + _bars(tags.get("session_type", {}))
                      + "</section>")

        if digest.get("response_dist"):
            extra += ("<section class='card'><div class='kick'>Response time</div>"
                      "<p class='ts'>How fast you reply after the assistant finishes.</p>"
                      + _bars(digest["response_dist"])
                      + "</section>")

    narr = f"<section class='card narrative'>{narrative_html}</section>" if narrative_html else ""

    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>vibe-insights</title>" + _CSS + "</head><body><div class='wrap'>"
        "<header class='hero'><div class='mark'>vibe<span>&middot;</span>insights</div>"
        f"<div class='meta'>{total} personal sessions &middot; {machines} machine(s) &middot; work walled</div></header>"
        + narr
        + "<section class='card'><div class='kick'>Coverage</div>"
        f"<div class='tiles'>{cov_tiles}</div></section>"
        "<section class='card'><div class='kick'>Where was I</div>"
        + tbl(["Repo", "Branch", "Title", "Last activity", "Machine"], recall_rows, {3}) + "</section>"
        + extra
        + (
            f"<footer class='foot'>{total} sessions &middot; "
            f"{digest['token_cost']['burn']:,} tokens &middot; "
            f"{esc(digest['glance']['top_project'] or '—')} ate "
            f"{esc(str(digest['glance']['top_project_pct']))}% of it. Imagine Something Else.</footer>"
            if digest and digest.get("glance")
            else "<footer class='foot'>Imagine Something Else.</footer>"
        )
        + "</div></body></html>"
    )


def write_reports(sessions: list[dict], data_dir: Path, digest: dict | None = None, narrative_html: str = "", limit: int = 15) -> dict:
    reports = Path(data_dir) / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    md_path = reports / "insights.md"
    html_path = reports / "insights.html"
    md_path.write_text(render_markdown(sessions, digest, limit), encoding="utf-8")
    html_path.write_text(render_html(sessions, digest, narrative_html, limit), encoding="utf-8")
    return {"md": str(md_path), "html": str(html_path)}
