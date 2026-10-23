# Round 19: the r/Daytrading ICT liquidity post (sweep + FVG) on BTC/ETH/SOL perpetuals (2026-10-23)

Paper only, on Binance USDⓈ-M perpetual futures (2x leverage, funding, shorts). Pre-registered
before any backtest of these rules; results are AUTHOR_REPORTED and not independently verified.
Every run is appended to the research ledger with `variants_tried`.

## Owner request (2026-10-23 11:25-11:28)
The owner pasted an r/Daytrading post ("Sometimes the best trade is literally not trading"): two
NQ/MNQ trades, +$684, 1.8R and 2.0R. The coordinator answered that two winners are a story, not
evidence, and offered a pre-registered round; the owner replied "ok được đó."

## What the post says (summary of the pasted text)
- Trade 1, "15-minute ORB + 1-minute FVG" (1.8R): before the New York open price swept both the
  Asia and the London overnight lows, while trading into a higher-timeframe fair value gap; then
  a bullish displacement back up. 15-minute opening range, then a 1-minute breakout with an FVG
  for entry. Target: the Asia highs (the draw on liquidity, DOL).
- Trade 2, "IRL -> ERL" (2R): Asia lows swept, London lows swept right before New York, bullish
  displacement, a higher-timeframe FVG tapped; entry on the retracement into the 30-minute FVG
  (internal range liquidity); fixed 2R target slightly above the Asia highs (external liquidity).
- The author is affiliated with TradeZella. No losses, fees or trade counts are given.

## Translation to crypto perpetuals (disclosed choices; the post gives none of these numbers)
- The trading day is the US Eastern date of the New York open, Monday to Friday only (the post's
  market has no weekend New York session). Asia = 00:00-06:00 UTC of that date, London =
  07:00-12:00 UTC, New York open = 09:30 ET with daylight saving (13:30 or 14:30 UTC).
- Shorts mirror longs (highs swept, bearish displacement, bearish HTF FVG, Asia low as target).
- Bars: 5m signal and execution (fills at the next 5m open). The post's 1-minute entry is tested
  only in a pilot, because 1m bars exist for BTC/ETH/SOL only in 2023-01..03.

## Rules (src/strategies/ict_liquidity.py, fixed now)
FVG: three bars with bar 3's low above bar 1's high (bullish gap [high1, low3]) or bar 3's high
below bar 1's low (bearish gap [high3, low1]); a gap must span at least 0.05% of price.

Context, fixed from bars before the New York open (long; short mirrors):
1. Sweep: the lowest low from 07:00 UTC to the New York open is below the Asia low, and the lowest
   low from 12:00 UTC to the open is below the London low.
2. HTF FVG: a bullish 1h or 4h FVG (UTC-aligned bars resampled from closed 5m bars) formed in the
   10 days before 00:00 UTC of the trading day, with no later 1h/4h close below its bottom by
   00:00 UTC; the sweep low is at or below its top and no 5m close from 07:00 UTC to the open is
   below its bottom.
3. Displacement: a 5m bar after the sweep-low bar, up to the signal bar, with a bullish body of at
   least 1.0 x ATR(14) of 5m bars and a close above both swept lows.
4. The Asia high (the target) has not been traded from 06:00 UTC to the signal bar.

Setup A, `orb_fvg` (trade 1): opening range = the three 5m bars 09:30-09:45 ET. From 09:45 to
11:00 ET, the bar that just closed completes a bullish FVG and closes above the range high. Stop
= low of FVG bar 1; target = the Asia high, which must be at least 1.5R away.

Setup B, `irl_erl` (trade 2): the latest bullish 30m FVG (UTC-aligned 30m bars from closed 5m
bars) whose bar 1 starts in or after the 30m bucket of the sweep low. From 09:30 to 12:00 ET, the
first 5m bar after that FVG closed to trade back to its top or below, while closing at or above
its bottom, enters. Stop = low of 30m bar 1; target = entry + 2R.

Both: a stop closer than 0.3% of price is skipped (round 17's rule: about twice the round-trip
cost). Each setup at most once a day; flat by 16:00 ET.

| Key | What | Selectable |
|---|---|---|
| C1 | reference: round-8 swing EMA pullback, long only, same coins | no |
| L1 | setup A only | yes |
| L2 | setup B only | yes |
| L3 | both, at most one each a day | yes |
| P1 | pilot: L1 with 1m signal/execution bars, 2023-01..03, against L1 on 5m in the same months | no |

