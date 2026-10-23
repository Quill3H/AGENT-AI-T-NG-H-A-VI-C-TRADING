# Research integrity protocol

This protocol improves how a strategy is tested. It does not make a strategy profitable and
does not replace an independent review.

## Future-round sequence

1. Write the hypothesis, candidate variants, control configuration and cost multipliers before
   reading performance results. Round 19 and later cannot append a result without this step.
2. Call `src.research.ledger.preregister(...)` before the first result for that round. The
   ledger refuses a late or duplicate registration.
3. Freeze the code/config commit in the registration itself.
4. Append each result with `ledger.record(..., protocol={...})`. A protocol run is rejected if
   its candidate, hypothesis, variant, role, control configuration, cost multiplier or commit
   differs from the registration.
5. Generate `docs/research/ledger/LEARNING_LOG.md` with `scripts/ledger_report.py`. Read the
   `Research integrity` table separately from the strategy's return and risk result.

Example:

```python
ledger.preregister(
    19,
    "btc_example_v1",
    variants=["V1", "V2"],
    controls={"matched_random": {"seed": 7, "repetitions": 100}},
    cost_multipliers=[1.0, 2.0],
    frozen_commit=commit,
)

ledger.record(
    19, "validation", "V1", "btc_example", "V1 base", start, end,
    ["BTCUSDT"], "0.5%", summary, frozen_commit=commit,
    protocol={
        "hypothesis_id": "btc_example_v1",
        "variant_id": "V1",
        "run_role": "candidate",
        "cost_multiplier": 1.0,
    },
)

ledger.record(
    19, "validation", "V1", "btc_example", "V1 placebo", start, end,
    ["BTCUSDT"], "0.5%", placebo_summary, frozen_commit=commit,
    protocol={
        "hypothesis_id": "btc_example_v1",
        "variant_id": "V1",
        "run_role": "matched_random",
        "cost_multiplier": 1.0,
        "control_spec": {"seed": 7, "repetitions": 100},
    },
)
```

`PROTOCOL_COMPLETE` means only that every declared variant, cost and role combination was
recorded from the registered commit. A single placebo row cannot satisfy multiple variants or
cost scenarios. `PROTOCOL_INCOMPLETE` names missing evidence.
`LEGACY_UNREGISTERED` means the round predates this causal record or did not use it. None of
these statuses is a profitability verdict.

Every new result receives a `run_id`. If two results reuse a label, pass the intended ID to
`ledger.void(..., run_id=...)`; the ledger rejects an ambiguous label instead of voiding both.
For a legacy duplicate that predates run IDs, use its exact timestamp with
`ledger.void(..., target_recorded_at=...)`. Metadata stages `preregister`, `lesson` and `void`
can only be written through their dedicated functions.

The reported Bonferroni value is `familywise_alpha / declared_variants`. It is a reference for
the declared search family. The project must not treat it as a valid significance result unless
the strategy supplies an appropriate, dependence-aware statistical test. Every strategy,
feature set, parameter set, asset universe or execution variation inspected while selecting a
winner belongs in the declared family; hiding attempts invalidates the reference.

## Matched random-entry control

Use `src.research.controls.matched_random_entry_sets(...)` with:

- `eligible_times`: timestamps at which an entry was genuinely possible using information
  available then, for the same symbol, window and regime filter;
- `signal_times`: the strategy's actual entry timestamps;
- a preregistered repetition count and seed.

The helper samples the same number of entries, excludes the actual signals and returns sorted
UTC timestamps. It deliberately does not calculate PnL. For every sample, the strategy runner
must reuse the candidate's position sizing, stop, target, maximum holding time, fee, slippage,
funding and risk gates. Compare the candidate against the distribution of placebo outcomes, not
against one lucky or unlucky seed.

Do not construct `eligible_times` from future returns, future volatility, whether a stop would
have hit, or whether an order would later fill. Event-driven strategies also need their cooldown
and one-position-at-a-time rules applied when converting sampled timestamps into executable
entries.

## Existing evidence

Historical ledger rows, including Round 18, remain unchanged. They cannot be retroactively
preregistered. Their existing frozen configs, controls and review evidence still stand on their
own terms; the generated integrity table labels the protocol limitation explicitly.

