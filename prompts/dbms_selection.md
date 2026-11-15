## Task: choose the relational DBMS for this system

Candidates: **postgresql** (PostgreSQL), **mysql** (MySQL / MariaDB), **sqlite** (SQLite),
**sqlserver** (Microsoft SQL Server).

## System summary
{{ summary }}

## Requirements
{{ requirements }}
{% if previous %}

## Your previous decision
{{ previous }}

## The client's feedback
"""
{{ feedback }}
"""
Reconsider the decision in light of this feedback. If the feedback reveals a new requirement or
constraint, reflect it in the criteria, weights and scores; do not just change the answer.
{% endif %}

## What to produce
1. **criteria**: 4 to 10 criteria that genuinely matter for THIS system, derived from the
   requirements. Typical ones: concurrent writes, data volume and growth, reporting/analytical
   queries, integrity features (CHECK, foreign keys, transactions), security and roles,
   deployment and administration effort, cost and licensing, ecosystem and hosting options.
   - **weight** 1–5: how important the criterion is for this system.
   - **scores** 1–5 for every candidate: how well it satisfies the criterion.
   - **requirement_ids**: the R-xx IDs that make the criterion matter (only IDs listed above).
2. **chosen**: the candidate with the highest weighted total (sum of weight × score).
   Your choice must agree with your own scores; the tool checks this.
3. **justification**: one paragraph explaining the choice, citing requirement IDs.
4. **rejected**: one entry per candidate not chosen, with a concrete reason for this system.
5. **trade_offs**: honest weaknesses or risks of the chosen DBMS for this system.

## Be realistic
- SQLite is excellent for a single user or an embedded/offline app, but allows only one writer at a time.
- SQL Server is strong, but licensing and hosting cost matter for small organisations.
- Do not favour a DBMS by default; base every score on the requirements.
