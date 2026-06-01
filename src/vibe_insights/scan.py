"""Walk sources, parse session logs, build SessionRecords, write indexes."""
import json
import os
import tempfile
from pathlib import Path

try:
    # Prefer the shared cc-logs package when installed, so token/parse
    # semantics stay identical with other tools (e.g. Sanduhr).
    from cc_logs import iter_raw_events, parse_iso, project_display_name, discover_under
except ImportError:
    # Standalone: vibe-insights ships its own copy of the primitives.
    from .cclogs import iter_raw_events, parse_iso, project_display_name, discover_under

from .records import SessionRecord


def locate_session_files(source_paths: list) -> dict:
    """Map session_id (top-level transcript stem) -> Path, across sources.
    Subagent transcripts (under a subagents/ dir) are excluded."""
    out: dict = {}
    for hp in source_paths:
        for f in discover_under(Path(hp)):
            if f.parent.name == "subagents":
                continue
            out.setdefault(f.stem, f)
    return out


def _text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [b["text"] for b in content
                 if isinstance(b, dict) and b.get("type") == "text" and b.get("text")]
        return " ".join(parts)
    return ""


def sample_session(path, max_field: int = 400) -> str:
    """A compact content sample for LLM tagging: first 2 user prompts, the last
    assistant text, and a tool-error count. Never raises."""
    users: list = []
    last_assistant = ""
    errors = 0
    for ev in iter_raw_events(Path(path)):
        t = ev.get("type")
        msg = ev.get("message") or {}
        if t == "user":
            txt = _text_of(msg.get("content"))
            if txt and len(users) < 2:
                users.append(txt[:max_field])
            c = msg.get("content")
            if isinstance(c, list):
                for b in c:
                    if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("is_error"):
                        errors += 1
        elif t == "assistant":
            txt = _text_of(msg.get("content"))
            if txt:
                last_assistant = txt[:max_field]
    parts = [f"USER {i+1}: {u}" for i, u in enumerate(users)]
    if last_assistant:
        parts.append(f"LAST ASSISTANT: {last_assistant}")
    parts.append(f"TOOL_ERRORS: {errors}")
    return "\n".join(parts)[:1600]


def ingest_event(records: dict, ev: dict, account: str, machine: str,
                 walled: bool, default_sid: str) -> None:
    """Fold one raw JSONL event into the records dict (keyed by session id)."""
    sid = ev.get("sessionId") or default_sid
    if not sid:
        return
    rec = records.get(sid)
    if rec is None:
        rec = SessionRecord(session_id=sid, account=account,
                            machine=machine, walled=walled)
        records[sid] = rec

    ts = parse_iso(ev.get("timestamp"))
    if ts is not None:
        if rec.first_ts is None or ts < rec.first_ts:
            rec.first_ts = ts
        if rec.last_ts is None or ts > rec.last_ts:
            rec.last_ts = ts

    cwd = ev.get("cwd")
    if cwd:
        rec.cwd = cwd
        rec.repo = project_display_name(cwd)
    if ev.get("gitBranch"):
        rec.branch = ev["gitBranch"]

    etype = ev.get("type")
    if etype == "ai-title":
        if ev.get("aiTitle"):
            rec.title = ev["aiTitle"]
    elif etype == "user":
        # response-time bucketing: measure gap from last assistant event
        user_ts_raw = ev.get("timestamp")
        if rec._last_asst_ts and user_ts_raw:
            last_asst = parse_iso(rec._last_asst_ts)
            user_ts = parse_iso(user_ts_raw)
            if last_asst is not None and user_ts is not None:
                secs = (user_ts - last_asst).total_seconds()
                if secs >= 0:
                    if secs < 60:
                        bucket = "<1m"
                    elif secs < 300:
                        bucket = "1-5m"
                    elif secs < 1800:
                        bucket = "5-30m"
                    else:
                        bucket = ">30m"
                    rec.response_buckets[bucket] = rec.response_buckets.get(bucket, 0) + 1
            rec._last_asst_ts = None
        rec.user_msgs += 1
        msg = ev.get("message") or {}
        content = msg.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result" and block.get("is_error"):
                    rec.tool_errors += 1
    elif etype == "assistant":
        rec.assistant_msgs += 1
        msg = ev.get("message") or {}
        model = msg.get("model")
        if model and model not in rec.models:
            rec.models.append(model)
        usage = msg.get("usage") or {}
        rec.tokens_input += int(usage.get("input_tokens") or 0)
        rec.tokens_output += int(usage.get("output_tokens") or 0)
        rec.tokens_cache_creation += int(usage.get("cache_creation_input_tokens") or 0)
        rec.tokens_cache_read += int(usage.get("cache_read_input_tokens") or 0)
        stu = usage.get("server_tool_use") or {}
        rec.web_search += int(stu.get("web_search_requests") or 0)
        rec.web_fetch += int(stu.get("web_fetch_requests") or 0)
        content = msg.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    name = block.get("name") or "unknown"
                    rec.tool_counts[name] = rec.tool_counts.get(name, 0) + 1
                    # Client-side web tools fold into the web fields too (the
                    # server_tool_use accounting above only sees the API's
                    # server-side web tool, which is ~0 in normal Claude Code use).
                    if name == "WebSearch":
                        rec.web_search += 1
                    elif name == "WebFetch":
                        rec.web_fetch += 1
                    if name in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
                        fp = (block.get("input") or {}).get("file_path") or (block.get("input") or {}).get("notebook_path") or ""
                        basename = fp.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
                        ext = basename.rsplit(".", 1)[-1].lower() if "." in basename else ""
                        if ext and len(ext) <= 8:
                            rec.file_exts[ext] = rec.file_exts.get(ext, 0) + 1
        rec._last_asst_ts = ev.get("timestamp")


