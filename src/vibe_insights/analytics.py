"""Phase-2 analytics: deterministic lenses over the merged personal session set."""
from collections import Counter, defaultdict
from datetime import datetime, timezone

_FEATURE_EXCLUDE = {"main", "master", "HEAD", ""}


def _parse(ts):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None


def token_cost(sessions: list[dict]) -> dict:
    n = len(sessions)
    inp = sum(int(s.get("tokens_input") or 0) for s in sessions)
    out = sum(int(s.get("tokens_output") or 0) for s in sessions)
    cread = sum(int(s.get("tokens_cache_read") or 0) for s in sessions)
    ccreate = sum(int(s.get("tokens_cache_creation") or 0) for s in sessions)
    burn = inp + out
    input_side = inp + cread + ccreate
    repo_burn: dict = defaultdict(int)
    repo_n: Counter = Counter()
    for s in sessions:
        r = s.get("repo") or "(none)"
        repo_burn[r] += int(s.get("human_tokens") or 0)
        repo_n[r] += 1
    top = [{"repo": r, "burn": b, "sessions": repo_n[r]}
           for r, b in sorted(repo_burn.items(), key=lambda kv: -kv[1])[:10]]
    models: Counter = Counter()
    for s in sessions:
        for m in s.get("models") or []:
            models[m] += 1
    return {
        "sessions": n, "burn": burn, "input": inp, "output": out,
        "cache_read": cread, "cache_creation": ccreate,
        "cache_read_share": round(cread / input_side * 100, 1) if input_side else 0.0,
        "output_share": round(out / burn * 100, 1) if burn else 0.0,
        "top_repos_by_burn": top,
        "model_session_counts": dict(models.most_common()),
    }


def trends(sessions: list[dict]) -> dict:
    by_day: dict = defaultdict(lambda: {"sessions": 0, "burn": 0})
    for s in sessions:
        ts = _parse(s.get("last_ts"))
        if not ts:
            continue
        d = ts.astimezone().date().isoformat()
        by_day[d]["sessions"] += 1
        by_day[d]["burn"] += int(s.get("human_tokens") or 0)
    days_sorted = sorted(by_day)
    recent_days = days_sorted[-2:]
    baseline_days = days_sorted[:-2]
    recent_burn = sum(by_day[d]["burn"] for d in recent_days)
    baseline_burn = sum(by_day[d]["burn"] for d in baseline_days)
    baseline_avg = (baseline_burn / len(baseline_days)) if baseline_days else 0
    recent_avg = (recent_burn / len(recent_days)) if recent_days else 0
    multiple = round(recent_avg / baseline_avg, 1) if baseline_avg else None
    return {
        "by_day": {d: dict(by_day[d]) for d in days_sorted},
        "recent_days": recent_days,
        "recent_burn": recent_burn,
        "baseline_avg_per_day": round(baseline_avg),
        "recent_avg_per_day": round(recent_avg),
        "acceleration_multiple": multiple,
    }


def tool_mix(sessions: list[dict]) -> dict:
    counts: Counter = Counter()
    for s in sessions:
        for tool, n in (s.get("tool_counts") or {}).items():
            counts[tool] += int(n or 0)
    tools = [{"tool": t, "count": c} for t, c in counts.most_common(12)]
    return {
        "tools": tools,
        "web_search": sum(int(s.get("web_search") or 0) for s in sessions),
        "web_fetch": sum(int(s.get("web_fetch") or 0) for s in sessions),
    }


def delegation(sessions: list[dict]) -> dict:
    agent_calls = sum(int((s.get("tool_counts") or {}).get("Agent", 0) or 0)
                      for s in sessions)
    haiku_sessions = sum(
        1 for s in sessions
        if any("haiku" in str(m).lower() for m in (s.get("models") or []))
    )
    return {"agent_calls": agent_calls, "haiku_sessions": haiku_sessions}


