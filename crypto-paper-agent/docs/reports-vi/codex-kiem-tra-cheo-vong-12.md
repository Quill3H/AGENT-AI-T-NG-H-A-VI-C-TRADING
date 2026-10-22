# Cross-check brief for Codex: round 12 (A2 and C1)

Paper-trading research only. Do not place orders, use API keys, or connect to any exchange account.
The goal is to rebuild two strategies **on your own, from the rules below**, run them on the same data,
and compare your numbers with the ones reported. Please report every difference, including the ones
you cannot explain. Do not tune your code to match the target numbers.

Repository: `Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING`, branch `claude/project-thread-uiqlsn`
(draft PR #7), project folder `crypto-paper-agent/`. Commits: frozen pick `33296b0`, checks
`a2ce1fd`. If you want an independent result, write your own backtester first and read the
repository code only afterwards, during the audit in section 5.

## 1. Data

Binance USDⓈ-M perpetual klines from Binance Vision, plus funding rates, stored as parquet files.
- Development window (2021-01-01 to 2023-12-31): `market-data/binance-vision-usdm/`
- Data to 2026-10-17: `market-data/binance-vision-usdm-forward/`
- Files: `{SYMBOL}_perp_4h.parquet`, `{SYMBOL}_perp_15m.parquet`, `{SYMBOL}_perp_funding.parquet`.
  - The klines are indexed by the bar's open time in UTC. Columns are open, high, low, close, volume and taker_buy_base_volume.
  - The funding file has the columns funding_rate and funding_interval_hours.
- Symbols: BTCUSDT, ETHUSDT, SOLUSDT.
- If you do not have the shared folder, download the same monthly files from data.binance.vision.

## 2. Rules (4h signal bars, long only)

- Indicators are computed only on closed 4h bars. The strategy sees the **last 260 closed 4h bars**.
  EMAs use `ewm(span=n, adjust=False)` starting at the first of those 260 bars, so values depend
  slightly on the window.
- ATR(14) is the **simple 14-bar mean** of true range.
- ADX(14) is Wilder's ADX, smoothed with `ewm(alpha=1/14, adjust=False)`.

**C1 (swing EMA pullback, long only)**
- **Entry.** All of these must hold on the 4h bar that just closed:
  - EMA50 > EMA200;
  - close > EMA200;
  - the previous bar's low ≤ the previous bar's EMA20;
  - this bar's close > this bar's EMA20;
  - this bar's close > its open (an up bar).
- **Stop.** The lowest low of the last 5 bars (this bar included) minus 0.5 × ATR(14).
- **Exit.** When a 4h bar closes below EMA50, close the position at the next 15m open.
- **One position per symbol.** While a position is open, no new entry is taken.

**A2 (C1 with an exit that follows trend strength)**
- Entries and stops are the same as C1.
- At each 4h close while a position is open:
  - if ADX(14) > 25, exit when the close is below EMA50 (the same as C1);
  - otherwise, exit when the close is below EMA20.

## 3. Execution and risk (the reported runs use these settings)

- **Starting capital.** $10,000, split equally into 3 independent accounts of $3,333.33 each, one per symbol.
  - Each account's equity is tracked on the 15m bars.
  - The portfolio is the sum of the 3 accounts.
- **Fills.** An entry fills at the open of the first 15m bar after the 4h close.
- **Costs.**
  - Fee: 0.05% of notional on every fill.
  - Slippage: 0.03% against you on every fill.
- **Stop-loss.** Checked on 15m bars. A stop that is touched intrabar fills at the stop price plus slippage. If the bar gaps through the stop, it fills at the open.
- **Position size.** quantity = (equity × risk%) / |entry − stop|, with risk% = 2% or 5%.
  - Leverage is 2x.
  - If the notional is more than 2 × equity, the order is **rejected**, not reduced.
- **Streak rule.** After 3 losing trades in a row, risk is halved. It returns to normal after 3 winning trades in a row.
- **Daily loss stop.** If the net loss over a rolling 24 hours reaches 5% of equity, close everything and stop trading for 24 hours.
- **Funding.**
  - It is paid or received on notional at each funding time (00:00, 08:00 and 16:00 UTC), using the latest rate already published.
  - A long position pays when the rate is positive.
- **Liquidation check.** The order is rejected if the stop is not at least 30% of entry price away from the liquidation price. At 2x this rarely binds.

## 4. Numbers to match

All numbers below are AUTHOR_REPORTED and not yet verified.

"Avg month" is the geometric average of monthly returns. A trade is a win when its net P&L is above 0, after fees and funding.

**Development window, BTC/ETH/SOL, 2021-01-01 to 2023-12-31**

| Run | Return | Max DD | Trades | Win % | Avg month | 2021 / 2022 / 2023 |
|---|---|---|---|---|---|---|
| C1, 2% | +71.8% | 14.13% | 366 | 26.5 | +1.51% | +24.56 / +2.24 / +34.91 |
| C1, 5% | +317.9% | 31.35% | 357 | 26.6 | +4.05% | +67.16 / +7.0 / +133.66 |
| A2, 2% | +107.2% | 13.17% | 469 | 28.4 | +2.04% | +28.83 / +1.7 / +58.12 |
| A2, 5% | +487.8% | 25.66% | 461 | 28.4 | +5.04% | +80.59 / +6.41 / +205.86 |

**2024-01-01 to 2026-09-30, BTC/ETH/SOL, 5% risk**

| Run | Return | Max DD | Trades | Win % |
|---|---|---|---|---|
| A2 | +18.6% | 21.98% | 468 | 23.9 |
| A2, costs ×2 (fee 0.10%, slippage 0.06%) | +1.5% | 28.06% | 469 | 22.6 |
| C1 | +17.8% | 24.27% | 375 | 22.9 |

A match within about ±10% on return and ±2 points on drawdown is good. A larger difference means
one implementation has a bug. Please list the trades that differ for one symbol and one year.

## 5. Things to audit

1. **Look-ahead.** Check that no decision uses a 4h bar before it has closed, and that fills happen only at the next 15m open.
2. **Entry and exit at the 4h close.** Check that both happen at the right 15m bar.
3. **Fees and slippage.** Check that they are charged on both entry and exit, and on every partial fill.
4. **Funding.**
   - Check that it is applied at the right times with the right sign.
   - Check that no rate is used before it was published.
   - Check that missing funding data stops the run instead of counting as 0.
5. **Rejected orders.** Check how the 2 × equity notional cap rejects orders. At 5% risk, any stop closer than 2.5% is rejected. This is why the 5% runs have fewer trades than the 2% runs.
6. **Win rate.** Check that it is counted per full trade, not per fill.
7. **Average month.** Check that it is the geometric average over every calendar month in the window.

## 6. Corrections after the 2026-10-19 cross-check

Two blind rebuilds and a code audit found that the description above was incomplete:

- **Daily loss stop.** It counts **realized** cash flows only: entry fee, funding, and exit P&L
  minus fee. It is applied **per account**, against 5% of equity after the event. Unrealized losses
  do not count. If you count mark-to-market losses instead, the results are very different.
- **Streak rule.** It is per account. A loss means net P&L < 0, and a P&L of exactly 0 resets both
  counters. Once risk has been halved, it needs 3 wins in a row to recover. In practice about 95% of
  "5%" trades run at 2.5%, and "2%" trades at 1%.
- **Liquidation check.** It uses Binance maintenance-margin brackets (BTC 0.4%, ETH 0.5%, SOL 1%).
  At 2x leverage it rejects stops more than about 19.5% away, which removes about 19–20 SOL signals
  in the development window. It is not "rarely binding".
- **Notional cap.** Margin plus fee must also fit in the wallet, so the effective cap is about
  1.998× equity. With risk usually halved, rejections are rare. Trade counts differ between the 2% and
  5% runs mainly through path dependence, not only through the 2.5% stop threshold.
- **Fills.**
  - A gap stop fills at open × (1 − 0.03%).
  - Signal exits fill at the next 15m open × (1 − 0.03%), after that bar's funding.
  - At the end of the window, open positions are closed at the last 15m close and counted as trades.
- **Funding.**
  - Notional is quantity × the 15m open at the settlement time.
  - The rate used is the event at that exact boundary; a missing rate raises an error.
  - The hours are fixed at 00/08/16 UTC, so SOL's 2h/4h events in November 2022 are ignored.
  - Funding is not doubled under costs ×2.
- **Warm-up.** 120 days of 4h history are loaded before the start.
- **Max drawdown.** It is measured on the sum of the three accounts at each 15m close, without
  intrabar lows, so it is somewhat understated.
