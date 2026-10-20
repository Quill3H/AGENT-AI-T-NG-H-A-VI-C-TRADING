# Round 16: funding carry at the bank-rate threshold and a three-sleeve portfolio (2026-10-20)

Paper only, on Binance USDⓈ-M perpetual futures plus Binance spot for the carry hedge.
Pre-registered before the development run; results are AUTHOR_REPORTED and not
independently verified. Every run is appended to the research ledger.

## Owner request (2026-10-20 08:08)
"nếu thấp như vậy thì thà gửi ngân hàng còn hơn, hãy lên mạng tìm và học hỏi thêm các phương
án khác". The benchmark is a Vietnamese 12-month deposit: 5.9% a year at Vietcombank, BIDV and
VietinBank in early October 2026 (range 3.7-7.8% over 35 banks; thitruongtaichinhtiente.vn).

## What the web search found (details in docs/reports-vi/nghien-cuu-phuong-an-2026-10-20.md)
- Spot/perp funding carry (delta neutral) has the strongest public record: He, Manela, Ross and
  von Wachter, "Fundamentals of Perpetual Futures" (arXiv 2212.06888, Binance 2020-01..2024-03)
  report 6.4% a year for BTC and 9.6% for ETH after high trading costs (Sharpe 1.8 and 2.6).
  Ethena's sUSDe, a live version, averaged about 18% in 2024, 4-15% in 2025 and about 3.7% in
  early 2026. Round 2 tested a carry basket that opened only at 15% APR; it made +28.7% over
  2021-25 with a 2.9% drawdown and never opened in 2026.
- Combining uncorrelated sleeves is how multi-strategy funds raise return per unit of risk.
  After 15 rounds we have three different edges: carry (funding), trend (C1) and relative
  value (P1).
- Market making, options volatility selling and copy trading cannot be tested with our data
  (no order book, no options data, no audited follower records); see the report.

## Candidates (scripts/reproduce_round16.py)
| Key | Sleeves |
|---|---|
| K1 | spot/perp funding baskets (round-2 simulator, unchanged rules) on BTC/ETH/SOL, one third each, opening when funding annualises to >= 6% (the bank rate) |
| K2 | as K1 with a 10% threshold |
| M2 | one third each: K1 carry on BTC/ETH/SOL, C1 swing EMA long only on the top-10, P1 distance pairs on the top-10 (frozen rounds 8 and 14 rules) |

Thresholds and weights are fixed before any run. K1/K2 have no risk-per-trade setting (baskets
are sized by notional); M2 runs at 2% and 5% risk for its C1 and P1 sleeves.

## Data, costs and risk
- Development: 2021-01-01..2023-12-31. Spot klines exist for BTC/ETH/SOL only and end
  2026-09-30, so there is no October check for this round.
- Costs 0.05% taker + 0.03% slippage per side on both legs; funding at the exact settlement.
  Every round-2 carry limit (basis stop, liquidation check, daily-loss breaker) and every
  directional limit is unchanged. No leverage or risk limit is raised in this round.
- All of 2021-2026/09 has been used by earlier rounds; the check on 2024-01..2026-09 (and costs
  x2) is context only. New evidence comes only from forward paper from 2026-10-18.

**Disclosure.** No backtest ran before this plan was committed. Round 2's results for the 15%
threshold (above) were known when the 6% and 10% thresholds were chosen.

## Selection (fixed now; the round-8 rule)
1. Among K1, K2 and M2 x risk with no losing development year and max drawdown <= 35%, take the
   highest geometric average month.
2. Otherwise the highest average month with max drawdown <= 35%.
3. Otherwise the best return / max drawdown.
The result is compared with the 5.9% a year deposit (about 0.48% a month). The choice is frozen
by commit before any check.

## Development results (2021-01..2023-12; AUTHOR_REPORTED)

| Run | End equity $ | Return % | Max DD % | Trades | Win % (rule sleeves) | Average month % | Median month % | Worst month % | Losing months / 36 | 2021 | 2022 | 2023 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| K1 | 11,447 | 14.47 | 3.38 | 253 |  | 0.38 | -0.01 | -0.48 | 19 | 16.99 | -2.73 | 0.6 |
| K2 | 11,563 | 15.63 | 3.24 | 215 |  | 0.4 | 0.01 | -0.37 | 17 | 17.16 | -2.15 | 0.86 |
| M2 risk 2% | 12,414 | 24.14 | 4.57 | 1568 | 24.7 | 0.6 | -0.08 | -0.78 | 22 | 18.15 | -2.2 | 7.43 |
| M2 risk 5% | 16,788 | 67.88 | 11.11 | 1546 | 24.9 | 1.45 | -0.47 | -2.17 | 23 | 37.41 | -3.79 | 26.99 |

**Selection: M2 at 5% risk** (one third each carry K1, C1 trend, P1 pairs), rule level
"drawdown only": every candidate lost a little in 2022. Average month +1.45% (about 19% a year,
against the 5.9% deposit), max drawdown 11.1%, 2022 -3.8%. Step reached: none.

Other findings: carry at the bank-rate (K1, 6%) or 10% (K2) threshold made +14-16% over three
years (about 5% a year), almost all in 2021, with a 3.3% drawdown and a small 2022 loss; K2's
higher threshold was slightly better. Carry alone is roughly a bank deposit. Blending it with
trend and pairs cut C1's drawdown from 21.3% (C1 alone on the top-10 at 5%, round 13) to
11.1% while keeping about half of C1's monthly return.

Frozen by this commit before any check.
