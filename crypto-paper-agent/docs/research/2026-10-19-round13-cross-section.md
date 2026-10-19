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
