# Learning log (generated from ledger.jsonl; do not edit by hand)

Paper-only research. Every run of every round is one row. A new round starts by reading
this file and the lessons at the bottom. Final-test data listed under "Spent final data"
cannot be reused for a new final test (src/research/ledger.py refuses it); new evidence has
to come from coins or months no final test has used, or from forward paper trading.


## Spent final data

- AAVEUSDT: 2021-01-01..2026-09-30
- ADAUSDT: 2021-01-01..2026-09-30
- ATOMUSDT: 2021-01-01..2026-09-30
- AVAXUSDT: 2021-01-01..2026-09-30
- BCHUSDT: 2021-01-01..2026-09-30
- BNBUSDT: 2021-01-01..2026-09-30
- BTCUSDT: 2024-01-01..2025-12-31, 2026-01-01..2026-09-30, 2024-01-01..2026-09-30
- DOGEUSDT: 2021-01-01..2026-09-30
- DOTUSDT: 2021-01-01..2026-09-30
- ETCUSDT: 2021-01-01..2026-09-30
- ETHUSDT: 2024-01-01..2025-12-31, 2026-01-01..2026-09-30, 2024-01-01..2026-09-30
- FILUSDT: 2021-01-01..2026-09-30
- LINKUSDT: 2021-01-01..2026-09-30
- LTCUSDT: 2021-01-01..2026-09-30
- NEARUSDT: 2021-01-01..2026-09-30
- SOLUSDT: 2024-01-01..2025-12-31, 2026-01-01..2026-09-30, 2024-01-01..2026-09-30
- UNIUSDT: 2021-01-01..2026-09-30
- XLMUSDT: 2021-01-01..2026-09-30
- XRPUSDT: 2021-01-01..2026-09-30

## Runs

