# Paper Bot Studio cloud candidate — NOT DEPLOYED

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
