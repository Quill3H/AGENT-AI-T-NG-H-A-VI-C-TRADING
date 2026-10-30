# Independent repair review - 2026-10-30

Reviewer: repair_review agent. Read-only review of the uncommitted repair on base main 56382df63f0a58ba249d39b005ad97e90cd30150. No production files changed or commits made.

## Finding

P1: universe_loader.py:710 permits funding_available_time up to the 15-minute candle close. The runner feeds this same rate to PaperBroker at that candle's opening settlement, where it changes wallet balance, breaker state and peer order admission/sizing. Thus an event first available at 08:14 can affect 08:00 execution. Nominal settlement timestamp jitter does not authorize arbitrary later observation availability to affect earlier decisions. Require availability within the explicit settlement jitter allowance before exposing it at open; retain the separate close-time decision check.

Read-only reproduction: import _funded_frame from tests/test_synthesized_input_contract.py, set funding_available_time = funding_time + pd.Timedelta(minutes=14), then UniverseDataLoader.validate_funding(frame). Current code accepts it. Exact source event remains at the nominal boundary, so the existing source jitter check does not reject it. Add a regression covering this delayed availability.

## Verified scope

Fresh independent command from crypto-paper-agent:

```powershell
$env:PYTHONUTF8='1'
../.venv/Scripts/python.exe -m pytest tests/test_broker_phase_repairs.py tests/test_fixed_simulated_funding.py tests/test_economic_evaluation.py tests/test_synthesized_input_contract.py tests/test_report_generator.py tests/test_paper_main_compatibility.py tests/test_paper_exposure_reconciliation.py -q --tb=short --basetemp ../../tmp/review-scope-1030
```

Result: 130 passed in 9.03s. No skips or deselections. This suite lacks the delayed-availability reproduction above.

Broker synchronized stage barriers defer peer breaker flattening until both funding cashflows/protective outcomes are processed, while lock state immediately blocks admissions. Current cap/gap guards remain in place. fork deep-copies broker-owned news/risk/execution/config state. Entry lifecycle terms are authored after actual fill, with request metadata unable to replace the order's broker_entry terms. Fixed simulated funding remains explicit and separate from public mode; deterministic event identity and settled-key idempotency are covered. No additional concrete broker finding in this review.

Synthetic output retains mode/source/seed/hashes and is economically rejected; missing historical provenance fails closed; economic eligibility requires an explicit drawdown contract and never grants owner acceptance. Source hashes currently cover four files only; root already plans to strengthen full source identity before the long replay.

Reviewed broker SHA256: 6c9e5f5cd071aeecface20aa5fd5b7e4698279dc69ff54c3ca0374926248d334. Loader SHA256 at finding: 226924f3410d3fe2a010792a9792a1aae241726b995e6b24d8bddeed130d9fc0. Runner SHA256: 40fb58331bca8bfc31b260bee5ede412b211bfd2845d755a39bbf298f8634d0b.

Limits: full core, long-year E2E, actual public historical provenance, frontend composition, Windows lifecycle and all recovery/runtime code were not independently verified here. Root owns those tests. Graph navigation is PARTIAL_STATIC and the original graph reviewer rejected stale filename-only summaries; no graph approval or economic acceptance follows from this review. Initial review verdict: CHANGES_REQUIRED for the P1 availability finding.

## Follow-up after root repair

The root added a distinct settlement-phase availability check: at event rows, available time cannot exceed normalized event plus the declared one-second jitter. The separate candle-close decision check remains. The exact 14-minute reproduction is now a regression that expects rejection. Loader parsing now consumes a BufferReader of the exact bytes that passed SHA validation, avoiding a later path reread race. The source manifest covers all src/scripts Python files, and replay refuses publication if that source identity changes mid-run.

Independent rerun of the same seven test files using basetemp ../../tmp/review-scope-1030-v2: **134 passed in 8.44s**, no skips/deselections. Reviewed the new delayed-availability, cache replacement, full source identity and mid-run source change tests and the connected implementation. P1 is resolved; no remaining actionable finding in this scoped review. This is scoped engineering review, not owner acceptance or market backtest validation. Full integration and independent testing outside this scope remain required.

Follow-up loader SHA256: dbf35c01c98251b33fa7c415d6b662cab51a22d41b2b3f0ef1feefce87b7be02. Runner SHA256: 40fb58331bca8bfc31b260bee5ede412b211bfd2845d755a39bbf298f8634d0b. Broker SHA256 remains as above.
