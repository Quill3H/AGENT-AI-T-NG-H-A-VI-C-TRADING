# Round 15: funding-rate crowding rules on the top-10 perpetuals (2026-10-19)

Paper only, on Binance USDⓈ-M perpetual futures (2x leverage, funding, shorts). Pre-registered
before the development run; results are AUTHOR_REPORTED and not independently verified.
Every run is appended to the research ledger.

## Owner requests (2026-10-19)
"Ok hãy chạy tiếp 1 phương pháp khác, được phép copy người khác", "Bằng mọi giá phải giúp tôi
tìm ra được cách", "Nên nhớ chúng ta đang trade future".

Rounds 1-14 used price only, apart from round 2's spot-perp cash-and-carry basket (entry at a
15% APR funding level; it never opened in 2026). Round 15 uses funding as information about
crowding, a signal only perpetual futures have. Source: Schmeling, Schrimpf and Todorov,
"Crypto carry", BIS working paper 1087 (https://bis.org/publ/work1087.htm): carry (the
futures-spot gap that funding tracks) averages above 10% a year, is driven by trend-chasing
leveraged demand and scarce arbitrage capital, and **high carry predicts future crashes**.
The cross-sectional sort (F2/F3) is our application of that finding to the top-10; we found
no published test of it with costs.

## Candidates (src/strategies/funding_signals.py)
A decision at a 4h close uses only funding events settled at or before that close.

| Key | Rule |
|---|---|
| C1 | reference: round-8 swing EMA pullback, long only, on the same 10 coins (not selectable) |
| F1 | C1, but no new long while the coin's 7-day mean funding is above the 90th percentile of its own daily 7-day means over the past 180 days (needs 90 days of history) |
| F2 | weekly (4h bar opening Sunday 20:00 UTC): rank the 10 coins by 7-day mean funding; long the 3 lowest, short the 3 highest; exit at a later weekly bar when the coin leaves its group; stop 2 daily ATR(14) |
| F3 | as F2, short side only, and only when the coin's 7-day mean funding is positive |

Settings (7 days, 180 days, 90th percentile, top 3 of 10, 2 ATR) are fixed before any run.

## Data, costs and risk
- Development: top-10 2021-01-01..2023-12-31 at 2% and 5% risk per trade.
- Costs 0.05% taker + 0.03% slippage per side, funding at 00/08/16 UTC. Leverage 2x, order cap
  2x equity, liquidation buffer, 5% daily-loss breaker (realized cash flows, per sleeve), stop
  on every trade. No limit is relaxed. The streak rule halves risk after 3 losses.
- After the freeze, checks are on **seen** data only and labelled as context: top-10
  2024-01..2026-09 (and with costs x2), 2026-10-01..17, and C1 on the same top-10 at the same
  risk. New evidence comes only from forward paper from 2026-10-18.

**Disclosure.** No backtest or signal count ran before this plan was committed; only the
unit tests on synthetic data.

## Selection (fixed now; the round-8 rule)
1. Among F1-F3 x risk with no losing development year and max drawdown <= 35%, take the
   highest geometric average month.
2. Otherwise the highest average month with max drawdown <= 35%.
3. Otherwise the best return / max drawdown.
The result also reports whether the pick beats C1 on the same top-10 at the same risk. The
choice is frozen by commit before any check.
