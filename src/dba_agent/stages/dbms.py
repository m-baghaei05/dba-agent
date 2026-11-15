"""Stage 3 — DBMS selection: requirements → DBMSChoice (+ dbms-choice.md).

The LLM chooses criteria, weights and scores; the code computes the totals and checks that the
choice agrees with them (DBMSChoice validator) and that every cited requirement exists (check below).
The user can accept, or give a reason to reconsider (e.g. "it must run offline on one laptop").
"""

from __future__ import annotations

from dba_agent.render.markdown import render_dbms_choice
from dba_agent.schemas import DBMS_NAMES, DBMSChoice
from dba_agent.stages.common import check_requirement_ids, find_requirement_ids, format_requirements
from dba_agent.stages.context import StageContext
from dba_agent.state import Session, Stage

MAX_FEEDBACK_ROUNDS = 2


def run(ctx: StageContext, session: Session) -> None:
    ctx.io.info("[bold]Stage 3/6 — DBMS selection[/bold]: comparing PostgreSQL, MySQL/MariaDB, "
                "SQLite and SQL Server against your requirements…")
    choice = _choose(ctx, session)

    for _ in range(MAX_FEEDBACK_ROUNDS):
        ctx.io.show_markdown(render_dbms_choice(_name(session), choice))
        feedback = ctx.io.ask(f"Use {DBMS_NAMES[choice.chosen]}? Press Enter to accept, "
                              "or explain what should change the decision.")
        if not feedback:
            break
        choice = _choose(ctx, session, previous=choice, feedback=feedback)
    else:
        ctx.io.show_markdown(render_dbms_choice(_name(session), choice))

    session.dbms_choice = choice
    path = ctx.store.write_file(session, "dbms-choice.md", render_dbms_choice(_name(session), choice))
    ctx.io.info(f"[green]Chosen: {DBMS_NAMES[choice.chosen]}.[/green] Saved {path}")
    session.stage = Stage.DESIGN


def _name(session: Session) -> str:
    return session.summary.system_name if session.summary else "System"


def _choose(ctx: StageContext, session: Session, previous: DBMSChoice | None = None,
            feedback: str = "") -> DBMSChoice:
    def check(choice: DBMSChoice) -> None:
        cited = [i for c in choice.criteria for i in c.requirement_ids]
        cited += find_requirement_ids(choice.justification)
        cited += [i for r in choice.rejected for i in find_requirement_ids(r.reason)]
        check_requirement_ids(cited, session.requirements)

    messages = ctx.prompts.messages(
        "dbms_selection.md",
        summary=session.summary.model_dump_json(indent=2) if session.summary else "{}",
        requirements=format_requirements(session.requirements),
        previous=previous.model_dump_json(indent=2) if previous else "",
        feedback=feedback,
    )
    return ctx.llm.generate_structured("dbms", messages, DBMSChoice, check=check)
