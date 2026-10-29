# Round 12: rules that adapt to the market state (2026-10-19)

Paper only. Pre-registered before the development run; results are AUTHOR_REPORTED and
not independently verified. Every run is appended to the research ledger.

## Owner request (2026-10-19 07:42)
"Hãy tiếp tục thích nghi với thị trường và thử phương pháp mới đi": keep adapting to the
market and try new methods.

Round 11 showed that C1 (round-8 swing EMA pullback, long only) is still the best and that a
filter that helps in 2021-2023 can hurt in 2024-2026. This round tries rules whose behaviour
changes with the market state: an adaptive average, exits that follow trend strength or
volatility, real order flow, a volatility regime, and a trend/range switch. None of these is
in the ledger yet (`regime_switch` from round 3 used Donchian/RSI2, not C1/Bollinger).

## Candidates (4h signal, 15m execution, long only, src/strategies/adaptive_suite.py)
| Key | Rule |
|---|---|
| C1 | reference: round-8 swing EMA pullback, long only (not selectable) |
| A1 | Kaufman adaptive moving average KAMA(10,2,30): close crosses above KAMA, KAMA above its value 3 bars ago, efficiency ratio(10) > 0.3; stop 5-bar low - 0.5 ATR; exit close < KAMA |
| A2 | C1 entries; exit at a close under EMA20 while ADX(14) <= 25 (weak trend), under EMA50 when ADX > 25 |
| A3 | C1 with a Chandelier trailing stop: 22-bar high - 3 ATR(22), stop only tightens; EMA50 exit stays |
| A4 | C1 only when the 20-bar sum of taker buy minus taker sell volume is above zero (Binance taker buy volume, in the bar data) |
| A5 | daily ADX(14) on the last completed day >= 20: C1; < 20: previous close under the lower Bollinger band (20,2), this close back above it -> long, stop 1 ATR under the 3-bar low, target the middle band, time exit 12 bars |
| A6 | C1 only when ATR(14)/close is above its median of the previous 100 bars (volatility expanding) |

Settings are published defaults (Kaufman 10/2/30, Chandelier 22/3, Bollinger 20/2, ADX 14
with the usual 20/25 levels), fixed before any run.

## Data, costs and risk
- Development: BTC/ETH/SOL 2021-01-01..2023-12-31, at 2% and 5% risk per trade.
- Costs 0.05% taker + 0.03% slippage per side. Leverage 2x, order cap 2x equity, 30%
  liquidation buffer, 5% daily-loss breaker, stop on every trade. No limit is relaxed.
- After the freeze, checks are on **seen** data only and labelled as context: BTC/ETH/SOL
  2024-01..2026-09 (and with costs x2), 2026-10-01..17, and the top-10 2021-01..2026-09, plus
  C1 on 2024-01..2026-09 side by side. New evidence comes only from forward paper from
  2026-10-18 (weekly check-in).

