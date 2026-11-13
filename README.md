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
dba info
```

## Usage

*TODO*

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
