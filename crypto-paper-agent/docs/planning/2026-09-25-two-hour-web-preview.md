# Two-hour paper-bot web preview task

## Authority and timebox

Owner instruction received 2026-09-25 (Asia/Bangkok): use the installed skills
and commands proactively, finish the safest useful web demo within a hard
two-hour execution window, and deploy it so the owner can inspect the app.
Stop expanding scope when the timebox expires; ship an honest partial preview or
report a concrete blocker instead of claiming completion.

This is a presentation and operator-access task for the existing paper/research
system. It does not accept pending engineering gates and does not authorize live
or testnet orders, exchange trading credentials, private keys, wallet signing,
withdrawals, production promotion, or a profitability claim.

## Required PM route

1. Recheck repository root, `main`, HEAD, origin/main, working tree, current
   project checkpoint and latest review. Preserve `.serena/` and unrelated
   owner-local changes.
2. Inspect the repository for an existing web surface. If none exists, choose
   the smallest deployable read-only dashboard that fits the current stack and
   timebox. Prefer committed/synthetic/demo artifacts; do not require a private
   exchange account or a long historical download.
3. Use the available equivalents of: planning; frontend implementation;
   `crypto-bot-engineering` for domain semantics; TDD/testing; security review
   for inputs/secrets; verification; and deployment. Explicit `$skill-name` is
   optional because PM must auto-route. A `/command` is allowed only when the
   current harness actually registers it.
4. Keep the UI honest: label PAPER/RESEARCH, show data source and timestamps,
   distinguish `VERIFIED`, author-reported and `NOT_VERIFIED`, and never imply
   live fills or future profitability. Prefer read-only reports, run metadata,
   risk/accounting status and a bounded offline demo action.
5. Build and run focused tests. Start the app locally and verify the complete
   visible flow in a browser, including console/network errors and at least one
   representative demo/report path. Capture evidence or screenshots when the
   harness supports it.
6. Deploy a **preview** using an already authenticated provider/CLI (Vercel is
   preferred when compatible). Never commit or print tokens. If authentication,
   provider access or required environment variables are missing, mark deploy
   `BLOCKED`, preserve the verified local demo, and provide the exact owner step
   needed. Do not silently create a paid resource or production deployment.
7. Report the preview URL, provider status, exact commit/SHA, files changed,
   build/test/browser results, known limitations, rollback/removal instructions
   and whether local `main`, origin/main and GitHub main match. Do not call the
   broader trading project complete solely because the web preview works.

## Completion trigger and watcher

After dispatch, record `threadId`, `hostId` and the latest wait cursor. Use
Codex `wait_threads` with `afterCursor` as the completion watcher. Do not create
a loop that repeatedly calls `list_threads`, `read_thread`, Git status, or
`wait_threads` after unchanged timeouts. The watcher should surface only:

- completed with preview URL and verification summary;
- failed/blocked with exact cause and required owner action;
- explicit approval or input request;
- a meaningful gate/status transition.

Unchanged progress is silent. A scheduled fallback monitor, if used by the
host, must follow the same notification rule and stop after a terminal result.

## Definition of done for this timebox

- A usable browser-visible paper/research demo exists locally.
- The core displayed flow was verified with fresh evidence.
- A preview URL is live, or deployment is explicitly `BLOCKED` only by an
  external credential/account/provider condition.
- No trading credentials or live-order path were introduced.
- The PM handoff distinguishes web-demo completion from project/gate acceptance.
