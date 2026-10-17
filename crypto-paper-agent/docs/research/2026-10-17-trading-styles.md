# Round 5: trading styles from the owner's document (2026-10-17)

Owner message relayed by the project coordinator (2026-10-17 10:59 UTC). The owner
attached a list of futures trading styles and a Japanese-candlestick book (Nison,
Vietnamese abridged translation) and asked to apply them: "Scalping hoặc swing đúng lúc".
Paper only. Account 10,000 USDT, split equally over the coins. No exchange orders, keys
or wallets.

## Risk and costs (unchanged gates)
- Each candidate runs at 1%, 2% (the document's rule) and 10% (owner choice, ADR 0014)
  risk per trade.
- Leverage is 2x on isolated margin; the broker already models isolated margin. The
  document allows up to 5x, but 5x failed the 30% liquidation-buffer invariant in round 1.
  The order cap stays at 2x equity, so for tight scalping stops the actual risk can be
  below the target percentage. That is reported, not worked around.
- Every entry carries a stop-loss. The 5% rolling-24h loss breaker, liquidation buffer
  and data-gap kill switch stay as they are.
- Costs: 0.05% taker fee + 0.03% slippage per side (about 0.16% per round trip).
  Scalping is also run with costs x2 on development data.

## Data
Binance Vision USD-M klines, checksum-verified. New in this round:
- 5m klines for BTC/ETH/SOL. SOL's 5 missing days were filled from daily archives.
- Full sets (5m/15m/1h/4h/1d, funding) for ETC, ATOM, NEAR and FIL. These are the
  final-test coins and have never been inspected.

## Splits
1. Development: BTC/ETH/SOL, 2021-01-01..2023-12-31.
2. Final test A (untouched): ETC/ATOM/NEAR/FIL, 2021-01-01..2026-09-30.
3. Final test B (validation; these coins and years were seen in earlier rounds with
   other rules): BTC/ETH/SOL, 2024-01-01..2026-09-30.

## Candidates (rules in src/strategies/style_suite.py, fixed before any run)
Swing:
- W1 `swing_ema_pullback` (4h): pullback to EMA20 in an EMA50/EMA200 trend, exit below EMA50.
- W2 `sr_candles` (1d): engulfing/hammer at 30-day support (mirror at resistance), take
  profit at the opposite level, reward >= 1.5x risk, 20-bar time exit.
- W3 `wyckoff_spring` (4h): spring/upthrust out of a 40-bar range (height <= 8 ATR,
  ADX < 25) on volume > 1.5x the 20-bar mean, take profit at the other side of the range.

Day trading (flat by the bar that ends the UTC day):
- D1 `day_orb` (1h signal): break of the first-4-hour range in the EMA(200) direction,
  stop at the other side, take profit 2R, one entry per day.
- D2 `day_vwap` (15m): close reclaims the session VWAP in the EMA(200) direction, stop
  1.5 ATR, take profit 2R.

Scalping (5m signal and execution):
- C1 `scalp_ema`: EMA9/21 cross with EMA(200) and RSI(14) filter, stop 1 ATR, take profit
  1.5 ATR, 2-hour time exit.
- C2 `scalp_bb`: fade a close outside Bollinger(20, 2) with RSI(7) extreme when ADX < 20,
  take profit at the middle band, stop 1.5 ATR, 2-hour time exit.

Ideas credited (no code copied): Steve Nison, "Japanese Candlestick Charting
Techniques" (as in the owner's file); Richard Wyckoff's accumulation/distribution
schematics; Toby Crabel's opening-range breakout; session VWAP as commonly used
intraday; Bollinger (2001); Wilder (1978).

## Selection rule
Selection happens at 2% risk. The chosen candidate has the highest development
return / max drawdown among candidates with no losing development year and at least
30 completed trades. If none qualifies, the best overall is chosen and flagged. The
choice is frozen by commit. It is then run once on final test A (at 1%, 2% and 10%,
plus costs x2 at 2%) and once on final test B (at 1%, 2% and 10%).

## Amendment 1 (2026-10-17 13:27 UTC, before C3-C6 and the 1m pilot ran)
Owner (relayed): "Để tăng tỷ lệ thắng, hãy scalp bằng nến 15m và 1h nhé" and "nếu 1 phút
tỷ lệ thắng cao thì cũng oke". At this point the dev results for W1-W3, D1-D2 and C1 were
known; C2 was still running. Adding candidates after seeing some results raises the
chance of a lucky pick. The final tests, not the dev ranking, carry the evidence.

New selectable candidates, all on BTC/ETH/SOL 2021-2023 with 15m execution:
- C3 `scalp_bb_15m`, C5 `scalp_bb_1h`: the C2 Bollinger reversion rule on 15m / 1h bars.
- C4 `scalp_rsi_15m`, C6 `scalp_rsi_1h`: with close above EMA(200), RSI(2) < 10 -> long
  (mirror short). Quick take profit 1 ATR(14), wider stop 1.5 ATR(14), exit after 8 bars.
  This aims at a high win rate; the report shows win rate and net P&L after costs.

1m pilot (not selectable): P1 `scalp_ema_1m` and P2 `scalp_bb_1m` use the C1/C2 rules on 1m
bars with 1m execution, BTC/ETH/SOL, 2023-01..2023-03 only (dev data). If a pilot is
net-positive after costs at 2% risk with at least 30 trades, the full 1m period is
downloaded and it becomes a candidate. Otherwise 1m is not pursued further.

Data: 1m klines for BTC/ETH/SOL 2023-01..03 (Binance Vision, checksum-verified, no gaps).
NEAR/FIL 1d bars for 2022-02-26..28 and 2022-04-01..02 are resampled from verified 1h
daily archives, because the 1d daily archives return 404.

## Development results (BTC/ETH/SOL 2021-2023, AUTHOR_REPORTED)

| Run | Return | Max DD | 2021 / 2022 / 2023 | Trades | Win rate |
|---|---|---|---|---|---|
| C1 risk 1% | -93.8% | 93.8% | -77.3 / -58.5 / -34.1 | 6833 | 41.1% |
| C1 risk 10% | -4.4% | 6.8% | -1.1 / -3.3 / +0.0 | 2 | 0.0% |
| C1 risk 2% | -46.1% | 46.4% | -20.5 / -24.7 / -10.0 | 1196 | 40.1% |
| C1 risk 2%, costs x2 | -62.7% | 62.9% | -41.9 / -27.5 / -11.4 | 1218 | 39.1% |
| C2 risk 1% | -81.2% | 81.3% | -46.8 / -55.4 / -20.8 | 2861 | 34.2% |
| C2 risk 10% | +0.1% | 3.6% | +3.9 / -3.6 / +0.0 | 2 | 50.0% |
| C2 risk 2% | -38.6% | 39.8% | -28.4 / -12.7 / -1.8 | 784 | 36.7% |
| C2 risk 2%, costs x2 | -66.3% | 66.6% | -50.1 / -29.9 / -3.6 | 1025 | 35.5% |
| C3 risk 1% | -52.5% | 52.5% | -26.4 / -22.0 / -17.2 | 1373 | 34.2% |
| C3 risk 10% | -3.4% | 3.4% | +0.0 / -3.4 / +0.0 | 1 | 0.0% |
| C3 risk 2% | -49.1% | 49.8% | -38.4 / -11.4 / -6.8 | 915 | 32.9% |
| C3 risk 2%, costs x2 | -67.2% | 67.2% | -52.9 / -23.4 / -8.9 | 973 | 31.8% |
| C4 risk 1% | -99.5% | 99.5% | -84.0 / -84.6 / -80.4 | 12074 | 55.1% |
| C4 risk 10% | -10.9% | 17.6% | -11.0 / -1.2 / +1.4 | 93 | 52.7% |
| C4 risk 2% | -93.8% | 94.2% | -79.4 / -56.4 / -30.8 | 6123 | 55.0% |
| C4 risk 2%, costs x2 | -99.6% | 99.6% | -96.2 / -84.3 / -35.7 | 6229 | 52.5% |
| C5 risk 1% | -18.5% | 19.1% | -7.7 / -0.7 / -11.1 | 429 | 32.2% |
| C5 risk 10% | +2.2% | 7.2% | -1.4 / +3.7 / +0.0 | 4 | 50.0% |
| C5 risk 2% | -26.9% | 27.8% | -15.0 / -0.7 / -13.3 | 393 | 33.3% |
| C5 risk 2%, costs x2 | -37.1% | 37.7% | -17.9 / -5.0 / -19.2 | 398 | 33.4% |
| C6 risk 1% | -65.2% | 65.9% | -26.6 / -27.9 / -34.4 | 3634 | 56.3% |
| C6 risk 10% | -16.4% | 47.3% | -24.9 / +6.2 / +4.8 | 176 | 55.1% |
| C6 risk 2% | -77.4% | 79.1% | -45.4 / -38.2 / -33.0 | 3132 | 56.4% |
| C6 risk 2%, costs x2 | -94.8% | 95.0% | -64.8 / -62.9 / -60.5 | 3223 | 53.9% |
| D1 risk 1% | -21.5% | 27.5% | +1.7 / -13.2 / -11.0 | 2234 | 42.4% |
| D1 risk 10% | -38.2% | 49.2% | -35.8 / -3.4 / -0.3 | 695 | 43.9% |
| D1 risk 2% | -30.6% | 40.5% | +2.5 / -21.2 / -14.1 | 2140 | 42.8% |
| D2 risk 1% | -72.5% | 77.1% | -28.2 / -43.2 / -32.5 | 6926 | 37.0% |
| D2 risk 10% | +22.5% | 19.4% | -9.2 / +19.4 / +12.9 | 55 | 45.5% |
| D2 risk 2% | -50.7% | 70.8% | -27.5 / -24.9 / -9.6 | 4240 | 37.5% |
| W1 risk 1% | +34.2% | 7.8% | +10.4 / +4.5 / +16.4 | 722 | 26.3% |
| W1 risk 10% | +1138.0% | 50.1% | +105.2 / +49.6 / +303.4 | 608 | 27.1% |
| W1 risk 2% | +80.1% | 13.6% | +21.3 / +9.2 / +36.0 | 718 | 26.5% |
| W2 risk 1% | -6.2% | 7.0% | -3.7 / +0.2 / -2.9 | 113 | 26.5% |
| W2 risk 10% | -46.3% | 50.3% | -25.5 / -12.3 / -17.8 | 99 | 26.3% |
| W2 risk 2% | -12.2% | 13.6% | -7.3 / +0.5 / -5.8 | 113 | 26.5% |
| W3 risk 1% | -0.8% | 4.3% | +0.3 / +0.4 / -1.5 | 156 | 34.6% |
| W3 risk 10% | -2.0% | 18.5% | -3.8 / +13.6 / -10.4 | 30 | 43.3% |
| W3 risk 2% | +1.0% | 8.8% | +0.3 / +0.8 / -0.1 | 152 | 35.5% |
| P1 risk 1% | -4.9% | 6.3% | -4.9 | 105 | 48.6% |
| P1 risk 10% | +0.0% | 0.0% | +0.0 | 0 | -% |
| P1 risk 2% | -1.5% | 1.8% | -1.5 | 2 | 0.0% |
| P1 risk 2%, costs x2 | -1.6% | 1.9% | -1.6 | 2 | 0.0% |
| P2 risk 1% | -7.5% | 7.9% | -7.5 | 101 | 33.7% |
| P2 risk 10% | +0.0% | 0.0% | +0.0 | 0 | -% |
| P2 risk 2% | -0.7% | 0.9% | -0.7 | 1 | 0.0% |
| P2 risk 2%, costs x2 | -0.8% | 0.9% | -0.8 | 1 | 0.0% |

P1/P2 rows are the 1m pilot (2023-01..03 only). Both lost money after costs, so 1m is
not pursued (amendment 1 rule).

At 10% (and for 1m and 5m also at 2%) risk, tight-stop strategies have very few trades.
The reason is the order cap: the size needed to risk that percentage with a tight stop
is more than 2x equity, so the risk gate rejects the order. The cap was kept.

High win rate did not mean profit. C4/C6 won 55-56% of trades and still lost 77-94%,
because costs and the wider stop outweigh the small take profit.

**Selection (rule above, at 2% risk): W1 `swing_ema_pullback`.** It is the only
candidate with no losing year (+80.1%, max DD 13.6%, 718 trades). Frozen by this commit.
The final runs use `--stage final --candidate W1`.
