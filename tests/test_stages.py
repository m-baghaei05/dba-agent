"""Intake and Interview stages, end to end, with a fake LLM and a fake user."""

import json

from conftest import dbms_json, followup_json, initial_json, requirements_json, summary_json

from dba_agent import orchestrator
from dba_agent.stages import intake, interview
from dba_agent.state import Stage

N_INITIAL = 7  # initial_json() asks one question per category


# ---------------------------------------------------------------- intake
def test_intake_accepts_summary(make_ctx):
    ctx, _ = make_ctx([summary_json()], user_answers=[""])
    s = ctx.store.create("A dental clinic.")
    intake.run(ctx, s)

    assert s.stage == Stage.INTERVIEW
    assert s.summary.system_name == "Dental Clinic"
    assert "# System Summary: Dental Clinic" in (ctx.store.dir(s.id) / "summary.md").read_text()


def test_intake_applies_corrections(make_ctx):
    ctx, backend = make_ctx([summary_json("Clinic v1"), summary_json("Clinic v2")],
                            user_answers=["We also have a lab.", ""])
    s = ctx.store.create("A dental clinic.")
    intake.run(ctx, s)

    assert s.summary.system_name == "Clinic v2"
    second_prompt = backend.calls[1][1]["content"]
    assert "We also have a lab." in second_prompt and "Clinic v1" in second_prompt


# ---------------------------------------------------------------- interview
def _ready_session(ctx):
    s = ctx.store.create("A dental clinic.")
    from dba_agent.schemas import SystemSummary
    s.summary = SystemSummary.model_validate_json(summary_json())
    s.stage = Stage.INTERVIEW
    return s


def test_interview_happy_path(make_ctx):
    llm = [initial_json(), followup_json(ready=True, n_questions=1),  # forced follow-up round
           followup_json(ready=True, n_questions=0), requirements_json()]
    answers = ["answer"] * N_INITIAL + ["skip"]
    ctx, _ = make_ctx(llm, answers)
    s = _ready_session(ctx)
    interview.run(ctx, s)

    iv = s.interview
    assert s.stage == Stage.DBMS
    assert iv.finished and iv.rounds_done == 2          # initial + one mandatory follow-up
    assert iv.qa[-1].answer == ""                        # "skip" stored as skipped
    assert [r.id for r in s.requirements] == [f"R-{i:02d}" for i in range(1, 8)]
    assert s.requirements[0].category.value == "entities_attributes"  # sorted by category order

    doc = (ctx.store.dir(s.id) / "requirements.md").read_text()
    assert "R-07" in doc and "Assumption" in doc and "Round 2 (follow-up)" in doc


def test_first_round_missing_a_category_is_retried(make_ctx):
    incomplete = initial_json(categories=["entities_attributes", "business_rules"] * 4)
    llm = [incomplete, initial_json(), followup_json(True, 1), followup_json(True, 0), requirements_json()]
    ctx, backend = make_ctx(llm, ["a"] * (N_INITIAL + 1))
    s = _ready_session(ctx)
    interview.run(ctx, s)

    first_call = ctx.llm.logger.records[0]
    assert first_call["num_attempts"] == 2
    assert "volume_growth" in first_call["attempts"][0]["error"]


def test_mandatory_followup_cannot_be_skipped(make_ctx):
    # In the mandatory round the model says ready with no questions -> rejected -> it retries.
    llm = [initial_json(), followup_json(True, 0), followup_json(True, 2),
           followup_json(True, 0), requirements_json()]
    ctx, _ = make_ctx(llm, ["a"] * (N_INITIAL + 2))
    s = _ready_session(ctx)
    interview.run(ctx, s)

    assert s.interview.rounds_done == 2
    assert any("at least one follow-up question" in (a.get("error") or "")
               for r in ctx.llm.logger.records for a in r["attempts"])


def test_interview_stops_at_max_rounds(make_ctx):
    llm = [initial_json(), followup_json(False, 1), followup_json(False, 1), requirements_json()]
    ctx, _ = make_ctx(llm, ["a"] * (N_INITIAL + 2), interview_max_rounds=3)
    s = _ready_session(ctx)
    interview.run(ctx, s)

    assert s.interview.rounds_done == 3
    assert "maximum of 3 rounds" in s.interview.stop_reason


def test_interview_resumes_mid_round(make_ctx):
    # First run: the user answers 3 questions, then the program is interrupted.
    ctx, _ = make_ctx([initial_json()], ["a1", "a2", "a3"])
    s = _ready_session(ctx)
    try:
        interview.run(ctx, s)
    except AssertionError:  # ScriptedIO ran out of answers = simulated Ctrl+C
        pass

    saved = ctx.store.load(s.id)
    assert [q.answer for q in saved.interview.qa[:4]] == ["a1", "a2", "a3", None]

    # Second run (resume): only the remaining questions are asked; no new initial round.
    ctx2, backend2 = make_ctx([followup_json(True, 1), followup_json(True, 0), requirements_json()],
                              ["a"] * (N_INITIAL - 3 + 1))
    ctx2.store = ctx.store
    interview.run(ctx2, saved)
    assert saved.stage == Stage.DBMS
    assert len(backend2.calls) == 3  # follow-up, follow-up, requirements


# ---------------------------------------------------------------- orchestrator
def test_orchestrator_runs_until_unimplemented_stage(make_ctx):
    llm = [summary_json(), initial_json(), followup_json(True, 1), followup_json(True, 0),
           requirements_json(), dbms_json()]
    ctx, _ = make_ctx(llm, [""] + ["a"] * (N_INITIAL + 1) + [""])
    s = ctx.store.create("A dental clinic.")
    orchestrator.run(ctx, s)

    reloaded = ctx.store.load(s.id)
    assert reloaded.stage == Stage.DESIGN
    assert reloaded.dbms_choice.chosen.value == "postgresql"
    assert "not implemented yet" in ctx.io.output[-1]
    assert {"summary.md", "requirements.md", "dbms-choice.md", "session.json"} <= {
        p.name for p in ctx.store.dir(s.id).iterdir()}
    json.loads((ctx.store.dir(s.id) / "session.json").read_text())  # valid JSON on disk


def test_table_cells_are_escaped():
    from dba_agent.render.markdown import _cell
    assert _cell("cash | card\nor both") == "cash \\| card or both"