def by_machine(sessions: list[dict]) -> list[dict]:
    agg: dict = defaultdict(lambda: {"sessions": 0, "assistant_msgs": 0,
                                     "burn": 0, "repos": set()})
    for s in sessions:
        m = s.get("machine") or ""
        row = agg[m]
        row["sessions"] += 1
        row["assistant_msgs"] += int(s.get("assistant_msgs") or 0)
        row["burn"] += int(s.get("human_tokens") or 0)
        repo = s.get("repo") or ""
        if repo:
            row["repos"].add(repo)
    out = [{"machine": m, "sessions": r["sessions"],
            "assistant_msgs": r["assistant_msgs"], "burn": r["burn"],
            "repos": len(r["repos"])}
           for m, r in agg.items()]
    out.sort(key=lambda r: -r["assistant_msgs"])
    return out


_VERY_OLD_DAYS = 10**6

_RESUME_KEYWORDS = (
    "continue", "complete", "finish", "wip", "smoke", "fix", "todo",
    "left off", "pick up",
)


def _age_days(last_ts) -> int:
    """Days since last_ts vs tz-aware now; unparseable/missing -> very old."""
    ts = _parse(last_ts)
    if ts is None:
        return _VERY_OLD_DAYS
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - ts).days


def _enrich_branch(s: dict) -> dict:
    """Per-branch record: existing fields + deterministic open-thread signals."""
    title = s.get("title", "") or ""
    age = _age_days(s.get("last_ts"))
    empty_title = not title.strip()
    lower = title.lower()
    resume_signal = any(kw in lower for kw in _RESUME_KEYWORDS)
    recency = max(0, 3 - age // 7)
    score = (3 if resume_signal else 0) + (2 if empty_title else 0) + recency
    return {
        "repo": s.get("repo", ""), "branch": s.get("branch", ""),
        "machine": s.get("machine", ""), "title": title,
        "last_ts": s.get("last_ts", ""),
        "age_days": age, "empty_title": empty_title,
        "resume_signal": resume_signal, "unfinished_score": score,
    }


def _feature_branches(sessions: list[dict]) -> list[dict]:
    """Unique (repo, branch, machine) feature branches, most-recent session wins,
    each enriched with open-thread signals."""
    feat = [s for s in sessions
            if (s.get("branch") or "") not in _FEATURE_EXCLUDE]
    feat.sort(key=lambda s: s.get("last_ts") or "", reverse=True)
    out: list[dict] = []
    seen: set = set()
    for s in feat:
        key = (s.get("repo"), s.get("branch"), s.get("machine"))
        if key in seen:
            continue
        seen.add(key)
        out.append(_enrich_branch(s))
    return out


def _is_prune(rec: dict) -> bool:
    return (rec["age_days"] >= 21
            and not rec["resume_signal"]
            and not rec["empty_title"])


def pick_back_up(sessions: list[dict], limit: int = 15) -> list[dict]:
    branches = [b for b in _feature_branches(sessions) if not _is_prune(b)]
    branches.sort(key=lambda b: (b["unfinished_score"], b["last_ts"] or ""),
                  reverse=True)
    return branches[:limit]


def prune_candidates(sessions: list[dict]) -> list[dict]:
    branches = [b for b in _feature_branches(sessions) if _is_prune(b)]
    branches.sort(key=lambda b: b["last_ts"] or "", reverse=True)
    return branches


_EXT_LANG = {
    "py": "Python", "ts": "TypeScript", "tsx": "TypeScript", "js": "JavaScript",
    "jsx": "JavaScript", "md": "Markdown", "json": "JSON", "css": "CSS",
    "html": "HTML", "cs": "C#", "swift": "Swift", "rs": "Rust", "go": "Go",
    "sh": "Shell", "ps1": "PowerShell", "yml": "YAML", "yaml": "YAML",
    "toml": "TOML", "sql": "SQL", "java": "Java", "rb": "Ruby", "cpp": "C++",
}


def languages(sessions: list[dict]) -> list[dict]:
    agg: dict = {}
    for s in sessions:
        for ext, n in (s.get("file_exts") or {}).items():
            lang = _EXT_LANG.get(ext, ext)
            agg[lang] = agg.get(lang, 0) + n
    return [{"language": k, "count": v}
            for k, v in sorted(agg.items(), key=lambda kv: -kv[1])][:12]


def tool_error_total(sessions: list[dict]) -> int:
    return sum(int(s.get("tool_errors") or 0) for s in sessions)


def parallel_sessions(sessions: list[dict]) -> dict:
    intervals = []
    for s in sessions:
        f = s.get("first_ts")
        t = s.get("last_ts")
        if f and t:
            intervals.append((f, t))
    intervals.sort()
    # sweep line over start/end events
    events = []
    for f, t in intervals:
        events.append((f, 1))
        events.append((t, -1))
    events.sort()
    cur = 0
    max_concurrent = 0
    for _, delta in events:
        cur += delta
        max_concurrent = max(max_concurrent, cur)
    # count sessions that overlap at least one other
    overlapping = 0
    for i, (f1, t1) in enumerate(intervals):
        for j, (f2, t2) in enumerate(intervals):
            if i != j and f1 < t2 and f2 < t1:
                overlapping += 1
                break
    return {"overlapping": overlapping, "max_concurrent": max_concurrent,
            "total": len(intervals)}


def tag_distributions(sessions: list[dict]) -> dict:
    fr, sat, out, st = Counter(), Counter(), Counter(), Counter()
    tagged = 0
    for s in sessions:
        t = s.get("tags")
        if not isinstance(t, dict):
            continue
        tagged += 1
        if t.get("friction"):
            fr[t["friction"]] += 1
        if t.get("satisfaction"):
            sat[t["satisfaction"]] += 1
        if t.get("outcome"):
            out[t["outcome"]] += 1
        if t.get("session_type"):
            st[t["session_type"]] += 1
    return {"tagged": tagged, "friction": dict(fr.most_common()),
            "satisfaction": dict(sat.most_common()), "outcome": dict(out.most_common()),
            "session_type": dict(st.most_common())}


_RESP_ORDER = ["<1m", "1-5m", "5-30m", ">30m"]


def response_distribution(sessions: list[dict]) -> dict:
    agg = Counter()
    for s in sessions:
        for k, v in (s.get("response_buckets") or {}).items():
            agg[k] += v
    return {k: agg[k] for k in _RESP_ORDER if agg.get(k)}


def at_a_glance(digest: dict) -> dict:
    tc = digest.get("token_cost", {})
    tr = digest.get("trends", {})
    tg = digest.get("tags", {})
    burn = tc.get("burn", 0) or 0
    top = (tc.get("top_repos_by_burn") or [{}])[0]
    top_burn = top.get("burn", 0) or 0
    friction = {k: v for k, v in (tg.get("friction") or {}).items() if k != "none"}
    dominant = max(friction, key=friction.get) if friction else None
    sat = tg.get("satisfaction") or {}
    tagged = tg.get("tagged", 0) or 0
    pos = (sat.get("satisfied", 0) + sat.get("likely_satisfied", 0))
    return {
        "top_project": top.get("repo"),
        "top_project_pct": round(top_burn / burn * 100, 1) if burn else 0.0,
        "dominant_friction": dominant,
        "positive_satisfaction_pct": round(pos / tagged * 100, 1) if tagged else 0.0,
        "acceleration": tr.get("acceleration_multiple"),
    }


def build_digest(sessions: list[dict]) -> dict:
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "token_cost": token_cost(sessions),
        "trends": trends(sessions),
        "pick_back_up": pick_back_up(sessions),
        "languages": languages(sessions),
        "tool_errors": tool_error_total(sessions),
        "parallel": parallel_sessions(sessions),
        "tags": tag_distributions(sessions),
        "response_dist": response_distribution(sessions),
    }
    result["glance"] = at_a_glance(result)
    return result
