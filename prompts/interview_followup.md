## Task: assess the interview so far and decide the next step

## System summary
{{ summary }}

## Interview transcript
{{ transcript }}

## What to produce
1. **coverage**: rate every category as `complete`, `partial` or `missing`.
   A category is `complete` when an experienced database designer could make all the related
   design decisions (tables, columns, keys, constraints, indexes) without guessing anything important.
   Categories: entities_attributes, relationships_cardinality, volume_growth, access_patterns,
   transactions_concurrency, security_privacy, business_rules.
2. **ready**: true only if the information is sufficient for a complete, correct database design.
   Minor details can become documented assumptions; they do not require more questions.
3. **reason**: one or two sentences explaining your decision.
4. **questions** for round {{ round_no }} (at most 6), targeting the most important gaps:
   - vague answers ("some", "it depends", "usually") that need a number, limit or rule;
   - skipped questions whose answer changes the design;
   - contradictions between answers;
   - relationships where one side ("one or many", "optional or required") is still unknown;
   - allowed values, statuses and what happens on delete (e.g. can a patient with invoices be deleted?).
   Do not repeat questions that were already answered clearly.
{% if must_ask %}

This is a **mandatory follow-up round**: you must ask at least one question, even if you
think the information is nearly complete. Ask about the weakest or vaguest answers.
{% endif %}
{% if last_round %}

This is the **last round**: ask only the questions whose answers matter most.
{% endif %}
