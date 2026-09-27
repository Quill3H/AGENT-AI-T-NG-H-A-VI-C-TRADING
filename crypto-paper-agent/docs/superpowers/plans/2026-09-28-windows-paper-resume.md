# Windows Paper Session Resume Implementation Plan

> Inline execution in this chat. No delegated agents or independent acceptance.

**Goal:** Restore a complete paper session after a Windows process restart when its persisted state and intervening market data can be verified.

**Architecture:** Save a versioned, typed broker/risk/strategy checkpoint in each committed journal state. On startup, validate the journal, configuration, restored accounting and rendered view before using the restored machine. Reconcile the closed-bar boundary from public USD-M REST before allowing the WebSocket to drive another broker step; retain `RECOVERY_REQUIRED` for incomplete evidence or an unprovable gap with exposure.

**Tech Stack:** Python 3.12, pytest, Windows PowerShell Scheduled Tasks, existing public Binance REST/WebSocket adapters.

**Spec:** `Project spec/CRYPTO_PAPER_TRADING_AGENT_MASTER_SPEC.md`, ADR 0006/0007, `docs/operations/PAPER_STREAM_API.md`.

## Global Constraints

- Paper-only BTC/ETH/SOL USD-M simulation, one 10,000 USDT starting account.
- Do not alter strategy thresholds, risk limits, funding provenance or order semantics.
- Preserve old journal bytes; legacy and invalid checkpoints stay read-only.
- A stopped bot must remain stopped across service restart.

### Task 1: Versioned exact state

**Files:** Create `src/paper/recovery_state.py`; modify `src/paper/durable_journal.py`, `src/paper/live_session.py`; test `tests/test_paper_resume.py`.

**Interface:** `capture_session(session) -> dict`, `restore_session(session, payload, saved_view) -> None`. Include broker identifiers, positions, pending orders/closes, trade/funding/account ledgers, breaker clock/rolling window, strategy setup and per-symbol processing marks. Reject missing or unexpected fields and non-finite values. The journal commits state and machine together.

- [ ] Add failing restart tests for flat, pending-order, open-position and settled-funding checkpoints.
- [ ] Add a typed allowlist codec and strict restore validation; run focused tests.
- [ ] Verify multiple restarts do not change IDs, fees, funding keys or money.

### Task 2: Reconcile downtime and service startup

**Files:** Modify `src/paper/live_session.py`, `src/paper/local_server.py`, `scripts/run_local_paper_web.py`; test `tests/test_paper_resume.py`, `tests/test_paper_windows_lifecycle.py`.

**Interface:** `LocalPaperSession.reconcile_resume() -> state`; server startup invokes it, and starts the public stream only when the session is eligible. No broker mutation during market check. A closed-bar gap with exposure or missing exact settlement evidence remains blocked. No-exposure gaps use existing documented rebaseline path after validation.

- [ ] Reproduce outage, stale feed, mismatch, duplicate stream and long downtime cases.
- [ ] Add gated startup, inspect API state/health and focused tests.
- [ ] Verify `POST /api/stop` persists a stopped bot while the service remains available.

### Task 3: Windows operation and handoff

**Files:** Modify `scripts/windows/*.ps1`, `docs/operations/PAPER_STREAM_API.md`, `docs/operations/LOCAL_PAPER_WEB.md`, project checkpoint/handoff.

- [ ] Test launcher conflict, process restart and journal ownership on Windows using isolated temp directories and ports.
- [ ] Document install, status, logs, stop, remove and plugged-in sleep setup without changing OS power settings.
- [ ] Run focused and full offline tests, review diff, commit and push the review branch; leave `main` untouched.