Variants tried, declared in every ledger row: 7 (L1-L3 x 2%/5% risk, plus P1). Costs x2 runs
and C1 are stresses and references, not extra variants. No parameter is tuned after a run.

## Data, costs and risk
- Data: Binance Vision 5m perps BTC/ETH/SOL from `/mnt/project-files/market-data/binance-vision-usdm-forward`
  (2021-01..2026-10-17); the pilot uses `/mnt/project-files/market-data/binance-vision-usdm` (1m and
  5m). No new download; ALGO/VET/SAND are not used.
- Development: 2021-01-01..2023-12-31 at 2% and 5% risk per trade, plus costs x2 for each.
- Costs as the engine has them: 0.05% taker + 0.03% slippage per side, real funding events.
  Leverage 2x, order cap 2x equity, liquidation buffer, 5% daily-loss breaker, STOP_WIDENED
  invariant, losing-streak halving. No limit is relaxed; v1 parameters and the project risk
  config are untouched.
- After the freeze, checks are on **seen** data only and labelled `validation`: 2024-01..2026-09
  (and costs x2), 2026-10-01..17, and C1 on the same coins at the same risk. The script asserts
  that `ledger.check_untouched` refuses those windows, so they can never be relabelled as a
  final test. New evidence can only come from forward paper (2026-10-18 onward), which
  `check_untouched` must accept.

## Selection (fixed now; the round-8/17 rule)
1. Among L1-L3 x risk with no losing development year and max drawdown <= 35%, take the highest
   average month.
2. Otherwise the highest average month with max drawdown <= 35%.
3. Otherwise the best return / max drawdown.
The choice is frozen by commit before any check.

## Forward gate (fixed now)
The pick joins the forward paper check-in (2026-10-25 list) only if all hold:
dev average month >= +0.48% (the 5.9%/yr bank deposit), dev max drawdown <= 35%, dev trades
>= 30, dev costs x2 return > 0, and seen 2024-01..2026-09 return > 0. Otherwise it is not added,
and the research conclusion stays NO_TRADES.

Reported for every run: trades, win rate, mean net R per trade (net P&L / initial risk), return,
max drawdown, average month, per-year return, and the costs x2 result.

**Disclosure.** No backtest of these rules ran before this plan was committed, except two crash
smoke runs (BTC 2021-01-04..17 on 5m and 2023-01-02..08 on 1m) whose results were not read beyond
"the run completes"; after them, a speed-only change skips the bar copy outside 09:30-12:00 ET
weekdays when flat, which cannot change any signal. Unit tests use synthetic bars only. Round 7
(London breakout and other session rules) and round 17 (US-open plan) already failed on the same
coins after costs, and the repo's original `smc_liquidity_sweep` strategy uses related ideas;
those results were known when this round was set up.

## Development results (BTC/ETH/SOL 2021-01..2023-12; pilot 2023-01..03; AUTHOR_REPORTED)

Run at 3fc2e7e; raw output docs/research/runs/round19-ict-3fc2e7e/dev.json.

| Run | Return % | Max DD % | Trades | Win % | Mean net R | Average month % | 2021 | 2022 | 2023 |
|---|---|---|---|---|---|---|---|---|---|
| C1 risk 2% | 71.8 | 14.13 | 366 | 26.5 | 0.438 | 1.51 | 24.56 | 2.24 | 34.91 |
| C1 risk 5% | 317.92 | 31.35 | 357 | 26.6 | 0.438 | 4.05 | 67.16 | 7.0 | 133.66 |
| L1 risk 5% | 0.0 | 0.0 | 0 |  |  | 0.0 | 0.0 | 0.0 | 0.0 |
| L1 risk 2% | 2.39 | 3.3 | 13 | 46.2 | 0.29 | 0.07 | 1.95 | 1.18 | -0.74 |
| L2 risk 5% | 3.59 | 2.02 | 4 | 100.0 | 0.53 | 0.1 | 3.05 | 0.52 | 0.0 |
| L2 risk 2% | 0.13 | 3.31 | 16 | 62.5 | 0.018 | 0.0 | 1.09 | -1.42 | 0.48 |
| L3 risk 2% | 2.66 | 3.63 | 25 | 56.0 | 0.168 | 0.07 | 1.68 | 1.26 | -0.29 |
| L3 risk 5% | 3.59 | 2.02 | 4 | 100.0 | 0.53 | 0.1 | 3.05 | 0.52 | 0.0 |
| L1 risk 2%, costs x2 | 1.89 | 3.38 | 16 | 50.0 | 0.385 | 0.05 | 1.55 | 1.12 | -0.78 |
| L1 risk 5%, costs x2 | 0.0 | 0.0 | 0 |  |  | 0.0 | 0.0 | 0.0 | 0.0 |
| L2 risk 2%, costs x2 | -1.62 | 4.33 | 17 | 58.8 | -0.139 | -0.05 | 0.74 | -1.85 | -0.5 |
| L2 risk 5%, costs x2 | 3.28 | 2.0 | 4 | 100.0 | 0.485 | 0.09 | 2.85 | 0.41 | 0.0 |
| L3 risk 2%, costs x2 | -0.67 | 4.71 | 28 | 53.6 | 0.03 | -0.02 | 1.05 | -0.35 | -1.36 |
| L3 risk 5%, costs x2 | 3.28 | 2.0 | 4 | 100.0 | 0.485 | 0.09 | 2.85 | 0.41 | 0.0 |
| L1 pilot window 5m, risk 2% | 0.0 | 0.0 | 0 |  |  | 0.0 |  |  | 0.0 |
| P1 pilot 1m, risk 2% | 0.0 | 0.0 | 0 |  |  | 0.0 |  |  | 0.0 |

