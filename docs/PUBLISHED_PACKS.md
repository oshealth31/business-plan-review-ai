# Published-guideline packs

`fundinglens_core/published.py` encodes what a funder has made public, and nothing else. Rules (enforced by tests):
1. No numeric thresholds are invented. If the funder publishes no number, there is none.
2. Plan-content checks are **coverage** checks ("does the plan address what the form asks?"), never proof of quality.
3. Attachments are a "prepare these" list and are not scored; eligibility is confirmed by the applicant.
4. Each pack lists its sources, the date they were read (`RETRIEVED`) and a `review_status`.
5. Wording never implies endorsement; the source note states it is not produced, reviewed or endorsed by the funder.

## Before a pack is offered to paying users (human review)
- [ ] Open each source URL, compare with `published.py` line by line (criteria, attachments, self-checks, notes).
- [ ] Confirm the checklists are still current (the CEDA sector checklists read "Effective 20-02-17"; the 2020 guidelines are third-party and partly expired).
- [ ] Set `review_status` to `reviewed:<name>:<date>` and bump `PACKS_VERSION`.
- [ ] Ideally ask the funder to confirm, or move to a licensed `basis='funder'` pack.
- [ ] Run `python scripts/check_sources.py --update` in CI once to create `docs/sources.lock.json` (the sandbox could not reach ceda.co.bw), commit it; the weekly workflow then flags changes.

## Known gaps (as read on 2026-10-05)
No owner-contribution percentage was found in the retrieved CEDA pages; the form has no version/date; loan limits are from 2020.
