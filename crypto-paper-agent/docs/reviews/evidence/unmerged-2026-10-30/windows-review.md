# Independent Windows/API verification — 2026-10-30

Reviewer: Codex windows_verification subagent. Paper-only; exported branches and disposable test accounts only. No main/index/ref changes, owner account initialization, task registration, exchange order, download, or GitHub comment was performed.

## Scope and identity

- Integration target inspected: main d4cc137.
- PR5: origin/codex/paper-futures-api-contract cfc6504, one feature commit over local-paper-futures-app d1cd95a.
- PR6: origin/codex/windows-paper-replay b293ee1.
- Each branch exported with `git archive --format=zip -o <branch>.zip <ref>` and `Expand-Archive` into this directory.
- Runtime: repository `.venv/Scripts/python.exe`, Python 3.12.14 / pytest 9.1.1, actual Windows.
- Route: ponytail-review, AGENTS paper-only and independent-verification rules. Current source/test checks supersede historical progress claims.

## Feature verification

PR6 command, in `pr6/crypto-paper-agent`, using the absolute repository Python executable:

```
python -m pytest tests/test_local_paper_server.py tests/test_paper_replay_server.py tests/test_paper_replay_recovery.py tests/test_paper_replay_review_fixes.py tests/test_paper_request_time_controls.py tests/test_paper_research_control_race.py tests/test_paper_scheduled_partial_restore.py tests/test_paper_store_commit_integrity.py tests/test_paper_account_lock.py tests/test_paper_compact_store.py tests/test_paper_exposure_reconciliation.py tests/test_paper_windows_lifecycle.py tests/test_fixed_simulated_funding.py tests/test_paper_causal_runner.py -q --basetemp=../pytest-verification-tmp2
```

Initial restricted run: **128 passed, 15 failed**, 234.66 seconds (`pr6/focused-pr6.log`). Local HTTP socket failures are sandbox WinError10013; actual PowerShell/process tests also need unrestricted local execution.

Rerun outside sandbox, same exported source:

```
python -m pytest tests/test_local_paper_server.py tests/test_paper_replay_server.py tests/test_paper_request_time_controls.py tests/test_paper_windows_lifecycle.py -q --basetemp=../pytest-loopback-verified
python -m pytest tests/test_paper_account_lock.py::test_start_during_server_teardown_cannot_allocate_account -q --basetemp=../pytest-account-loopback
```

Results: **22 passed / 1 failed** in 53.70 seconds (`pr6/loopback-pr6.log`); **1 passed** in 1.72 seconds (`pr6/loopback-account-pr6.log`). Across those initial 143 distinct cases, **142 independently verified pass**. The remaining launcher test fails because `websocket-client` is absent in this verification environment: its launcher checks `import websocket` before executing the fixture backend. This is not established as a branch implementation defect. The five other actual Windows lifecycle cases pass, including process identity verification, preserving corrupt accounts, refusing occupied ports, and repeated restart with pending/open positions and idempotent funding. No Scheduled Tasks were installed.

Separately, adding `tests/test_paper_replay_contract.py` initially blocked collection on absent `jsonschema`; the schema-validation test is **NOT VERIFIED**, not included in the 143 cases. Existing tests also emitted a background missing-websocket warning. No public stream integration or operational uptime claim is made.

PR5 command, in `pr5/crypto-paper-agent`, outside sandbox for local loopback:

```
python -m pytest tests/test_paper_futures_api_contract.py tests/test_local_paper_server.py tests/test_paper_recovery_review.py tests/test_paper_resume.py tests/test_paper_safe_integration.py -q -k 'not transport_closes_socket_when_session_requests_reconnect' --basetemp=../pytest-pr5-loopback
```

**53 passed / 1 deselected** in 6.54 seconds (`pr5/loopback-pr5.log`). Excluded transport test imports absent `websocket`. Initial restricted run was 49 passed / 5 failed: four loopback access failures and the missing websocket import (`pr5/focused-pr5.log`). No concrete PR5-only logic defect was reproduced in this scope.

