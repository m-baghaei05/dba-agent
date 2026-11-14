"""The workflow state machine.

    INTAKE → INTERVIEW → DBMS → DESIGN → REVISION (loops until approved) → SQL → DONE

The orchestrator only knows the order: it looks up the handler for the session's current stage,
runs it, and saves. Each handler does its work and sets the next stage itself, so a stage like
REVISION can choose to stay where it is (loop) or move on.
"""

from __future__ import annotations

from typing import Callable

from dba_agent.stages import intake, interview
from dba_agent.stages.context import StageContext
from dba_agent.state import Session, Stage

Handler = Callable[[StageContext, Session], None]

HANDLERS: dict[Stage, Handler] = {
    Stage.INTAKE: intake.run,
    Stage.INTERVIEW: interview.run,
    # Stage.DBMS, Stage.DESIGN, Stage.REVISION, Stage.SQL: added on Days 3–6
}


def run(ctx: StageContext, session: Session) -> None:
    while session.stage != Stage.DONE:
        handler = HANDLERS.get(session.stage)
        if handler is None:
            ctx.io.info(f"[yellow]Stage '{session.stage.value}' is not implemented yet.[/yellow] "
                        f"Progress is saved; continue later with: dba resume {session.id}")
            return
        handler(ctx, session)
        ctx.save(session)
    ctx.io.info(f"[green]Session {session.id} is complete.[/green]")
