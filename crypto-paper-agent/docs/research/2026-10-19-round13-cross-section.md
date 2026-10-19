# Round 13: cross-sectional momentum on the top-10 coins (2026-10-19)

Paper only. Pre-registered before the development run; results are AUTHOR_REPORTED and
not independently verified. Every run is appended to the research ledger.

## Owner request (2026-10-19 08:31)
"Sau khi chạy xong, tổng hợp các thông tin thu được từ 12 vòng. Xong rút kinh nghiệm để chạy
thử tiếp vòng 13 ? không lẽ trên thế giới không ai có lời từ việc trade future ?"

Rounds 1-12 all judged each coin on its own chart (trend, pullback, breakout, candles,
reversion). The best (C1/A2) earned most of their profit from a handful of trend trades and
were thin in 2024-2026. Round 13 tests a different kind of edge: rank coins against each
other and hold the relatively strong ones, with the weak ones as the short side. This is
the best-documented crypto return factor in the academic literature we found: Liu,
Tsyvinski and Wu, "Common Risk Factors in Cryptocurrency" (NBER w25882), report a weekly
long-short spread of about 4% a week for a 3-week lookback over 2014-2018 (t = 2.74), also
for above-median-size coins; their Fama-MacBeth tests are not significant, so the effect is
not settled. Their universe was hundreds of coins with spot prices and no costs; ours is 10
perpetuals with fees, slippage and funding.

## Candidates (4h signal, 15m execution, src/strategies/cross_section.py)
Universe: the top-10 list (BTC, ETH, XRP, BNB, SOL, DOGE, TRX, ADA, LINK, AVAX), one sleeve
per coin with equal capital ($1,000 each). Rebalance at the close of the 4h bar that opens
Sunday 20:00 UTC (the end of the UTC week). Ranking needs at least 6 coins with both the
current close and the close one lookback ago; only closed bars are used.

| Key | Rule |
|---|---|
| C1 | reference: round-8 swing EMA pullback, long only, on the same 10 coins (not selectable) |
| X1 | 3-week return rank: long the top 3, short the bottom 3; exit at a weekly bar when the coin leaves its group |
| X2 | as X1, long side only |
| X3 | as X1, but a long also needs its own 3-week return > 0 and a short < 0 ("dual" momentum) |
| X4 | as X1 with a 1-week lookback |

Every entry has a stop 2 x daily ATR(14) from the close (needs 15 completed days). Top 3 of
10 and 2 ATR are fixed before any run; no other values will be tried in this round.

## Data, costs and risk
- Development: top-10 2021-01-01..2023-12-31 (TRX data starts 2021-01-01), at 2% and 5%
  risk per trade.
- Costs 0.05% taker + 0.03% slippage per side, funding at 00/08/16 UTC. Leverage 2x, order cap
  2x equity, liquidation buffer, 5% daily-loss breaker (realized cash flows, per sleeve),
  stop on every trade. No limit is relaxed. Note from the round-12 audit: the streak rule
  halves risk after 3 losses and needs 3 wins in a row to recover, so "5%" mostly runs at 2.5%.
- After the freeze, checks are on **seen** data only and labelled as context: top-10
  2024-01..2026-09 (and with costs x2), 2026-10-01..17, and C1 on the same top-10
  2024-01..2026-09 at the same risk. New evidence comes only from forward paper from
  2026-10-18 (weekly check-in).

**Disclosure.** Before this plan was committed, a wiring smoke test ran X1 on the top-10
2021-01-01..2021-02-28 at 2% (inside this round's development window; +0.16%, not written to
the ledger). No other data was touched.

## Selection (fixed now; the round-8 rule)
1. Among X1-X4 x risk with no losing development year and max drawdown <= 35%, take the
   highest geometric average month.
2. Otherwise the highest average month with max drawdown <= 35%.
3. Otherwise the best return / max drawdown.
The result also reports whether the pick beats C1 on the same top-10 at the same risk. Steps
of 10/20/30/50% a month are reported. The choice is frozen by commit before any check.

## Development results (top-10 2021-01..2023-12; AUTHOR_REPORTED)

| Run | Return % | Max DD % | Trades | Win % | Average month % | Median month % | Worst month % | Losing months / 36 | 2021 | 2022 | 2023 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C1 risk 2% | 52.37 | 10.95 | 1291 | 24.2 | 1.18 | -0.35 | -1.88 | 22 | 37.47 | -3.18 | 14.48 |
| C1 risk 5% | 174.45 | 21.31 | 1269 | 24.4 | 2.84 | -0.74 | -4.31 | 22 | 95.24 | -6.06 | 49.64 |
| X1 risk 2% | 11.5 | 3.04 | 357 | 40.3 | 0.3 | 0.17 | -1.03 | 14 | 5.35 | 1.32 | 4.46 |
| X1 risk 5% | 23.98 | 8.29 | 357 | 40.1 | 0.6 | 0.5 | -2.61 | 13 | 8.62 | 3.64 | 10.14 |
| X2 risk 2% | 10.33 | 5.01 | 184 | 41.3 | 0.27 | 0.07 | -1.3 | 15 | 7.09 | -2.39 | 5.55 |
| X2 risk 5% | 28.67 | 12.76 | 184 | 41.3 | 0.7 | 0.1 | -2.97 | 15 | 18.98 | -6.07 | 15.14 |
| X3 risk 2% | 11.08 | 4.74 | 258 | 41.9 | 0.29 | 0.08 | -0.89 | 16 | 5.26 | 0.18 | 5.34 |
| X3 risk 5% | 29.48 | 13.22 | 258 | 41.9 | 0.72 | 0.18 | -2.86 | 16 | 13.88 | 0.36 | 13.29 |
| X4 risk 2% | 5.9 | 3.88 | 458 | 46.3 | 0.16 | -0.04 | -0.78 | 20 | 4.68 | 0.28 | 0.88 |
| X4 risk 5% | 14.64 | 8.98 | 457 | 46.2 | 0.38 | -0.05 | -2.37 | 20 | 11.97 | 0.51 | 1.86 |

**Selection: X3 at 5% risk** (3-week dual momentum: long a top-3 coin only if its own return
is positive, short a bottom-3 coin only if negative), rule level "full": no losing year, max
drawdown 13.2%, average month +0.72%. It does **not** beat C1 on the same top-10 at 5%
(+2.84% a month, drawdown 21.3%, but C1 lost 6.1% in 2022). Win rate 41.9% (C1 24.4%). Step
reached: none (10% not reached).

Other findings: every relative-strength variant wins 40-46% of trades with small, steady
gains and a 3-13% drawdown, far smoother than C1 but with a quarter of its monthly return.
The long/short X1 had no losing year and the smallest drawdown (8.3% at 5%); the long-only
X2 lost in 2022; the 1-week X4 was weakest (+0.38% a month).

Frozen by this commit before any check.
