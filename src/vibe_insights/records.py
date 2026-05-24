"""The per-session record produced by the scan and consumed by reports."""
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class SessionRecord:
    session_id: str
    account: str            # "work" | "personal"
    machine: str
    walled: bool
    repo: str = ""
    cwd: str = ""
    branch: str = ""
    title: str = ""
    first_ts: Optional[datetime] = None
    last_ts: Optional[datetime] = None
    user_msgs: int = 0
    assistant_msgs: int = 0
    tool_counts: Dict[str, int] = field(default_factory=dict)
    tokens_input: int = 0
    tokens_output: int = 0
    tokens_cache_creation: int = 0
    tokens_cache_read: int = 0
    models: List[str] = field(default_factory=list)
    web_search: int = 0
    web_fetch: int = 0
    file_exts: Dict[str, int] = field(default_factory=dict)
    tool_errors: int = 0
    response_buckets: Dict[str, int] = field(default_factory=dict)
    _last_asst_ts: Optional[str] = None

    @property
    def human_tokens(self) -> int:
        """Burn that counts: input + output. Matches cc_logs.human_tokens."""
        return self.tokens_input + self.tokens_output

    def to_dict(self) -> dict:
        d = asdict(self)
        d["first_ts"] = self.first_ts.isoformat() if self.first_ts else None
        d["last_ts"] = self.last_ts.isoformat() if self.last_ts else None
        d["human_tokens"] = self.human_tokens
        d.pop("_last_asst_ts", None)
        return d
