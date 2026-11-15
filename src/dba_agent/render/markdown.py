"""Deterministic Markdown rendering for the requirements phase (no LLM involved).

The LLM produces structured data; these functions turn it into documents. Same data in,
same document out, which makes the outputs predictable and easy to test.
"""

from __future__ import annotations

from dba_agent.schemas import (CATEGORY_TITLES, DBMS, DBMS_NAMES, QA, Category, DBMSChoice, Requirement,
                               SystemSummary)


def _cell(text: str) -> str:
    """Make text safe inside a Markdown table cell."""
    return " ".join(str(text).split()).replace("|", "\\|")


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {i}" for i in items) if items else "- (none)"


def render_summary(s: SystemSummary) -> str:
    entities = "\n".join(
        f"| {_cell(e.name)} | {_cell(e.description)} | {_cell(', '.join(e.example_attributes)) or '—'} |" for e in s.entities
    )
    processes = _bullets(
        [f"**{p.name}**: {p.description}" + (f" *(by {', '.join(p.actors)})*" if p.actors else "")
         for p in s.processes]
    )
    return f"""# System Summary: {s.system_name}

**Domain:** {s.domain}

**Purpose:** {s.purpose}

## Actors
{_bullets([f"**{a.name}**: {a.description}" for a in s.actors])}

## Candidate entities
| Entity | Description | Example attributes |
|---|---|---|
{entities}

## Main processes
{processes}

## Points to clarify
{_bullets(s.unclear_points)}
"""


def number_requirements(items) -> list[Requirement]:
    """Assign R-01, R-02, ... grouped in the fixed category order."""
    ordered = sorted(items, key=lambda i: list(Category).index(i.category))
    return [Requirement(id=f"R-{n:02d}", **i.model_dump()) for n, i in enumerate(ordered, start=1)]


def render_requirements(system_name: str, overview: str, reqs: list[Requirement], qa: list[QA]) -> str:
    sections = []
    for cat in Category:
        rows = [r for r in reqs if r.category == cat]
        lines = "\n".join(
            f"| {r.id} | {_cell(r.text)} | {'User' if r.source == 'user' else 'Assumption'} |" for r in rows
        )
        sections.append(f"### {CATEGORY_TITLES[cat]}\n| ID | Requirement | Source |\n|---|---|---|\n{lines}")

    n_assumed = sum(r.source == "assumption" for r in reqs)
    transcript = []
    for rnd in sorted({q.round for q in qa}):
        transcript.append(f"\n### Round {rnd}" + (" (initial)" if rnd == 1 else " (follow-up)"))
        for q in (q for q in qa if q.round == rnd):
            answer = q.answer if q.answer else "*(skipped — the agent decides and records an assumption)*"
            transcript.append(f"- **[{CATEGORY_TITLES[q.category]}] {q.question}**  \n  {answer}")

    return f"""# Requirements: {system_name}

## Overview
{overview}

{len(reqs)} requirements, of which {n_assumed} are assumptions made by the agent
(marked "Assumption") and should be confirmed by the user.

## Requirements by category

{(chr(10) * 2).join(sections)}

## Appendix: Interview transcript

{chr(10).join(transcript)}
"""


def render_dbms_choice(system_name: str, choice: DBMSChoice) -> str:
    chosen = DBMS_NAMES[choice.chosen]
    order = [choice.chosen] + [d for d in DBMS if d != choice.chosen]  # chosen first

    def head(d: DBMS) -> str:
        return f"**{DBMS_NAMES[d]}**" if d == choice.chosen else DBMS_NAMES[d]

    rows = []
    for c in choice.criteria:
        scores = " | ".join(str(c.scores[d]) for d in order)
        based_on = ", ".join(c.requirement_ids) or "—"
        rows.append(f"| {_cell(c.name)} | {c.weight} | {based_on} | {scores} | {_cell(c.note)} |")
    totals = choice.totals()
    total_row = " | ".join(f"**{totals[d]}**" if d == choice.chosen else str(totals[d]) for d in order)

    rejected = {r.dbms: r.reason for r in choice.rejected}
    why_not = "\n".join(f"- **{DBMS_NAMES[d]}**: {rejected[d]}" for d in order[1:])

    return f"""# DBMS Choice: {system_name}

## Decision
**{chosen}**

{choice.justification}

## Comparison
Scores: 1 = poor fit, 5 = excellent fit. Weight: importance for this system (1–5).
Weighted total = sum of weight × score, computed by the tool.

| Criterion | Weight | Based on | {" | ".join(head(d) for d in order)} | Notes |
|---|---|---|{"---|" * len(order)}---|
{chr(10).join(rows)}
| **Weighted total** | | | {total_row} | |

## Why not the others
{why_not}

## Trade-offs of {chosen}
{_bullets(choice.trade_offs)}
"""
