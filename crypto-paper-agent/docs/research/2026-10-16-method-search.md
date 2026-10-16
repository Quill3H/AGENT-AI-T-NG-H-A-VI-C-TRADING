# Method search log, 2026-10-16

Status: AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED. Paper simulation only.

## Owner goal
Start with 10,000 USDT, trade BTCUSDT bar by bar from 2021-01-01 to 2025-12-31 with no
look-ahead. Success: more than +20% and steady growth (measured as: at least 4 of 5
calendar years profitable and no year below -10%). Otherwise try a new method.

## Protocol (fixed before any result was seen)
- Data: Binance Vision monthly archives 2020-09..2026-09, 584 files, all SHA-256
  checksums matched (`/mnt/project-files/market-data/binance-vision-btcusdt/`).
- Development window: 2021-01-01..2023-12-31. Every method below was scored here only.
- Final check: 2024-01-01..2025-12-31, opened once, only for the frozen candidate.
- Selection rule: highest dev return / max drawdown among candidates with no losing dev year.
- Every attempt is listed, including failures.

## Attempts on the development window (2021-2023)

| # | Method | Return | Max DD | 2021 | 2022 | 2023 | Trades |
|---|---|---|---|---|---|---|---|
| 1 | Existing Trend Following (4h EMA cross + pullback) | +4.62% | 20.69% | +1.73 | +3.68 | -0.81 | 29 |
| 2 | Existing Breakout & Retest (4h) | -26.25% | 29.29% | -13.21 | -4.74 | -10.80 | 35 |
| 3 | Donchian 20/10 long+short (Turtle System 1, daily) | +14.57% | 13.42% | -0.95 | +1.57 | +13.87 | 37 |
| 4 | Donchian 20/10 long only | +4.44% | 12.17% | -1.17 | -7.28 | +13.97 | 20 |
| 5 | Donchian 55/20 long+short (Turtle System 2) | -6.25% | 10.94% | -5.83 | -3.39 | +3.04 | 21 |
| 6 | Donchian 55/20 long only | +0.33% | 10.13% | -5.84 | -2.10 | +8.83 | 11 |
| 7 | Funding carry basket, enter at >=15% APR (existing config) | +19.00% | 1.74% | +16.78 | +0.08 | +1.82 | 8 |
| 8 | Funding carry basket, enter at >=10% APR | +14.38% | 1.74% | +14.31 | -1.19 | +1.27 | 58 |
| 9 | 50% #3 + 50% #7 | +16.78% | 6.83% | +7.91 | +0.76 | +7.40 | - |

SMC Liquidity Sweep was not run: it needs 1-minute bars that were not downloaded.
Cost stress on #7: fees and slippage x2 gave +17.46%, x3 gave +15.94% (2022 -0.05%).

## Frozen candidate
#7, funding carry basket (`config/strategies/funding_arbitrage.yaml`, min_apr 0.15,
exit after two negative settlements, basis emergency stop 2%), 1-hour quotes,
fees x1. Ratio 10.9 versus 2.5 for #9 and 1.1 for #3.
