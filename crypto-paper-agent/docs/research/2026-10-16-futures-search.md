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
