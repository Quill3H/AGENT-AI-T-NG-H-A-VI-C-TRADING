# ADR 0013 — Exchange Settlement Timestamp Jitter Tolerance

## Context

Under ADR 0011, funding settlement requires an exact source funding timestamp and readiness at each nominal 8-hour boundary (00:00, 08:00, 16:00 UTC).

However, real-world public exchange archives and REST endpoints from Binance Futures record settlement execution timestamps with millisecond system latency (e.g., `00:00:00.003` UTC instead of `00:00:00.000` UTC). In an empirical 7-day sample from Binance Vision (2026-08-20 to 2026-08-26), 10 out of 21 settlement events arrived with a delay of 1–6 ms.

Because backward as-of merges strictly match events with timestamps $\le$ candle open time, a funding event at `00:00:00.003` was not matched to the `00:00:00.000` candle, causing `funding_readiness` to evaluate to `False` at settlement boundaries. This caused the simulation engine to fail closed with `ERROR [INVALID_INPUT]: funding_readiness must be True at settlement`.

Under Binance exchange rules, the funding rate for boundary $T$ is determined by the TWAP of the Premium Index over the preceding 8-hour interval $[T - 8\text{h}, T]$. It contains zero future information relative to $T$. The millisecond timestamp $T + \delta$ reflects only internal transaction commit latency in Binance's database.

## Decision

1. **Jitter Tolerance Window**: A funding source event with timestamp $t_{\text{source}}$ is recognized as the valid settlement event for nominal 8-hour boundary $T \in \{00:00, 08:00, 16:00\}$ UTC if:
   $$0 \le t_{\text{source}} - T \le \Delta t_{\text{jitter}}$$
   where $\Delta t_{\text{jitter}}$ defaults to 5,000 ms (5 seconds).

2. **Provenance Preservation**:
   - `observed_funding_time`: Preserves the exact, unmodified exchange timestamp (e.g., `00:00:00.003000Z`) for 100% auditability.
   - `funding_time`: Aligned to the nominal settlement boundary $T$ for causal matching with candle settlement boundaries.
   - `funding_readiness`: Evaluates to `True` at boundary $T$ when a valid jitter-tolerated source event is present.

3. **Configurable Policy**:
   - `prepare_public_research_sample.py` supports `--settlement-tolerance-ms` (default: 5,000 ms). Setting `--settlement-tolerance-ms 0` retains strict legacy ADR 0011 zero-jitter behavior.
   - Diagnostic coverage metrics in `dataset_manifest.json` report both strict zero-jitter `exact_ready` and `jitter_tolerated_ready`.

## Consequences

- Resolves the G2 bottleneck where 10/21 Binance funding boundaries failed closed.
- Eliminates replay crashes on real Binance public data while strictly maintaining anti-lookahead invariants.
- 100% backward compatible: strict zero-jitter verification remains testable with `--settlement-tolerance-ms 0`.

