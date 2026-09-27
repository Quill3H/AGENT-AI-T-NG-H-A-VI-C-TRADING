# Review high-priority data fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. The owner requires inline work in this task; no subagent is dispatched.

**Goal:** Repair reproducible broker chronology and market-input integrity defects from the 2026-09-23 independent review without changing paper-only strategy or risk policy.

**Architecture:** Keep PaperBroker as the sole execution authority and validate candle intervals before state mutation. Treat OI and taker-side volume as observed only while their source identity and freshness are known; propagate missingness into CVD and RL observations. Keep branch changes separate from `main` pending owner review.

**Tech Stack:** Python 3.14.7 in the available isolated QA environment, pandas, pytest, Gymnasium and Stable-Baselines3 already used by the repository.

**Spec:** `docs/planning/PRODUCT_CHARTER_AND_GATE_SPEC.md`, ADR 0005/0007/0010/0011, `Project spec/CRYPTO_PAPER_TRADING_AGENT_MASTER_SPEC.md`, and `C:/Users/Lenovo/Downloads/REVIEW_GITHUB_2026-09-23.md`.

## Global Constraints

- Paper/research only. No exchange order or testnet, no trading credentials, no profit claim.
- Preserve UTC event/availability chronology, no-lookahead, exact funding-source and risk-gate behavior.
- Existing one-symbol and historical regression behavior must remain intact.
- No `main` merge; preserve unrelated local work.

Execution note: Tasks 1–4 were completed inline. The 2026-09-27 author handoff records exact evidence and remaining scope; this plan's checkboxes below retain their original prospective wording for traceability rather than serving as an acceptance verdict.

---

### Task 1: Broker event chronology and atomic rejection

**Files:** Modify `src/execution/paper_broker.py`; test `tests/test_review_high_priority_fixes.py`.

**Interfaces:** `PaperBroker.process_candle(candle)` remains public. Any new batch entry point consumes ordered candle dictionaries and produces the same per-candle result dictionaries.

- [ ] Write a regression that opens BTC/ETH at the same minute, closes one intrabar on the next minute, and checks both symbol orders, ledger, breaker time and accounting. Name the mutation it catches: advancing the breaker to a close before another symbol's same-open admission.
- [ ] Write a separate invalid-time/overlap regression asserting complete broker and breaker state unchanged.
- [ ] Run both tests and capture the expected failures on base `fe1c1330d913e78239db575ff8433cf069fe1b01`.
- [ ] Implement one chronology model that processes all same-open admissions before future close events, retaining exact event timestamps. If the existing single-candle API cannot safely infer batch completeness, expose an explicit batch API and fail closed in direct ambiguous calls before mutation; record that limitation rather than weakening the breaker.
- [ ] Rerun focused broker/review tests and verify reconciliation.

### Task 2: Candle and PPO partition intervals

**Files:** Modify `src/execution/paper_broker.py`, `src/research/rl_env.py`; test `tests/test_review_high_priority_fixes.py`.

**Interfaces:** A candle occupies `[open_time, close_time)`; RL train/validation/holdout each use `timeframe` duration. Gaps may be disclosed but intervals must not overlap.

- [ ] Write red tests for direct 15m candles opened at 01:00/01:05, overlapping RL partitions with legal ascending open indexes, and evaluate-only frames overlapping the saved validation interval.
- [ ] Add pre-mutation per-symbol close watermark in broker; validate within-partition cadence and cross-partition last-close <= first-open for train/evaluate.
- [ ] Rerun direct broker, RL and no-lookahead focused tests.

### Task 3: OI freshness and CVD missingness

**Files:** Modify `src/data_layer/fetcher.py`, `src/features/cvd.py`; test `tests/test_review_high_priority_fixes.py` and relevant existing data/CVD tests.

**Interfaces:** Merged data adds `oi_source_time` and `oi_available` with source timestamp no later than bar time. Default OI freshness is one mapped OI period; stale OI is NaN, invoking the existing ADR 0005 fallback. Missing taker-buy remains NaN, and CVD is NaN once the cumulative stream is incomplete.

- [ ] Write red tests for 30-day stale OI, fresh backward OI with source time, six-field candles, CVD missingness and RL CVD mask.
- [ ] Add bounded `merge_asof` tolerance and source metadata; reject future provenance. Remove implicit 50/50 taker substitution and propagate NaN through cumulative CVD.
- [ ] Rerun data, features, no-lookahead and RL focused tests.

### Task 4: UI handoff and verification

Before handoff, also close review F5 without broadening data-selection policy: `run_backtest.py` special `all` and `funding_arbitrage` modes must reject explicit `--start`/`--end` rather than silently ignore them. Add CLI negative tests in `tests/test_review_high_priority_fixes.py` before the minimal early argument validation. Dataset-content identity F6 remains a separate report contract change and will be listed as open if not implemented.

**Files:** Create a small JSON fixture under `docs/reviews/evidence/` and a Markdown contract report under `docs/reviews/`; no performance number may be invented.

- [ ] Describe typed fields, UTC as-of/source time, freshness/missingness, and synthetic-only result labels. Create a static example from the passing synthetic regression, not a claimed market result.
- [ ] Run the relevant focused suites, full offline suite and historical review probes, recording exact counts/exit status. Run no live/testnet/network order path.
- [ ] Inspect `git diff --check`, all order paths touched, funding/risk/accounting invariants and documentation claims. Commit on `codex/review-high-priority-data-fixes`; keep `main` unchanged and report remaining F1–F7 honestly.
