# End-to-End Paper Bot Functional Completion Plan

> **For agentic workers:** Execute this plan task-by-task. The Technical Lead
> owns implementation. A separate Tester validates every completed task and a
> separate Independent Reviewer checks the frozen branch before owner approval.

**Goal:** Deliver a usable, correct and reproducible local crypto futures
research/paper bot with four rulebook workflows, PPO train/evaluate/save/load,
simulated execution/risk/accounting/reporting, and clear operator instructions.

**Architecture:** Reuse the existing data, feature, strategy, PaperBroker,
research and report modules. Close wiring/usability gaps rather than refactor
the system or optimize alpha. Use checked-in fixtures/caches/evidence first;
download only the minimum public data required to exercise a missing core path.

**Tech Stack:** Python 3.12.14 validation runtime, pandas, NumPy, PyArrow,
Gymnasium, Stable-Baselines3, PyTorch CPU, pytest and existing JSON/SQLite/CSV/
PNG report artifacts.

**Spec:** `docs/planning/PRODUCT_CHARTER_AND_GATE_SPEC.md`, current
`PROJECT_STATE.md`, `PLANNER_HANDOVER.md`, master spec and ADR 0007-0012.

## Global Constraints

- Paper-only: no real/testnet orders, trading credentials, signing or money.
- Preserve no-lookahead, stop/leverage/margin/liquidation/breaker, exact
  funding provenance, lifecycle accounting and deterministic identity.
- G0/G1 is accepted only after independent review of code A/docs B; do not
  silently build later work on an unaccepted moving checkout.
- Functional completion does not require profit, an ideal sample count, a
  chosen best strategy, full multi-year coverage or regime optimization.
- `NO_TRADES`, missing optional data and negative results are explicit output
  states. Required data failures remain fail-closed.
- Every task produces a small code SHA and docs/evidence child SHA, exact
  commands/runtime, clean-environment reproduction and independent QA result.
- Preserve existing caches/artifacts and `.serena/`; do not delete unrelated
  user data to meet resource limits.

## Review Focus

1. A quick-start run must not silently fetch network data or depend on the
   caller's current directory.
2. All four strategies and PPO must use causal input and the approved broker/
   risk path; Funding remains a distinct two-leg basket.
3. Missing, stale, duplicate or out-of-order required input must produce a
   named error or `NO_TRADES`/`INSUFFICIENT_DATA`, never fabricated signals.
4. Artifacts must identify code, config, input and model/scaler and reconcile
   JSON/SQLite/CSV/PNG totals and completed lifecycle metrics.
5. Start/stop/recovery must preserve idempotency and explain how to inspect
   logs, failures and output without requiring chat history.

---

### Task 0: Accept the G0/G1 Correctness Baseline

**Files:**
- Review: `docs/reviews/G0_SETTLEMENT_LIFECYCLE_HANDOFF.md`
- Review: `docs/reviews/evidence/g0-2c9a4d0/`
- Code target: commit `2c9a4d0985fc9eafd29386482793425c26d47835`
- Docs target: commit `b174f544462d45bacec3e6b27a1409ca4fc32325`

- [ ] Verify docs commit parent equals code commit and contains no source/test/
      script/config changes.
- [ ] Tester reruns frozen baseline, V2 and V3 probes, focused suite, full
      offline suite and historical Review05/06/07 on pinned Python 3.12.14.
- [ ] Reviewer independently checks exact funding source identity, rejection
      atomicity, direct-position close paths, incomplete lifecycle exclusion,
      completed-position metrics and evidence hashes.
- [ ] PM records the independent verdict. If rejected, create a new G0 repair
      task and repeat; do not start implementation tasks below on a moving fix.

### Task 1: Capability Inventory and Stable Command Contract

**Files:**
- Inspect/modify: `run_backtest.py`
- Inspect/modify: `scripts/fetch_market_data.py`
- Inspect/modify: `scripts/run_funding_arbitrage.py`
- Inspect/modify: `scripts/run_walk_forward.py`
- Inspect/modify: `scripts/train_ppo.py`
- Inspect/modify: `scripts/evaluate_ppo.py`
- Create: `docs/operations/CAPABILITY_MATRIX.md`
- Test: `tests/test_functional_cli_contract.py`