**Disclosure.** Before this plan was committed, a wiring smoke test ran all seven candidates on
BTC 2021-01..02 at 2% (inside this round's development window). No other data was touched.

## Selection (fixed now; the round-8 rule)
1. Among A1-A6 x risk with no losing development year and max drawdown <= 35%, take the
   highest geometric average month.
2. Otherwise the highest average month with max drawdown <= 35%.
3. Otherwise the best return / max drawdown.
The result also reports whether the pick beats C1 at the same risk. Steps of 10/20/30/50% a
month are reported. The choice is frozen by commit before any check.

## Development results (BTC/ETH/SOL 2021-01..2023-12; AUTHOR_REPORTED)

| Run | Return % | Max DD % | Trades | Win % | Average month % | Median month % | Worst month % | Losing months / 36 | 2021 | 2022 | 2023 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A1 risk 2% | -2.14 | 6.02 | 188 | 25.5 | -0.06 | -0.11 | -1.62 | 21 | -1.67 | -0.26 | -0.22 |
| A1 risk 5% | -0.48 | 12.5 | 180 | 26.7 | -0.01 | -0.2 | -3.93 | 19 | -4.22 | -0.28 | 4.2 |
| A2 risk 2% | 107.17 | 13.17 | 469 | 28.4 | 2.04 | 0.0 | -2.29 | 16 | 28.83 | 1.7 | 58.12 |
| A2 risk 5% | 487.78 | 25.66 | 461 | 28.4 | 5.04 | 0.0 | -4.97 | 15 | 80.59 | 6.41 | 205.86 |
| A3 risk 2% | 37.11 | 12.1 | 507 | 29.0 | 0.88 | 0.0 | -2.76 | 15 | 16.77 | 1.98 | 15.14 |
| A3 risk 5% | 127.1 | 24.18 | 495 | 29.1 | 2.3 | 0.01 | -6.48 | 14 | 43.05 | 5.57 | 50.37 |
| A4 risk 2% | 46.77 | 5.7 | 79 | 30.4 | 1.07 | 0.0 | -1.61 | 15 | 4.25 | 0.7 | 39.8 |
| A4 risk 5% | 131.22 | 12.83 | 79 | 29.1 | 2.36 | 0.0 | -3.97 | 16 | 9.88 | 0.95 | 108.45 |
| A5 risk 2% | 50.44 | 13.8 | 396 | 29.5 | 1.14 | -0.35 | -2.82 | 21 | 17.45 | -3.01 | 32.06 |
| A5 risk 5% | 167.32 | 28.35 | 375 | 30.1 | 2.77 | -0.65 | -7.64 | 19 | 45.21 | -5.89 | 95.62 |
| A6 risk 2% | 26.05 | 7.37 | 165 | 28.5 | 0.65 | 0.0 | -1.92 | 15 | 11.85 | 1.89 | 10.6 |
| A6 risk 5% | 74.46 | 16.22 | 164 | 28.7 | 1.56 | 0.0 | -4.83 | 15 | 30.03 | 5.49 | 27.18 |
| C1 risk 2% | 71.8 | 14.13 | 366 | 26.5 | 1.51 | -0.08 | -1.99 | 18 | 24.56 | 2.24 | 34.91 |
| C1 risk 5% | 317.92 | 31.35 | 357 | 26.6 | 4.05 | -0.07 | -6.81 | 18 | 67.16 | 7.0 | 133.66 |

**Selection: A2 at 5% risk** (C1 with the ADX-adaptive exit), rule level "full": no losing
year, max drawdown 25.7%, average month +5.04% (C1 at 5%: +4.05%, drawdown 31.4%). Win rate
28.4% (C1 26.6%), losing months 15 of 36 (C1 18). Step reached: none (10% not reached).

Other findings: the KAMA trend (A1) is flat to slightly negative; the Chandelier stop (A3)
and the volatility filter (A6) cut C1's big winners; the order-flow filter (A4) keeps only 79
trades with the lowest drawdown (12.8% at 5%) but half C1's monthly return; the trend/range
switch (A5) lost in 2022, inferred to come from the Bollinger reversion leg since C1 alone was positive that year.

Frozen by this commit before any check.

## Checks for A2 at 5% (frozen at 33296b0; all on seen data, context only; AUTHOR_REPORTED)

| Run | End equity $ | Return % | Max DD % | Trades | Win % | Average month % | Losing months |
|---|---|---|---|---|---|---|---|
| **B: BTC/ETH/SOL 2024-01..2026-09** | 11,860 | +18.6 | 22.0 | 468 | 23.9 | +0.52 | 13 / 33 |
| B, costs x2 | 10,154 | +1.5 | 28.1 | 469 | 22.6 | +0.05 | 16 / 33 |
| Reference C1, B | 11,778 | +17.8 | 24.3 | 375 | 22.9 | +0.50 | 17 / 33 |
| BTC/ETH/SOL 2026-10-01..17 | 9,864 | -1.4 | 2.0 | 3 | 0 | | |
| Top-10 2021-01..2026-09 | 32,241 | +222.4 | 24.0 | 3,117 | 24.0 | +1.71 | 41 / 69 |

B by year: 2024 +16.5%, 2025 +5.6%, 2026 to September -3.6%. Top-10 by year: 2021 +95.8%,
2022 -6.0%, 2023 +72.4%, 2024 +11.2%, 2025 -1.9%, 2026 -6.8%.

Verdict: step 1 (10% a month) NOT reached. A2 is the first variant that is at least as good
as C1 on both the development years and 2024-2026 (more return, less drawdown, fewer losing
months), but the 2024-2026 gain is small (+0.5% a month) and nearly disappears with doubled
costs. A2 joins the weekly forward paper next to C1.
