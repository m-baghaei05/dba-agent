# Test scenario: Dental clinic management

*Written for development and testing while the TA's official scenario.md is not available.
The agent must not depend on anything specific to this scenario.*

We are a private dental clinic with four dentists, two hygienists and three receptionists,
and we want a system to replace our paper records and Excel sheets.

Receptionists register patients and book appointments. A patient can book with a specific
dentist or with whoever is free. During a visit the dentist records the treatments done,
for example a filling on a particular tooth, a cleaning or an extraction, and may write a
treatment plan with several steps spread over future visits. Some patients have dental
insurance that covers part of the cost of certain treatments.

After each visit the receptionist issues an invoice. Patients often pay in instalments,
sometimes partly in cash and partly by card. We also want to see each patient's full history,
upcoming appointments for each dentist, unpaid balances, and monthly income per dentist.

Patients' medical notes (allergies, medications) must only be visible to dentists and hygienists.
