# Not done yet - read before charging real users
- **Legal/privacy:** terms and privacy notice are placeholders (`TERMS_VERSION=draft-...`). Business plans are personal/commercial data: get Botswana data-protection advice, name a controller, define AI-provider terms.
- **Accounts:** no email verification and no password reset (admin can reset a password).
- **Storage:** plans sit unencrypted on disk until retention expiry (default 30 days); use encrypted disks/object storage in production.
- **Payments:** provider undecided; the webhook is provider-neutral and needs a small adapter. Unmatched payments are reconciled by the admin.
- **Published packs:** compiled by automated reading; `needs_human_review`. CEDA has not endorsed them.
- **Scale:** rate limiting is per process (use one instance or add a shared limiter); free hosting sleeps and may lose disk.
- **Org product:** not restructured to import `fundinglens_core` yet; do that so both products share one engine.
