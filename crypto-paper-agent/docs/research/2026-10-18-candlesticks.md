# Round 6: Japanese candlesticks and take-profit methods (2026-10-18)

Owner messages (relayed 2026-10-18 04:18 and 04:21 UTC):
- "Các cách trên đã áp dụng phương pháp nến nhật mà tôi gửi chưa". Round 5 used only
  engulfing and hammer/shooting star (W2).
- The owner sent a list of take-profit methods: fixed R:R 1:1 / 1:2, support/resistance or
  Fibonacci, a fixed 0.5-1% target, a trailing stop, and indicator exits (RSI, Bollinger,
  MACD).
- The owner asked for leverage x20 on BTC/ETH and x5 on altcoins. That needs a decision on
  the risk limits (card posted). This plan runs with the current limits: 2x leverage,
  orders capped at 2x equity, 30% liquidation buffer. Paper only.

## Patterns (src/strategies/candles.py, after Nison, chapters 4-8 of the owner's file)
Doji, hammer / hanging man, shooting star / inverted hammer, engulfing, harami, piercing
line / dark cloud cover, morning / evening (doji) star, three white soldiers / three black
crows, rising / falling three methods.
- A long body is at least 0.6 ATR(14).
- Crypto has no overnight gaps, so the book's gap conditions are relaxed to "opens at or
  beyond the prior close".
- A reversal pattern counts only after a prior move: the close before the pattern is below
  (or, for bearish patterns, above) the close 5 bars earlier.

## Entries
- K1 `candle_pullback` (4h): reversal pattern in the trend direction after a pullback, in an
  EMA50/EMA200 trend.
- K2 `candle_reversal` (1d): reversal pattern at the previous 20-day low or high.
- K3 `candle_continuation` (4h): three soldiers/crows or three methods in an EMA50/EMA200 trend.
- K4 `candle_pullback_1h`: K1 on 1h bars.

Every entry has a stop 0.25 ATR(14) beyond the pattern.

## Exits (rules.exit_mode, CandleExits)
- `base`: K1/K3/K4 exit on a close through EMA50; K2 takes profit at 2R or exits after 10 bars.
- `rr1` / `rr2`: take profit at 1R / 2R.
- `sr`: take profit at the 20-bar high (long) / low (short), skipped when already there.
- `pct`: take profit at 1% (the top of the owner's 0.5-1% range).
- `trail`: trailing stop at the 10-bar extreme minus 2 ATR(14).
- `indicator`: exit when RSI(14) > 70 / < 30, the close reaches the opposite Bollinger
  band (20, 2), or the MACD histogram turns.

Every take-profit mode also exits after 30 bars. Fibonacci targets are not tested
separately; `sr` stands for the "nearest level" idea.

## Data and splits
- Development: BTC/ETH/SOL, 2021-01-01..2023-12-31.
- Final A (untouched): XLM, BCH, UNI and AAVE, 2021-01..2026-09. These are new
  Binance Vision downloads, checksum-verified.
- Final B (validation; seen in earlier rounds): BTC/ETH/SOL, 2024-01..2026-09.
- Costs: 0.05% taker fee + 0.03% slippage per side; costs x2 is also run on A.

## Selection
All 28 entry x exit combinations run at 2% risk. The rule is the same as before: the best
development return / max drawdown among those with no losing year and at least 30 trades,
otherwise the best overall, flagged. Testing 28 variants raises the chance that the
winner is lucky, so only the final tests count as evidence. The choice is frozen by
commit, then the chosen one runs at 1% and 10% on development, and once on A and B
(1%, 2%, 10%, plus costs x2 on A).
