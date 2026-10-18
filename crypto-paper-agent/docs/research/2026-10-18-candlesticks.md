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

## Amendment 1 (2026-10-18, before the development results were read): leverage what-if
The owner asked for x20 on BTC/ETH and x5 on altcoins and chose "Chỉ chạy thử" (paper
what-if only) on the decision card. Defaults stay unchanged (2x, cap 5x, notional cap 2x
equity, liquidation buffer 30%). `config/research/candles_2026_10_18/whatif_leverage_x20.yaml`
sets per-symbol leverage and relaxes `risk.max_leverage` to 20, `max_notional_pct_of_equity`
to 20 and `min_liquidation_buffer_pct` to 0.005. The stop must still sit before the estimated
liquidation price; stop-loss, daily loss limit, kill switch, fees and simulated liquidation
stay on. With risk-based sizing, leverage alone changes margin, not position size; the what-if
matters where the 2x notional cap rejected orders (tight stops, 10% risk).

`--stage leverage --candidate <frozen>` runs the frozen candidate once with this file at 2%
and 10% risk on development, A and B. It is reported beside the default runs, never in
their place, and does not change the selection.

## Development results (BTC/ETH/SOL 2021-01..2023-12, risk 2%; AUTHOR_REPORTED)

| Candidate | Return % | Max DD % | Trades | Win % | 2021 | 2022 | 2023 |
|---|---|---|---|---|---|---|---|
| K1-base | 70.6 | 24.2 | 883 | 28.9 | 30.3 | -2.4 | 34.1 |
| K1-rr1 | -13.3 | 25.9 | 964 | 52.7 | -5.0 | -2.9 | -6.0 |
| K1-rr2 | 1.4 | 19.3 | 835 | 38.1 | 0.5 | 3.0 | -2.1 |
| K1-sr | -0.6 | 21.6 | 838 | 37.2 | -8.5 | 5.0 | 3.4 |
| K1-pct | -35.4 | 38.3 | 1159 | 73.3 | -14.1 | -11.2 | -15.4 |
| K1-trail | -7.0 | 22.4 | 1057 | 32.6 | -3.6 | 7.8 | -10.5 |
| K1-indicator | -14.3 | 29.2 | 936 | 34.7 | -8.8 | -4.8 | -1.3 |
| K2-rr1 | -11.3 | 15.1 | 188 | 44.1 | -4.2 | -4.8 | -2.8 |
| K2-sr | -7.7 | 12.0 | 159 | 26.4 | -7.8 | -1.1 | 1.2 |
| K2-pct | -4.3 | 7.0 | 228 | 85.5 | 0.3 | 1.0 | -5.5 |
| K2-trail | -11.6 | 13.5 | 176 | 33.5 | -6.8 | -3.5 | -1.7 |
| K2-indicator | -6.9 | 11.5 | 169 | 28.4 | -6.0 | 0.1 | -1.0 |
| K3-base | 14.8 | 5.6 | 20 | 45.0 | -0.1 | 8.3 | 6.1 |
| K3-rr1 | 4.5 | 1.5 | 21 | 66.7 | -0.0 | 3.2 | 1.3 |
| K3-rr2 | 7.0 | 2.3 | 21 | 61.9 | 0.6 | 3.5 | 2.8 |
| K3-sr | -0.9 | 1.5 | 7 | 57.1 | 0.0 | -0.5 | -0.4 |
| K3-pct | 1.7 | 0.7 | 22 | 95.5 | 0.1 | 0.5 | 1.1 |
| K3-trail | 4.3 | 2.1 | 21 | 52.4 | -0.6 | 1.5 | 3.4 |
| K3-indicator | 1.2 | 1.0 | 21 | 57.1 | -0.3 | 0.7 | 0.8 |
| K4-base | -75.7 | 81.8 | 3264 | 25.4 | -44.7 | -33.9 | -33.6 |
| K4-rr1 | -85.0 | 86.3 | 2947 | 49.1 | -47.8 | -41.9 | -50.4 |
| K4-rr2 | -73.8 | 75.3 | 3035 | 34.6 | -36.4 | -26.1 | -44.3 |
| K4-sr | -79.1 | 81.7 | 2984 | 34.8 | -44.8 | -36.4 | -40.6 |
| K4-pct | -86.3 | 86.8 | 3132 | 61.6 | -56.9 | -39.5 | -47.4 |
| K4-trail | -77.2 | 80.0 | 3738 | 29.0 | -26.0 | -28.1 | -57.0 |
| K4-indicator | -67.8 | 73.7 | 3174 | 34.5 | -39.5 | -27.0 | -27.1 |
| K2-rr2 | -8.4 | 14.0 | 176 | 31.2 | -3.0 | -3.0 | -2.7 |
| K2-base | -4.5 | 11.3 | 186 | 36.6 | 1.0 | -4.3 | -1.2 |

K2-base and K2-rr2 first stopped with an error (a short 2R target below zero, see commit
c5c5220); they were rerun after the fix. No other result changed.

**Selection: K3-rr2** (three soldiers/crows or three methods in an EMA50/EMA200 trend,
take profit at 2R). No candidate met the rule (no losing year and at least 30 trades), so
the fallback picked the best return/DD overall, and the pick is flagged. K3-rr2 made only
21 development trades, so its result rests on very few trades. Every 1h variant (K4) lost
68-86%; high win rates (K1-pct 73%, K2-pct 86%) still lost money after fees.
Frozen by this commit before any final run.
