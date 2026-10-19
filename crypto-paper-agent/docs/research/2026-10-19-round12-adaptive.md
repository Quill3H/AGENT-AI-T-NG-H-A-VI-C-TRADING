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
