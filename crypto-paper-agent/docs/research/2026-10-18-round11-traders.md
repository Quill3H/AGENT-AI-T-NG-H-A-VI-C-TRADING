# Round 11: raise the swing EMA win rate with three traders' public rules (2026-10-18)

Paper only. Pre-registered before the development run; results are AUTHOR_REPORTED and
not independently verified. Every run is appended to the research ledger.

## Owner request (2026-10-18 18:02)
"Rất tốt, hãy nghiên cứu và phát triển cách mà đang có lãi và có khả năng win cao nhất,
lãi tốt nhất nhé." The owner named IncomeSharks, Nebraskangooner and Cheds Trading (Big
Cheds). Goal: develop the method that is profitable now (swing EMA, C1 of round 8: +4.05% a
month at 5% risk in development, win rate 26.6%) toward a higher win rate without lower net
profit after fees.

## What the three traders publish (sources read 2026-10-18; their own profit claims are not used)
- **IncomeSharks**: two Supertrends on the daily chart, default (10, 3) and a second with the
  multiplier 2; On-Balance Volume (OBV) must confirm, and he de-risks when OBV fails to follow
  price. Sources: a summary of his method on Medium (BitcoinShrimps, "Using the
  @incomesharks trading strategy"); his posts such as "Daily supertrends still bullish and
  OBV still bullish" (x.com/IncomeSharks/status/1352376837679144961).
- **Nebraskangooner**: horizontal support and resistance, volume-confirmed breakouts, a
  repeatable setup with at least 2:1 reward to risk, low leverage, 6h/daily charts, a pause
  after four or five losses in a row. Sources: BingX (Bingbon) interview on Medium; TrendSpider
  "Comprehensive Guide to Trading Fundamentals".
- **Big Cheds**: trend from the daily chart, buy pullbacks to the 8 EMA in a clear uptrend,
  scale out in pieces on the way up, never more than 5% of the bankroll in one play, 1-2% risk
  when starting, RSI and OBV as confluence only, candlesticks (hammer at support). Sources:
  The Wolf Of All Streets podcast transcript (podscripts.co); BingX AMA recap on Medium.

**Not testable here**: chart-pattern judgement (triangles, flags, hand-drawn trendlines),
discretionary position management, altcoin rotation by Bitcoin dominance, news, and their
self-reported track records. The four-loss pause is already covered by the engine's
streak rule (half risk after three losses), which stays unchanged.

## Candidates (4h signal, 15m execution, long only, src/strategies/trader_suite.py)
| Key | Rule |
|---|---|
| C1 | reference: round-8 swing EMA pullback, long only |
| P1 | C1, half the position taken at 1R, then the broker moves the stop to break-even |
| P2 | C1 scaled out in thirds: 1/3 at 1R, 1/3 at 2R, rest rides the EMA50 exit (Cheds) |
| S1 | C1 only when both daily Supertrends (10,3) and (10,2) are up and 4h OBV > its EMA20 (IncomeSharks) |
| X1 | S1 with half taken at 1R |
| S2 | Supertrend(10,2) turns up while Supertrend(10,3) is up and OBV > EMA20; stop on the (10,3) line; exit when (10,2) turns down |
| G1 | EMA50 > EMA200; close breaks the 30-bar high on volume > 1.5x the 20-bar mean; stop 5-bar low - 0.5 ATR; target 2R; exit under EMA50 (Nebraskangooner) |
| K1 | daily close > daily EMA21 and daily EMA8 > EMA21, 4h EMA8 > EMA21; dip to EMA8 and an up close back above it; stop 5-bar low - 0.5 ATR; exit under EMA21 (Cheds) |
| K2 | K1 scaled out in thirds at 1R and 2R |

Scale-outs use the existing broker partial-exit path (`rules.partial_exits`). A partial is
filled at the target touch with slippage; a gap through the target fills at the open. The
remaining position keeps the original stop until the bar after the partial, then
break-even. Numbers are the traders' stated defaults or round-8 values, not fitted.

## Data, costs and risk
- Development: BTC/ETH/SOL 2021-01-01..2023-12-31, at 2% and 5% risk per trade.
- Costs 0.05% taker + 0.03% slippage per side. Leverage 2x, order cap 2x equity, 30%
  liquidation buffer, 5% daily-loss breaker, stop on every trade. No limit is relaxed.
- After the freeze, checks are on **seen** data only and labelled as context: BTC/ETH/SOL
  2024-01..2026-09 (and with costs x2), 2026-10-01..17, and the top-10 2021-01..2026-09.
  Every top-10 bar to 2026-10-17 has been used by an earlier final. New evidence comes only
  from forward paper from 2026-10-18 (weekly check-in).

**Disclosure.** Before this plan was committed, a wiring smoke test ran all nine candidates on
BTC 2021-01..02 at 2% (development data, inside this round's development window). No holdout
data was touched.

## Selection (fixed now)
1. Eligible: no losing development year, max drawdown <= 35%, and a geometric average month
   at least as high as C1 at the same risk (net profit after fees not lower).
2. Among eligible runs, the highest win rate; ties go to the higher average month. C1 itself
   is in the pool, so if nothing beats it on win rate without losing monthly return, C1 stays.
3. If nothing is eligible, the round-8 rule picks.
The round-8 rule's pick is also reported. Steps of 10/20/30/50% a month are reported. The
choice is frozen by commit before any check.

## Development results (BTC/ETH/SOL 2021-01..2023-12; AUTHOR_REPORTED)

| Run | Return % | Max DD % | Trades | Win % | Average month % | Median month % | Worst month % | Losing months / 36 | 2021 | 2022 | 2023 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C1 risk 2% | 71.8 | 14.13 | 366 | 26.5 | 1.51 | -0.08 | -1.99 | 18 | 24.56 | 2.24 | 34.91 |
| C1 risk 5% | 317.92 | 31.35 | 357 | 26.6 | 4.05 | -0.07 | -6.81 | 18 | 67.16 | 7.0 | 133.66 |
| G1 risk 2% | 21.72 | 4.2 | 139 | 42.4 | 0.55 | 0.0 | -1.87 | 12 | 7.3 | -0.43 | 13.93 |
| G1 risk 5% | 67.7 | 10.39 | 139 | 42.4 | 1.45 | 0.0 | -4.64 | 12 | 18.98 | -1.22 | 42.69 |
| K1 risk 2% | 57.32 | 9.95 | 381 | 30.4 | 1.27 | -0.11 | -1.81 | 19 | 19.43 | -0.66 | 32.6 |
| K1 risk 5% | 146.71 | 22.48 | 376 | 30.6 | 2.54 | -0.26 | -4.48 | 18 | 47.42 | -0.87 | 68.82 |
| K2 risk 2% | 20.58 | 7.87 | 394 | 36.8 | 0.52 | -0.03 | -1.8 | 18 | 9.99 | -1.53 | 11.33 |
| K2 risk 5% | 45.44 | 14.81 | 385 | 37.1 | 1.05 | -0.09 | -3.64 | 18 | 23.58 | -3.19 | 21.56 |
| P1 risk 2% | 39.62 | 11.35 | 387 | 37.2 | 0.93 | -0.04 | -2.58 | 18 | 17.25 | 1.23 | 17.64 |
| P1 risk 5% | 183.6 | 22.12 | 367 | 37.9 | 2.94 | 0.0 | -7.8 | 16 | 65.57 | 5.17 | 62.86 |
| P2 risk 2% | 27.55 | 10.39 | 387 | 37.2 | 0.68 | -0.1 | -2.46 | 18 | 14.94 | 0.79 | 10.11 |
| P2 risk 5% | 119.24 | 20.19 | 367 | 37.9 | 2.2 | 0.0 | -7.62 | 16 | 53.35 | 3.58 | 38.03 |
| S1 risk 2% | 77.32 | 12.56 | 212 | 27.4 | 1.6 | 0.0 | -2.7 | 12 | 24.22 | 1.88 | 40.12 |
| S1 risk 5% | 368.24 | 25.95 | 209 | 26.8 | 4.38 | 0.0 | -6.6 | 10 | 67.22 | 7.56 | 160.32 |
| S2 risk 2% | 12.04 | 8.52 | 128 | 40.6 | 0.32 | -0.06 | -1.39 | 19 | 8.22 | 0.04 | 3.49 |
| S2 risk 5% | 35.29 | 18.78 | 128 | 40.6 | 0.84 | -0.12 | -3.49 | 19 | 21.93 | 0.69 | 10.21 |
| X1 risk 2% | 39.86 | 9.64 | 230 | 39.6 | 0.94 | 0.0 | -2.72 | 11 | 20.41 | 1.57 | 14.36 |
| X1 risk 5% | 157.29 | 20.7 | 224 | 39.3 | 2.66 | 0.0 | -6.66 | 11 | 57.91 | 5.85 | 53.93 |

**Selection: S1 at 2% risk** (C1 with the IncomeSharks daily Supertrend + OBV filter), rule
level "full". Eligible runs (no losing year, drawdown <= 35%, average month >= C1 at the same
risk) were S1 at both risks; S1 at 2% has the higher win rate (27.4% vs 26.8%). Step reached:
none. The round-8 rule would pick S1 at 5% (+4.38% a month, drawdown 26%, 10 losing months
of 36 against C1's 18). Same rules, so the checks below are also run at 5% and labelled as
not the pick.

Findings:
- Scale-outs raise the win rate from about 27% to 37-39% but cut the monthly return by a
  quarter to a half (P1 5% +2.94% vs C1 +4.05%): the half sold at 1R is the half that would
  have caught the few large trends that pay for everything.
- The IncomeSharks filter keeps C1's large winners and removes 41% of the trades, mostly
  losers in sideways markets: higher return, lower drawdown, half the losing months.
- The 2R breakout (G1) wins 42% but lost in 2022; the dual Supertrend (S2) wins 41% with a
  small edge; the Cheds 8 EMA pullback (K1) lost slightly in 2022.

Frozen by this commit before any check.
