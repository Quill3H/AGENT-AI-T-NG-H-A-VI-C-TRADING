# Kronos Gemini Advisory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Supply causal pinned Kronos forecasts to the three existing deployed Gemini paper wallets.
**Architecture:** Authenticated Render input capture; Actions CPU inference; authenticated forecast transfer; strict context binding at Gemini admission. Original wallet schema and execution rules remain unchanged.
**Tech Stack:** Node.js 22, Python 3.12, PyTorch CPU, Kronos-small, GitHub Actions, existing Render service.
**Spec:** ../specs/2026-11-02-kronos-gemini-advisory-design.md (owner approved in chat).

## Global Constraints

- Paper only; preserve paper-state-okx and all three wallets.
- Fixed upstream/model revisions; 40 closed candles, four future candles, seed123, T1, top_p0.9, sample_count3.
- No new entry on unavailable/mismatched forecast. Reconcile existing positions first.
- Existing authenticated transport, context expiry and admission checks remain enforced.
- No billing upgrade or paid service.

## Review Focus

- Stale/reordered/tampered candles and forecast identities fail closed.
- Forecast failures must not prevent existing-position reconciliation or silently fall back to Gemini-only entries.
- Due frames must be independent, including partial input/inference failure.
- Slow inference must not renew the current cycle or entry context lifetime.
- Deployment uses the matching Render runtime and Actions workflow, preserving ledger history.

## Task 1 — forecast contract and input endpoint

Files: scripts/kronos-advisory.mjs and tests; scripts/render-service.mjs.
- [ ] RED: tests for hash identity, timeframe, expiry, finite values, authenticated capture and no state writes.
- [ ] GREEN: normalized input contract, read-only endpoint, strict forecast validator.

## Task 2 — pinned CPU worker and cloud integration

Files: scripts/kronos_forecast.py, scripts/requirements-kronos.txt, scripts/prepare-kronos.mjs, scripts/render-cycle.mjs, scripts/gemini-paper.mjs and integration tests.
- [ ] RED: missing/mismatched forecasts cannot reach entry analysis; settlement still runs; successful forecasts enter prompt and evidence.
- [ ] GREEN: Actions helper captures authenticated input and invokes Python; forecast result travels in signed cloud request and is validated against actual context.
- [ ] Real pinned-model inference, malformed input tests and existing cloud regression suite.

## Task 3 — evidence, workflow and deployment

Files: .github/workflows/paper-bot-studio.yml, paper-bot-studio/dashboard.js, operator docs/review handoff.
- [ ] Persist advisory evidence and expose availability in decision detail without changing wallet schema.
- [ ] Add cached Python/model bootstrap to Actions and application deadline.
- [ ] Separate Tester and Reviewer; resolve findings and rerun scoped checks.
- [ ] Publish runtime and workflow, verify one bounded cloud cycle and durable forecast evidence. If external access blocks deployment, identify exact blocker without claiming activation.

## Ledger

- Started from clean separate cloud checkout main df07280de7dc5fb19c334d17a4d356ed102902e4 on codex/kronos-gemini-advisory. Primary research checkout's unrelated uncommitted files preserved.
- Ruling: use seed123 matching installed smoke, an explicit reproducibility setting; no economic parameter selection implied.
# Cloud recovery follow-up — 2026-11-03

Owner explicitly requested applying Kronos and running the existing free bots. PR14 integrated at b59872f and Render bb87caf reports kronosProtocol1. Linux dependency installation and95Node/3Python checks passed. First real run41572263004 failed waiting for /run headers after300seconds; no authenticated batch or ledger commit occurred. The360second application budget allowed this transport timeout to discard provisional catch-up progress.

Scope of follow-up: cap cloud cycle at180seconds and propagate its deadline into every queued/paced/in-flight OKX request, preserving the last completed replay checkpoint and signed recovery response. Add meaningful queued-deadline and in-flight abort tests; independently review/test, deploy matching runtime and verify a signed partial/success batch actually commits before declaring recovery fixed. Existing state must not be reset or manually advanced. Linux model inference and advisory entry evidence remain separately required.

# Exact no-touch replay coverage follow-up — 2026-11-03

Observed100BTC native trades span roughly0.8seconds, making a100minute backlog impractical within a free cloud request. Use closed confirmed1m OKX trade-price OHLC solely as a no-touch proof for positions with no management history: require contiguous full coverage, valid prices and strict containment between unchanged TP/SL; retain source/bars/window. Stop before the first candle that could touch either level and use the original chronological native replay for that minute/current open minute. Missing coverage uses native replay, malformed confirmed data fails closed, and positions with management events keep native replay throughout. No fill, order, funding, strategy or risk calculation is inferred from candles. Independent tests and review are required before rollout.