def is_private_repo(repo: str, private_repos) -> bool:
    if not repo or not private_repos:
        return False
    r = repo.strip().lower()
    return any(r == str(w).strip().lower() for w in private_repos)


def build_records(sources: list[dict], machine: str, private_repos=()) -> dict:
    """Walk every source's logs (recursively, incl. subagent transcripts) and
    fold into records by session id. Subagent events carry the parent
    sessionId, so their burn folds into the parent automatically.

    Each source's `private` flag sets the initial wall. When private_repos is
    provided, records are then reclassified by repo name: a session whose repo
    matches a private_repos entry is private (local-only); all others personal."""
    records: dict = {}
    for src in sources:
        private = bool(src.get("private", False))
        account = "private" if private else "personal"
        for f in discover_under(Path(src["path"])):
            for ev in iter_raw_events(f):
                ingest_event(records, ev, account=account, machine=machine,
                             walled=private, default_sid=f.stem)
    if private_repos:
        for rec in records.values():
            rec.walled = is_private_repo(rec.repo, private_repos)
            rec.account = "private" if rec.walled else "personal"
    return records


def _atomic_write_json(path: Path, data) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


# Local-only index filename. Renamed from index.work.local.json in v0.3 to
# match the "private" vocabulary. read_local_private_index() dual-reads both
# so existing data keeps working. Downstream consumers reading the old name
# get fixed when/if they surface — not preemptively hunted.
PRIVATE_INDEX = "index.private.local.json"
LEGACY_PRIVATE_INDEX = "index.work.local.json"


def write_indexes(records: dict, data_dir: Path, machine: str) -> dict:
    """Personal -> <data_dir>/synced/<machine>/index.json (the only thing that
    syncs across machines). Private -> <data_dir>/index.private.local.json
    (OUTSIDE synced/, so local-only data never enters the synced folder)."""
    data_dir = Path(data_dir)
    personal = [r.to_dict() for r in records.values() if not r.walled]
    private = [r.to_dict() for r in records.values() if r.walled]
    _atomic_write_json(data_dir / "synced" / machine / "index.json",
                       {"sessions": personal})
    if private:
        _atomic_write_json(data_dir / PRIVATE_INDEX, {"sessions": private})
    return {"personal": len(personal), "private": len(private)}


def read_local_private_index(data_dir: Path) -> list[dict]:
    """Read this machine's local-only session shard. Prefers the new
    index.private.local.json; falls back to the legacy index.work.local.json.
    Never raises — missing/unreadable returns []."""
    data_dir = Path(data_dir)
    for name in (PRIVATE_INDEX, LEGACY_PRIVATE_INDEX):
        p = data_dir / name
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8")).get("sessions", [])
            except (OSError, json.JSONDecodeError):
                return []
    return []
