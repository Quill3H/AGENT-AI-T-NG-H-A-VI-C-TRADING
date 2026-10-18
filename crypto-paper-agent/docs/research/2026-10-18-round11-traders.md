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
