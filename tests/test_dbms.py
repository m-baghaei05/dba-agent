"""DBMS choice: schema rules and dbms-choice.md rendering (no LLM involved)."""

import copy

import pytest
from pydantic import ValidationError

from dba_agent.render.markdown import render_dbms_choice
from dba_agent.schemas import DBMS, DBMSChoice


def scores(pg, my, lite, ms):
    return {"postgresql": pg, "mysql": my, "sqlite": lite, "sqlserver": ms}


VALID = {
    "chosen": "postgresql",
    "justification": "Concurrent receptionists and monthly reports favour PostgreSQL (R-05, R-04).",
    "criteria": [
        {"name": "Concurrent writes", "weight": 5, "requirement_ids": ["R-05"],
         "scores": scores(5, 4, 1, 5), "note": "Several receptionists book at once."},
        {"name": "Reporting queries", "weight": 4, "requirement_ids": ["R-04"],
         "scores": scores(5, 4, 3, 5)},
        {"name": "Cost and licensing", "weight": 3, "scores": scores(5, 5, 5, 2)},
        {"name": "Deployment simplicity", "weight": 2, "scores": scores(4, 4, 5, 2)},
    ],
    "rejected": [
        {"dbms": "mysql", "reason": "Weaker CHECK constraint support in older versions."},
        {"dbms": "sqlite", "reason": "Single-writer locking does not fit concurrent bookings."},
        {"dbms": "sqlserver", "reason": "Licensing cost for a small private clinic."},
    ],
    "trade_offs": ["Needs a server process and backups."],
}


def test_valid_choice_and_totals():
    choice = DBMSChoice.model_validate(VALID)
    # 5*5 + 4*5 + 3*5 + 2*4 = 68 ; computed by code, not by the LLM
    assert choice.totals()[DBMS.POSTGRESQL] == 68
    assert max(choice.totals(), key=choice.totals().get) == DBMS.POSTGRESQL


def test_every_dbms_must_be_scored():
    data = copy.deepcopy(VALID)
    del data["criteria"][0]["scores"]["sqlite"]
    with pytest.raises(ValidationError, match="Missing: sqlite"):
        DBMSChoice.model_validate(data)


def test_scores_must_be_1_to_5():
    data = copy.deepcopy(VALID)
    data["criteria"][0]["scores"]["mysql"] = 9
    with pytest.raises(ValidationError, match="between 1 and 5"):
        DBMSChoice.model_validate(data)


def test_rejected_must_cover_the_other_three():
    data = copy.deepcopy(VALID)
    data["rejected"] = data["rejected"][:2]
    with pytest.raises(ValidationError, match="exactly one entry for each DBMS"):
        DBMSChoice.model_validate(data)


def test_choice_must_match_its_own_scores():
    data = copy.deepcopy(VALID)
    data["chosen"] = "sqlite"
    data["rejected"] = [{"dbms": d, "reason": "x"} for d in ("postgresql", "mysql", "sqlserver")]
    with pytest.raises(ValidationError, match="contradict your choice"):
        DBMSChoice.model_validate(data)


def test_render_dbms_choice():
    doc = render_dbms_choice("Dental Clinic", DBMSChoice.model_validate(VALID))
    assert doc.startswith("# DBMS Choice: Dental Clinic")
    assert "| Criterion | Weight | Based on | **PostgreSQL** | MySQL / MariaDB |" in doc
    assert "| **Weighted total** | | | **68** |" in doc
    assert "- **SQLite**: Single-writer locking" in doc
    assert "## Trade-offs of PostgreSQL" in doc
