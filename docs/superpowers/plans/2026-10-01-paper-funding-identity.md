# Paper funding and recipe identity implementation plan

## Current publication checkpoint - 2026-10-17

Implementation and regression files are included in the GitHub candidate.
Use the [current handoff](../../handover/2026-10-17-github-checkpoint.md) for
the repaired code SHA, fresh offline/web/build results and remaining gates.
The older combined verification checklist below is historical: unperformed
clean-checkout/browser/public/scheduled-operation checks remain NOT_VERIFIED.
Independent review and owner acceptance remain pending.

## Prior execution addendum - 2026-10-02

S1 implementation is present as an **AUTHOR_SELF_REVIEWED candidate**, not
independent acceptance. The owner later expressly authorized helper agents;
that authorization supersedes the inline-only execution restriction in the
original plan below. Preserve that paragraph as the original decision record.
Helper audits/documentation are author-side assistance, not reviewer acceptance.

- [x] Candidate `funding_model.py` and broker fixed/public separation are present.
- [x] Candidate `recipes.py` freezes registered recipe/formula/config/source identity.
- [x] Broker LONG/SHORT/funding/phase/public-isolation and recipe/formula regression
  files exist: `test_fixed_simulated_funding.py`, `test_paper_recipes.py`,
  `test_paper_formula_contract.py` in `crypto-paper-agent/tests`.
- [ ] Final repaired code SHA and frozen focused/full/clean verification evidence:
  pending root finalization. `c89333516f9032155923375a876d0350deb6c267` is an
  earlier checkpoint, not certification of later repairs.

Fixed 0.01% at UTC+7 07/15/23 is scoped to the separately authorized
`windows-paper-v3` experiment; old capital/history and public-source provenance
remain unchanged. Recipe registration is not an economic promotion verdict.
The original task checklist/commands below are retained as the planned TDD
record, not a claim every command was rerun on the final repaired commit.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Execution is inline, as requested by the owner; no subagents.

**Goal:** Separate the approved fixed simulated funding experiment from public-source funding, retaining all broker risk and accounting checks.

**Architecture:** A frozen, validated funding model supplies predetermined rates directly to the broker. Public funding keeps the existing exact provenance contract. Immutable recipe snapshots identify the strategy, formulas, costs and risk configuration without changing strategy rules.

**Tech Stack:** Python 3.12, dataclasses, hashlib, existing PaperBroker, pytest.

**Spec:** `docs/superpowers/specs/2026-10-01-windows-paper-replay-design.md`, sections 3, 5, 8.

## Global constraints

- PAPER/RESEARCH only; BTCUSDT/ETHUSDT/SOLUSDT share one 10,000 imaginary USDT account.
- Fixed SIMULATED positive funding `0.0001` at 00/08/16 UTC (07/15/23 UTC+7).
- No fabricated public funding metadata; no risk/strategy retuning; main untouched.
- Existing accounts switch prospectively only after exact reconciliation; this slice does not migrate accounts.
- Preserve unrelated dirty files. Reuse the existing owner-selected branch/workspace.

## Task 1: Broker funding isolation

**Files:** Create `crypto-paper-agent/src/execution/funding_model.py`; modify `crypto-paper-agent/src/execution/paper_broker.py`; test `crypto-paper-agent/tests/test_fixed_simulated_funding.py`.

**Interfaces:** `FixedFundingModel.from_config(config: dict) -> FixedFundingModel | None`, `rate_at(symbol: str, timestamp: datetime) -> float`, `describe() -> dict`. None means existing public mode, never a default fixed rate.

- [ ] Write real broker regressions: quantity 1 at price 10,000 has -1/+1 USDT funding for LONG/SHORT, no public metadata; same-boundary entry is ineligible; gap exit precedes funding; duplicate bar rejects before mutation; public mode still fails without readiness; malformed model rejects at construction.

```python
assert broker.funding_history[0].cashflow_usd == -1.0
assert broker.wallet_balance == 9999.0
broker.verify_accounting_invariants()
```

- [ ] Run RED: `.\.venv-paper\Scripts\python.exe -m pytest tests/test_fixed_simulated_funding.py -q` from `crypto-paper-agent`; fixed settlement must initially fail due to missing public rate, while public isolation passes.
- [ ] Implement frozen validated identity and direct fixed/public branch before mutation, with rate/UTC hours/version/effective time/price proxy/symbol validation. Event IDs include position/model/settlement; price remains broker open-price proxy.

```python
model = FixedFundingModel.from_config(self.config)
f_rate = model.rate_at(symbol, open_time) if model else public_rate
```

- [ ] Run GREEN plus execution/accounting regressions: `python -m pytest tests/test_fixed_simulated_funding.py tests/test_execution_accounting.py tests/test_paper_broker.py tests/test_g0_settlement_lifecycle.py -q`.

## Task 2: Recipe identity

**Files:** Create `crypto-paper-agent/src/paper/recipes.py`; test `crypto-paper-agent/tests/test_paper_recipes.py`.

**Interfaces:** `recipe_snapshot(name: str, config: dict, available_at: datetime) -> dict`; `make_strategy(name: str, config: dict, symbol: str) -> BaseStrategy`. Registered names only: trend_following and breakout_retest. No executable payload or arbitrary parameter search.

- [ ] Test causal availability, deterministic portable snapshot identity, cost/risk changes changing identity, unsupported strategies rejected, and caller mutation not changing an existing snapshot.

```python
assert snapshot['strategy_id'] == 'trend_following'
assert snapshot['config']['risk'] == original_risk
assert snapshot['formula_version'] == 'features-v1'
```

- [ ] Run RED, implement deep-copied canonical hash with recipe/formula/cost/funding identity, then run GREEN.
- [ ] Run full offline suite before milestone commit; stage only production/tests. Documentation/checklists and scoped ADR are committed separately with actual code-under-test SHA.

Self-review: every funding path retains phase ordering, liquidation preflight and breaker cashflow; public contract is unchanged. Recipe registration alone is not promotion/validation evidence.
