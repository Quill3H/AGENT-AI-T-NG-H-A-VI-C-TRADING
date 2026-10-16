# Paper trials and bounded research implementation plan

## Current publication checkpoint - 2026-10-17

Implementation and regression files are included in the GitHub candidate.
Use the [current handoff](../../handover/2026-10-17-github-checkpoint.md) for
the repaired code SHA, fresh offline/web/build results and remaining gates.
The older combined verification checklist below is historical: unperformed
clean-checkout/browser/public/scheduled-operation checks remain NOT_VERIFIED.
Independent review and owner acceptance remain pending.

## Prior execution addendum - 2026-10-02

S4 implementation is present as an **AUTHOR_SELF_REVIEWED candidate**, not
economic validation or independent acceptance. Later express owner permission
for helper agents supersedes the original inline-only instruction below;
that original decision and planned TDD checklist remain historical records.

- [x] `trials.py` records strict <5,000 failure, >=15,000 target/continue,
  previous trial equity/history and exactly-once imaginary allocations.
- [x] `research_cycle.py` and session integration implement frozen causal
  catalog/cutoff, 180/90/90-day partitions, one claimed final candidate,
  isolated shared-account holdout folds, sample/drawdown/expectancy/cost gates,
  bounded budget and verdict identities before promotion.
- [x] `test_paper_trials.py`, `test_paper_research_cycle.py` and
  `test_paper_research_control_race.py` provide lifecycle/research/control
  regressions. Separate synthetic actual-broker LONG/SHORT evidence is not
  market performance and is not a substitute for full-window validation.
- [x] Candidate shadow execution retains transaction accounting and blocks
  promotion until old exposure/funding and request-time controls are reconciled.
- [ ] Final repaired code SHA and frozen technical results: pending root
  finalization; `c89333516f9032155923375a876d0350deb6c267` is an earlier checkpoint.
- [ ] Full empirical 360-day study and an actually eligible real-data promotion:
  NOT_VERIFIED. Sparse/failed/blocked rounds must not allocate fresh capital.

Initial Trend is the owner-selected baseline, not a researched winner.
Breakout is only a promotion candidate, not currently asserted active. No
SMC/PPO/Arbitrage expansion, curve fitting, risk tuning or profitability claim.
Helper audit evidence remains author-side work; acceptance awaits owner/reviewer.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline; no subagents.

**Goal:** Track the approved failure/target milestones and allocate a replacement paper trial only after bounded causal validation.

**Architecture:** A durable TrialBook records milestones, final/parked equity and all imaginary capital allocations. A closed two-recipe research evaluator uses the shared runner and existing whole-position metrics, frozen partitions and one frozen holdout candidate. Session integration journals verdict/promotion atomically; sparse, failed, blocked or over-budget rounds wait without resetting capital.

**Tech Stack:** Python 3.12, existing strategies/features/PaperBroker/metrics, compact SQLite, pytest.

**Spec:** `docs/superpowers/specs/2026-10-01-windows-paper-replay-design.md`, sections 7–8.

## Global constraints

- Failure equity strictly <5,000; target equity >=15,000 once; same successful trial continues.
- No new allocation while old exposure/pending/funding is unreconciled; preserve active breaker lock/streak.
- Max8 fixed candidates; no runtime code generation, tuning or funding-arbitrage candidate.
- 360d cutoff: 180train/90validation/90holdout; three independent30d holdout folds, shared BTC/ETH/SOL account per fold.
- >=30 completed positions total, >=5/fold, expectancy>0, positive PnL in2/3 folds, DD<=20% each, doubled-cost aggregate>=0.
- Ten-minute evaluation wall budget, one worker, max3 retries/page; no profitability/independent-acceptance claims.
- Candidate and input availability <=selection cutoff; a used holdout cannot be reused for another candidate.

## Task 1: Trial lifecycle

**Files:** Create `src/paper/trials.py`; integrate `causal_runner.py`; test `tests/test_paper_trials.py`.

**Interfaces:** `TrialBook(initial_recipe, available_at)`, `observe(equity, timestamp) -> list`, `promote(recipe, timestamp, reconciled, verdict) -> dict`, `capture()/restore(payload)`.

- [ ] RED literal boundary tests at5000/4999.99/15000; repeated target and failure generate one event; failed target history remains; malformed equity blocks; promotion requires eligibility, causal availability and exact reconciliation; repeated allocation is idempotent.

```python
assert book.observe(5000, t) == []
assert book.observe(4999.99, t)[0]['kind'] == 'TRIAL_FAILED'
assert book.total_capital_injected == 10000
```

- [ ] Implement minimal durable summaries and allocation keys; runner cancels entries and queues broker close after failure at the next valid open, then WAITING_RESEARCH when flat. Operator stop disables research/promotion.
- [ ] GREEN with broker/funding/recovery tests; verify no breaker bypass on promotion.

## Task 2: Frozen research evaluator

**Files:** Create `src/paper/research_cycle.py`; test `tests/test_paper_research_cycle.py`.

**Interfaces:** `research_windows(cutoff) -> dict`, `promotion_verdict(folds, stressed_folds) -> dict`, `evaluate_research(config, catalog, inputs, cutoff, used_intervals, budget_seconds=600) -> dict`. Inputs use actual validated raw bars, no UI-provided performance numbers.

- [ ] RED tests: chronology/no overlap, sample threshold, negative fold/drawdown/cost results, sparse fixtures, unavailable recipe, used holdout, budget expiry and NaN; selected candidate frozen before holdout.

```python
assert verdict['status'] == 'INSUFFICIENT_EVIDENCE'
assert verdict['eligible'] is False
```

- [ ] Implement formula checks and train diagnostics, validation ranking on net expectancy/drawdown/stableID; freeze one selected candidate; fresh state/capital in all three holdout folds and cost stress; force-close costs; precise data/config/recipe/report checksums. Research snapshots are diagnostics, not an independently verified holdout claim.
- [ ] GREEN and synthetic fixture execution through actual evaluator, then full offline gate. Integrate public acquisition/cache/verdict/promotion in session with no parallel trading mutation.

## Task 3: Compact transactional execution performance

**Files:** `src/execution/paper_broker.py`, `src/paper/causal_runner.py`, `src/paper/replay_session.py`; tests `tests/test_paper_causal_runner.py` and execution transaction regressions.

- [ ] Verify prior published financial records never change on a rejected later batch; pending order updates remain isolated. Reduce repeated copies/encoding of immutable published histories while retaining atomic shadow state and all authoritative accounting assertions.
- [ ] Benchmark the >500bar fixture again; record actual runtime, not a claimed speedup without measurement. Avoid unrelated cosmetic refactoring.

Self-review: event roots/config transitions preserve previous trials and actual injected capital. A target milestone is not a performance certification. Budget and missing data cannot produce an eligible verdict.
