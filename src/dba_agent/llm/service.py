"""LLMService: the single entry point the workflow stages use to call the model.

Two kinds of calls:
- generate_text():       free text (e.g. a Markdown section)
- generate_structured(): a validated Pydantic object; if the output is invalid, the error is
                         sent back to the model and it gets another attempt (up to max_retries)

Every call is logged once, with all its attempts: stage, input, outputs, errors, timing.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Sequence, TypeVar

from pydantic import BaseModel

from dba_agent.config import AppConfig
from dba_agent.llm.backends import BackendError, ChatBackend, Message, OpenAICompatibleBackend
from dba_agent.llm.call_log import CallLogger
from dba_agent.llm.structured import OutputError, parse_model, schema_instructions

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """The LLM call failed for good (after all attempts). The stage cannot continue."""


class LLMService:
    def __init__(self, backend: ChatBackend, logger: CallLogger, *, max_retries: int = 3,
                 temperature: float = 0.2, json_mode: bool = False,
                 max_tokens: int | None = None) -> None:
        self.backend = backend
        self.logger = logger
        self.max_retries = max_retries
        self.temperature = temperature
        self.json_mode = json_mode
        self.max_tokens = max_tokens  # default reply-length cap; each call may override it

    # ------------------------------------------------------------------ public API
    def generate_text(self, stage: str, messages: Sequence[Message], *,
                      max_tokens: int | None = None) -> str:
        record = self._new_record(stage, messages, schema=None)
        try:
            text = self._attempt(record, list(messages), json_mode=False,
                                 max_tokens=max_tokens or self.max_tokens)
        except BackendError as e:
            self._finish(record, success=False, error=str(e))
            raise LLMError(f"[{stage}] LLM call failed: {e}") from e
        self._finish(record, success=True)
        return text

    def generate_structured(self, stage: str, messages: Sequence[Message], schema: type[T], *,
                            max_tokens: int | None = None) -> T:
        # The schema is appended automatically, so prompts and code can never disagree on it.
        convo = list(messages) + [{"role": "system", "content": schema_instructions(schema)}]
        record = self._new_record(stage, convo, schema=schema)

        last_error = ""
        for _ in range(self.max_retries):
            try:
                text = self._attempt(record, convo, json_mode=self.json_mode,
                                     max_tokens=max_tokens or self.max_tokens)
            except BackendError as e:
                self._finish(record, success=False, error=str(e))
                raise LLMError(f"[{stage}] LLM call failed: {e}") from e
            try:
                result = parse_model(text, schema)
            except OutputError as e:
                last_error = str(e)
                record["attempts"][-1]["error"] = last_error
                # Feedback: show the model its own answer and what was wrong with it.
                convo = convo + [
                    {"role": "assistant", "content": text},
                    {"role": "user", "content": f"Your previous response was invalid. {last_error}\n"
                                                "Return the corrected, complete JSON object only."},
                ]
                continue
            self._finish(record, success=True)
            return result

        self._finish(record, success=False, error=last_error)
        raise LLMError(
            f"[{stage}] No valid output after {self.max_retries} attempts. Last error: {last_error}"
        )

    # ------------------------------------------------------------------ internals
    def _attempt(self, record: dict, messages: list[Message], *, json_mode: bool,
                 max_tokens: int | None) -> str:
        n = len(record["attempts"]) + 1
        started = time.perf_counter()
        entry: dict = {"attempt": n, "input_messages": len(messages)}
        record["attempts"].append(entry)
        try:
            text = self.backend.complete(messages, temperature=self.temperature,
                                         json_mode=json_mode, max_tokens=max_tokens)
        except BackendError as e:
            entry["error"] = str(e)
            raise
        finally:
            entry["latency_ms"] = round((time.perf_counter() - started) * 1000)
        entry["output"] = text
        if n > 1:  # log the feedback messages added since the first attempt
            entry["feedback"] = messages[-1]["content"]
        return text

    def _new_record(self, stage: str, messages: Sequence[Message], schema) -> dict:
        return {
            "stage": stage,
            "model": self.backend.model,
            "schema": schema.__name__ if schema else None,
            "input": [dict(m) for m in messages],
            "attempts": [],
        }

    def _finish(self, record: dict, *, success: bool, error: str | None = None) -> None:
        record["num_attempts"] = len(record["attempts"])
        record["success"] = success
        if error:
            record["error"] = error
        self.logger.write(record)


def build_llm_service(cfg: AppConfig, log_path: str | Path | None) -> LLMService:
    """Create the service for the active profile in config.yaml."""
    p = cfg.provider
    backend = OpenAICompatibleBackend(
        base_url=p.base_url, api_key=p.api_key(), model=p.model,
        timeout=cfg.llm.timeout_seconds,
    )
    return LLMService(
        backend, CallLogger(log_path),
        max_retries=cfg.llm.max_retries, temperature=cfg.llm.temperature, json_mode=p.json_mode,
        max_tokens=cfg.llm.max_tokens,
    )