- [ ] Enumerate each command's required input, optional input, output directory,
      network behavior, exit codes and `NO_TRADES`/missing-data behavior.
- [ ] Add `--help`/argument tests and fail-first tests proving invalid paths,
      malformed config and unavailable required data fail clearly before state
      mutation or output overwrite.
- [ ] Normalize a shared command contract: explicit config/input/output, no
      implicit machine paths, bounded network flag, deterministic seed/run ID
      and nonzero exit for invalid input.
- [ ] Write the capability matrix with status `WORKING`, `PARTIAL`, `BLOCKED`
      or `NOT_VERIFIED` and link one reproducible command/evidence path per row.
- [ ] Run:

```powershell
python -m pytest -p no:cacheprovider tests/test_functional_cli_contract.py -q
python run_backtest.py --help
python scripts/run_funding_arbitrage.py --help
python scripts/run_walk_forward.py --help
python scripts/train_ppo.py --help
python scripts/evaluate_ppo.py --help
```

### Task 2: Clean-Environment Quick Start with Existing Data

**Files:**
- Create: `scripts/verify_quickstart.py`
- Create: `docs/operations/QUICKSTART.md`
- Create: `tests/test_quickstart.py`
- Reuse: `requirements-repair-lock.txt`
- Reuse: checked-in synthetic/public sample manifests and G0 replay inputs

- [ ] Write a clean-environment test that installs the lockfile, invokes a
      deterministic offline example from an external working directory and
      asserts it does not access the network.
- [ ] Make the quick-start select checked-in fixture/recorded input explicitly;
      never fall back to downloading when a local input is missing.
- [ ] Verify produced JSON, SQLite, CSV and PNG/report checksums, config/data
      identities, ledger reconciliation and absence of absolute machine paths.
- [ ] Document exact setup, one-command smoke, expected outputs, runtime/disk
      estimate, optional dependencies and the recovery action for each common
      failure.
- [ ] Run the quick-start twice and prove deterministic semantic outputs; wall
      time/path metadata may differ only where documented.

### Task 3: Four Rulebook Workflows

**Files:**
- Inspect/modify: `run_backtest.py`
- Inspect/modify: `scripts/run_funding_arbitrage.py`
- Inspect: `src/strategies/trend_following.py`
- Inspect: `src/strategies/breakout_retest.py`
- Inspect: `src/strategies/smc_liquidity_sweep.py`
- Inspect: `src/strategies/funding_arbitrage.py`
- Create/modify: `tests/test_functional_strategy_workflows.py`
- Create: `docs/operations/STRATEGY_WORKFLOWS.md`

- [ ] Add a deterministic fixture workflow for Trend, Breakout and SMC that
      produces at least one LONG and one SHORT completed lifecycle through the
      same broker/risk/report path used by normal CLI execution.
- [ ] Add a deterministic Funding workflow with synchronized spot/perp legs,
      one distinct funding settlement, close/unwind and ledger reconciliation.
- [ ] Add negative fixtures for `NO_TRADES`, missing required funding/spot leg,
      stale/out-of-order bars and SMC input fidelity limitations.
- [ ] Document what each rulebook knows, timeframe/input needs, configuration,
      output fields and what the fixture demonstrates versus what remains an
      economic hypothesis.
- [ ] Verify no workflow bypasses admission, breaker, accounting, lifecycle or
      reporting contracts.

### Task 4: PPO Train Evaluate Save Load Workflow

**Files:**
- Inspect/modify: `src/research/rl_env.py`
- Inspect/modify: `scripts/train_ppo.py`
- Inspect/modify: `scripts/evaluate_ppo.py`
- Inspect/modify: `src/research/artifacts.py`
- Create/modify: `tests/test_functional_ppo_workflow.py`
- Create: `docs/operations/PPO_WORKFLOW.md`

- [ ] Run Gymnasium/SB3 checkers and a bounded CPU smoke using recorded input,
      train-only scaler and fixed seed; assert actions pass PaperBroker/risk.
- [ ] Persist model ZIP, scaler, config, data/code identity, seed/hyperparameters,
      actual steps and train/validation/evaluation time boundaries.
