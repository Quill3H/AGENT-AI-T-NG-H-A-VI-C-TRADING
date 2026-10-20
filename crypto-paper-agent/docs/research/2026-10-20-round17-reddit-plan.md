# Round 17: the r/Daytrading "simple futures trading plan" on BTC/ETH/SOL perpetuals (2026-10-20)

Paper only, on Binance USDⓈ-M perpetual futures (2x leverage, funding, shorts). Pre-registered
before the development run; results are AUTHOR_REPORTED and not independently verified.
Every run is appended to the research ledger.

## Owner request (2026-10-20 08:32-08:44)
"hãy tổng hợp thêm thông tin và kinh nghiệm từ bài này" with a link to the r/Daytrading post
"The Simple Futures Trading Plan I Wish I Had When I Started". Reddit is blocked from this
session, so the owner pasted the post and its comments. The coordinator relayed: test it the
usual way on perps, record it, push it, and list the risk and behaviour lessons worth making
bot rules.

## What the post says (summary of the pasted text)
- Trade only around the market open; outside it the market chops.
- Use one or two recognisable setups (examples: trend pullback, failed breakout, VWAP bounce).
- Put the stop where the idea is wrong, then check that the reward is worth it; never widen a
  stop, fix the entry instead.
- At most a couple of trades a session, then stop. Journal every trade with a screenshot.
- Two concrete setups from the comments: (1) the pre-market "hesitation zone" of the hour
  before, broken between 7:00 and 7:30; (2) the reversal of the 9:30 opening candle: wait to
  9:45, look for a hammer, shooting star or engulfing candle on 5m, enter on the 1m pullback.
  Two trades a day, then stop.

The post trades CME index futures. Crypto perps trade 24/7, but the US open still moves them,
so the same US Eastern clock is used (with daylight saving). Whether that transfers is the
question this round tests.

## Rules (src/strategies/reddit_plan.py, fixed now)
- Setup 1 (premarket): range = high/low of the twelve 5m bars 06:00-07:00 ET. The first 5m
  close outside the range between 07:00 and 07:30 ET enters that way; the stop is the far side
  of the range. A later break the same day is ignored.
- Setup 2 (open_reversal): opening move = 09:30 open to the 09:45 close (three 5m bars). From
  09:45 to 11:00 ET, a 5m reversal candle against the move enters against it; the stop is
  beyond that candle's extreme. Hammer / shooting star: wick >= 2x body, opposite wick <= body,
  wick >= 60% of the bar. Engulfing: opposite colour, body covers the previous body.
- Target 2R. A trade whose stop is closer than 0.3% of price (about twice the round-trip cost)
  is skipped: "check that the reward is worth it".
- Each setup at most once a day, at most two entries a day; flat by 16:00 ET (or 96 bars).

| Key | Setups |
|---|---|
| C1 | reference: round-8 swing EMA pullback, long only, same BTC/ETH/SOL (not selectable) |
| R1 | setup 1 only |
| R2 | setup 2 only |
| R3 | both, the post's plan |

**Simplifications (disclosed).** The post times the setup-2 entry on a 1m pullback; here the
fill is the next 5m open after the signal bar. The range hour (06:00-07:00 ET), the 2R target,
the 0.3% minimum stop and the candle definitions are our choices; the post gives none of them.
VWAP and the "failed breakout" examples are not tested. One test mutant (moving the setup-2
window start from 09:45 to 09:30) is equivalent, because the rule already needs four bars
since 09:30.

## Data, costs and risk
- Data: Binance Vision 5m perps, BTC/ETH/SOL, from the forward dir (2021-01..2026-10-17).
- Development: 2021-01-01..2023-12-31 at 2% and 5% risk per trade.
- Costs 0.05% taker + 0.03% slippage per side, funding at 00/08/16 UTC. Leverage 2x, order cap
  2x equity, liquidation buffer, 5% daily-loss breaker, stop on every trade. No limit is
  relaxed. The streak rule halves risk after 3 losses.
- After the freeze, checks are on **seen** data only, labelled as context: 2024-01..2026-09
  (and costs x2), 2026-10-01..17, and C1 on the same coins at the same risk. New evidence comes
  only from forward paper.

**Disclosure.** No backtest of these rules ran before this plan was committed. Unit tests use
synthetic bars only. Round 7 tested other session-clock 5m rules (London breakout and others)
on the same coins, and its results were known when this round was set up.

## Selection (fixed now; the round-8 rule)
1. Among R1-R3 x risk with no losing development year and max drawdown <= 35%, take the
   highest geometric average month.
2. Otherwise the highest average month with max drawdown <= 35%.
3. Otherwise the best return / max drawdown.
The result reports whether the pick beats C1 at the same risk and the 5.9% a year bank
deposit (about 0.48% a month). The choice is frozen by commit before any check.

## Development results (BTC/ETH/SOL 2021-01..2023-12; AUTHOR_REPORTED)

| Run | Return % | Max DD % | Trades | Win % | Average month % | Median month % | Worst month % | Losing months / 36 | 2021 | 2022 | 2023 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C1 risk 2% | 71.8 | 14.13 | 366 | 26.5 | 1.51 | -0.08 | -1.99 | 18 | 24.56 | 2.24 | 34.91 |
| C1 risk 5% | 317.92 | 31.35 | 357 | 26.6 | 4.05 | -0.07 | -6.81 | 18 | 67.16 | 7.0 | 133.66 |
| R1 risk 2% | -50.49 | 54.71 | 1195 | 35.2 | -1.93 | -1.73 | -10.31 | 26 | -31.81 | -25.08 | -3.08 |
| R1 risk 5% | -22.9 | 37.41 | 410 | 39.0 | -0.72 | -0.42 | -11.77 | 19 | -12.14 | -14.75 | 2.93 |
| R2 risk 2% | -12.48 | 23.42 | 397 | 37.5 | -0.37 | -0.29 | -4.09 | 21 | 3.39 | -10.1 | -5.83 |
| R2 risk 5% | -10.56 | 12.53 | 27 | 33.3 | -0.31 | 0.0 | -5.36 | 9 | -2.62 | -7.48 | -0.73 |
| R3 risk 2% | -68.27 | 69.59 | 1638 | 35.3 | -3.14 | -2.86 | -11.46 | 26 | -40.24 | -41.24 | -9.64 |
| R3 risk 5% | -34.25 | 45.56 | 416 | 38.5 | -1.16 | -0.8 | -11.7 | 20 | -8.46 | -29.16 | 1.41 |

**Selection: R2 at 5% risk** (rule level "drawdown only"; it has the highest average month
among runs with drawdown <= 35%, and it is still a loss: -0.31% a month). Every R1-R3 run lost
money in development; none beats C1 or the bank deposit. Step reached: none.

Other findings: the post's full plan (R3) lost 68% at 2% risk with 1,638 trades: with a 2R
target the 35-39% win rate is just below break-even before costs, and costs on tight 5m stops
push it well under. At 5% risk far fewer signals became trades (27 for R2 against 397 at 2%);
one full stop plus costs can reach the 5% daily-loss lock and the losing-streak rule cuts size,
but the exact split was not traced. The pre-market breakout (R1) is the weakest part.

Frozen by this commit before any check.
