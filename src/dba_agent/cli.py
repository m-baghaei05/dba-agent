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
            max_tokens=100,  # the answer is tiny; keeps the cost estimate minimal
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


# ---------------------------------------------------------------- design sessions
def _build_context(cfg: AppConfig, session_id: str):
    from dba_agent.llm import build_llm_service
    from dba_agent.prompts import PromptLibrary
    from dba_agent.stages.context import StageContext
    from dba_agent.state import SessionStore
    from dba_agent.userio import ConsoleIO

    store = SessionStore(cfg.paths.output_dir)
    return StageContext(
        llm=build_llm_service(cfg, store.log_path(session_id)),
        prompts=PromptLibrary(cfg.paths.prompts_dir),
        io=ConsoleIO(),
        store=store,
        workflow=cfg.workflow,
    )


def _run_session(cfg: AppConfig, session) -> None:
    from dba_agent import orchestrator
    from dba_agent.llm import LLMError

    console.print(f"Session [bold]{session.id}[/bold] — files in {Path(cfg.paths.output_dir) / session.id}")
    try:
        ctx = _build_context(cfg, session.id)
        orchestrator.run(ctx, session)
    except (LLMError, ConfigError) as e:
        console.print(f"[red]Stopped:[/red] {e}")
        console.print(f"Progress is saved. Fix the problem, then run: dba resume {session.id}")
        raise typer.Exit(code=1)
    except KeyboardInterrupt:
        console.print(f"\n[yellow]Interrupted.[/yellow] Progress is saved. Continue with: dba resume {session.id}")
        raise typer.Exit(code=130)


@app.command()
def new(
    brief_file: Path = typer.Option(None, "--brief-file", "-f", exists=True, dir_okay=False,
                                    help="Read the system description from a text/Markdown file."),
    config: str = CONFIG_OPT,
) -> None:
    """Start a new design session from a description of your system."""
    from dba_agent.state import SessionStore
    from dba_agent.userio import ConsoleIO

    cfg = _load(config)
    if brief_file:
        brief = brief_file.read_text(encoding="utf-8")
    else:
        brief = ConsoleIO().ask_multiline("Describe the system you need a database for.")
    if not brief.strip():
        console.print("[red]The description is empty.[/red]")
        raise typer.Exit(code=1)

    session = SessionStore(cfg.paths.output_dir).create(brief)
    _run_session(cfg, session)


@app.command()
def resume(
    session_id: str = typer.Argument(None, help="Session ID (default: the most recent session)."),
    config: str = CONFIG_OPT,
) -> None:
    """Continue a saved session from where it stopped."""
    from dba_agent.state import SessionNotFound, SessionStore

    cfg = _load(config)
    store = SessionStore(cfg.paths.output_dir)
    session_id = session_id or store.latest_id()
    if not session_id:
        console.print("No sessions yet. Start one with: dba new")
        raise typer.Exit(code=1)
    try:
        session = store.load(session_id)
    except SessionNotFound as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=1)
    console.print(f"Resuming at stage [bold]{session.stage.value}[/bold]")
    _run_session(cfg, session)


@app.command("list")
def list_sessions(config: str = CONFIG_OPT) -> None:
    """List saved sessions."""
    from dba_agent.state import SessionStore

    cfg = _load(config)
    sessions = SessionStore(cfg.paths.output_dir).list()
    if not sessions:
        console.print("No sessions yet. Start one with: dba new")
        return
    table = Table("ID", "System", "Stage", "Last update")
    for s in sessions:
        table.add_row(s.id, s.summary.system_name if s.summary else "—", s.stage.value, s.updated_at)
    console.print(table)


@app.command()
def status(
    session_id: str = typer.Argument(None, help="Session ID (default: the most recent session)."),
    config: str = CONFIG_OPT,
) -> None:
    """Show the progress of one session."""
    from dba_agent.state import SessionNotFound, SessionStore

    cfg = _load(config)
    store = SessionStore(cfg.paths.output_dir)
    session_id = session_id or store.latest_id()
    try:
        s = store.load(session_id) if session_id else None
    except SessionNotFound as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=1)
    if s is None:
        console.print("No sessions yet. Start one with: dba new")
        return

    iv = s.interview
    table = Table(title=f"Session {s.id}", show_header=False)
    table.add_row("System", s.summary.system_name if s.summary else "—")
    table.add_row("Stage", s.stage.value)
    table.add_row("Interview", f"{iv.rounds_done} round(s), {len([q for q in iv.qa if q.answer is not None])} "
                               f"answers, {'finished' if iv.finished else 'in progress'}")
    if iv.coverage:
        table.add_row("Coverage", ", ".join(f"{k.value}: {v}" for k, v in iv.coverage.items()))
    table.add_row("Requirements", str(len(s.requirements)))
    files = sorted(p.name for p in store.dir(s.id).iterdir() if p.is_file())
    table.add_row("Files", ", ".join(files))
    console.print(table)


if __name__ == "__main__":
    app()
