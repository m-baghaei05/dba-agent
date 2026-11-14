# DBA Agent — An LLM-Powered Database Design Assistant

A command-line agent that interviews a user about a system, chooses a relational DBMS,
produces consistent design documentation (with Mermaid diagrams), supports iterative
revisions, and generates executable `schema.sql` and `seed.sql` files.

Database Lab · Shiraz University · Fall 2026

> 🚧 Work in progress — sections marked *TODO* are filled in as the stages are built.

## Workflow

`Intake → Interview → DBMS selection → Design documentation → Revision loop → SQL generation`

*TODO: short description of each stage and its output files.*

## Installation

Requirements: Python 3.11+, Git. Docker is optional (only needed to run SQL on real servers).

```bash
git clone <repo-url> dba-agent
cd dba-agent
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
```

## Configuration

1. Copy `.env.example` to `.env` and add the API key for your provider.
2. Choose the provider/model in `config.yaml` (`active_profile`), or set `DBA_PROFILE`
   in `.env`. Every profile uses the OpenAI-compatible API, so switching needs no code changes.
3. Check the setup:

```bash
dba info      # active profile, model, whether the API key is set
dba models    # model IDs the provider offers (copy one into config.yaml)
dba ping      # one small structured request; logged to output/_ping/llm_calls.jsonl
```

## Usage

```bash
dba new --brief-file examples/test-scenario.md   # start a session from a file
dba new                                          # or type the description (finish with /end)
dba list                                         # all sessions
dba status [SESSION_ID]                          # progress of one session (default: latest)
dba resume [SESSION_ID]                          # continue where it stopped (default: latest)
```

During the interview, type `skip` if you don't know an answer; the agent will make a reasonable
assumption and mark it as such in `requirements.md`. Progress is saved after every answer, so
you can stop at any time (Ctrl+C) and resume later.

Each session has its own folder:

```
output/<session_id>/
  session.json        full saved state (used by `dba resume`)
  llm_calls.jsonl     every LLM call: stage, input, output, attempts, errors, latency
  summary.md          Stage 1: structured summary of the description
  requirements.md     Stage 2: numbered requirements (R-01…) + interview transcript
```

## Example run

*TODO*

## Project structure

```
config.yaml     provider profiles and workflow limits
prompts/        all LLM prompts (Jinja2 templates)
src/dba_agent/  application code
tests/          tests (run without any API calls)
docs/           architecture, report, critique, diagrams
examples/       test scenario and a complete example run
output/         generated sessions (not committed)
```

## Running tests

```bash
pytest
```
