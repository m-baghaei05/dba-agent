"""Backends: the only code that actually talks to a model.

A backend has one job: take a list of chat messages and return the model's text.
Everything else (retries, JSON validation, logging) lives in LLMService, so it can be
tested with ScriptedBackend and no network.
"""

from __future__ import annotations

from typing import Protocol, Sequence

Message = dict[str, str]  # {"role": "system" | "user" | "assistant", "content": "..."}


class BackendError(Exception):
    """The provider call failed (network, auth, rate limit, server error...)."""


class ChatBackend(Protocol):
    model: str

    def complete(self, messages: Sequence[Message], *, temperature: float, json_mode: bool) -> str:
        ...


class OpenAICompatibleBackend:
    """Works with any provider exposing the OpenAI Chat Completions API
    (AvalAI, GapGPT, Kilo, OpenRouter, DeepSeek, Ollama, ...)."""

    def __init__(self, *, base_url: str, api_key: str, model: str, timeout: float,
                 transport_retries: int = 2) -> None:
        from openai import OpenAI  # imported here so tests don't need the package

        self.model = model
        # The SDK itself retries connection errors, 429 and 5xx with backoff.
        self._client = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout,
                              max_retries=transport_retries)

    def complete(self, messages: Sequence[Message], *, temperature: float, json_mode: bool) -> str:
        import openai

        kwargs = {}
        if json_mode:
            # Asks the provider to force syntactically valid JSON. Not every provider
            # supports it, so it is switched on per profile in config.yaml.
            kwargs["response_format"] = {"type": "json_object"}
        try:
            resp = self._client.chat.completions.create(
                model=self.model, messages=list(messages), temperature=temperature, **kwargs
            )
        except openai.OpenAIError as e:
            raise BackendError(f"{type(e).__name__}: {e}") from e

        if not resp.choices:
            raise BackendError("Provider returned no choices.")
        content = resp.choices[0].message.content
        if not content:
            raise BackendError("Provider returned an empty message.")
        return content


class ScriptedBackend:
    """Fake backend for tests: returns pre-written responses in order.

    A response may be an Exception instance, which is raised instead (to simulate API failures).
    Every received message list is kept in `calls` so tests can inspect the prompts sent.
    """

    def __init__(self, responses: Sequence[str | Exception], model: str = "scripted") -> None:
        self.model = model
        self._responses = list(responses)
        self.calls: list[list[Message]] = []

    def complete(self, messages: Sequence[Message], *, temperature: float, json_mode: bool) -> str:
        self.calls.append([dict(m) for m in messages])
        if not self._responses:
            raise AssertionError("ScriptedBackend ran out of responses")
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item
