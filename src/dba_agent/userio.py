"""User input/output, behind a small interface.

Stages never call print() or input() directly; they use a UserIO object. The real CLI passes
ConsoleIO (Rich in the terminal); tests pass ScriptedIO with pre-written answers. This is the
same dependency-injection idea as ScriptedBackend for the LLM.
"""

from __future__ import annotations

from typing import Protocol, Sequence

END_MARKER = "/end"


class UserIO(Protocol):
    def info(self, text: str) -> None: ...
    def show_markdown(self, markdown: str) -> None: ...
    def ask(self, prompt: str) -> str: ...
    def ask_multiline(self, prompt: str) -> str: ...


class ConsoleIO:
    def __init__(self) -> None:
        from rich.console import Console  # imported here so tests don't need Rich

        self.console = Console()

    def info(self, text: str) -> None:
        self.console.print(text)

    def show_markdown(self, markdown: str) -> None:
        from rich.markdown import Markdown
        from rich.panel import Panel

        self.console.print(Panel(Markdown(markdown), expand=True))

    def ask(self, prompt: str) -> str:
        return self.console.input(f"[bold cyan]{prompt}[/bold cyan]\n> ").strip()

    def ask_multiline(self, prompt: str) -> str:
        self.console.print(f"[bold cyan]{prompt}[/bold cyan]  (finish with a line containing only {END_MARKER})")
        lines = []
        while True:
            line = input()
            if line.strip() == END_MARKER:
                break
            lines.append(line)
        return "\n".join(lines).strip()


class ScriptedIO:
    """Fake user for tests: returns answers in order and records everything shown."""

    def __init__(self, answers: Sequence[str] = ()) -> None:
        self.answers = list(answers)
        self.output: list[str] = []
        self.prompts: list[str] = []

    def info(self, text: str) -> None:
        self.output.append(text)

    def show_markdown(self, markdown: str) -> None:
        self.output.append(markdown)

    def ask(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if not self.answers:
            raise AssertionError(f"ScriptedIO ran out of answers at prompt: {prompt}")
        return self.answers.pop(0)

    ask_multiline = ask
