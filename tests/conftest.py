"""Shared test helpers: canned LLM replies and a ready-made StageContext."""

import json
from pathlib import Path

import pytest

from dba_agent.config import WorkflowSettings
from dba_agent.llm import CallLogger, LLMService, ScriptedBackend
from dba_agent.prompts import PromptLibrary
from dba_agent.schemas import Category
from dba_agent.stages.context import StageContext
from dba_agent.state import SessionStore
from dba_agent.userio import ScriptedIO

ROOT = Path(__file__).resolve().parents[1]
CATS = [c.value for c in Category]


def summary_json(name="Dental Clinic") -> str:
    return json.dumps({
        "system_name": name, "domain": "Healthcare", "purpose": "Manage patients and visits",
        "actors": [{"name": "Receptionist", "description": "Books appointments"}],
        "entities": [{"name": "Patient", "description": "A clinic patient", "example_attributes": ["name"]},
                     {"name": "Appointment", "description": "A booked visit"}],
        "processes": [{"name": "Booking", "description": "Book a visit", "actors": ["Receptionist"]}],
        "unclear_points": ["Can one appointment have several treatments?"],
    })


def initial_json(categories=CATS) -> str:
    return json.dumps({"questions": [
        {"category": c, "question": f"Question about {c}?", "why": "matters"} for c in categories]})


def followup_json(ready: bool, n_questions: int = 1) -> str:
    return json.dumps({
        "coverage": {c: "complete" if ready else "partial" for c in CATS},
        "ready": ready,
        "reason": "Enough information." if ready else "Some answers are vague.",
        "questions": [{"category": "business_rules", "question": f"Follow-up {i}?"}
                      for i in range(n_questions)],
    })


def requirements_json() -> str:
    return json.dumps({
        "overview": "A clinic system.",
        "items": [{"category": c, "text": f"Requirement for {c}.",
                   "source": "assumption" if c == "volume_growth" else "user"} for c in reversed(CATS)],
    })


@pytest.fixture
def make_ctx(tmp_path):
    def _make(llm_responses, user_answers=(), **workflow):
        backend = ScriptedBackend(llm_responses)
        ctx = StageContext(
            llm=LLMService(backend, CallLogger(None), max_retries=3),
            prompts=PromptLibrary(ROOT / "prompts"),
            io=ScriptedIO(user_answers),
            store=SessionStore(tmp_path / "output"),
            workflow=WorkflowSettings(**workflow),
        )
        return ctx, backend
    return _make


def dbms_json(chosen="postgresql", req_id="R-05") -> str:
    def sc(pg, my, lite, ms):
        return {"postgresql": pg, "mysql": my, "sqlite": lite, "sqlserver": ms}
    others = [d for d in ("postgresql", "mysql", "sqlite", "sqlserver") if d != chosen]
    return json.dumps({
        "chosen": chosen,
        "justification": f"Fits concurrent bookings ({req_id}).",
        "criteria": [
            {"name": "Concurrent writes", "weight": 5, "requirement_ids": [req_id], "scores": sc(5, 4, 1, 4)},
            {"name": "Reporting", "weight": 4, "scores": sc(5, 4, 3, 5)},
            {"name": "Cost", "weight": 3, "scores": sc(5, 5, 5, 2)},
            {"name": "Deployment", "weight": 2, "scores": sc(4, 4, 5, 2)},
        ],
        "rejected": [{"dbms": d, "reason": "Worse fit."} for d in others],
        "trade_offs": ["Needs a server."],
    })
