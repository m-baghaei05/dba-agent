"""Append-only log of every LLM call (spec, Technical Requirement ❸).

One JSON object per line (JSONL): easy to append, easy to read with any tool,
and a crash never corrupts earlier entries.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class CallLogger:
    def __init__(self, path: str | Path | None) -> None:
        self.path = Path(path) if path is not None else None  # None = logging disabled (tests)
        self.records: list[dict[str, Any]] = []               # in-memory copy, handy for tests
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, record: dict[str, Any]) -> None:
        record = {"timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"), **record}
        self.records.append(record)
        if self.path is not None:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
