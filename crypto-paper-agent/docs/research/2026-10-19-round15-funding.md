# Round 15: funding-rate crowding rules on the top-10 perpetuals (2026-10-19)

Paper only, on Binance USDⓈ-M perpetual futures (2x leverage, funding, shorts). Pre-registered
before the development run; results are AUTHOR_REPORTED and not independently verified.
Every run is appended to the research ledger.

## Owner requests (2026-10-19)
"Ok hãy chạy tiếp 1 phương pháp khác, được phép copy người khác", "Bằng mọi giá phải giúp tôi
tìm ra được cách", "Nên nhớ chúng ta đang trade future".

Rounds 1-14 used price only, apart from round 2's spot-perp cash-and-carry basket (entry at a
15% APR funding level; it never opened in 2026). Round 15 uses funding as information about
crowding, a signal only perpetual futures have. Source: Schmeling, Schrimpf and Todorov,
"Crypto carry", BIS working paper 1087 (https://bis.org/publ/work1087.htm): carry (the
futures-spot gap that funding tracks) averages above 10% a year, is driven by trend-chasing
leveraged demand and scarce arbitrage capital, and **high carry predicts future crashes**.
The cross-sectional sort (F2/F3) is our application of that finding to the top-10; we found
no published test of it with costs.

## Candidates (src/strategies/funding_signals.py)
A decision at a 4h close uses only funding events settled at or before that close.

| Key | Rule |
|---|---|
| C1 | reference: round-8 swing EMA pullback, long only, on the same 10 coins (not selectable) |
| F1 | C1, but no new long while the coin's 7-day mean funding is above the 90th percentile of its own daily 7-day means over the past 180 days (needs 90 days of history) |
| F2 | weekly (4h bar opening Sunday 20:00 UTC): rank the 10 coins by 7-day mean funding; long the 3 lowest, short the 3 highest; exit at a later weekly bar when the coin leaves its group; stop 2 daily ATR(14) |
| F3 | as F2, short side only, and only when the coin's 7-day mean funding is positive |

Settings (7 days, 180 days, 90th percentile, top 3 of 10, 2 ATR) are fixed before any run.

## Data, costs and risk
- Development: top-10 2021-01-01..2023-12-31 at 2% and 5% risk per trade.
- Costs 0.05% taker + 0.03% slippage per side, funding at 00/08/16 UTC. Leverage 2x, order cap
  2x equity, liquidation buffer, 5% daily-loss breaker (realized cash flows, per sleeve), stop
  on every trade. No limit is relaxed. The streak rule halves risk after 3 losses.
- After the freeze, checks are on **seen** data only and labelled as context: top-10
  2024-01..2026-09 (and with costs x2), 2026-10-01..17, and C1 on the same top-10 at the same
  risk. New evidence comes only from forward paper from 2026-10-18.

**Disclosure.** No backtest or signal count ran before this plan was committed; only the
unit tests on synthetic data.

## Selection (fixed now; the round-8 rule)
1. Among F1-F3 x risk with no losing development year and max drawdown <= 35%, take the
   highest geometric average month.
2. Otherwise the highest average month with max drawdown <= 35%.
3. Otherwise the best return / max drawdown.
The result also reports whether the pick beats C1 on the same top-10 at the same risk. The
choice is frozen by commit before any check.

## Development results (top-10 2021-01..2023-12; AUTHOR_REPORTED)

| Run | Return % | Max DD % | Trades | Win % | Average month % | Median month % | Worst month % | Losing months / 36 | 2021 | 2022 | 2023 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C1 risk 2% | 52.37 | 10.95 | 1291 | 24.2 | 1.18 | -0.35 | -1.88 | 22 | 37.47 | -3.18 | 14.48 |
| C1 risk 5% | 174.45 | 21.31 | 1269 | 24.4 | 2.84 | -0.74 | -4.31 | 22 | 95.24 | -6.06 | 49.64 |
| F1 risk 2% | 44.36 | 9.89 | 1080 | 23.8 | 1.03 | -0.3 | -1.82 | 21 | 29.05 | -3.09 | 15.43 |
| F1 risk 5% | 127.74 | 21.31 | 1050 | 24.1 | 2.31 | -0.69 | -4.7 | 22 | 72.37 | -6.48 | 41.28 |
| F2 risk 2% | 9.37 | 3.13 | 346 | 46.2 | 0.25 | 0.03 | -0.78 | 17 | 5.89 | -1.28 | 4.62 |
| F2 risk 5% | 23.99 | 7.06 | 344 | 46.2 | 0.6 | -0.11 | -2.22 | 20 | 16.98 | -3.6 | 9.95 |
| F3 risk 2% | -1.71 | 2.8 | 195 | 46.7 | -0.05 | -0.05 | -1.02 | 18 | -0.72 | 0.74 | -1.72 |
| F3 risk 5% | -7.21 | 8.1 | 194 | 46.4 | -0.21 | -0.25 | -2.52 | 21 | -1.91 | 1.66 | -6.95 |

**Selection: F1 at 5% risk** (C1 with the crowded-funding filter), rule level "drawdown only":
every variant lost in at least one development year. Average month +2.31%, max drawdown
21.3%, 1,050 trades, win rate 24.1%. It does **not** beat C1 at the same risk (+2.84%): the
filter removed about 220 C1 trades and more winners than losers. Step reached: none.

Other findings: the weekly funding sort (F2) made +0.6% a month at 5% with a 7.1% drawdown
but lost 3.6% in 2022; shorting only the most crowded longs (F3) lost money (-7.2% at 5%),
so in 2021-23 high funding on a coin did not predict that coin falling within a week.

Frozen by this commit before any check.