**Selection: L2 at 5% risk** (rule level "drawdown only": no run is free of a losing year with
trades, so the highest average month with drawdown <= 35% is taken). It made +3.6% in three
years on **4 trades** (+0.10% a month); it does not beat C1 at 5% (+4.05% a month) or the bank
deposit (0.48% a month). L3 at 5% is identical to L2 at 5% (its L1 half never traded at 5%).

Funnel (diagnostic only, computed after the run from the frozen code; long and short counted
separately, weekdays 2021-01-15..2023-12-29):

| Coin | Weekdays | Side-days with both levels swept | + HTF FVG tapped and held | + Asia target still open at the NY open |
|---|---|---|---|---|
| BTCUSDT | 771 | 373 | 179 | 124 |
| ETHUSDT | 771 | 364 | 173 | 126 |
| SOLUSDT | 771 | 335 | 143 | 104 |

About 100-125 side-days a coin pass the context, but the displacement, the entry trigger, the
0.3% minimum stop and (L1) the 1.5R room to the Asia extreme leave 13-28 trades in three years at
2% risk. At 5% risk most of those orders disappear; the likely cause is the 2x-equity notional
cap (5% risk on a 0.3-1% stop asks for 5-16x equity), as in rounds 5 and 17, not traced order by
order. The 1m pilot and the 5m run on 2023-01..03 both made **0 trades**, so the 1m entry
question is unanswered on the data we have.

Pre-registered forward gate on the pick (dev part): average month 0.10% < 0.48% FAIL, trades
4 < 30 FAIL, drawdown 2.0% <= 35% pass, costs x2 +3.3% > 0 pass. The pick therefore cannot join
the forward check-in whatever the seen-data checks show; they run anyway, as registered.

Frozen by this commit before any check.

## Checks after the freeze (seen data; context only; AUTHOR_REPORTED)

Frozen pick L2 at 5% risk, run at 9d94cd6; raw output docs/research/runs/round19-ict-3fc2e7e/check.json.
`ledger.check_untouched` refused both windows (already spent), so they are recorded as `validation`.

| Run | Return % | Max DD % | Trades | Win % | Mean net R | Average month % | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|---|
| L2 risk 5%, 2024-01..2026-09 | -2.87 | 3.74 | 5 | 20.0 | -0.327 | -0.09 | -0.96 | -1.93 | 0.0 |
| L2 risk 5%, costs x2 | -3.27 | 3.99 | 5 | 20.0 | -0.397 | -0.10 | -1.04 | -2.25 | 0.0 |
| L2 risk 5%, 2026-10-01..17 | 0.0 | 0.0 | 0 | | | 0.0 | | | 0.0 |
| Reference C1 risk 5%, 2024-01..2026-09 | 17.78 | 24.27 | 375 | 22.9 | 0.091 | 0.50 | 18.36 | 5.52 | -5.7 |

**Verdict: fail.** The forward gate fails on three lines (dev average month, dev trade count,
seen return). The post's two setups, translated to BTC/ETH/SOL perpetuals with UTC sessions and
the New York open, almost never line up (4-28 trades in three years) and do not make money after
costs; the 4/4 dev winners at 5% are followed by 1 winner in 5 on 2024-26/09. Not added to the
forward check-in; the research conclusion stays NO_TRADES.
