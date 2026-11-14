from pathlib import Path

import pytest
from jinja2 import UndefinedError

from dba_agent.prompts import PromptLibrary

PROMPTS = Path(__file__).resolve().parents[1] / "prompts"


def test_messages_have_system_and_user_parts():
    msgs = PromptLibrary(PROMPTS).messages("intake.md", brief="A gym.", previous="", corrections="")
    assert [m["role"] for m in msgs] == ["system", "user"]
    assert "A gym." in msgs[1]["content"]
    assert "corrections" not in msgs[1]["content"].lower().split("## guidelines")[0]


def test_corrections_section_appears_only_when_given():
    msgs = PromptLibrary(PROMPTS).messages("intake.md", brief="A gym.", previous="{...}",
                                           corrections="There are two branches.")
    assert "two branches" in msgs[1]["content"]


def test_missing_variable_is_an_error():
    with pytest.raises(UndefinedError):
        PromptLibrary(PROMPTS).render("intake.md", brief="x")
