"""Command-line entry point (`dba ...`). More commands are added in later stages."""

from __future__ import annotations

from pathlib import Path

import typer
from pydantic import BaseModel
from rich.console import Console
from rich.table import Table

from dba_agent import __version__
from dba_agent.config import AppConfig, ConfigError, load_config

app = typer.Typer(help="DBA Agent — an LLM-powered database design assistant.")
console = Console()

CONFIG_OPT = typer.Option("config.yaml", "--config", help="Path to the config file.")


def _load(config: str) -> AppConfig:
    try:
        return load_config(config)
    except ConfigError as e:
        console.print(f"[red]Config error:[/red] {e}")
        raise typer.Exit(code=1)


@app.command()
def version() -> None:
    """Print the version."""
    console.print(f"dba-agent {__version__}")


@app.command()
def info(config: str = CONFIG_OPT) -> None:
    """Show the active provider/model (never prints the API key)."""
    cfg = _load(config)
    p = cfg.provider
    table = Table(title="Active LLM configuration", show_header=False)
    table.add_row("Profile", cfg.active_profile)
    table.add_row("Base URL", p.base_url)
    table.add_row("Model", p.model)
    table.add_row("JSON mode", str(p.json_mode))
    if p.api_key_env:
        try:
            p.api_key()
            status = "set"
        except ConfigError:
            status = "[red]MISSING[/red]"
        table.add_row("API key", f"{p.api_key_env} ({status})")
    else:
        table.add_row("API key", "not required")
    table.add_row("Output dir", str(cfg.paths.output_dir))
    console.print(table)


@app.command()
def models(config: str = CONFIG_OPT, contains: str = typer.Option("", help="Filter by substring.")) -> None:
    """List the model IDs offered by the active provider."""
    from openai import OpenAI, OpenAIError

    cfg = _load(config)
    p = cfg.provider
    try:
        client = OpenAI(base_url=p.base_url, api_key=p.api_key(), timeout=60)
        ids = sorted(m.id for m in client.models.list())
    except (ConfigError, OpenAIError) as e:
        console.print(f"[red]Could not list models:[/red] {e}")
        raise typer.Exit(code=1)
    for mid in ids:
        if contains.lower() in mid.lower():
            console.print(mid)


class _PingReply(BaseModel):
    answer: int


@app.command()
def ping(config: str = CONFIG_OPT) -> None:
    """Send one small structured request to check the provider, model and logging."""
    from dba_agent.llm import LLMError, build_llm_service

    cfg = _load(config)
    log_path = Path(cfg.paths.output_dir) / "_ping" / "llm_calls.jsonl"
    try:
        llm = build_llm_service(cfg, log_path)
        reply = llm.generate_structured(
            "ping",
            [{"role": "user", "content": "What is 17 + 25? Put the number in the field `answer`."}],
            _PingReply,
        )
    except (ConfigError, LLMError) as e:
        console.print(f"[red]Ping failed:[/red] {e}")
        console.print(f"See the log: {log_path}")
        raise typer.Exit(code=1)

    attempts = llm.logger.records[-1]["num_attempts"]
    ok = reply.answer == 42
    colour = "green" if ok else "yellow"
    console.print(f"[{colour}]{cfg.active_profile} / {cfg.provider.model}: answer={reply.answer} "
                  f"({'correct' if ok else 'wrong'}), attempts={attempts}[/{colour}]")
    console.print(f"Logged to {log_path}")


if __name__ == "__main__":
    app()
