# Render transport and GitHub ledger plan

Owner selected no-card Free hosting and explicitly approved Render deployment of public repository. Gemini key was installed by owner as Render Secret File GEMINI_API_KEY. Existing public-clock probe from Singapore succeeds; GitHub EastUS is HTTP451.

## Design
GitHub Actions is the single durable writer on paper-state, serialised by concurrency. Render receives a signed state snapshot, runs a bounded speculative paper cycle, and returns a signed ledger plus evidence. It never receives a GitHub credential. The existing Gemini key derives a domain-separated HMAC transport key at each end; raw key never travels over transport. Verify body, timestamp, run id, base SHA and response signature before saving anything. Worker auth-token and lock files are never transferred.

Every response, including partial-cycle failure, carries the resulting state. Client atomically stages a complete response before workflow commits it. A remote result is provisional until GitHub persistence succeeds. If Render dies or HTTP response is lost, that uncommitted run is void; no exchange order exists, and the last GitHub ledger remains authoritative. Mark workflow failure, never claim an uncommitted paper entry. Duplicate requests in one process share a cached result; caller must not retry ambiguous POSTs automatically. State branch push is non-force compare-and-swap via normal fast-forward push; rejected push retains artifact and requires reconciliation.

Manual validation uses an explicitly labelled synthetic wallet state in an isolated validation directory. No original wallet resets or cutover. Only after tests, independent review, host/model verification and owner main-publication approval do we pause local heartbeat, capture original state, migrate and enable schedule. No venue substitution, trading keys, orders, billing upgrade or hidden risk changes.

## Files and checks
- scripts/cloud-transport.mjs: HMAC helpers and strict transferable-file names.
- scripts/render-service.mjs: authenticated /run endpoint, bounded body/cache/concurrency and safe temp lifecycle; /health and fixed public probes; public dashboard only reads committed state.
- scripts/render-cycle.mjs: Actions client, warmup, signed request/response, file staging and no automatic ambiguous retry.
- workflow: manual validation first; durable state/evidence on success or signed partial failure; no automatic schedule before cutover.
- Tests first: bad signature/expiry/traversal, missing key, auth/concurrency, response loss/partial failure, client rejects tamper/base mismatch, no credential files copied.

Limits: GitHub cron can be late/dropped; free Render sleeps and may suspend outbound use; application deadlines and original stale-data/replay gates still apply. Secrets match must be verified by authenticated smoke test without printing them. Free-tier account billing remains owner-controlled and unverified by code.
