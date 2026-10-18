# Learning log (generated from ledger.jsonl; do not edit by hand)

Paper-only research. Every run of every round is one row. A new round starts by reading
this file and the lessons at the bottom. Final-test data listed under "Spent final data"
cannot be reused for a new final test (src/research/ledger.py refuses it); new evidence has
to come from coins or months no final test has used, or from forward paper trading.


## Spent final data

- AAVEUSDT: 2021-01-01..2026-09-30
- ADAUSDT: 2021-01-01..2026-09-30, 2026-10-01..2026-10-17
- ATOMUSDT: 2021-01-01..2026-09-30
- AVAXUSDT: 2021-01-01..2026-09-30, 2026-10-01..2026-10-17
- BCHUSDT: 2021-01-01..2026-09-30
- BNBUSDT: 2021-01-01..2026-09-30, 2026-10-01..2026-10-17
- BTCUSDT: 2024-01-01..2025-12-31, 2026-01-01..2026-09-30, 2024-01-01..2026-09-30, 2026-10-01..2026-10-17
- DOGEUSDT: 2021-01-01..2026-09-30, 2026-10-01..2026-10-17
- DOTUSDT: 2021-01-01..2026-09-30
- ETCUSDT: 2021-01-01..2026-09-30
- ETHUSDT: 2024-01-01..2025-12-31, 2026-01-01..2026-09-30, 2024-01-01..2026-09-30, 2026-10-01..2026-10-17
- FILUSDT: 2021-01-01..2026-09-30
- LINKUSDT: 2021-01-01..2026-09-30, 2026-10-01..2026-10-17
- LTCUSDT: 2021-01-01..2026-09-30
- NEARUSDT: 2021-01-01..2026-09-30
- SOLUSDT: 2024-01-01..2025-12-31, 2026-01-01..2026-09-30, 2024-01-01..2026-09-30, 2026-10-01..2026-10-17
- TRXUSDT: 2021-01-01..2026-09-30, 2026-10-01..2026-10-17
- UNIUSDT: 2021-01-01..2026-09-30
- XLMUSDT: 2021-01-01..2026-09-30
- XRPUSDT: 2021-01-01..2026-09-30, 2026-10-01..2026-10-17

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
| 7 | dev | V1 | london_breakout | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 1% | -68.36 | 69.28 | 11.2 | 30.8 |
| 7 | dev | V1 | london_breakout | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -61.65 | 64.28 | 6.28 | 31.1 |
| 7 | dev | V2 | london_breakout_trend | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 1% | -53.55 | 54.99 | 7.46 | 30.4 |
| 7 | dev | V2 | london_breakout_trend | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -44.92 | 47.39 | 4.05 | 32.1 |
| 7 | dev | V4 | zone_swing_break | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 1% | -50.26 | 52.69 | 17.65 | 36.2 |
| 7 | dev | V3 | heikin_ashi_scalp | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -35.98 | 42.01 | 4.86 | 43.2 |
| 7 | dev | V3 | heikin_ashi_scalp | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 1% | -76.4 | 76.7 | 20.4 | 40.8 |
| 7 | dev | V5 | swing_ema_pullback_1h | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 1% | -0.73 | 28.39 | 20.97 | 20.7 |
| 7 | dev | V4 | zone_swing_break | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -44.16 | 52.63 | 12.77 | 38.0 |
| 7 | dev | V5 | swing_ema_pullback_1h | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | 23.57 | 39.71 | 20.43 | 21.1 |
| 7 | dev | T1 | holy_grail | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 1% | -35.81 | 36.81 | 7.96 | 49.1 |
| 7 | dev | T1 | holy_grail | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -46.87 | 49.03 | 7.13 | 51.4 |
| 7 | dev | T2 | volatility_breakout | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 1% | -2.8 | 19.49 | 11.76 | 40.5 |
| 7 | dev | T3 | nr7_breakout | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 1% | -32.4 | 35.56 | 8.97 | 36.2 |
| 7 | dev | T3 | nr7_breakout | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -50.41 | 54.93 | 8.5 | 36.4 |
| 7 | dev | T2 | volatility_breakout | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | 24.35 | 19.3 | 11.26 | 41.5 |
| 7 | validation | V5 | swing_ema_pullback_1h | 2024-01-01..2026-09-30 | BTC/ETH/SOL | 1% | -26.29 | 32.85 | 21.86 | 19.2 |
| 7 | validation | V5 | swing_ema_pullback_1h | 2024-01-01..2026-09-30 | BTC/ETH/SOL | 2% | -46.05 | 55.1 | 21.41 | 19.4 |
| 7 | validation | V5 | swing_ema_pullback_1h | 2024-01-01..2026-09-30 | BTC/ETH/SOL | 10% | -75.47 | 77.23 | 5.9 | 25.0 |
| 7 | final-whatif | V5 | swing_ema_pullback_1h | 2024-01-01..2026-09-30 | BTC/ETH/SOL | 2% | -48.13 | 56.23 | 21.62 | 19.0 |
| 7 | final-whatif | V5 | swing_ema_pullback_1h | 2024-01-01..2026-09-30 | BTC/ETH/SOL | 10% | -98.6 | 98.66 | 16.26 | 19.5 |
| 7 | final | V5 | swing_ema_pullback_1h | 2021-01-01..2026-09-30 | TRX | 10% | -54.58 | 86.77 | 1.32 | 24.6 |
| 7 | final | V5 | swing_ema_pullback_1h | 2021-01-01..2026-09-30 | TRX | 2% | -88.78 | 92.73 | 6.78 | 19.5 |
| 7 | final | V5 | swing_ema_pullback_1h | 2021-01-01..2026-09-30 | TRX | 1% | -71.76 | 77.69 | 7.22 | 18.6 |
| 7 | final | V5 | swing_ema_pullback_1h | 2021-01-01..2026-09-30 | TRX | 1% | -94.4 | 95.28 | 7.23 | 15.3 |
| 7 | validation | V5 | swing_ema_pullback_1h | 2021-01-01..2026-09-30 | BTC/ETH/SOL/TRX | 1% | -36.43 | 51.22 | 28.61 | 19.6 |
| 7 | validation | V5 | swing_ema_pullback_1h | 2021-01-01..2026-09-30 | BTC/ETH/SOL/TRX | 2% | -42.17 | 66.1 | 27.67 | 20.1 |
| 7 | final-whatif | V5 | swing_ema_pullback_1h | 2021-01-01..2026-09-30 | TRX | 2% | -92.33 | 95.07 | 7.21 | 18.6 |
| 7 | final-whatif | V5 | swing_ema_pullback_1h | 2021-01-01..2026-09-30 | TRX | 10% | -99.9 | 99.99 | 4.02 | 21.4 |
| 8 | dev | C1 | swing_ema_pullback_long | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | 71.8 | 14.13 | 2.34 | 26.5 |
| 8 | dev | C1 | swing_ema_pullback_long | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 5% | 317.92 | 31.35 | 2.28 | 26.6 |
| 8 | dev | C1 | swing_ema_pullback_long | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 10% | 1243.71 | 50.99 | 1.98 | 28.5 |
| 8 | dev | C2 | blowoff_fade | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -9.94 | 14.04 | 0.44 | 32.4 |
| 8 | dev | C2 | blowoff_fade | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 5% | -24.53 | 24.7 | 0.3 | 31.9 |
| 8 | dev | C2 | blowoff_fade | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 10% | -22.77 | 24.78 | 0.14 | 27.3 |
| 8 | dev | C3 | flush_buy | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -1.61 | 7.16 | 0.13 | 42.9 |
| 8 | dev | C3 | flush_buy | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 5% | -9.68 | 17.34 | 0.11 | 35.3 |
| 8 | dev | C3 | flush_buy | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 10% | -12.37 | 21.37 | 0.06 | 40.0 |
| 8 | dev | C4 | swing_ema_pullback_long+candle_continuation+volatility_breakout | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | 34.38 | 7.36 | 13.74 | 39.2 |
| 8 | dev | C4 | swing_ema_pullback_long+candle_continuation+volatility_breakout | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 5% | 97.54 | 23.01 | 10.24 | 37.8 |
| 8 | dev | W1 | swing_ema_pullback | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | 80.06 | 13.58 | 4.59 | 26.5 |
| 8 | dev | W1 | swing_ema_pullback | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 5% | 301.42 | 26.08 | 4.4 | 27.1 |
| 8 | dev | W1 | swing_ema_pullback | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 10% | 1137.99 | 50.13 | 3.89 | 27.1 |
| 8 | dev | K3 | candle_continuation | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | 6.98 | 2.31 | 0.13 | 61.9 |
| 8 | dev | K3 | candle_continuation | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 5% | 14.16 | 5.62 | 0.13 | 60.0 |
| 8 | dev | K3 | candle_continuation | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 10% | 19.33 | 7.37 | 0.1 | 60.0 |
| 8 | dev | C4 | swing_ema_pullback_long+candle_continuation+volatility_breakout | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 10% | 398.01 | 42.87 | 5.69 | 34.7 |
| 8 | dev | T2 | volatility_breakout | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | 24.35 | 19.3 | 11.26 | 41.5 |
| 8 | dev | T2 | volatility_breakout | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 5% | -39.48 | 51.26 | 7.83 | 40.7 |
| 8 | dev-whatif | C1 | swing_ema_pullback_long | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 5% | 228.55 | 30.0 | 1.87 | 25.6 |
| 8 | dev-whatif | C1 | swing_ema_pullback_long | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 10% | 1117.94 | 57.58 | 1.82 | 26.4 |
| 8 | dev | T2 | volatility_breakout | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 10% | -69.01 | 71.42 | 3.62 | 37.5 |
| 8 | validation | C1 | swing_ema_pullback_long | 2024-01-01..2026-09-30 | BTC/ETH/SOL | 5% | 17.78 | 24.27 | 2.62 | 22.9 |
| 8 | final | C1 | swing_ema_pullback_long | 2026-10-01..2026-10-17 | BTC/ETH/SOL | 5% | -1.4 | 2.1 | 1.75 | 0.0 |
| 8 | final | C1 | swing_ema_pullback_long | 2026-10-01..2026-10-17 | BTC/ETH/SOL | 5% | -1.69 | 2.32 | 1.75 | 0.0 |
| 8 | final | W1 | swing_ema_pullback | 2026-10-01..2026-10-17 | BTC/ETH/SOL | 2% | -1.49 | 4.59 | 6.56 | 20.0 |
| 8 | final | K3 | candle_continuation | 2026-10-01..2026-10-17 | BTC/ETH/SOL | 2% | 0.0 | 0.0 | 0.0 | None |
| 8 | final | T2 | volatility_breakout | 2026-10-01..2026-10-17 | BTC/ETH/SOL | 2% | -3.56 | 5.45 | 7.88 | 22.2 |
| 9 | dev | I1-4h | ichimoku_tk_4h | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | 23.0 | 9.13 | 1.93 | 31.9 |
| 9 | dev | I1-4h | ichimoku_tk_4h | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 5% | 32.91 | 22.79 | 1.75 | 31.8 |
| 9 | dev | I2-4h | ichimoku_kumo_4h | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 5% | 4.9 | 18.37 | 1.61 | 32.7 |
| 9 | dev | I2-4h | ichimoku_kumo_4h | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | 1.88 | 7.69 | 1.72 | 32.7 |
| 9 | dev | I1-1h | ichimoku_tk_1h | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 5% | 50.02 | 29.94 | 4.81 | 36.4 |
| 9 | dev | I1-1h | ichimoku_tk_1h | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | 32.88 | 21.42 | 7.28 | 32.3 |
| 9 | dev | I2-1h | ichimoku_kumo_1h | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -19.94 | 30.32 | 7.58 | 28.4 |
| 9 | dev | I2-1h | ichimoku_kumo_1h | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 5% | -29.37 | 46.63 | 5.58 | 30.8 |
| 9 | dev | I1-15m | ichimoku_tk_15m | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -63.89 | 75.77 | 22.89 | 29.9 |
| 9 | dev | I1-15m | ichimoku_tk_15m | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 5% | -52.61 | 59.82 | 6.28 | 33.7 |
| 9 | dev | I2-15m | ichimoku_kumo_15m | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -77.04 | 78.02 | 26.85 | 26.7 |
| 9 | dev | I2-15m | ichimoku_kumo_15m | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 5% | -78.26 | 78.78 | 11.86 | 28.3 |
| 9 | dev | I1-4h-long | ichimoku_tk_4h_long | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | 19.67 | 6.44 | 1.05 | 37.8 |
| 9 | dev | I1-4h-long | ichimoku_tk_4h_long | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 5% | 35.12 | 22.67 | 0.97 | 38.4 |
| 9 | dev | I2-4h-long | ichimoku_kumo_4h_long | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 2% | -4.61 | 9.21 | 0.74 | 29.3 |
| 9 | dev | I2-4h-long | ichimoku_kumo_4h_long | 2021-01-01..2023-12-31 | BTC/ETH/SOL | 5% | -9.78 | 20.81 | 0.69 | 28.7 |
| 9 | validation | I1-4h | ichimoku_tk_4h | 2026-10-01..2026-10-17 | BTC/ETH/SOL | 5% | 1.66 | 2.74 | 0.44 | 100.0 |
| 9 | validation | I1-4h | ichimoku_tk_4h | 2024-01-01..2026-09-30 | BTC/ETH/SOL | 5% | 34.04 | 21.58 | 1.57 | 35.1 |
| 9 | final | I1-4h | ichimoku_tk_4h | 2026-10-01..2026-10-17 | XRP/BNB/DOGE/TRX/ADA/LINK/AVAX | 5% | -2.46 | 3.08 | 2.62 | 16.7 |
| 9 | final | I1-4h | ichimoku_tk_4h | 2026-10-01..2026-10-17 | XRP/BNB/DOGE/TRX/ADA/LINK/AVAX | 5% | -2.31 | 2.98 | 2.62 | 16.7 |
| 9 | validation | I1-4h | ichimoku_tk_4h | 2021-01-01..2026-09-30 | BTC/ETH/XRP/BNB/SOL/DOGE/TRX/ADA/LINK/AVAX | 5% | 153.58 | 18.07 | 5.48 | 33.2 |

