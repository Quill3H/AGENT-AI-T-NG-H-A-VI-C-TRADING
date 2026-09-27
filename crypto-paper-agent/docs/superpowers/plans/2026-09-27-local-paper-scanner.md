# Local Paper Scanner Implementation Plan

> **For agentic workers:** This task is implemented inline in the current conversation. Do not delegate or self-accept. Steps use the project's paper-only safety contract.

**Goal:** Show a near-current BTC chart and a local BTC/ETH/SOL prospective paper session in the existing web console.

**Architecture:** A loopback-only Python service obtains public Binance USD-M futures candles, admits only complete and contiguous 15m/4h bars, and routes existing Trend Following signals through the existing PaperBroker. A Vite development proxy exposes the local read-only state to the existing React console; the static hosted preview remains an archived evidence viewer.

**Tech Stack:** Python standard-library HTTP service, requests, pandas, existing broker/strategy, React/Vite/Vitest, pytest.

**Spec:** `docs/planning/PRODUCT_CHARTER_AND_GATE_SPEC.md` G5 paper boundary; ADR 0007/0008; current owner request.

## Global Constraints

- Paper-only public data; no exchange order endpoint, API key, testnet or live orders.
- Retain source/event/receipt timestamps and exclude still-open candles from strategy decisions.
- Each symbol uses existing stop, sizing, risk, circuit breaker, fee, slippage and funding rules.
- If funding provenance, sequence, timestamp or source fails validation, stop admission and expose the failure.
- A new session starts from observation time; historical warm-up is never labeled prospective trades.
- A no-trade session remains a valid, honest result; this is not G5 acceptance or economic validation.

### Task 1: Multi-symbol broker baseline

**Files:** Existing broker and regression tests in commit `d6c639d`; no new implementation here.

- [x] Apply the tested multi-symbol/data-correctness commit to this feature branch.
- [x] Run its focused regression tests and inspect the resulting broker diff.

### Task 2: Public closed-bar source and paper session

**Files:** Create `src/paper/live_session.py`, `src/paper/local_server.py`, `tests/test_local_paper_session.py`.

- [x] Test that still-open, duplicate, gapped, malformed or stale bars never reach the broker.
- [x] Test startup baseline, three-symbol chronological batch, zero-trade status, and stop/idempotency.
- [x] Implement a bounded public REST source with exact funding provenance; call only `/fapi/v1/klines`, `/fapi/v1/fundingRate` and `/fapi/v1/time`.
- [x] Prime a fixed Trend Following rulebook from closed 4h history; do not backfill old trades.
- [x] Persist a session manifest and append-only event records in local, ignored runtime storage.

### Task 3: Existing web console integration

**Files:** Modify `web-preview/src/App.jsx`, `web-preview/src/styles.css`, `web-preview/vite.config.js`, `web-preview/src/App.test.jsx`; create a focused live panel module if needed.

- [x] Add UI tests for local auto-start, BTC/ETH/SOL scanning state, chart, zero trades and unavailable backend; verify stop in browser.
- [x] Integrate a chart and paper-session ledger with source/as-of/provisional timestamps and clear PAPER label.
- [x] Keep archived evidence separate from prospective local results and hosted static preview.

### Task 4: Verification and handoff

- [x] Run focused Python, frontend tests/build and a suitable offline suite.
- [x] Open local UI, verify chart, API and stop behavior in a browser; inspect console/network failures.
- [x] Self-review every order path; document exact branch/SHA, tests, failures and no-trade limitations.
