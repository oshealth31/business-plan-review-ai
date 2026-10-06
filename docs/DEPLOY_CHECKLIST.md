# Deploy checklist - from zero to a live demo
1. [ ] Create a **private** GitHub repo; push this folder. Confirm `.env` is not committed.
2. [ ] Actions tab: confirm `ci` is green (sqlite tests, Postgres API tests, container smoke). Fix before continuing.
3. [ ] Create a managed Postgres (Neon/Supabase/Render free tier). Copy its URL as `postgresql+psycopg://...`.
4. [ ] On Render: New > Blueprint > pick the repo (`render.yaml`). Set `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `DATABASE_URL`. `JWT_SECRET` and webhook secret are generated.
5. [ ] Persistent storage: uploaded plans live on disk (`DATA_DIR`). Free tiers lose disk on redeploy - attach a disk or accept that demo plans vanish.
6. [ ] Wait for deploy; run `python scripts/smoke_test.py https://<your-app>`.
7. [ ] Sign in as admin; create an invite with 6 credits; sign up in a private window; run a quick scan with `demo_data/business_plan_demo.txt`; unlock a report.
8. [ ] Check `/api/health/ready` is 200. Set an uptime monitor on `/api/health`.
9. [ ] Run `python scripts/check_sources.py --update`, commit `docs/sources.lock.json`; enable the weekly `published-source-drift` workflow.
10. [ ] Do the human review in `docs/PUBLISHED_PACKS.md`; hide CEDA packs from the demo until done if unsure.
11. [ ] Payments (optional for demo): pick a provider, put payment links in `PACKS_JSON`, point its webhook adapter at `/api/payments/webhook` (HMAC-SHA256 of `timestamp.body`, headers `x-fl-timestamp`, `x-fl-signature`).
12. [ ] Share only with invited testers. Do not charge real money before `docs/LAUNCH_RISKS.md` is cleared.
