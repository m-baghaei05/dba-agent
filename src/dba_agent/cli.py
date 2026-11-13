"""Command-line entry point (`dba ...`). More commands are added in later stages."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from dba_agent import __version__
from dba_agent.config import ConfigError, load_config

app = typer.Typer(help="DBA Agent — an LLM-powered database design assistant.")
console = Console()


@app.command()
def version() -> None:
    """Print the version."""
    console.print(f"dba-agent {__version__}")


@app.command()
def info(config: str = typer.Option("config.yaml", help="Path to the config file.")) -> None:
    """Show the active provider/model (never prints the API key)."""
    try:
        cfg = load_config(config)
    except ConfigError as e:
        console.print(f"[red]Config error:[/red] {e}")
        raise typer.Exit(code=1)

    p = cfg.provider
    table = Table(title="Active LLM configuration", show_header=False)
    table.add_row("Profile", cfg.active_profile)
    table.add_row("Base URL", p.base_url)
    table.add_row("Model", p.model)
    if p.api_key_env:
        has_key = "set" if _key_present(p) else "[red]MISSING[/red]"
        table.add_row("API key", f"{p.api_key_env} ({has_key})")
    else:
        table.add_row("API key", "not required")
    table.add_row("Output dir", str(cfg.paths.output_dir))
    console.print(table)


def _key_present(profile) -> bool:
    try:
        profile.api_key()
        return True
    except ConfigError:
        return False


if __name__ == "__main__":
    app()
