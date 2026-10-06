# Changelog
## 0.1.1 - 2026-10-06
- Engine hardened against realistic plans (new `tests/fixtures`): values on the line after a label, "Year 1" no longer read as an amount, monthly figures annualised, more label variants (loan requested, owner's contribution, we request).
- New flag when the request or contribution written in the plan differs from the figures the applicant entered.
- "if any" and contradictory mentions handled; the report warns when a plan says an item is both done and not done.
- Applicant reports no longer contain officer wording.
## 0.1.0 - 2026-10-06
- First version: generic templates + CEDA published packs (agri, manufacturing, services; status `needs_human_review`).
- Free quick scan, paid full report, credit ledger, invite signup, signed payment webhook, retention and deletion.
- Per-report AI consent and an applicant-oriented AI prompt that never predicts approval.
- Web interface, Docker, CI (SQLite + Postgres + container smoke), weekly source-drift check.
