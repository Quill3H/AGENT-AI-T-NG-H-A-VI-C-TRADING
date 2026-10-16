# Shared causal runner implementation plan

## Current publication checkpoint - 2026-10-17

Implementation and regression files are included in the GitHub candidate.
Use the [current handoff](../../handover/2026-10-17-github-checkpoint.md) for
the repaired code SHA, fresh offline/web/build results and remaining gates.
The older combined verification checklist below is historical: unperformed
clean-checkout/browser/public/scheduled-operation checks remain NOT_VERIFIED.
Independent review and owner acceptance remain pending.

## Prior execution addendum - 2026-10-02

S3 implementation is present as an **AUTHOR_SELF_REVIEWED candidate**, not
independent acceptance. Later express owner authorization permits helper
agents; the original inline-only paragraph remains a historical decision.
Helper review is not an independent verdict. The original TDD checklist below
is retained without inventing final repaired-code test execution.

- [x] `causal_runner.py`, `history_source.py` and `replay_session.py` implement
  one shared BTC/ETH/SOL chronological broker runner, retained feature prefix,
  full paginated gaps and verified synchronized closed-bar admission.
- [x] Exact positions/pending entries/closes/fees/funding/risk restoration and
  no reset/duplicate processing have executable recovery/long-gap tests.
- [x] Post-checkpoint repairs cover ledger-exposure reconciliation, valid
  halted/partial-position restore, request-time pause/stop handling, paused
  setup expiry and honest older REPLAY versus matching fresh REALTIME batches.
- [x] Regression files exist: `test_paper_causal_runner.py`,
  `test_paper_replay_recovery.py`, `test_paper_replay_review_fixes.py`,
  `test_paper_exposure_reconciliation.py`, `test_paper_scheduled_partial_restore.py`
  and `test_paper_request_time_controls.py` in `crypto-paper-agent/tests`.
- [ ] Final repaired SHA and exact-commit focused/full/historical/clean/public
  evidence: pending root finalization. `c89333516f9032155923375a876d0350deb6c267`
  is only the earlier checkpoint; its results cannot certify subsequent repairs.

Replay may generate modeled trades from historical inputs, but never passes a
future downloaded suffix to an earlier decision. Unknown legacy/invalid inputs
remain RECOVERY_REQUIRED. Short public reception or fixture crash/restart does
not prove a real trading signal, economic quality, power-loss safety or uptime.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline; no subagents.

**Goal:** Resume the same account across arbitrarily many paginated closed bars, with the same decisions/accounting as uninterrupted processing.

**Architecture:** A data-only `CausalRunner` owns broker, strategy setup and watermarks; SQLite stores its financial history separately and retains the exact signal prefix. `PaperReplaySession` provides transport/display/API without duplicating broker accounting. The existing v2 session remains the legacy verifier and is not used for new accounts. Full catch-up is active trading, not a skipped baseline.

**Tech Stack:** existing PaperBroker, pandas fallback features, sqlite3, public requests/WebSocket, pytest.

**Spec:** `docs/superpowers/specs/2026-10-01-windows-paper-replay-design.md`, sections 3–6, 9–10.

## Global constraints

- Canonical UTC synchronized BTC/ETH/SOL closed bars; deterministic symbol order.
- Signals only see their closed prefix; entry on next eligible open through broker gates.
- Fixed funding never fakes public source metadata. Old public obligations cannot be erased by migration.
- Advance in-memory state/watermark only after durable transaction commit.
- Freeze catch-up target; max three attempts per failed public page; no last-500 truncation.
- Keep unknown/corrupt/unsupported legacy states read-only; main untouched.

## Task 1: Pure runner and exact compact state

**Files:** Create `crypto-paper-agent/src/paper/causal_runner.py`; extend typed record allowlist in `recovery_state.py`; test `tests/test_paper_causal_runner.py`.

**Interfaces:** `CausalRunner(config, recipe_name, available_at)`, `initialize(warmup, baseline)`, `advance(bars, signals=None, mode='REPLAY')`, `capture() -> dict`, `restore(config, checkpoint, inputs, events) -> CausalRunner`.

- [ ] RED tests: a real pending LONG fills once on the next bar, SHORT accounting, settlement across many bars, malformed third symbol rolls back, exact recovery of pending/active exposure/breaker, stable indicator prefix, future perturbation leaves past orders unchanged.

```python
before = runner.capture()
with pytest.raises(ValueError):
    runner.advance(malformed_three_symbol_batch)
assert runner.capture() == before
assert restarted.broker.wallet_balance == uninterrupted.broker.wallet_balance
assert restarted.broker.funding_history == uninterrupted.broker.funding_history
```

- [ ] Implement validated shadow advance; store all exact warmup/raw signal inputs once, recompute fallback features on the same retained prefix (never sliding windows); typed active state plus compact financial event reconstruction.

```python
candidate = deepcopy(runner)
candidate.broker.process_batch([bars[s] for s in sorted(bars)])
features = add_all_features(prefix_only, config, use_fallback_indicators=True)
```

- [ ] GREEN focused runner/store/funding/strategy tests.

## Task 2: Paginated public recovery and API adapter

**Files:** Create `src/paper/history_source.py`, `src/paper/replay_session.py`; modify `local_server.py` only at the API/session seam; test `tests/test_paper_replay_recovery.py` and `tests/test_paper_replay_server.py`.

**Interfaces:** `fetch_closed_range(source, symbol, interval, start, end, server_ms) -> list` with a half-open UTC interval and max500/page; `PaperReplaySession` supplies existing state/start/stop/health/chart/connection callbacks plus pause/resume/history.

- [ ] RED: >500-bar outage with pending/open exposure, multiple restarts, all missing pages requested, partial synchronization/revisions/stale/future inputs, disconnect/reconnect, source exhaustion/retry, SQLite/legacy corrupt data, original evidence preserved.

```python
assert len(source.range_requests) > 1
assert resumed.broker.funding_history == continuous.broker.funding_history
assert resumed.state()['execution_mode'] == 'REPLAY'
assert resumed.state()['risk_gate']['admission_open'] is False  # until fresh WS
```

- [ ] Implement frozen target, per-page continuity and all-symbol validation, one-batch-at-a-time transactional replay, restore prior committed boundary on error, explicit recovery reason, fresh WS before REALTIME; no public funding/time guess.
- [ ] GREEN focused recovery/API tests; full offline and historical gates before milestone commit. Publish v3 schema/examples and Windows contract in S5.

Self-review: receipt time is actual, simulated time is the modeled closed boundary; future suffix is not passed to strategies. New recipe availability cannot be moved backward into catch-up. Reusing legacy evidence is allowed only after full typed-state and seed verification.
