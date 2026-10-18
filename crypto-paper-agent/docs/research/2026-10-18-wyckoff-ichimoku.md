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

## Development results (BTC/ETH/SOL 2021-01..2023-12; AUTHOR_REPORTED)

| Run | Return % | Max DD % | Trades | Win % | Average month % | Worst month % | Losing months / 36 | 2021 | 2022 | 2023 |
|---|---|---|---|---|---|---|---|---|---|---|
| I1-4h risk 2% | 23.0 | 9.13 | 301 | 31.9 | 0.58 | -3.83 | 14 | 6.29 | 5.67 | 9.5 |
| I1-4h risk 5% | 32.91 | 22.79 | 274 | 31.8 | 0.79 | -9.57 | 16 | 16.64 | 3.5 | 10.1 |
| I3-4h risk 2% | 15.44 | 8.86 | 166 | 33.7 | 0.4 | -3.83 | 17 | 8.08 | 7.69 | -0.82 |
| I3-4h risk 5% | 28.0 | 23.29 | 146 | 34.2 | 0.69 | -9.45 | 19 | 25.66 | 8.74 | -6.32 |
| I4-4h risk 2% | 18.72 | 8.38 | 302 | 32.8 | 0.48 | -3.77 | 13 | 4.74 | 4.14 | 8.84 |
| I4-4h risk 5% | 23.96 | 18.38 | 274 | 32.8 | 0.6 | -9.76 | 14 | 12.51 | 3.14 | 6.82 |
| M1 risk 2% | 27.51 | 10.65 | 871 | 25.6 | 0.68 | -2.31 | 17 | 6.18 | 1.98 | 17.76 |
| M1 risk 5% | 108.18 | 24.77 | 777 | 26.8 | 2.06 | -5.12 | 19 | 17.35 | 3.21 | 71.87 |
| W3 risk 2% | 0.97 | 8.82 | 152 | 35.5 | 0.03 | -4.44 | 19 | 0.31 | 0.79 | -0.13 |
| W3 risk 5% | 8.83 | 15.22 | 102 | 40.2 | 0.24 | -6.56 | 17 | -4.72 | 14.36 | -0.12 |
| WY1-1h risk 2% | -40.68 | 41.1 | 918 | 37.7 | -1.44 | -4.86 | 28 | -16.29 | -12.07 | -19.4 |
| WY1-1h risk 5% | -25.14 | 29.56 | 325 | 39.1 | -0.8 | -5.14 | 24 | -3.81 | -16.15 | -7.19 |
| WY1-4h risk 2% | -10.93 | 13.22 | 194 | 33.5 | -0.32 | -2.2 | 24 | -0.66 | -5.88 | -4.74 |
| WY1-4h risk 5% | -5.96 | 14.41 | 139 | 38.1 | -0.17 | -3.94 | 22 | 5.42 | -7.02 | -4.06 |
| WY2-1h risk 2% | -33.86 | 41.11 | 789 | 15.6 | -1.14 | -8.76 | 24 | -23.55 | 2.48 | -15.57 |
| WY2-1h risk 5% | -13.19 | 44.78 | 366 | 22.1 | -0.39 | -12.67 | 25 | -31.0 | 5.75 | 18.96 |
| WY2-4h risk 2% | -12.27 | 33.07 | 204 | 14.7 | -0.36 | -6.93 | 27 | -12.3 | -2.88 | 3.0 |
| WY2-4h risk 5% | -26.3 | 44.75 | 146 | 17.8 | -0.84 | -13.28 | 26 | -31.73 | -6.53 | 15.51 |

**Selection: M1 at 5% risk** (C1 + I1-4h + WY2-4h), rule level "full": no losing year, max
drawdown 24.8%, average month +2.06%. Step reached: none.
- Every Wyckoff candidate lost in development (WY1 -6 to -41%, WY2 -12 to -34%). The SOS/LPS
  entry won only 15-22% of trades: breakouts from quiet ranges mostly fell back.
- Neither Ichimoku change beat round 9's I1-4h: the daily filter lost 2023 and cut trades,
  and the Kijun trail cut winners (0.6% vs 0.79% a month at 5%).
- M1 wins the rule only because it carries C1. It still trails C1 alone (+4.05% a month in
  round 8), so the WY2 sleeve costs return. Reported as is; the rule is not changed after
  the fact.
Frozen by this commit before any check run.
