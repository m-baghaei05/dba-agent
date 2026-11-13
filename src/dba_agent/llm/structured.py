"""Turn raw model text into a validated Pydantic object.

Models often wrap JSON in ```json fences, add a sentence before it, or (reasoning models)
emit a <think>...</think> block first. We strip those, then let Pydantic check that the
JSON has exactly the fields and types our code expects.
"""

from __future__ import annotations

import json
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


class OutputError(Exception):
    """The model's output could not be parsed or failed validation.
    The message is written so it can be sent back to the model as feedback."""


def extract_json(text: str) -> str:
    """Return the JSON object contained in `text`, or raise OutputError."""
    text = _THINK_RE.sub("", text).strip()

    fenced = _FENCE_RE.search(text)
    if fenced:
        text = fenced.group(1).strip()

    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise OutputError("No JSON object found. Respond with a single JSON object only.")
    return text[start : end + 1]


def parse_model(text: str, schema: type[T]) -> T:
    """Extract JSON from `text` and validate it against `schema`."""
    raw = extract_json(text)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise OutputError(f"Invalid JSON syntax: {e.msg} (line {e.lineno}, column {e.colno}).") from e

    try:
        return schema.model_validate(data)
    except ValidationError as e:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in err['loc']) or '(root)'}: {err['msg']}" for err in e.errors()
        )
        raise OutputError(f"JSON does not match the required schema: {problems}") from e


def schema_instructions(schema: type[BaseModel]) -> str:
    """Instruction text telling the model the exact JSON shape required."""
    return (
        "Respond with ONLY one JSON object (no prose, no Markdown fences) that conforms to "
        "this JSON Schema:\n" + json.dumps(schema.model_json_schema(), indent=2)
    )