| Round | Stage | Candidate | Strategy | Window | Symbols | Risk | Return % | Max DD % | Trades/week | Win % |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | final | - | donchian_trend | 2024-01-01..2025-12-31 | BTC/ETH/SOL | - | None | None | 0.0 | None |
| 2 | final | - | carry/trend | 2026-01-01..2026-09-30 | BTC/ETH/SOL | - | None | None | 0.0 | None |
| 5 | dev | W2 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 1% | -6.25 | 6.97 | 0.72 | 26.5 |
| 5 | dev | W1 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 1% | 34.18 | 7.85 | 4.62 | 26.3 |
| 5 | dev | W1 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | 80.06 | 13.58 | 4.59 | 26.5 |
| 5 | dev | W1 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 10% | 1137.99 | 50.13 | 3.89 | 27.1 |
| 5 | dev | W2 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 10% | -46.27 | 50.28 | 0.63 | 26.3 |
| 5 | dev | W2 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -12.24 | 13.61 | 0.72 | 26.5 |
| 5 | dev | W3 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 1% | -0.82 | 4.29 | 1.0 | 34.6 |
| 5 | dev | W3 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | 0.97 | 8.82 | 0.97 | 35.5 |
| 5 | dev | W3 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 10% | -2.02 | 18.48 | 0.19 | 43.3 |
| 5 | dev | D1 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 1% | -21.48 | 27.53 | 14.29 | 42.4 |
| 5 | dev | D1 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -30.65 | 40.45 | 13.69 | 42.8 |
| 5 | dev | D1 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 10% | -38.18 | 49.19 | 4.45 | 43.9 |
| 5 | dev | D2 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 1% | -72.51 | 77.11 | 44.32 | 37.0 |
| 5 | dev | D2 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -50.74 | 70.77 | 27.13 | 37.5 |
| 5 | dev | D2 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 10% | 22.5 | 19.4 | 0.35 | 45.5 |
| 5 | dev | C1 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 1% | -93.81 | 93.85 | 43.72 | 41.1 |
| 5 | dev | C1 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -46.1 | 46.35 | 7.65 | 40.1 |
| 5 | dev | C1 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 10% | -4.36 | 6.77 | 0.01 | 0.0 |
| 5 | dev-costs | C1 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -62.71 | 62.86 | 7.79 | 39.1 |
| 5 | dev-costs | C2 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -66.26 | 66.64 | 6.56 | 35.5 |
| 5 | dev | C2 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 1% | -81.22 | 81.31 | 18.31 | 34.2 |
| 5 | dev | C2 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 10% | 0.12 | 3.64 | 0.01 | 50.0 |
| 5 | dev | C2 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -38.6 | 39.81 | 5.02 | 36.7 |
| 5 | dev | C3 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 1% | -52.49 | 52.53 | 8.79 | 34.2 |
| 5 | dev | C3 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 10% | -3.4 | 3.4 | 0.01 | 0.0 |
| 5 | dev-costs | C3 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -67.15 | 67.25 | 6.23 | 31.8 |
| 5 | dev | C3 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -49.12 | 49.82 | 5.85 | 32.9 |
| 5 | dev | C4 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -93.78 | 94.24 | 39.18 | 55.0 |
| 5 | dev | C4 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 1% | -99.51 | 99.53 | 77.26 | 55.1 |
| 5 | dev | C4 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 10% | -10.88 | 17.58 | 0.6 | 52.7 |
| 5 | dev-costs | C4 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -99.61 | 99.63 | 39.86 | 52.5 |
| 5 | dev | C5 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 1% | -18.52 | 19.09 | 2.74 | 32.2 |
| 5 | dev | C5 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -26.85 | 27.82 | 2.51 | 33.3 |
| 5 | dev | C5 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 10% | 2.25 | 7.18 | 0.03 | 50.0 |
| 5 | dev-costs | C5 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -37.08 | 37.72 | 2.55 | 33.4 |
| 5 | dev | C6 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 1% | -65.24 | 65.91 | 23.25 | 56.3 |
| 5 | dev | C6 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -77.4 | 79.08 | 20.04 | 56.4 |
| 5 | dev | C6 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 10% | -16.44 | 47.29 | 1.13 | 55.1 |
| 5 | dev-costs | C6 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -94.84 | 94.97 | 20.62 | 53.9 |
| 6 | dev | K1-base |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | 70.57 | 24.18 | 5.65 | 28.9 |
| 6 | dev | K1-rr1 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -13.28 | 25.9 | 6.17 | 52.7 |
| 6 | dev | K1-rr2 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | 1.38 | 19.34 | 5.34 | 38.1 |
| 6 | dev | K1-sr |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -0.62 | 21.61 | 5.36 | 37.2 |
| 6 | dev | K1-pct |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -35.44 | 38.29 | 7.42 | 73.3 |
| 6 | dev | K1-trail |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -7.02 | 22.41 | 6.76 | 32.6 |
| 6 | dev | K1-indicator |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -14.3 | 29.17 | 5.99 | 34.7 |
| 6 | dev | K2-rr1 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -11.29 | 15.07 | 1.2 | 44.1 |
| 6 | dev | K2-sr |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -7.66 | 12.02 | 1.02 | 26.4 |
| 6 | dev | K2-pct |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -4.27 | 7.0 | 1.46 | 85.5 |
| 6 | dev | K2-trail |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -11.59 | 13.51 | 1.13 | 33.5 |
| 6 | dev | K2-indicator |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -6.92 | 11.51 | 1.08 | 28.4 |
| 6 | dev | K3-base |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | 14.79 | 5.56 | 0.13 | 45.0 |
| 6 | dev | K3-rr1 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | 4.52 | 1.5 | 0.13 | 66.7 |
| 6 | dev | K3-rr2 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | 6.98 | 2.31 | 0.13 | 61.9 |
| 6 | dev | K3-sr |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -0.95 | 1.53 | 0.04 | 57.1 |
| 6 | dev | K3-pct |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | 1.71 | 0.73 | 0.14 | 95.5 |
| 6 | dev | K3-trail |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | 4.27 | 2.13 | 0.13 | 52.4 |
| 6 | dev | K3-indicator |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | 1.19 | 1.03 | 0.13 | 57.1 |
| 6 | dev | K4-base |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -75.73 | 81.81 | 20.88 | 25.4 |
| 6 | dev | K4-rr1 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -84.95 | 86.28 | 18.86 | 49.1 |
| 6 | dev | K4-rr2 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -73.82 | 75.35 | 19.42 | 34.6 |
| 6 | dev | K4-sr |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -79.13 | 81.74 | 19.09 | 34.8 |
| 6 | dev | K4-pct |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -86.3 | 86.82 | 20.04 | 61.6 |
| 6 | dev | K4-trail |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -77.15 | 80.02 | 23.92 | 29.0 |
| 6 | dev | K4-indicator |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -67.79 | 73.74 | 20.31 | 34.5 |
| 6 | dev | K2-rr2 |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -8.37 | 14.04 | 1.13 | 31.2 |
| 6 | dev | K2-base |  | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -4.49 | 11.32 | 1.19 | 36.6 |
| 3 | final | I5 | adx_donchian | 2024-01-01..2026-09-30 | BTC/ETH/SOL | 10% | -1.28 | 38.48 | 0.41 | 35.6 |
| 3 | final | I5 | adx_donchian | 2021-01-01..2026-09-30 | BNB/XRP/DOGE/ADA | 10% | 125.97 | 47.51 | 0.48 | 31.7 |
| 4 | final | N2 | regime_switch | 2021-01-01..2026-09-30 | LINK/AVAX/LTC/DOT | 10% | 183.36 | 41.7 | 0.58 | 47.4 |
| 4 | final | N2 | regime_switch | 2024-01-01..2026-09-30 | BTC/ETH/SOL | 10% | -6.1 | 39.69 | 0.59 | 41.2 |
| 5 | final | W1 | swing_ema_pullback | 2024-01-01..2026-09-30 | BTC/ETH/SOL | 2% | 6.49 | 10.73 | 5.34 | 23.3 |
| 5 | final | W1 | swing_ema_pullback | 2021-01-01..2026-09-30 | ETC/ATOM/NEAR/FIL | 1% | 8.72 | 11.89 | 6.63 | 26.0 |
| 5 | final | W1 | swing_ema_pullback | 2021-01-01..2026-09-30 | ETC/ATOM/NEAR/FIL | 2% | 14.92 | 24.32 | 6.63 | 26.0 |
| 5 | final | W1 | swing_ema_pullback | 2024-01-01..2026-09-30 | BTC/ETH/SOL | 1% | 3.49 | 5.69 | 5.35 | 23.2 |
| 5 | final | W1 | swing_ema_pullback | 2021-01-01..2026-09-30 | ETC/ATOM/NEAR/FIL | 10% | -22.61 | 90.21 | 6.23 | 26.0 |
| 5 | final | W1 | swing_ema_pullback | 2024-01-01..2026-09-30 | BTC/ETH/SOL | 10% | -9.24 | 39.95 | 4.08 | 23.6 |
| 6 | final | K3-rr2 | candle_continuation | 2024-01-01..2026-09-30 | BTC/ETH/SOL | 1% | 0.3 | 3.07 | 0.14 | 40.0 |
| 6 | final | K3-rr2 | candle_continuation | 2024-01-01..2026-09-30 | BTC/ETH/SOL | 2% | 0.52 | 6.05 | 0.14 | 40.0 |
| 6 | final | K3-rr2 | candle_continuation | 2021-01-01..2026-09-30 | XLM/BCH/UNI/AAVE | 1% | 3.65 | 0.92 | 0.15 | 54.3 |
| 6 | final | K3-rr2 | candle_continuation | 2021-01-01..2026-09-30 | XLM/BCH/UNI/AAVE | 2% | 7.5 | 1.78 | 0.15 | 54.3 |
| 6 | final | K3-rr2 | candle_continuation | 2021-01-01..2026-09-30 | XLM/BCH/UNI/AAVE | 10% | 29.43 | 9.01 | 0.12 | 54.1 |
| 6 | final | K3-rr2 | candle_continuation | 2024-01-01..2026-09-30 | BTC/ETH/SOL | 10% | -3.66 | 19.9 | 0.11 | 37.5 |
| 6 | final-whatif | K3-rr2 | candle_continuation | 2024-01-01..2026-09-30 | BTC/ETH/SOL | 2% | 0.24 | 4.19 | 0.05 | 42.9 |
| 6 | final-whatif | K3-rr2 | candle_continuation | 2024-01-01..2026-09-30 | BTC/ETH/SOL | 10% | 1.05 | 18.65 | 0.05 | 42.9 |
| 6 | final-whatif | K3-rr2 | candle_continuation | 2021-01-01..2026-09-30 | XLM/BCH/UNI/AAVE | 2% | 7.5 | 1.78 | 0.15 | 54.3 |
| 6 | final-whatif | K3-rr2 | candle_continuation | 2021-01-01..2026-09-30 | XLM/BCH/UNI/AAVE | 10% | 45.8 | 8.35 | 0.15 | 54.3 |

## Lessons

- Round 1: A daily Donchian trend system chosen on 2021-23 lost on 2024-25; 20-50% a month is not realistic.
- Round 2: Funding carry made money only when funding was high; in 2026 it took no trades.
- Round 3: Indicator systems that win big in development (mostly SOL 2021) fail on later data.
- Round 4: One coin (AVAX) carried a +183% holdout; returns spread over few coins are luck, not edge.
- Round 5: Every scalp (1m-1h) lost after fees, even with 55% wins; 4h EMA pullback was weakly positive at 1-2% risk.
- Round 6: Fast take-profits raise the win rate but lose money; 4h continuation patterns with a 2R target were small but positive on unseen coins with very few trades. x20 leverage cut BTC/ETH trades because liquidation sits about 5% away.