## Lessons

- Round 1: A daily Donchian trend system chosen on 2021-23 lost on 2024-25; 20-50% a month is not realistic.
- Round 2: Funding carry made money only when funding was high; in 2026 it took no trades.
- Round 3: Indicator systems that win big in development (mostly SOL 2021) fail on later data.
- Round 4: One coin (AVAX) carried a +183% holdout; returns spread over few coins are luck, not edge.
- Round 5: Every scalp (1m-1h) lost after fees, even with 55% wins; 4h EMA pullback was weakly positive at 1-2% risk.
- Round 6: Fast take-profits raise the win rate but lose money; 4h continuation patterns with a 2R target were small but positive on unseen coins with very few trades. x20 leverage cut BTC/ETH trades because liquidation sits about 5% away.
- Round 7: Trading more often (5-10+ a week) made every method worse after fees. The video's London breakout, Heikin-Ashi scalp and zone break all lost on 5m crypto bars; W1 rules on 1h (about 20 trades a week on three coins) lost 72% on untouched TRX at 1% risk. Williams volatility breakout (T2) was the only frequent method positive in development (+24% at 2%), untested on fresh data.
- Round 7: Check that every test coin has a leverage-bracket table before a final; TRX lacked one and its first final runs took zero trades (voided and rerun).
- Round 8: Dropping W1's shorts changed little (4.05% vs 3.94% a month in development at 5%); GCR-style blow-off fades and flush buys on 4h lost at every risk and traded rarely; T2's fees took 60% of its gross profit.
- Round 8: Frozen C1 (W1 long only, 5% risk) averaged +4.05% a month in development (drawdown 31%) but +0.5% a month on 2024-2026/09 (drawdown 24%; SOL lost) and -1.4% on the unused 2026-10-01..17 window (4 trades). Step 1 (10% a month) not reached. The median month is about 0% in every run: a few large trend months carry the result, so a higher monthly target needs more uncorrelated edges, not more risk on one.
- Round 8: Binance Vision has no funding for the current month and the engine rejects funding older than 24h; forward runs take funding from the public /fapi/v1/fundingRate endpoint via the owner's computer (scripts/extend_vision_daily.py --funding).
- Round 9: Ichimoku (9/26/52): the Tenkan/Kijun cross on 4h was the only steady variant (+0.8% a month at 5%, no losing year in development); cloud breakouts were flat on 4h and lost on 1h, and every 15m run lost 53-78% after fees.
- Round 9: Frozen I1-4h at 5% lost 2.3% on the unused 7-coin 2026-10-01..17 window (6 trades). On seen data it made +34% on BTC/ETH/SOL 2024-2026 (all from SOL) and +154% on the top 10 2021-2026 with an 18% drawdown, mostly 2021 and four coins. Step 1 (10% a month) not reached; the whole top-10 history to 2026-10-17 is now spent, so the next evidence is forward paper.
