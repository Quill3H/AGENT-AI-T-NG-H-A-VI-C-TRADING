# OKX Paper Bot Studio — current operation

Owner approved PR12 merge and schedule activation on2026-11-02. Main integration commit: df07280de7dc5fb19c334d17a4d356ed102902e4. The approved workflow runs at minutes02,17,32,47 each hour and supports manual dispatch. Render currently runs the reviewed runtime at e9eef3e; subsequent commits through this merge only changed documentation/workflow configuration. Render remains sourced from codex/paper-cloud-probe, so future runtime changes on main require an explicit corresponding deployment.

Dashboard: https://paper-studio-connectivity.onrender.com/ . Authoritative durable ledger: paper-state-okx. Three fresh OKX wallets started at100USD each; original Binance history and local automation remain separate and unchanged. Never copy the isolated smoke position into the production ledger, reinitialize this branch, or replace its state with a stale local checkout.

First production run41420089050 passed85offline checks, but Gemini's ETH LONG was rejected by the unchanged quantity gate. The execution-time quote is not retained for this rejected entry, so its exact quantity-limit cause cannot be reconstructed from the artifact. The signed rejection, context and intent were successfully committed at fcf035c37f7ede53919ffd458957d5b6c9b4274a; all balances remain100and there are zero trades. Public /api/state returned200and the dashboard rendered the committed ledger. This verifies persistence on a rejected cycle, not a successful production fill, funding debit or closure. The earlier isolated smoke did exercise a paper entry and replay.

Funding is an approved estimate from actual realizedRate and the confirmed1m mark close immediately before settlement, with source/method metadata. Runtime and dashboard retain PAPER_ONLY. Cron can be late; missed entry boundaries are skipped. TP/SL is reconciled on each cloud run, not monitored continuously. Credential configuration and successful inference do not establish billing tier or guarantee future quota/uptime. No billing upgrade is authorized.

The sections below are historical setup notes, superseded by the current operation above and CLOUD_VERIFICATION_2026_11_02.md. In particular, the earlier migration/paper-state/manual-only instructions do not apply to the owner-selected fresh OKX ledger.

## Current Render transport (supersedes direct Actions execution below)

Render Singapore public clock probe succeeds; direct GitHub EastUS Binance returns451. Server scripts/render-service.mjs loads GEMINI_API_KEY environment or /etc/secrets/GEMINI_API_KEY Secret File. It stages an authenticated paper run; scripts/render-cycle.mjs on GitHub verifies the response and installs the whole batch before creating .cloud-ready. Only a full authenticated batch is eligible for state-branch commit. A signed cycle error can still return partial progress, which is preserved; an absent/invalid response or failed install cannot publish state.

Render never receives a GitHub write credential. Key-derived domain-separated HMAC authenticates transport; raw API key is never sent. Runtime auth-token/worker.lock are excluded. A response lost on restart is provisional and void, not a committed paper trade. The client must start from a fresh checkout after any failed install; dirty artifact evidence is not the authoritative ledger.

Initial workflow validation uses synthetic wallets under cloud-validation, never original state. For final activation: owner approves main integration, manual production run, one-way cutover with local heartbeat/worker paused and consistent state captured, then schedule. Original wallets must not be reset. Hosted startup sleeps, cron lateness/drop, quota and no guaranteed uptime remain explicit limits. No billing upgrade is performed.

Owner selected Gemini API free tier. Implementation lives in scripts/gemini-paper.mjs; manual workflow in .github/workflows/paper-bot-studio.yml. Original runtime and ledger were not modified. No local state/auth-token was copied or published.

Required before activation:
1. In a Google AI Studio project explicitly on Free tier, obtain an API key. Do not enable billing to bypass quota. Confirm a supported text model and its actual quota; three frames need up to 126 entry calls/day, plus review calls. Hitting quota fails closed.
2. Save it as repository Actions secret GEMINI_API_KEY; save supported model ID as Actions variable GEMINI_MODEL. Do not send keys in chat or commit them.
3. Complete runner orchestration integration tests and independent review. Existing tests cover runtime safety and Gemini helpers, not a real Gemini cloud cycle.
4. Publish reviewed source to main. At cutover, stop original local heartbeat/worker, copy one consistent state.json into dedicated paper-state branch, preserving history and context snapshot evidence. Never put auth-token/worker.lock there. Do not run cloud and local writers concurrently.
5. Dispatch one manual workflow; verify recorded balances, decisions, funding, reviews, model identity, persistence after failure and restart. Workflow is intentionally manual until this passes.
6. Add schedule only after acceptance. GitHub may delay/drop scheduled runs; original 10-minute entry lateness and 47-hour replay limits remain. Dashboard Pages publication is not yet implemented.

Incomplete-cycle intents block same-cycle retries for manual reconciliation rather than repeat position management. These intents are persisted with the ledger. Logs/artifacts may contain paper research data, never API keys.

The runner has an application deadline, plus a 9-minute shell ceiling inside the 12-minute job. This reserves time for ledger push and recovery artifacts. GitHub runner loss or hard job cancellation can still prevent persistence; never treat always() as a durable external transaction. Compare remote state commit and artifacts after failure before retry/cutover. Do not run a second writer during reconciliation.

Checks: copied runtime plus initial Gemini helper suite: 45 passed, 0 skipped. After review fixes, helper suite: 5 passed. No live Gemini inference, Linux Actions run, state cutover or dashboard publication has been verified.

Sources: https://ai.google.dev/gemini-api/docs/pricing ; https://ai.google.dev/api/generate-content ; https://github.blog/changelog/2026-07-01-github-models-is-being-fully-retired-on-July-30-2026/
