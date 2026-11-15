"""Session state and its persistence (spec, Technical Requirement ❶).

A Session is everything the agent knows about one design job. It is saved to
output/<session_id>/session.json after every meaningful step (even after each interview
answer), so a crash or Ctrl+C loses at most the step in progress, and `dba resume`
continues from the saved stage.
"""

from __future__ import annotations

import os
from datetime import datetime
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field

from dba_agent.schemas import DBMSChoice, InterviewState, Requirement, SystemSummary

SESSION_FILE = "session.json"
LOG_FILE = "llm_calls.jsonl"


class Stage(str, Enum):
    INTAKE = "intake"
    INTERVIEW = "interview"
    DBMS = "dbms"
    DESIGN = "design"
    REVISION = "revision"
    SQL = "sql"
    DONE = "done"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Session(BaseModel):
    id: str
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)
    stage: Stage = Stage.INTAKE
    brief: str

    # Stage 1
    summary: SystemSummary | None = None
    # Stage 2
    interview: InterviewState = Field(default_factory=InterviewState)
    requirements_overview: str = ""
    requirements: list[Requirement] = Field(default_factory=list)
    # Stage 3
    dbms_choice: DBMSChoice | None = None
    # Later stages add their fields here (with defaults, so older session files still load).


class SessionNotFound(Exception):
    pass


class SessionStore:
    """Creates, saves, loads and lists sessions under the output directory."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def dir(self, session_id: str) -> Path:
        return self.root / session_id

    def log_path(self, session_id: str) -> Path:
        return self.dir(session_id) / LOG_FILE

    def create(self, brief: str) -> Session:
        base = datetime.now().strftime("%Y%m%d-%H%M%S")
        sid, n = base, 2
        while self.dir(sid).exists():  # two sessions in the same second
            sid, n = f"{base}-{n}", n + 1
        session = Session(id=sid, brief=brief.strip())
        self.save(session)
        return session

    def save(self, session: Session) -> None:
        session.updated_at = _now()
        folder = self.dir(session.id)
        folder.mkdir(parents=True, exist_ok=True)
        # Atomic write: write a temp file, then rename over the old one.
        # If the program dies mid-write, the previous session.json is still intact.
        tmp = folder / (SESSION_FILE + ".tmp")
        tmp.write_text(session.model_dump_json(indent=2), encoding="utf-8")
        os.replace(tmp, folder / SESSION_FILE)

    def load(self, session_id: str) -> Session:
        path = self.dir(session_id) / SESSION_FILE
        if not path.exists():
            raise SessionNotFound(f"No session '{session_id}' in {self.root}")
        return Session.model_validate_json(path.read_text(encoding="utf-8"))

    def list(self) -> list[Session]:
        if not self.root.exists():
            return []
        sessions = [self.load(p.parent.name) for p in self.root.glob(f"*/{SESSION_FILE}")]
        return sorted(sessions, key=lambda s: s.id)  # IDs are timestamps, so this is chronological

    def latest_id(self) -> str | None:
        sessions = self.list()
        return sessions[-1].id if sessions else None

    def write_file(self, session: Session, name: str, content: str) -> Path:
        """Write an output document (e.g. requirements.md) into the session folder."""
        path = self.dir(session.id) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path
