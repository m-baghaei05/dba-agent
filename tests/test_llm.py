"""Tests for the LLM layer, using ScriptedBackend (no network, no API key)."""

import json

import pytest
from pydantic import BaseModel

from dba_agent.llm import BackendError, CallLogger, LLMError, LLMService, OutputError, ScriptedBackend
from dba_agent.llm.structured import extract_json, parse_model


class Entity(BaseModel):
    name: str
    attributes: list[str]


MSGS = [{"role": "user", "content": "Describe one entity."}]
GOOD = '{"name": "Student", "attributes": ["id", "full_name"]}'


def make_service(responses, tmp_path=None, max_retries=3):
    log_path = tmp_path / "calls.jsonl" if tmp_path else None
    backend = ScriptedBackend(responses)
    return LLMService(backend, CallLogger(log_path), max_retries=max_retries), backend


# ---------------------------------------------------------------- JSON extraction
@pytest.mark.parametrize("text", [
    GOOD,
    f"```json\n{GOOD}\n```",
    f"Sure! Here is the JSON:\n{GOOD}\nHope this helps.",
    f"<think>The user wants an entity...</think>\n{GOOD}",
])
def test_extract_json_handles_common_wrappers(text):
    assert json.loads(extract_json(text))["name"] == "Student"


def test_extract_json_without_object_fails():
    with pytest.raises(OutputError, match="No JSON object"):
        extract_json("I cannot answer that.")


def test_parse_model_reports_missing_field():
    with pytest.raises(OutputError, match="attributes"):
        parse_model('{"name": "Student"}', Entity)


# ---------------------------------------------------------------- service
def test_structured_success_first_try(tmp_path):
    llm, backend = make_service([GOOD], tmp_path)
    result = llm.generate_structured("intake", MSGS, Entity)

    assert result == Entity(name="Student", attributes=["id", "full_name"])
    # The JSON schema was appended to the prompt automatically
    assert "JSON Schema" in backend.calls[0][-1]["content"]

    record = json.loads((tmp_path / "calls.jsonl").read_text(encoding="utf-8"))
    assert record["stage"] == "intake"
    assert record["num_attempts"] == 1 and record["success"] is True
    assert record["attempts"][0]["output"] == GOOD


def test_invalid_output_is_fed_back_and_retried(tmp_path):
    llm, backend = make_service(["not json at all", '{"name": "Student"}', GOOD], tmp_path)
    result = llm.generate_structured("design", MSGS, Entity)

    assert result.name == "Student"
    record = llm.logger.records[-1]
    assert record["num_attempts"] == 3 and record["success"] is True
    # The second request contained the bad answer and the error message
    second = backend.calls[1]
    assert second[-2] == {"role": "assistant", "content": "not json at all"}
    assert "invalid" in second[-1]["content"]
    assert "error" in record["attempts"][1] and "attributes" in record["attempts"][1]["error"]


def test_gives_up_after_max_retries():
    llm, _ = make_service(["bad", "bad", "bad"], max_retries=3)
    with pytest.raises(LLMError, match="after 3 attempts"):
        llm.generate_structured("design", MSGS, Entity)
    record = llm.logger.records[-1]
    assert record["success"] is False and record["num_attempts"] == 3


def test_api_failure_is_logged_and_raised():
    llm, _ = make_service([BackendError("RateLimitError: 429")])
    with pytest.raises(LLMError, match="429"):
        llm.generate_structured("interview", MSGS, Entity)
    record = llm.logger.records[-1]
    assert record["success"] is False and "429" in record["error"]


def test_generate_text_returns_raw_text():
    llm, _ = make_service(["## Assumptions\n- A student has one advisor."])
    text = llm.generate_text("assumptions", MSGS)
    assert text.startswith("## Assumptions")
    assert llm.logger.records[-1]["schema"] is None


def test_max_tokens_default_and_override():
    backend = ScriptedBackend([GOOD, GOOD])
    llm = LLMService(backend, CallLogger(None), max_tokens=8192)
    llm.generate_structured("design", MSGS, Entity)
    llm.generate_structured("ping", MSGS, Entity, max_tokens=100)
    assert backend.max_tokens_seen == [8192, 100]
