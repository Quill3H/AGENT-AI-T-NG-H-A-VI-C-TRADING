# Research Integrity Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add causal research preregistration, protocol-completeness reporting and deterministic matched-random entry controls without changing any strategy or historical result.

**Architecture:** Extend the append-only ledger with an opt-in enforced protocol used by future rounds while retaining legacy compatibility. Add a small research-control utility that only samples eligible timestamps; strategy-specific runners remain responsible for execution, exits and PnL.

**Tech Stack:** Python standard library, NumPy, pandas, pytest

**Spec:** `docs/superpowers/specs/2026-10-23-research-integrity-design.md`

## Global Constraints

- Do not change trading rules, risk, fills or Round 18 artifacts.
- Add no dependency.
- Do not represent historical rounds as preregistered.
- Protocol status is not an economic pass/fail verdict.

## Review Focus

- A preregistration attempted after a result must fail before writing.
- Undeclared variants and cost multipliers must fail before writing.
- Metadata rows must not appear as trading runs or affect spent holdout data.
- A complete protocol requires every declared variant/cost combination, required controls and frozen commits.
- Random controls must be deterministic, exclude actual signals and reject invalid timestamp pools.

---

### Task 1: Enforced preregistration and audit

**Files:**
- Modify: `src/research/ledger.py`
- Modify: `tests/test_ledger.py`
- Modify: `scripts/ledger_report.py`

**Interfaces:**
- Produces: `preregister(...)`, protocol-aware `record(..., protocol=...)`, `research_integrity(records)` and `integrity_markdown(records)`.

- [ ] **Step 1: Write failing ledger tests**

Cover causal ordering, undeclared inputs, a complete protocol, an incomplete protocol, legacy labelling and exclusion of preregistration rows from run tables.

- [ ] **Step 2: Run the focused tests and confirm they fail because the new interfaces are absent**

Run: `python -m pytest -q tests/test_ledger.py`

- [ ] **Step 3: Implement the minimum append-only protocol and audit logic**

Keep the legacy `record` call valid. Validate protocol metadata only when supplied and compute a Bonferroni reference as `familywise_alpha / number_of_declared_variants`.

- [ ] **Step 4: Add the integrity table to the generated learning log and rerun focused tests**

Run: `python -m pytest -q tests/test_ledger.py`

### Task 2: Matched random-entry control primitive

**Files:**
- Create: `src/research/controls.py`
- Create: `tests/test_research_controls.py`

**Interfaces:**
- Produces: `matched_random_entry_sets(eligible_times, signal_times, repetitions, seed)` returning deterministic UTC `DatetimeIndex` samples.

- [ ] **Step 1: Write failing behavior and validation tests**

Assert equal sample counts, exclusion of actual signals, reproducibility and rejection of unsorted, duplicate, non-UTC or insufficient pools.

- [ ] **Step 2: Run the focused test and confirm it fails because the module is absent**

Run: `python -m pytest -q tests/test_research_controls.py`

- [ ] **Step 3: Implement sampling with NumPy's existing generator**

Use no market data lookup and no exit simulation in this helper.

- [ ] **Step 4: Run both focused suites**

Run: `python -m pytest -q tests/test_ledger.py tests/test_research_controls.py`

### Task 3: Operator contract and project checkpoint

**Files:**
- Create: `docs/operations/RESEARCH_INTEGRITY.md`
- Modify: `PROJECT_STATE.md`

**Interfaces:**
- Consumes: Task 1 and Task 2 interfaces.

- [ ] **Step 1: Document the future-round sequence and placebo limitations**

State that eligible timestamps must be known causally and each sampled entry must reuse the strategy's sizing, stop, target, holding period and costs.

- [ ] **Step 2: Record the scoped checkpoint without claiming economic validation**

List exact code commit after implementation, test evidence and remaining independent review.

- [ ] **Step 3: Run the full offline suite and regenerate the learning log in a temporary copy**

Run: `python -m pytest -q -m "not network"`

- [ ] **Step 4: Review the diff and commit the scoped change**

Expected: only the files above change; no strategy/config/result artifact changes.

