"""Everything a stage needs, bundled in one object so stage functions stay small."""

from __future__ import annotations

from dataclasses import dataclass

from dba_agent.config import WorkflowSettings
from dba_agent.llm.service import LLMService
from dba_agent.prompts import PromptLibrary
from dba_agent.state import Session, SessionStore
from dba_agent.userio import UserIO


@dataclass
class StageContext:
    llm: LLMService
    prompts: PromptLibrary
    io: UserIO
    store: SessionStore
    workflow: WorkflowSettings

    def save(self, session: Session) -> None:
        self.store.save(session)
