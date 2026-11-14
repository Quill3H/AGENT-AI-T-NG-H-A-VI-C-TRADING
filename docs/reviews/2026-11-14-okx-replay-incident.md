# OKX Paper Bot Studio: dense-replay incident

Scope: native historical replay and recovery, not strategy profitability or a whole-repository audit. Base: `9f7473cc9e5fc16933ac2f52671f16eca0e504e1`. Branch: `codex/fix-okx-dense-replay`.

## Observed production failure

Actions run https://github.com/Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING/actions/runs/43592442015 fails in the Render cycle with `Worker replay/funding failed: 15m: AI-15m-1793921400000: OKX one-minute replay exceeded bounded page coverage`. The diagnostics report 128 history-trades requests and no Gemini attempts. Offline checks and ledger preservation succeed. Node action deprecation warnings are not this failure's cause.

The committed open BTC short is blocked at replayTime `1794174899999`. Public OKX calls using the exact timestamp show 100 transactions spanning only 20 milliseconds near the requested minute's end. Pagination by string native trade ID moves correctly. The fixed one-minute window exhausts 128 pages before reaching its lower boundary, discards progress, and repeats the same failure next run.

API reference: https://www.okx.com/docs-v5/en/#order-book-trading-market-data-get-trades-history (type 2 timestamp initial lookup; type 1 trade-ID backward continuation; maximum 100 records per page).

## Change

After eight pages without full lower-bound coverage, halve the requested time prefix and restart the timestamp query. Discard the unproven suffix. Retain the total 128-request bound, shared deadline, strict native ID/timestamp checks, and failure on an uncovered one-millisecond interval. Return only fully verified `(from, through]` events, chronologically ordered by native IDs.

For an immediately adjacent next request, start from twice the previously covered duration, capped at one minute. This avoids repeatedly paying the full shrink cost and lets the window grow after a dense burst. It is a query-size hint, never proof of coverage.

No changes to server tick/manage callers, funding semantics, TP/SL, allocation, fees, model, cloud credentials or authoritative ledger. Existing worker partial-progress persistence handles the returned prefix; incomplete catch-up remains visible and blocks entries.

## Verification

Deterministic dense-minute regression fails with the original production error before the fix. New tests check exact native IDs across adjacent prefixes, equal-timestamp batches with IDs above 2^53, bounded requests, growth after a burst, and fail-closed behavior at minimum duration. Existing runtime tests cover rollback when funding fails and first-touch accounting.

Commands:

```sh
node --test scripts/cloud-transport.test.mjs scripts/render-transport.integration.test.mjs scripts/gemini-paper*.test.mjs scripts/kronos-advisory.test.mjs scripts/prepare-kronos.test.mjs paper-bot-studio/*.test.mjs
python3 scripts/test_kronos_forecast.py
git diff --check
```

Final evidence and independent review are recorded in the delivered incident report. Historical live probes use a copied ledger only. A successful prefix is not proof of a successful scheduled workflow or successful Gemini inference.

## Separate review finding

Funding always starts its retention check from `trade.openedAt`. A position open longer than 89 days can fail permanently even if previous funding was processed. This is not the present incident (the blocked position is much newer). Correcting it needs a durable funding-coverage checkpoint and delayed-publication policy, not substituting `lastFundingCheckedAt` for proven coverage. Deferred to a separate accounting change.

## Release boundary

This patch must reach the Render service, which executes `OkxMarket`, as well as GitHub source. Updating only the Actions runner cannot repair old deployed Render code. After authorized publication/deployment, execute one paper workflow, inspect signed recovery and committed ledger, verify no reset/duplicate fees, and inspect remaining model or inference failures separately. Do not reset wallets or declare unverified replay complete to obtain a green job.

## Final results (2026-11-14)

AUTHOR_VERIFIED: final workflow Node suite 116 pass, 0 fail/skip; Kronos Python validation 3 pass; `git diff --check` clean. Independent reviewer Dirac verified 35 focused tests plus boundary assertions: 12,799 same-millisecond events plus boundary fit 128 pages; 12,800 plus boundary fail closed. No remaining patch-correctness blocker for adapter SHA-256 `292cff7599db9693532b213a767f6e182b453513c788190e16faa0980379ec56`, dense-test SHA-256 `86edde2f308c4ac6cf92d7663460531ab8c666fe0bedf9a0d642c2d8ef2a26d8`.

Real historical replay using the final adapter and copied ledger advanced from `1794174899999` to `1794174914073` (14.074 seconds of very dense history), with funding validation, before the shared 180-second deadline. It made 717 public requests across replay/candle/funding endpoints. The position remained OPEN; no full closure or end-to-end cloud recovery is claimed. The signed cloud partial-progress persistence has passing integration coverage, but production recovery after deployment remains NOT_VERIFIED. Further scheduled runs must carry the authoritative saved prefix forward; no fake completion or entry bypass is introduced.

No GitHub branch was pushed, no Render deployment was performed, and no production ledger was changed. Publication requires the owner authorization prescribed by AGENTS.md for external mutations. GitHub CLI is not authenticated in this environment. Browser authentication was sufficient to inspect Actions.

## Authorized deployment and preparation optimization

Owner approved publication, deployment and useful optimizations. PR #20 merged as `f82f5605a32a24cba6449490fe5f4628474ac05c`, primary checkout synchronized, Render deployment `dep-dbs8nnk9v7es73c1c4j0` reports Live; `/health` returned PAPER_CLOUD. Render source branch changed to main (auto-deploy stays off), and build syntax checks now cover render-service.mjs and okx-market.mjs instead of the obsolete connectivity probe.

Run `43615773260` exercised the deployed patch: signed partial ledger was committed and replayTime advanced from 1794174899999 to 1794174913979. It still failed honestly at the 180-second recovery deadline before Gemini. A second manual run was started to continue from the committed boundary.

The next small optimization shares the existing due-frame selector with an early workflow preflight. Pip install, pinned Kronos source checkout, model cache and inference are skipped when no frame is eligible. Python validation, Render recovery and signed ledger preservation remain unconditional. An empty advisory bundle is initialized for the skipped branch. Preparation rechecks eligibility if bootstrap was selected. A frame becoming due after skipped bootstrap waits for a later scheduled run; the existing missing-advisory gate still blocks entry.

Author verification for this change: 118 Node tests, 3 Python tests, Ruby YAML parse and `git diff --check` pass. No global suppression based on stale wallet.blocked or worker.healthy flags was added. Independent review and live workflow observations are recorded in the task delivery report.
