"""Stage 2 — Interview: ask questions in rounds until the agent decides it has enough,
then write requirements.md.

Who decides what
- The LLM writes the questions and judges coverage/readiness (it understands the domain).
- The code enforces the spec's hard rules, whatever the LLM says:
    * round 1 covers all 7 categories        (InitialQuestions validator)
    * at least N follow-up rounds happen     (RequiredFollowUp while N not reached)
    * the interview always ends              (interview_max_rounds)
- State is saved after every answer, so `dba resume` continues mid-interview.
"""

from __future__ import annotations

from dba_agent.render.markdown import number_requirements, render_requirements
from dba_agent.schemas import (CATEGORY_TITLES, QA, FollowUp, InitialQuestions, InterviewState,
                               Question, RequiredFollowUp, RequirementsDraft)
from dba_agent.stages.context import StageContext
from dba_agent.state import Session, Stage

SKIP_WORDS = {"skip", "-", "?", "idk", "don't know", "dont know"}


def run(ctx: StageContext, session: Session) -> None:
    ctx.io.info("[bold]Stage 2/6 — Interview[/bold]: a few rounds of questions. "
                "Type 'skip' if you don't know; the agent will make (and record) an assumption.")
    iv = session.interview
    wf = ctx.workflow

    while not iv.finished:
        if iv.pending:
            _ask_pending(ctx, session)
            continue

        if not iv.qa:
            initial = ctx.llm.generate_structured(
                "interview", ctx.prompts.messages("interview_initial.md", **_vars(session)),
                InitialQuestions)
            _add_round(iv, initial.questions, round_no=1)
            ctx.save(session)
            continue

        followups_done = iv.rounds_done - 1
        if iv.rounds_done >= wf.interview_max_rounds:
            _finish(iv, f"Reached the maximum of {wf.interview_max_rounds} rounds.")
            break

        must_ask = followups_done < wf.interview_min_followup_rounds
        decision: FollowUp = ctx.llm.generate_structured(
            "interview",
            ctx.prompts.messages("interview_followup.md", **_vars(session),
                                 round_no=iv.rounds_done + 1, must_ask=must_ask,
                                 last_round=iv.rounds_done + 1 >= wf.interview_max_rounds),
            RequiredFollowUp if must_ask else FollowUp,
        )
        iv.coverage = decision.coverage

        if decision.ready and not must_ask:
            _finish(iv, decision.reason)
        else:
            ctx.io.info(f"[dim]Agent: {decision.reason}[/dim]")
            _add_round(iv, decision.questions, round_no=iv.rounds_done + 1)
        ctx.save(session)

    ctx.io.info(f"[green]Interview finished.[/green] {iv.stop_reason}")
    _write_requirements(ctx, session)
    session.stage = Stage.DBMS


# ---------------------------------------------------------------- helpers
def _vars(session: Session) -> dict:
    return {
        "summary": session.summary.model_dump_json(indent=2) if session.summary else "{}",
        "transcript": _transcript(session.interview),
    }


def _transcript(iv: InterviewState) -> str:
    lines = []
    for q in iv.qa:
        if q.answer is None:
            continue
        answer = q.answer or "(skipped by the user)"
        lines.append(f"[Round {q.round} | {q.category.value}] Q: {q.question}\nA: {answer}")
    return "\n\n".join(lines) or "(no answers yet)"


def _add_round(iv: InterviewState, questions: list[Question], round_no: int) -> None:
    iv.qa.extend(QA(round=round_no, category=q.category, question=q.question, why=q.why)
                 for q in questions)


def _ask_pending(ctx: StageContext, session: Session) -> None:
    iv = session.interview
    pending = iv.pending
    ctx.io.info(f"\n[bold]Round {iv.current_round}[/bold] — {len(pending)} question(s)")
    for q in pending:
        hint = f"\n[dim]{q.why}[/dim]" if q.why else ""
        ctx.io.info(f"\n[yellow]{CATEGORY_TITLES[q.category]}[/yellow]{hint}")
        answer = ctx.io.ask(q.question)
        q.answer = "" if answer.strip().lower() in SKIP_WORDS else answer.strip()
        ctx.save(session)  # save after every answer
    iv.rounds_done = iv.current_round
    ctx.save(session)


def _finish(iv: InterviewState, reason: str) -> None:
    iv.finished = True
    iv.stop_reason = reason


def _write_requirements(ctx: StageContext, session: Session) -> None:
    ctx.io.info("Writing requirements.md…")
    draft = ctx.llm.generate_structured(
        "requirements", ctx.prompts.messages("requirements.md", **_vars(session)), RequirementsDraft)
    session.requirements_overview = draft.overview
    session.requirements = number_requirements(draft.items)
    doc = render_requirements(session.summary.system_name if session.summary else "System",
                              draft.overview, session.requirements, session.interview.qa)
    path = ctx.store.write_file(session, "requirements.md", doc)
    ctx.io.info(f"[green]Saved[/green] {path}")
