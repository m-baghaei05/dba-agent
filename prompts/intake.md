## Task: summarise the client's system description

Read the client's description and extract a structured summary that will guide a
database-design interview.

## Client's description
"""
{{ brief }}
"""
{% if previous %}

## Your previous summary
{{ previous }}

## The client's corrections
"""
{{ corrections }}
"""
Update the previous summary so it reflects these corrections. Keep everything else that was correct.
{% endif %}

## Guidelines
- **actors**: people, roles or external systems that use or feed the system.
- **entities**: things the system must store data about (usually nouns: Patient, Appointment,
  Invoice). Use singular names. An actor is also an entity if the system stores data about it.
  Give a few obvious example attributes for each; do not invent detailed ones.
- **processes**: the main things that happen (booking, paying, reporting) and who does them.
- **unclear_points**: ambiguities, gaps and contradictions to resolve in the interview,
  e.g. missing rules, unclear relationships, unknown data volumes.
- The description may be one line or several pages. For a short description, still produce
  your best summary and put everything you had to guess into **unclear_points**.
- Do not design tables yet.
