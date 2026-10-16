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
