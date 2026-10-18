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

## Development results (BTC/ETH/SOL 2021-01..2023-12; AUTHOR_REPORTED)

| Candidate | Risk | Return % | Max DD % | Trades | Trades/week | Win % | 2021 | 2022 | 2023 |
|---|---|---|---|---|---|---|---|---|---|
| T1 | 1% | -35.8 | 36.8 | 1244 | 8.0 | 49.1 | -16.4 | -5.9 | -18.4 |
| T1 | 2% | -46.9 | 49.0 | 1114 | 7.1 | 51.4 | -27.6 | -9.9 | -18.5 |
| T2 | 1% | -2.8 | 19.5 | 1838 | 11.8 | 40.5 | 3.8 | 4.2 | -10.1 |
| T2 | 2% | 24.4 | 19.3 | 1760 | 11.3 | 41.5 | 7.7 | 14.8 | 0.6 |
| T3 | 1% | -32.4 | 35.6 | 1402 | 9.0 | 36.2 | -8.0 | -10.5 | -17.9 |
| T3 | 2% | -50.4 | 54.9 | 1328 | 8.5 | 36.4 | -16.5 | -20.1 | -25.7 |
| V1 | 1% | -68.4 | 69.3 | 1750 | 11.2 | 30.8 | -24.6 | -41.2 | -28.7 |
| V1 | 2% | -61.6 | 64.3 | 981 | 6.3 | 31.1 | -24.3 | -42.7 | -11.7 |
| V2 | 1% | -53.5 | 55.0 | 1166 | 7.5 | 30.4 | -15.5 | -29.2 | -22.4 |
| V2 | 2% | -44.9 | 47.4 | 633 | 4.0 | 32.1 | -17.6 | -22.6 | -13.7 |
| V3 | 1% | -76.4 | 76.7 | 3188 | 20.4 | 40.8 | -54.6 | -38.6 | -15.4 |
| V3 | 2% | -36.0 | 42.0 | 759 | 4.9 | 43.2 | -16.0 | -21.1 | -3.3 |
| V4 | 1% | -50.3 | 52.7 | 2759 | 17.6 | 36.2 | -12.0 | -25.1 | -24.5 |
| V4 | 2% | -44.2 | 52.6 | 1995 | 12.8 | 38.0 | -13.1 | -26.8 | -12.2 |
| V5 | 1% | -0.7 | 28.4 | 3277 | 21.0 | 20.7 | 14.0 | -7.2 | -6.2 |
| V5 | 2% | 23.6 | 39.7 | 3193 | 20.4 | 21.1 | 32.0 | -8.1 | 1.9 |

**Selection: V5** (round-5 EMA pullback rules on 1h bars), at rule level "frequency only".
All candidates at 1% risk traded at least 5 times a week, but none had
no losing year at 1% risk. V5 lost 0.7% at 1% and had the best return/drawdown among the
frequent ones. T2 (Williams volatility breakout) made +24% at 2% with no losing year, but
the rule selects at 1%, where it lost 2.8%; it is not picked.

Every video setup lost after fees: the London breakout (V1/V2) won about 31% of trades at
2R, the Heikin-Ashi scalp 41-43% at 1R, the zone swing break 36-38% at 2.5R. Trades at 1%
outnumber trades at 2% because tight 5m stops at 2% exceed the 2x notional cap.
Frozen by this commit before any final run.
