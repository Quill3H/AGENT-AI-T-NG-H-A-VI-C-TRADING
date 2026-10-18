# Round 10: Wyckoff and Ichimoku on BTC/ETH/SOL (2026-10-18)

Paper only. Pre-registered before any development run (a loading smoke test ran on
BTC 2021-01..04, inside development); results are AUTHOR_REPORTED and not independently
verified. Every run is appended to the research ledger.

## Owner request (2026-10-18 16:54)
"Ok, phát triển thử thêm Phương pháp giao dịch Wyckoff. và cả phương pháp giao dịch
ichimoku, hãy phát triển trên BTC ETH SOL duy nhất": develop Wyckoff further and keep
developing Ichimoku, on BTC, ETH and SOL only.

## Data limits, stated first
Every BTC/ETH/SOL bar up to 2026-10-17 has already been used by a final test (rounds 1-9).
So this round has no untouched holdout: after the freeze it runs checks on seen data only
(labelled `validation`, context, not evidence). The frozen pick joins the weekly forward
paper runs from 2026-10-18, which are the only new evidence.

## Candidates
Wyckoff (src/strategies/wyckoff_suite.py). A trading range is the 40 bars before the signal
with height <= 8 ATR(14) and ADX(14) < 25 (round 5's W3 definition). Exit for both: a close
across EMA(50) or 60 bars, so a move out of the range can run (round 8: a few big moves
carry the result).
- WY1 spring/upthrust: a bar with volume > 1.5x the 20-bar mean trades below the range low
  and closes back inside -> long, stop 0.25 ATR under its low. Mirror short. On 4h and 1h.
- WY2 sign of strength + last point of support: within the last 10 bars a high-volume bar
  closed above the range (SOS), no close has fallen back into it, and this bar's low comes
  back within 0.5 ATR of the range high and closes above it (LPS) -> long, stop 0.25 ATR
  under this bar's low. Mirror (sign of weakness + last point of supply) short. 4h and 1h.
Ichimoku (src/strategies/ichimoku_suite.py), building on round 9's I1-4h:
- I3-4h: I1 entries only on the side of the daily cloud (daily bars from finished days).
- I4-4h: I1 with the stop trailed to 0.5 ATR beyond the Kijun every bar.
Mix:
- M1: equal-weight sleeves of round-8 C1 (W1 long only), round-9 I1-4h and WY2-4h.
References (not selectable): I1-4h and round-5 W3.

## Splits, costs, selection
- Development: BTC/ETH/SOL 2021-01..2023-12, risk 2% and 5%.
- After the freeze (seen, context): BTC/ETH/SOL 2024-01..2026-09, the same with costs x2,
  and 2026-10-01..17.
- Costs 0.05% taker + 0.03% slippage per side; leverage 2x, order cap 2x equity, 30%
  liquidation buffer, 5% daily-loss breaker, a stop on every trade. Nothing is relaxed.
- Selection (round-8 rule): among runs with no losing development year and max drawdown
  <= 35%, the highest geometric average month; else the highest average month with max
  drawdown <= 35%; else the best return / max drawdown. Steps 10/20/30/50% a month reported.
