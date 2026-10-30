# Remaining branch audit — 2026-10-30

Verifier: remaining_branches subagent. Main/base inspected: d4cc137. Paper-only; no network data downloads, exchange orders, credentials, GitHub mutation, main/index/ref mutation, or source-reference edits.

## Integration recommendation

1. `origin/codex/review-high-priority-data-fixes` (`ffbc14b`, ancestor `fe1c133`): **selective patch is ready for independent review; full branch remains pending**. Its data/CVD/CLI fixes are absent from current main. Broker and RL changes cannot be called superseded or accepted: current broker has important later functionality, and genuine old findings still reproduce. Do not merge its old broker wholesale.
2. `origin/claude/project-thread-bla4me` (`c0ca8dd`, ancestor `ab1ad81`): **preserve as superseded research history**. Main already has separately reviewed F1–F5 (`ff64ed7`, `85df7c4`) and later robustness diagnostics. The alternate is pre-F5 and has no verified additive code scope worth integration. Its alternate run records must remain identified by their own code/data version.

## Selective candidate

Independent scratch clone: `candidate/`, branch `audit/high-priority-integration`, clean frozen commit **0654b277a5e1815ca94068c1793f5e42b061baaf**, parent d4cc137. This is a selective commit, not a merge of ffbc14b.

Only four files changed (111 insertions, 13 deletions):

- `crypto-paper-agent/run_backtest.py`: reject explicit dates in funding/all modes that ignore them, before output/loading.
- `crypto-paper-agent/src/data_layer/fetcher.py`: missing taker data remains NaN; backward OI join preserves source time, excludes observations at or beyond mapped cadence age, and exposes availability; infinities become unavailable. Current FetchError and funding jitter handling remain intact.
- `crypto-paper-agent/src/features/cvd.py`: invalid/missing taker data is unknown, and cumulative CVD stays unknown after the first unobserved delta.
- `crypto-paper-agent/tests/test_input_fidelity.py`: five extracted original non-RL regression cases; no newly skipped or failing tests ship.

No broker, RL, strategy rule, risk setting, funding accounting, run artifact or historical result changed. Existing research runs require regeneration before making claims from the new input treatment.

## Verification

Runtime: main checkout `.venv/Scripts/python.exe`, Python 3.12.14. Commands run from `candidate/`; every pytest invocation uses a fresh explicit `--basetemp` in this audit directory. Early default-temp fixture failures were environment errors and are not counted as behavioral evidence. The original branch test module initially could not collect without optional gymnasium; the external audit copy relocates RL imports into optional RL tests and preserves every original assertion. That copy is not shipped.

- `pytest crypto-paper-agent/tests/test_input_fidelity.py -q --tb=short --basetemp=../pytest-red`: **5 failed, 1 optional mask skipped** on d4cc137 before extraction. Failures: missing OI provenance, fabricated 50% taker volume, CVD resuming after missing input, funding dates silently ignored (exit 0), comparison input loading before date guard. This first extraction copy contained the separately isolated optional mask assertion; the shipped final file omits that unrelated RL test.
- After patch, same cases: **5 passed**. `red-data.log`, `green-data.log`, `focused-final.log` preserve the outputs.
- Final focused run: **90 passed, 2 skipped (existing pandas-ta), 5 network deselected**, 5.16s. Modules: `test_input_fidelity`, `test_data_layer`, `test_fetcher_fail_closed`, `test_fetcher_public_only`, `test_cvd`, `test_indicators`, `test_no_lookahead`, `test_execution_no_lookahead`, `test_execution_accounting`, `test_paper_broker`, `test_crypto_orb_portfolio`. Flags: `-q --tb=short -m "not network" --basetemp=../pytest-final`.
- `git diff --check`: clean before commit. Candidate status clean after commit.
- Full repository/artifact suites: **not run by this subagent**; parent owns those. PPO/gym behavior: **NOT_VERIFIED**, dependencies absent and RL implementation retained unchanged.

## Concrete risks of taking the old broker implementation

