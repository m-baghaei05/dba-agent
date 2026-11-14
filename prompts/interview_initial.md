## Task: first round of interview questions

You are about to interview the client to collect the requirements for this system's database.

## System summary
{{ summary }}

## What to produce
Write the first round of questions: **7 to 14 questions, at least one for each category**:

| category | what you need to learn |
|---|---|
| entities_attributes | which data must be stored for each entity; required vs optional fields; identifiers |
| relationships_cardinality | how entities relate: one or many on each side, optional or mandatory |
| volume_growth | how many records now, how fast they grow, how long data is kept |
| access_patterns | what is read or written most often; searches; reports and statistics needed |
| transactions_concurrency | operations that must succeed or fail together; simultaneous users editing the same data |
| security_privacy | user roles and what each may see or change; sensitive or personal data |
| business_rules | rules, limits, allowed values, statuses and their transitions, uniqueness |

## How to ask
- Ask in plain business language. Instead of "What is the cardinality between X and Y?",
  ask "Can one appointment include several treatments?"
- One topic per question; make each question answerable in a sentence or two.
- Be concrete: use this system's entity names and realistic examples.
- Turn the summary's **unclear_points** into questions.
- In `why`, say in one short sentence what design decision the answer affects.