## Main compatibility blockers

Do not resolve the broker conflict by copying PR6's broker over current main. Main test files were copied unchanged into `probes/`, with only fixture config location adapted; tests were run against PR6 via PYTHONPATH. Reproduce with repository Python:

```
.venv/Scripts/python.exe tmp/windows-verify-20261030/run_main_probes.py
```

Result **30 failed / 6 passed** in 1.78 seconds (`main-regressions-final.log`). Some failures are expected absence of newer main scripts, not PR6-local defects. Concrete broker-only regressions nevertheless prohibit overwriting main:

1. **P1: current kill-switch/data-gap protections disappear.** Seven current-main kill-switch tests fail: PR6 has no `engage_kill_switch`, no `kill_switch_reason`, and does not reject invalid `max_data_gap_minutes` values. These are current-main capabilities, absent in the older PR6 broker. Relevant PR6 source: broker initialization around line 199–210 and the open path around line 462 onward.
2. **P1: actual-fill portfolio exposure cap disappears.** Current-main `test_portfolio_gross_notional_limit_applies_at_actual_fill` requests two 40-unit positions with a 50%-of-equity gross cap. PR6 opens both instead of one. Capacity including pending orders and invalid capacity validation also fail. These rules must survive integration; restoring only the textual conflict hunks does not establish this.
3. **P2: funding-drained collateral solver regression.** Two current-main regression cases fail because PR6 rejects valid liquidation solutions above entry for a long / below entry for a short. PR6 `src/execution/paper_broker.py:1300` and `:1320` retain the obsolete entry-side restrictions; current main removed those restrictions after actual funding-drain cases. Preserve main's corrected solver.

Current-main `test_stop_and_journal.py` cannot collect against the pristine PR6 export because the newer `src.report.trade_journal` is absent. This confirms branch age, not that a normal three-way merge deletes main-only additions.

PR6 and main have materially different batch engines: PR6 `paper_broker.py:363–446` forks a shadow broker, sorts symbol admission canonically, runs all per-symbol open phases then close phases, records broker request/entry metadata, and commits collaborator state; main uses a shared five-phase generator with caller order. PR6 recovery specifically reads `_defer_cb_lock_for_batch` at `src/paper/recovery_state.py:185`, and replay/reconciliation use `broker.fork()` plus `broker_request`/`broker_entry` metadata. Keeping main's broker unchanged is therefore not sufficient either. A composed adapter/merge must retain both contracts and rerun both suites.

## Branch relationship and recommendation

- PR5 is **not** an ancestor of PR6 (`git merge-base --is-ancestor ...` exit 1). PR6 vs PR5 replaces 90 files and removes the old v2 contract test while introducing v3 replay contracts. Treat them as different API implementations, not proof of commit containment. PR5's small feature can pass on its own old base, but merging its entire legacy stack into main has not been validated. Hold main integration until a current-main candidate is tested.
- `local-paper-futures-app` and `web-chart-timeframes-and-signals` are ancestors of PR6 (exit 0).
- Current `paper-windows-recovery` and `review-high-priority-data-fixes` tips are not ancestors of PR6 (exit 1). This does not imply missing equivalent patches; another reviewer owns those branches.
- **PR6: do not merge directly yet.** Feature tests are strong, but current-main broker safeguards/accounting and batch/recovery contracts need an explicit composed integration and verification. Draft status/operational soak are separate from these concrete code blockers.
- **PR5: no blocker found on own base within 53 verified tests; not ready as a full main merge.** Its old base includes broker changes; a smaller current-main port would need its own combined regression tests. Avoid merging both protocol implementations merely to empty the PR list.

## Dependency-review block

Parent requested installing declared `websocket-client>=1.8,<2` and `jsonschema>=4.26,<5` to complete missing checks. Automatic approval review rejected the scoped pip command because downloading packages conflicts with this subtask's original no-download instruction, and instructed no workaround. No installation happened. Missing-dependency checks remain explicitly unverified. This is independent of the proven main broker integration blockers above.
