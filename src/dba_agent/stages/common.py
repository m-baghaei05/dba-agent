"""Helpers shared by several stages."""

from __future__ import annotations

import re
from typing import Iterable

from dba_agent.llm.structured import OutputError
from dba_agent.schemas import Requirement

_REQ_ID = re.compile(r"R-\d{2,}")


def format_requirements(reqs: list[Requirement]) -> str:
    """Requirements as compact prompt text: one line each, with ID, category and source."""
    return "\n".join(f"{r.id} [{r.category.value}] ({r.source}) {r.text}" for r in reqs) or "(none)"


def check_requirement_ids(used: Iterable[str], reqs: list[Requirement]) -> None:
    """Raise OutputError if the model cited requirement IDs that do not exist."""
    known = {r.id for r in reqs}
    unknown = sorted({i for i in used if i not in known})
    if unknown:
        valid = f"{reqs[0].id}…{reqs[-1].id}" if reqs else "(none)"
        raise OutputError(f"Unknown requirement IDs: {', '.join(unknown)}. Only use existing IDs ({valid}).")


def find_requirement_ids(text: str) -> list[str]:
    return _REQ_ID.findall(text)