- [ ] Load without refitting and reproduce deterministic evaluation/accounting;
      reject wrong model/scaler/config/data/timeframe/checksum combinations.
- [ ] Compare only as diagnostics against no-trade and a causal rule baseline;
      negative PnL is a valid workflow outcome.
- [ ] Document training, evaluation-only use, output inspection, limitations and
      how creating a new model version differs from changing a scored run.

### Task 5: Unified Replay Reporting and Failure Semantics

**Files:**
- Inspect/modify: `src/research/workflow.py`
- Inspect/modify: `src/research/comparison.py`
- Inspect/modify: `src/report/generator.py`
- Inspect/modify: `src/report/metrics.py`
- Inspect/modify: `src/logging/trade_logger.py`
- Create/modify: `tests/test_functional_artifact_contract.py`
- Create: `docs/operations/ARTIFACT_REFERENCE.md`

- [ ] Define a versioned manifest shared by rulebook, funding and PPO workflows:
      code/config/data/model identities, UTC boundaries, costs, status and files.
- [ ] Ensure raw realization slices reconcile cash while primary metrics use
      completed lifecycles/baskets; independent accounts and folds remain clear.
- [ ] Define exact status/error vocabulary for success, `NO_TRADES`,
      `INSUFFICIENT_DATA`, `DATASET_UNAVAILABLE`, invalid input, interrupted run
      and accounting/reconciliation failure.
- [ ] Test rerun/idempotency, output collision, interrupted write/recovery and
      conflicting payload rejection.
- [ ] Document every artifact, field ownership, how to verify hashes and how to
      distinguish technical evidence from performance claims.

### Task 6: Operator Start Stop Recovery and Public-Feed Boundary

**Files:**
- Create: `docs/operations/OPERATOR_GUIDE.md`
- Create/modify: `tests/test_operator_recovery.py`
- Modify only if needed after inventory: data/replay entry points from Task 1

- [ ] Document setup validation, start, graceful stop, emergency paper stop,
      resume/replay, output backup, log inspection and daily reconciliation.
- [ ] Test stale/missing/duplicate/out-of-order input, clock drift, process
      interruption and restart without duplicate order/funding/ledger events.
- [ ] Specify the public-feed interface and timestamps in an observe-only mode;
      use recorded events for functional tests. Do not add order endpoints,
      credentials or claim a prospective market session is running.
- [ ] State what remains required before a scored prospective paper experiment:
      venue/instrument/timeframe, session duration, latency/fill proxy, freeze
      identity, fault thresholds and owner-approved measurement protocol.

### Task 7: Independent Functional Acceptance and Owner Handoff

**Files:**
- Create: `docs/reviews/FUNCTIONAL_COMPLETION_HANDOFF.md`
- Update after independent verdict: `PROJECT_STATE.md`, `PLANNER_HANDOVER.md`,
  `CHANGELOG.md`

- [ ] Technical Lead freezes code A, runs offline/network-separated suites and
      every documented quick-start/workflow from an external CWD, then creates
      docs/evidence B as a documentation-only child.
- [ ] Tester repeats clean setup, quick-start, four strategy workflows, PPO,
      artifact checks and operator recovery without modifying production code.
- [ ] Reviewer checks code-vs-docs, old findings, causal/risk invariants,
      evidence hashes and every capability row; reports residual gaps by scope.
- [ ] PM presents the owner with: capability checklist, how-to-use links, exact
      A/B SHAs, Tester evidence, Reviewer verdict, limitations and the separate
      LATER data/model-improvement backlog.
- [ ] Only the owner marks the bot functionally accepted or requests another
      repair. No functional acceptance implies economic validation or real use.

## LATER Backlog after Functional Acceptance

- Broader historical acquisition and per-year/regime coverage audit.
- Causal regime features/labels, candidate comparison and bounded tuning.
- Pre-registered sample, drawdown, uncertainty and cost-stress protocol.
- Untouched historical/near-current holdout per version.
- Prospective public live-data paper experiments with frozen versions.
- A separate owner decision for manual signal assistance or real-money design;
  neither is part of this plan.
