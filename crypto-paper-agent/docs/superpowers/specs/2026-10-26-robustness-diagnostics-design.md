# Research robustness diagnostics design

## Goal

Make future strategy reports answer four questions that headline return and maximum drawdown do not:

1. How long did the strategy remain below its prior equity high, and how long did its worst drawdown take to recover?
2. Did the candidate beat matched random entries run under the same execution and risk rules?
3. Did returns depend mainly on broad market direction or one market regime?
4. Were gains concentrated in a small number of months or years?

## Design

Add pure, reusable diagnostics in `src/research/robustness.py`. They consume already-produced equity, periodic-return and placebo-result series; they do not fetch data, label regimes using future information or simulate fills.

- `drawdown_diagnostics` reports both the deepest episode and the longest underwater episode. An unrecovered episode is measured to the final observation and explicitly marked open.
- `profit_concentration` decomposes additive equity changes by month and year and reports how much of gross positive change came from the top one and top three periods.
- `placebo_comparison` requires an explicit higher-is-better direction, then reports the candidate's empirical percentile and a finite-sample one-sided exceedance probability against all preregistered random runs. It does not declare significance.
- `benchmark_dependence` reports beta, correlation and compounded strategy return during benchmark-up, benchmark-down and benchmark-flat observations.
- `regime_stability` reports count, compounded return, mean return and win rate for caller-supplied causal regime labels. It does not invent a universal stability threshold.

The standard owner-facing curve summary includes drawdown duration and profit concentration automatically. Placebo, benchmark and regime diagnostics require additional inputs from the strategy runner and remain separate evidence blocks.

## Boundaries

- Existing strategy rules, fills, risk settings and historical ledger rows remain unchanged.
- Random entries must still reuse the candidate's sizing, stop, target, holding period, costs, funding and risk gates.
- Regime labels must be available at the evaluated timestamp; future-derived labels are invalid.
- These diagnostics describe behavior. They do not turn protocol completeness into a profitability verdict.
