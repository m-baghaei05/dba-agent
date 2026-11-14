"""Stage 1 — Intake: free-text brief → structured SystemSummary (+ summary.md).

The user sees the summary and can accept it or type corrections; corrections are sent back
to the model together with its previous summary.
"""

from __future__ import annotations

from dba_agent.render.markdown import render_summary
from dba_agent.schemas import SystemSummary
from dba_agent.stages.context import StageContext
from dba_agent.state import Session, Stage

MAX_CORRECTION_ROUNDS = 3


def run(ctx: StageContext, session: Session) -> None:
    ctx.io.info("[bold]Stage 1/6 — Intake[/bold]: summarising your description…")
    summary = _summarise(ctx, session.brief)

    for _ in range(MAX_CORRECTION_ROUNDS):
        ctx.io.show_markdown(render_summary(summary))
        corrections = ctx.io.ask("Is this summary correct? Press Enter to accept, or type corrections.")
        if not corrections:
            break
        summary = _summarise(ctx, session.brief, previous=summary, corrections=corrections)
    else:
        ctx.io.show_markdown(render_summary(summary))
        ctx.io.info("Continuing with this summary; anything still missing will come up in the interview.")

    session.summary = summary
    ctx.store.write_file(session, "summary.md", render_summary(summary))
    session.stage = Stage.INTERVIEW


def _summarise(ctx: StageContext, brief: str, previous: SystemSummary | None = None,
               corrections: str = "") -> SystemSummary:
    messages = ctx.prompts.messages(
        "intake.md",
        brief=brief,
        previous=previous.model_dump_json(indent=2) if previous else "",
        corrections=corrections,
    )
    return ctx.llm.generate_structured("intake", messages, SystemSummary)
