# FundingLens Check

A paid, applicant-facing readiness check. An applicant uploads a business plan, picks a checklist (a general one, or one built from a funder's **published** forms) and sees how well the plan covers it **before** submitting. It is a separate product from the organisation-side FundingLens AI and shares the `fundinglens_core` engine.

**What it never does:** predict a funder's decision, show a percentage score, or claim any funder's endorsement.

## How it works
- **Free quick scan** - band + counts only (server-side: no criterion names or advice are returned).
- **Full report** - every item, what was found, how to fix, the likely reviewer question, documents to prepare, self-confirm items, sources. 2 credits first time, 1 credit to re-check within 30 days. Idempotent (`Idempotency-Key`); if the report cannot be produced you pay 0.
- **AI notes are optional** and requested per report (`use_ai`), with PII redaction, quotation verification and a rules-only fallback.
- Invite-only signup, append-only credit ledger, provider-neutral signed payment webhook, 30-day retention, delete-check and delete-account.

## Run locally
```bash
pip install -r requirements-dev.txt
export ENVIRONMENT=development JWT_SECRET=$(python -c "import secrets;print(secrets.token_urlsafe(48))") \
       ADMIN_EMAIL=you@example.com ADMIN_PASSWORD='a-long-password-1'
uvicorn backend.app:app --reload     # http://127.0.0.1:8000
python -m unittest discover -s tests -t . -v
```
Sign in as the admin, create an invite on the Admin page, then sign up with it.

## Layout
`fundinglens_core/` engine (analysis, readiness language, templates, **published.py** funder packs, documents, ai) - `backend/` FastAPI app, billing, printable report - `frontend/` dependency-free SPA - `tests/` 116 tests - `scripts/` smoke test and source-drift monitor - `docs/`.

## Docs
`docs/DEPLOY_CHECKLIST.md` (step-by-step to a live demo) - `docs/PUBLISHED_PACKS.md` (how packs are built and must be reviewed) - `docs/LAUNCH_RISKS.md` (what is NOT done) - `CHANGELOG.md`.
