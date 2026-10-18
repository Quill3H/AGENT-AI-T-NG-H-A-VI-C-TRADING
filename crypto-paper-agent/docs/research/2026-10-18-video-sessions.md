# Round 7: the owner's video, published trader methods, 5-10 trades a week (2026-10-18)

Paper only. Pre-registered before any run; results are AUTHOR_REPORTED and not
independently verified. Each run is also appended to the research ledger
(`docs/research/ledger/ledger.jsonl`; digest in `LEARNING_LOG.md`).

## Owner requests
- Learn from the video https://www.youtube.com/watch?v=qt55sMTiH68 ("Beginners Guide To
  Start Day Trading In 2026", 7.5 hours). Its English captions were fetched from the
  owner's computer (the cloud proxy blocks YouTube); transcript in
  `/mnt/project-files/research-inputs/youtube-qt55sMTiH68-transcript.txt`.
- Trade more: about 5-10 trades a week.
- Add published methods of well-known traders, and keep a learning record after every run.

The video trades CME index futures in the New York morning. It teaches price structure,
4h/1h support and resistance zones, a 1m swing-break entry, a Heikin-Ashi scalp, the
London range breakout, and a triangle squeeze. It uses no ICT/SMC concepts. Its win rates
(75%, 44% at 2R) come from hand backtests and are not taken as evidence. Our smallest
bar is 5m, so 1m triggers run on 5m bars. Crypto trades 24/7, so the session edge may not
carry over; testing that is part of the round.

## Candidates (src/strategies/session_suite.py)
- V1 `london_breakout`: London range 03:00-08:00 ET; first 5m close outside it between
  08:00 and 11:00 ET; stop beyond the trigger bar; 2R target; flat by 16:00 ET.
- V2 `london_breakout_trend`: V1 with the video's EMA(100) 1h trend filter (EMA 1200 on 5m).
- V3 `heikin_ashi_scalp`: EMA(100) trend; two clean opposite HA bars then a larger HA doji;
  stop at the doji; 1R from the doji's tip; 2-hour exit.
- V4 `zone_swing_break`: 1h pivot zones that price left by 1 ATR; tap within the last hour,
  then a 5m close through the last swing; stop beyond the last swing plus 0.1 ATR; 2.5R;
  09:30-12:00 ET, at most 2 a day.
- V5 `swing_ema_pullback_1h`: the round-5 W1 rules on 1h bars (more trades than 4h).
- T1 `holy_grail`: Linda Raschke, *Street Smarts* (1995). ADX(14) > 30, pullback to EMA(20),
  close above the previous high; stop at the 5-bar low; target the 20-bar high; 1h bars.
- T2 `volatility_breakout`: Larry Williams, *Long-Term Secrets to Short-Term Trading*
  (1999). First 5m close beyond the UTC day open ± 0.6 × yesterday's range; stop 0.5 ×
  range; flat at the day's end.
- T3 `nr7_breakout`: Toby Crabel, *Day Trading with Short Term Price Patterns* (1990).
  Close beyond an NR7 4h bar; stop at its other end; 2R; 1-day exit.

The trader methods use only their published rules. Their own performance claims are not
used, since none is independently verified. Excluded, because the rules cannot be coded
from OHLCV alone: zone "quality" judgement, the daily bias, the news blackout (no event
calendar) and the triangle squeeze (no reliable trend-line fit).

## Data and splits
- Development: BTC/ETH/SOL, 2021-01-01..2023-12-31, at 1% and 2% risk.
- Final A (untouched): TRX, ALGO, VET and SAND, 2021-01..2026-09. These are new Binance
  Vision downloads, 483 checksum-verified archives each. The ledger refuses a final on
  data any earlier final used.
- B (validation): BTC/ETH/SOL, 2024-01..2026-09. Already seen in earlier rounds, so it is
  context, not evidence.
- Costs: 0.05% taker fee + 0.03% slippage per side; costs x2 on A at 1%.
- Defaults stay at 2x leverage, a notional cap of 2x equity and a 30% liquidation buffer.
  The x20/x5 what-if from round 6 runs on A and B at 2% and 10% as a labelled what-if.

## Selection (fixed now)
Selection risk is 1%, the video's 0.5-1% range. Tight 5m stops at 2% often exceed the 2x
notional cap.

1. Among candidates with at least 5 trades a week on the three-coin development
   portfolio and no losing year, take the best return / max drawdown.
2. Otherwise take the best with at least 5 trades a week.
3. Otherwise take the best overall.

The rule level reached is reported. Eight candidates raise the chance of a lucky winner;
only A counts as evidence. The choice is frozen by commit before the final run.

## Amendment 1 (2026-10-18 07:34, before any development result was read): test universe
The owner asked to test only the 10 largest coins by market cap and to download no more
altcoins. Final tests use the 10 largest coins we already hold: BTC, ETH, XRP, BNB, SOL,
DOGE, TRX, ADA, LINK and AVAX. ALGO, VET and SAND are dropped; they were downloaded but
are never used.
- Final A (untouched): TRX only. It is the only one of the 10 no final test has used.
- Top-10 check (seen): all 10 coins, 2021-01..2026-09. The other 9 coins were used by
  earlier final tests, so this run is context, not evidence.
- Only BTC, ETH, SOL and TRX have 5m bars. A 5m candidate can therefore run only on those
  four. For a 1h or 4h candidate, missing 1h bars are resampled from the 15m archives
  (recorded per file).
- B (BTC/ETH/SOL 2024-01..2026-09) and the x20/x5 what-if are unchanged.
