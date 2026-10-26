# Research Integrity Hardening Design

## Intent

Turn the useful parts of the reviewed Reddit post into reusable research safeguards. Future
rounds must be able to declare the hypothesis, the variants being selected, required controls
and cost stresses before results are appended. The ledger must then show whether that protocol
was completed. A deterministic helper supplies matched random entry timestamps; the strategy
runner remains responsible for applying the same sizing, exits and costs.

## Goals

- Keep an append-only, causal preregistration in the existing research ledger.
- Reject protocol-tagged runs that use an undeclared variant or cost multiplier.
- Report the observed trial count and a Bonferroni reference threshold without claiming that
  the threshold itself proves an edge.
- Generate reproducible random-entry placebo samples from a caller-provided eligible universe.
- Preserve all existing ledger writers and historical records.

## Non-goals

- No trading rule, risk limit, fill model or Round 18 result changes.
- No retrofit that pretends old rounds were preregistered.
- No generic profitability verdict, Deflated Sharpe implementation or automatic parameter
  search.
- No strategy-specific placebo backtest in this change; each strategy must replay the sampled
  entries through its own unchanged execution and exit logic.

## Approaches

1. Documentation only. Smallest diff, but nothing enforces causal registration or declared
   variants.
2. Break every existing runner by making the new protocol mandatory immediately. Strongest
   enforcement, but it rewrites historical workflows and risks invalidating reproducibility.
3. Add an enforced protocol path beside the legacy path, surface both in the generated ledger
   report, and require the new path for future research plans. This preserves old evidence while
   making new research auditable.

Approach 3 is selected. It adds no dependency and leaves old JSONL rows readable. Legacy rounds
are labelled `LEGACY_UNREGISTERED`; that label is a protocol limitation, not an economic verdict.

## Constraints

- Paper only; no exchange, credential or wallet behavior.
- Append-only JSONL remains the source of truth.
- Registration must precede the first result for its round.
- Random controls use only timestamps supplied by the caller and never infer future eligibility.
- Protocol completeness and strategy profitability remain separate conclusions.
