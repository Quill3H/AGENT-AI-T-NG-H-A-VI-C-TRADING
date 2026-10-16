# Round 4: new directions beyond single-coin trend rules (2026-10-16)

Owner choice relayed by the project coordinator (2026-10-16 20:19 UTC): "Thử hướng
mới" after round 3. Paper only; 10,000 USDT; 10% risk per trade (ADR 0014);
all other risk gates unchanged; every attempt logged.

## Data
- Price: Binance Vision USD-M klines (checksum-verified) for BTC, ETH, SOL, BNB, XRP,
  DOGE, ADA (already used) and LINK, AVAX, LTC, DOT (new, never inspected).
- New non-price data: Binance Vision daily `metrics` files (5-minute open interest
  value, top-trader and global long/short ratios, taker long/short volume ratio),
  checksum-verified and aggregated to daily values. Snapshot times are within the
  day, so a daily decision at the day's close uses only that day's snapshots.
- Taker buy share from the klines (taker_buy_base_volume / volume).
- No funding-based strategy (owner request); funding is still charged on positions.
- No new Python package: models are written in numpy.

## Splits
1. Development: 2021-01-01..2023-12-31. Single-coin candidates trade BTC/ETH/SOL;
   the cross-sectional candidate ranks the 7 already-used coins.
2. Final test A (untouched): LINK, AVAX, LTC, DOT, 2021-01-01..2026-09-30.
3. Final test B (validation, coins seen earlier with other rules): BTC/ETH/SOL,
   2024-01-01..2026-09-30.

## Candidates (all daily decisions, filled at the next 15m open, stop 3 x ATR(20) on every entry)
- N1 `xs_momentum`: every 7 days rank the universe by 30-day return; long the top
  third, short the bottom third, flat otherwise; exit when a coin leaves its group.
  (Cross-sectional momentum, Jegadeesh & Titman 1993; Liu, Tsyvinski & Wu 2022 for crypto.)
- N2 `regime_switch`: ADX(14) > 25 -> Donchian 20 breakout with 10-day trailing exit;
  ADX(14) < 20 -> RSI(2) reversion (long < 10 above SMA(100), short > 90 below),
  exit on SMA(5) cross; 20..25 -> no new entry.
- N3 `ml_price`: walk-forward logistic regression (L2, numpy) pooled over the
  traded coins. Features: 1/5/20-day returns, 20-day volatility, distance to
  EMA(50), RSI(14), 5-day taker buy share, 20-day volume z-score. Target: sign of
  the next 5-day return. Retrain every 30 days on all data with a known target
  (labels end 5 days before the decision day); first prediction after 365 days of
  history. Long if p > 0.55, short if p < 0.45; exit when p crosses 0.5.
- N4 `ml_metrics`: N3 plus 1/5-day change in open interest value, top-trader
  long/short ratio, global long/short ratio, taker long/short volume ratio.
  Days without metrics give no new entry.

Model hyper-parameters (L2 = 1.0, thresholds, horizon) are fixed here and not tuned.

## Selection rule
Highest development return / max drawdown among candidates with no losing
development year and at least 30 completed trades; otherwise the best overall,
flagged. Frozen by commit, then run once on final test A and once on B.

Ideas credited (no code copied): Jegadeesh & Titman 1993; Liu, Tsyvinski & Wu
2022 "Common risk factors in cryptocurrency" (J. Finance); Wilder 1978; Connors &
Alvarez (RSI(2)); walk-forward evaluation as described by Lopez de Prado,
"Advances in Financial Machine Learning" (2018).

## Development results, N1-N3 (2021-01-01..2023-12-31, 10% risk, AUTHOR_REPORTED)

| Candidate | Return | Max DD | 2021 / 2022 / 2023 | Trades | Eligible |
|---|---|---|---|---|---|
| N1 xs_momentum (7 coins) | +38.1% | 9.1% | +4.7 / -1.3 / +33.7 | 165 | no (2022 loss) |
| N2 regime_switch | +643.2% | 37.8% | +83.6 / +35.7 / +198.5 | 67 | yes |
| N3 ml_price | +2.5% | 41.1% | -7.3 / -28.3 / +54.3 | 95 | no (2021, 2022 loss) |

N4 is not run yet: its open-interest metrics files are on the owner's device and the
device folder link dropped during the download. No final-stage run has been made, so
the selection is still open. Raw output: `results_new_directions_dev_N1-N3.json` in
the shared market-data folder.
