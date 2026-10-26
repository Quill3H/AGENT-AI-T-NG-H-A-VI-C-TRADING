# Research Robustness Diagnostics Implementation Plan

**Goal:** Add reusable drawdown-duration, profit-concentration, placebo, benchmark-dependence and regime-stability diagnostics without changing strategy behavior.

**Spec:** `docs/superpowers/specs/2026-10-26-robustness-diagnostics-design.md`

## Task 1: Pure diagnostics

- [ ] Write failing tests for recovered and open drawdowns, monthly/yearly concentration, placebo ranking, market dependence and regime aggregation.
- [ ] Implement the minimum pure functions in `src/research/robustness.py` with fail-closed input validation.
- [ ] Run focused tests.

## Task 2: Standard summaries and operator contract

- [ ] Add drawdown duration and profit concentration to `curve_summary` and `summarize_run`.
- [ ] Document how strategy runners must supply matched random, benchmark and causal regime inputs.
- [ ] Run the full offline suite and request independent review.
- [ ] Update the project checkpoint and summary report without claiming economic validation.
