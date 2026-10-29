# Round 3: indicator-based futures strategies, no funding (2026-10-16)

Owner request (zhilie meng, 2026-10-16 20:00 UTC): deploy a new trading method;
free to try other formulas and indicators; do not rely on funding (may drop it).
Paper only. 10,000 USDT, BTC/ETH/SOL perpetuals, 10% risk per trade (ADR 0014),
all other risk gates unchanged.

## Why a new holdout is needed
Every BTC/ETH/SOL month from 2021-01 to 2026-09 has already been looked at by an
earlier round. Round 3 therefore uses three tiers:
1. **Development:** BTC, ETH, SOL, 2021-01-01..2023-12-31. Candidates are chosen here.
2. **Validation:** BTC, ETH, SOL, 2024-01-01..2026-09-30. Seen in earlier rounds,
   but never with these strategies; reported, not used to choose.
3. **Untouched holdout:** BNB, XRP, DOGE, ADA perpetuals, 2021-01-01..2026-09-30.
   Downloaded for this round and never inspected before the candidate is frozen.

## Candidates (rules fixed in advance from published, widely used settings; no fitting)
- I1 `tsmom`: daily time-series momentum. Direction = sign of the 30-day return,
  entered only if close is on the same side of EMA(50); exit when the 30-day
  return changes sign; initial stop 3 x ATR(20).
- I2 `rsi2_reversion`: 4h Connors RSI(2). Long when close > SMA(200) and RSI(2) < 10;
  short when close < SMA(200) and RSI(2) > 90; exit when close crosses SMA(5);
  stop 2.5 x ATR(14).
- I3 `squeeze_breakout`: 4h volatility squeeze. Bollinger(20, 2) width in the lowest
  20% of the last 120 bars, then close outside Keltner(20, 1.5 x ATR(20)); exit on a
  close back through EMA(20); stop 2 x ATR(20).
- I4 `mtf_trend`: daily regime (EMA50 vs EMA200 on completed daily closes built from
  closed 4h bars) + 4h Donchian 20 breakout in the regime direction only; 10-bar
  channel trailing exit; stop 2 x ATR(20).
- I5 `adx_donchian`: daily Donchian 20/10 (round-1 F3) entered only when ADX(14) > 25.
- I6 `supertrend`: 4h Supertrend(10, 3). Enter on a flip, exit on the opposite flip;
  stop at the Supertrend line, trailed.
- Reference: F3 daily Donchian 20/10 at 10% risk (already known; not selectable).

## Selection rule
Highest development return / max drawdown among candidates with no losing
development year and at least 30 completed trades; if none qualifies, the best
return / drawdown overall, flagged. The winner is frozen by commit, then run once
on validation and once on the untouched holdout (equal thirds/quarters of 10,000).
Every attempt is logged here, including failures and crashes.

Ideas credited (no code copied): Connors & Alvarez, "Short Term Trading Strategies
That Work" (RSI(2)); Moskowitz, Ooi & Pedersen 2012 (time-series momentum);
Carter, "Mastering the Trade" (TTM squeeze); Wilder 1978 (ADX, ATR); Olivier
Seban (Supertrend).

## Development results, BTC/ETH/SOL 2021-2023, 10% risk per trade

AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED. Raw output:
`/mnt/project-files/market-data/binance-vision-usdm/indicator_search_dev_2026-10-16.json`.

| # | Strategy | Final | Return | Max DD | 2021 / 2022 / 2023 | Trades | Avg month | Months >= +20% | Losing months | BTC / ETH / SOL sleeve |
|---|---|---|---|---|---|---|---|---|---|---|
| I1 | tsmom | 17,241.68 | +72.42% | 27.88% | +15.47 / +2.44 / +45.77 | 110 | +1.52% | 0 | 15 | +38 / +110 / +69 |
| I2 | rsi2_reversion | 10,393.75 | +3.94% | 23.79% | +10.68 / -9.29 / +3.53 | 511 | +0.11% | 0 | 15 | +30 / +39 / -57 |
| I3 | squeeze_breakout | 11,396.57 | +13.97% | 43.10% | +21.45 / +8.49 / -13.51 | 166 | +0.36% | 2 | 20 | -18 / +87 / -27 |
| I4 | mtf_trend | 22,707.12 | +127.07% | 40.94% | -7.46 / +16.35 / +110.90 | 223 | +2.30% | 3 | 18 | -35 / -41 / +458 |
| I5 | adx_donchian | 97,464.27 | +874.64% | 31.83% | +107.33 / +60.47 / +192.95 | 52 | +6.53% | 6 | 15 | -10 / +239 / +2396 |
| I6 | supertrend | 12,710.90 | +27.11% | 38.53% | +11.56 / -15.30 / +34.53 | 357 | +0.67% | 2 | 18 | -50 / -63 / +195 |
| ref | F3 donchian 20/10 | 77,853.10 | +678.53% | 28.09% | +136.89 / +41.15 / +132.83 | 89 | +5.87% | 7 | 15 | +8 / +195 / +1833 |

Selection rule applied: candidates with no losing year and >= 30 trades are I1
and I5; **I5 (ADX-filtered daily Donchian) is frozen by this commit** (return/DD
27.5 vs 2.6). Warning recorded before the final run: I5's development profit
comes overwhelmingly from the SOL sleeve in 2021-2023; BTC lost money.

## Final runs of frozen I5 (frozen in 355b5dd)

AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED. Raw output:
`/mnt/project-files/market-data/binance-vision-usdm/indicator_search_final_2026-10-16.json`.

| Run | Final | Return | Max DD | Yearly | Trades | Avg month | Months >= +20% | Losing months | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| Validation BTC/ETH/SOL 2024-01..2026-09 | 9,871.66 | -1.28% | 38.48% | 2024 -1.33, 2025 -2.59, 2026 +2.70 | 59 | -0.04% | 0/33 | 20 | FAIL |
| Holdout BNB/XRP/DOGE/ADA 2021-01..2026-09 | 22,597.17 | +125.97% | 47.51% | +119.97 / -12.62 / +4.56 / +16.79 / +4.02 / -7.45 | 145 | +1.19% | 3/69 | 41 | FAIL |
| Holdout, costs x2 | 21,832.45 | +118.32% | 48.49% | +118.37 / -13.00 / +3.87 / +16.14 / +3.65 / -8.09 | 145 | +1.14% | 3/69 | 41 | FAIL |

Conclusions:
- The +875% development result did not carry over. On BTC/ETH/SOL after 2023 it
  roughly broke even with a 38% drawdown; on the four never-seen coins it made
  +126% over 69 months, almost all in 2021 (+120%), with a 47.5% drawdown and 41
  losing months. The 95% interval of the mean trade includes zero in both runs.
- Same pattern as rounds 1-2: daily trend breakouts earn in strong bull years
  (2021, SOL 2023) and give it back slowly in sideways years.
- No strategy in rounds 1-3 reached the hoped-for 20-50% per month on a
  sustained basis. Out-of-sample months >= +20%: 3 of 69 on the holdout coins.
