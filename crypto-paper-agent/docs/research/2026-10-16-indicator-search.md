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
