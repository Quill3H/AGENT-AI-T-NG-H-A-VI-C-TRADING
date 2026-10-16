# Futures method search on BTC, ETH and SOL (2026-10-16)

Owner request (zhilie meng, 2026-10-16): focus on directional futures trading of
BTC, ETH and SOL; hoped-for result 20-50% profit per month; 10,000 USDT paper
account; no look-ahead. Paper simulation only; no exchange orders, testnet or keys.

## Protocol (written before any 3-coin result was seen)

- Data: Binance Vision USD-M monthly archives, checksum-verified
  (`/mnt/project-files/market-data/binance-vision-usdm/`). SOLUSDT monthly
  archives miss 2022-02-26..28 and 2022-04-01..02; those days come from
  Binance Vision daily archives, also checksum-verified.
- Portfolio: 10,000 USDT split into three equal sleeves (BTC, ETH, SOL), each
  with its own paper broker and the unchanged default risk gate (2% risk per
  trade, max 5x leverage, order notional <= 2x sleeve equity, 5% daily-loss
  breaker, 60-minute data-gap kill switch).
- Development window 2021-01-01..2023-12-31. Candidates:
  - F1 trend_following (existing rules)
  - F2 breakout_retest (existing rules)
  - F3 Donchian daily 20/10 long+short
  - F4 Donchian daily 55/20 long+short
  - F5 Donchian 4h 20/10 long+short
  - F6 Donchian 4h 55/20 long+short
- Selection rule (same as the BTC search): highest development return / max
  drawdown among candidates with no losing development year; if none qualifies,
  the highest return / drawdown overall, flagged.
- The chosen candidate is frozen in a commit, then scored once on the final
  check 2024-01-01..2025-12-31 and on the owner's window 2021..2025, plus a
  cost x2 stress. No parameter is changed after the final check is opened.
- Reported per run: total and yearly return, max drawdown, and per month the
  number of months >= +20%, losing months, worst month, and whether equity ever
  fell to half the start.
- Risk what-ifs (5% and 10% risk per trade, orders up to 5x equity) are run on
  the frozen candidate only to show the return/drawdown trade-off. They are not
  adopted; changing risk defaults needs an explicit owner decision.

Ideas credited (no code copied): Turtle trading rules (Donchian breakouts,
Curtis Faith, "Way of the Turtle"); time-series momentum (Moskowitz, Ooi,
Pedersen 2012, "Time series momentum", JFE).

## Development results 2021-2023 (10,000 USDT, 3 sleeves)

AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED. Raw output:
`/mnt/project-files/market-data/binance-vision-usdm/futures_search_dev_2026-10-16.json`.

| # | Candidate | Return | Max DD | 2021 / 2022 / 2023 | Trades | Avg month | Months >= +20% | Losing months |
|---|---|---|---|---|---|---|---|---|
| F1 | trend_following | +4.58% | 11.36% | +6.92 / -4.41 / +2.33 | 90 | +0.12% | 0 | 22 |
| F2 | breakout_retest | -16.91% | 17.45% | -10.32 / +1.45 / -8.68 | 104 | -0.51% | 0 | 25 |
| F3 | Donchian 1d 20/10 | +60.43% | 8.86% | +21.53 / +8.02 / +22.21 | 90 | +1.32% | 0 | 15 |
| F4 | Donchian 1d 55/20 | +48.80% | 10.19% | +33.74 / -0.39 / +11.69 | 47 | +1.11% | 0 | 19 |
| F5 | Donchian 4h 20/10 | +20.31% | 13.83% | -4.82 / +7.11 / +18.02 | 654 | +0.52% | 0 | 17 |
| F6 | Donchian 4h 55/20 | +37.45% | 10.79% | +8.82 / +4.25 / +21.15 | 308 | +0.89% | 0 | 13 |

Selection rule applied: F3 (return/DD 6.8, no losing year). **F3 is frozen by
this commit before the 2024-2025 check is opened.** No candidate reached +20%
in any single month during development (best month +11.37%).

The first dev run crashed on F4/SOLUSDT (broker liquidation solver bug when
funding drains collateral of a winning long); it was fixed with a regression
test before this run, and no result was used before the fix.

## Final check and owner window (F3 frozen in 25b0862)

AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED. Raw output:
`/mnt/project-files/market-data/binance-vision-usdm/futures_search_final_2026-10-16.json`.

| Run | Final equity | Return | Max DD | Yearly | Avg month | Months >= +20% | Losing months | Verdict |
|---|---|---|---|---|---|---|---|---|
| Final check 2024-2025 | 9,833.77 | -1.66% | 8.25% | 2024 +1.43, 2025 -3.05 | -0.07% | 0/24 | 15 | FAIL |
| Owner window 2021-2025 | 15,331.81 | +53.32% | 10.04% | +21.53 / +8.02 / +22.09 / -1.07 / -3.31 | +0.71% | 0/60 | 30 | FAIL (3/5 years up) |
| 2021-2025, costs x2 | 14,882.26 | +48.82% | 10.64% | +21.24 / +7.49 / +20.16 / -1.48 / -3.53 | +0.66% | 0/60 | 31 | FAIL |
| WHAT-IF 5% risk/trade | 26,665.49 | +166.65% | 24.57% | +59.17 / +20.94 / +60.71 / -5.42 / -8.86 | +1.65% | 2/60 | 30 | FAIL |
| WHAT-IF 10% risk/trade | 53,270.64 | +432.71% | 44.41% | +136.89 / +41.15 / +132.00 / -15.66 / -18.58 | +2.83% | 7/60 | 29 | FAIL |

Conclusions:
- F3 does not generalise: its edge is concentrated in 2021-2023 (mostly SOL) and
  it loses slightly in 2024-2025. Under the protocol the method fails.
- No setting reached the owner's hoped-for 20-50% per month. Even at 10% risk
  per trade (5x the default, not adopted) only 7 of 60 months reached +20%, the
  average month was +2.83%, the max drawdown 44%, and the last two years lost
  16-19% each.
- A first what-if version also raised leverage to 5x; the 30% liquidation-buffer
  invariant rejected every order (0 trades). It was replaced with a version that
  keeps leverage and all gates at defaults; the strategy results above were not
  changed after the final check was opened.
- 2024-2025 is now seen. Any further method search must use a new untouched
  check window (for example 2026-01..2026-09, already downloaded) and log
  every attempt.

## Round 2 protocol (written before any round-2 result was seen)

Owner chose 10% risk per trade for the directional sleeve (ADR 0014).
2021-2025 has now been seen, so it becomes the development window; the new
untouched final check is **2026-01-01..2026-09-30** (already downloaded, never
used in any decision so far).

Candidates (10,000 USDT):
- H1: funding-carry baskets (entry APR >= 15%, unchanged rules) on BTC, ETH, SOL, one third each.
- H2: half in F3 (daily Donchian 20/10, 10% risk/trade, 3 coins), half in H1.
- H3: F3 alone at 10% risk/trade (reference).

Selection rule unchanged (best return / max DD among candidates with no losing
year in 2021-2025). The chosen candidate is frozen by commit, then run once on
2026-01..09. Hybrid sleeves run independently and are summed hour by hour.