The old broker `ffbc14b:src/execution/paper_broker.py:343-426` uses a deepcopy/canonical-symbol implementation (`369` sorts symbols), replacing current caller-priority generator phases (`main:374-406`). Current portfolio scope added capacity, gross-notional limits and peak exposure tracking. `old_broker_probe.py` loads only the old broker into memory and runs current portfolio regressions; candidate files stay unchanged.

- **P1: removes gross-notional enforcement.** `test_crypto_orb_portfolio.py:179-187` configured 0.5x equity, yet the old broker opened both 40-unit positions instead of one. Current enforcement is `paper_broker.py:861-866`. Test failed with `2 != 1`.
- **P2: breaks current ORB replay.** `scripts/run_crypto_orb_portfolio.py:246` reads `last_batch_peak_positions`; old broker has no such attribute. `test_real_replay_allows_multiple_entries_per_day_but_never_five` failed with AttributeError.

Both current tests pass in the final focused suite. Exact old-version probe: `python ../old_broker_probe.py`; log `old-broker-regressions.log`: **2 failed** as expected. These are source-level integration hazards, not a claim that every possible manual conflict resolution must retain those hazards.

## Existing broker findings still reproduced on current main

These are **preexisting defects**, unchanged by the selective data candidate; full high-priority integration remains pending separate broker repair. Original regression assertions are preserved in external `original-regressions.py`; `prepare_tests.py` reconstructs that copy in the scratch candidate from the original branch fixture if needed. Logs: `broker-current-failures.log`, `broker-overlap.log`, `red-highpriority.log`.

- **P1: breaker can skip another symbol's due funding.** At 08:00 simultaneous BTC/ETH, first 1-USDT funding charge locks a low-threshold breaker and flattens ETH before its settlement. Only BTC funding appears; required wallet is 9998, with both charges. Source `paper_broker.py:670-689`, `1395-1405`, `_handle_circuit_breaker_lock:1231-1245`; original regression lines 211-230.
- **P1: intrabar breaker unwind uses peer's stale opening mark and can bypass a touched stop.** BTC stop triggers a lock; ETH with close 102 force-exits at 100. If ETH also touched 95 stop, it still force-exits at 100. Source `paper_broker.py:962-1031` executes intrabar exits before `1032-1052` updates all close marks; `_execute_exit:1203-1204` immediately flattens peers. Original regressions lines 156-190.
- **P2: direct candle accepts overlapping interval or late same-open peer.** 15m bar at 01:00 followed by same-symbol 01:05 bar is accepted. A direct ETH bar at an opening time already followed by BTC intrabar close is also accepted instead of rejecting before mutation. Preflight `paper_broker.py:461-477` checks last opens, not prior interval closes or breaker timestamp. Original regressions lines 94-112.
- One additional old test failure is **message wording only**: current process_batch rejects mixed durations atomically, but message says `same duration` instead of the old test's `same.*close`. Do not count it as a broker defect.

## OI alternate F5 reproduction

`c0ca8dd:src/strategies/oi_reclaim.py:187` unconditionally assigns v1's 5% loss limit over project's stricter limit. Main `oi_reclaim.py:165-166` validates both and uses their minimum.

`python ../oi_f5_probe.py` uses current F5 regression fixture (project 1%, v1 5%, a funding loss of -201.7719 USDT). Output in `oi-f5.log`:

- current main: effective limit **1%**, `CIRCUIT_BREAKER_LOCK` at **2024-03-02 18:30 UTC**;
- alternate c0ca8dd: effective limit **5%**, holds until `TIME_STOP` at **2024-03-03 18:15 UTC**.

This is a concrete **P1** risk-rule regression if alternate OI implementation replaces main. The alternate CLI also records only scored rows, while main records failed runs as `data-quality-failed`; alternate performance summary predates current drawdown diagnostics. Do not overwrite later auditability/diagnostic safeguards to import alternate historical artifacts.

Verdict: independently review/apply selective 0654b27; preserve ffbc14b pending broker/RL reconciliation; preserve c0ca8dd as superseded. This is software verification only, not acceptance or economic validation.
