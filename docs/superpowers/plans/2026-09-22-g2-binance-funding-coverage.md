# G2 Binance funding-coverage diagnostic

Gate: G2 data integrity, author implementation only. This slice does not accept G2 or change ADR 0011 settlement policy.

## Scope and ownership

- Own `src/research/artifacts.py`, `scripts/prepare_public_research_sample.py`, and `tests/test_public_data_pipeline.py` for a portable, deterministic funding coverage summary in the public dataset manifest.
- Count scheduled 00:00/08:00/16:00 UTC one-minute boundaries, exact source timestamps, and readiness independently. Record unavailable boundaries without shifting funding events or creating simulated cashflows.
- Keep all market access public and read-only. No TradingView browser session, exchange orders, testnet, credentials, or parameter tuning.
- Preserve the dirty original checkout by working only on `codex/g2-binance-funding-coverage` in an isolated worktree.

## Test-first sequence

1. Add a pure regression oracle with one exact, one delayed, and one absent settlement. Confirm it fails before implementation.
2. Add a mocked-archive test that confirms the manifest includes the coverage summary and retains source timestamps. Confirm it fails before implementation.
3. Implement the smallest calculation and manifest inclusion, then run focused tests, historical probes and full offline tests on frozen code.
4. Re-run the bounded seven-day Binance sample without tuning, verify all source checksums and recompute the manifest coverage against source events. Keep sample artifacts outside Git and report exact SHA-256 identities.
5. Self-review; commit code/tests as A, docs/evidence as B, and push this branch without changing `main`.

## Non-goals and exit

- Do not reinterpret delayed funding as occurring on the nominal candle open; that needs an explicit owner/ADR decision.
- Do not call an unavailable full-funding replay a pass. Directional/PPO results from a blocked data window remain scoped diagnostics, not performance claims.
- A completed diagnostic is `AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED` until separate Tester and Independent Reviewer verification.
