# Binance Public Stream Paper Backend Implementation Plan

> **For agentic workers:** Implement inline in this conversation. Do not delegate or self-accept. Use red/green tests for each task.

**Goal:** Drive a local BTC/ETH/SOL paper account from Binance USD-M public kline streams, with fail-closed reconnect and restart semantics plus a stable UI API.

**Architecture:** A public WebSocket worker delivers provisional 1m and closed 15m/4h notifications. Closed 15m batches are revalidated against public REST before PaperBroker mutation; REST is also used only for initial warm-up and bounded reconnect reconciliation. An append-only journal captures inputs and resulting account state. A restart with an earlier account is read-only RECOVERY_REQUIRED, never a new 10,000 USDT account or inferred replay.

**Tech Stack:** Python 3.12, websocket-client, requests, existing PaperBroker and TrendFollowingStrategy, pytest, loopback HTTP server and Windows Task Scheduler.

**Spec:** Product charter section 6, ADR 0007/0008/0011, current owner request.

## Global constraints

- Only Binance public USD-M market streams/REST GET; no key, account, order, testnet or wallet call.
- All simulated fills and accounting remain inside PaperBroker, with max 5x and mandatory directional stops.
- Only complete causal candles reach the strategy/broker; provenance and clock failures block admission.
- A gap may be skipped only when no open/pending paper exposure exists; never invent fills while disconnected.
- An existing journal is a persistent account identity. Without exact broker restore, restart is RECOVERY_REQUIRED and read-only.
- Do not edit web-preview source or Antigravity's branch. API examples and schema are backend-owned docs.

### Task 1: Stream input and connection gate

**Files:** Create `src/paper/public_stream.py`; modify `src/paper/live_session.py`, `src/paper/local_server.py`; tests in `tests/test_local_paper_stream.py`.

- [x] Test strict combined-stream symbol, interval, kline geometry, event time, close flag and duplicate handling.
- [x] Test that provisional candles update the display only, while closed 15m events from all three symbols trigger one chronological paper batch.
- [x] Implement public WebSocket worker with bounded reconnect/backoff and stream heartbeat. Connection loss immediately blocks new paper orders; reconnect checks REST continuity before resuming.
- [x] Test/implement gap reconciliation: journal skipped bars and rebaseline only with no open or pending exposure; otherwise RECOVERY_REQUIRED.

### Task 2: Durable paper account and API

**Files:** Modify `src/paper/live_session.py`, `src/paper/local_server.py`; tests in `tests/test_local_paper_session.py` and `tests/test_local_paper_server.py`.

- [x] Test journal writes before broker mutation and durable post-batch snapshots including order, position, fee/funding, wallet/equity and rejection state.
- [x] Test process restart with a prior journal: show the last account snapshot, block `/api/start`, preserve journal and 10,000-USDT initial identity; no silent reset or duplicate order.
- [x] Add `/api/health`, connection/risk state and timestamps without changing existing top-level UI fields; start/stop remain idempotent.
- [x] Check local-only Host/Origin, no JSON body and no external mutation surfaces.

### Task 3: Windows operation and evidence

**Files:** Create backend-only launcher and install/uninstall scripts under `scripts/windows/`; modify `scripts/run_local_paper_web.py`; add API schema/examples and operating guide under `docs/operations/`.

- [x] Test a duplicate port exits cleanly and does not create another account.
- [x] Implement login task registration/unregistration with restart-on-failure settings, log path and no npm install/build on each startup.
- [x] Run focused and full offline tests; run a bounded live public-feed observation, inspect API; restart the server and verify RECOVERY_REQUIRED.
- [x] Self-review all order paths, commit/push only the backend branch, report exact SHA and independent-review gap.
