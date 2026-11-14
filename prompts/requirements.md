## Task: write the requirements from the interview

## System summary
{{ summary }}

## Interview transcript
{{ transcript }}

## What to produce
- **overview**: one paragraph describing the system, its users and its scope.
- **items**: the requirement statements, with at least one per category
  (entities_attributes, relationships_cardinality, volume_growth, access_patterns,
  transactions_concurrency, security_privacy, business_rules).

## Rules for each requirement
- Atomic and checkable: one fact or rule per item, with numbers and limits when known,
  e.g. "A patient can have at most one appointment per time slot."
- Write requirements, not design: say *what* must be stored or enforced, not which tables to create.
- **source = "user"** only for things the client actually said.
- **source = "assumption"** for anything you decided yourself, including every skipped or
  vague answer. Choose sensible, common defaults for this kind of system and state them precisely.
- Cover everything the client said; do not drop details that matter for the database.
- Do not number the items; numbering is done automatically.
