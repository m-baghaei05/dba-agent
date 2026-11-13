# Prompts

All prompts used by the agent live here, outside the source code (spec, Technical Requirement ❷).
Each file is a Jinja2 template rendered with the data for its stage, e.g. `{{ summary }}`.

One file per LLM task, named after the stage it serves (added stage by stage):
`intake.md`, `interview_*.md`, `dbms_selection.md`, `design_model.md`, `normalization.md`,
`assumptions.md`, `revision.md`, `seed_data.md`, `sql_repair.md`.
