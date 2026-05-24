"""Assemble a project's build-story spine (sessions + decisions + commits) for the
publishing pipeline. Deterministic; git log via subprocess (local, read-only)."""
import subprocess
from collections import Counter


def infer_repo_path(sessions: list[dict]) -> str | None:
    cwds = Counter(s.get("cwd") for s in sessions if s.get("cwd"))
    return cwds.most_common(1)[0][0] if cwds else None


def _git_log(repo_path: str) -> list[str]:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_path), "log", "--reverse",
             "--format=%ad %s", "--date=format:%Y-%m-%d %H:%M"],
            capture_output=True, text=True, timeout=15)
        if out.returncode == 0:
            return [ln for ln in out.stdout.splitlines() if ln.strip()]
    except (OSError, subprocess.SubprocessError):
        pass
    return []


def build_story_input(repo: str, sessions: list[dict], decisions: list[dict],
                      repo_path: str | None = None) -> str:
    repo_path = repo_path or infer_repo_path(sessions)
    lines = [f"# Build story spine: {repo}", "",
             f"- Sessions: {len(sessions)}",
             f"- Decisions: {len(decisions)}",
             f"- Repo path: {repo_path or '(unknown)'}",
             "", "## Session timeline", ""]
    for s in sorted(sessions, key=lambda s: s.get("last_ts") or ""):
        ts = (s.get("last_ts") or "")[:16].replace("T", " ")
        lines.append(f"- {ts} [{s.get('machine', '')}] {s.get('title', '')}")
    lines += ["", "## Decisions", ""]
    for d in sorted(decisions, key=lambda d: d.get("timestamp") or ""):
        lines.append(f"- {(d.get('timestamp') or '')[:10]} {d.get('title', '')}")
    lines += ["", "## Commits", ""]
    for c in (_git_log(repo_path) if repo_path else []):
        lines.append(f"- {c}")
    return "\n".join(lines) + "\n"
