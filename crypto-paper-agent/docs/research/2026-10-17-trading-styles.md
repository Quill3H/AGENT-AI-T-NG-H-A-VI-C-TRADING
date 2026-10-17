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
