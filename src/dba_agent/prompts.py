"""Load prompt templates from the prompts/ folder (spec, Technical Requirement ❷).

Each LLM task has its own Markdown file, rendered with Jinja2. StrictUndefined means a
missing variable is an error instead of silently becoming an empty string.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from dba_agent.llm.backends import Message

SYSTEM_TEMPLATE = "system.md"


class PromptLibrary:
    def __init__(self, prompts_dir: str | Path) -> None:
        self.dir = Path(prompts_dir)
        self.env = Environment(
            loader=FileSystemLoader(self.dir),
            undefined=StrictUndefined,
            keep_trailing_newline=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, name: str, **variables) -> str:
        return self.env.get_template(name).render(**variables).strip()

    def messages(self, name: str, **variables) -> list[Message]:
        """The shared system prompt + the task prompt as the user message."""
        return [
            {"role": "system", "content": self.render(SYSTEM_TEMPLATE)},
            {"role": "user", "content": self.render(name, **variables)},
        ]
