# ADR 0014: Owner-selected 10% risk per trade for the directional futures sleeve (paper)

Date: 2026-10-16. Status: owner decision recorded; not an engineering gate acceptance.

## Context
The owner (zhilie meng) asked to focus on directional futures on BTC, ETH and SOL
with a hoped-for 20-50% per month. The 3-coin search
(`docs/research/2026-10-16-futures-search.md`) showed no setting reaches that:
at 2% risk/trade the frozen F3 strategy made +53% over 2021-2025 (max DD 10%)
and failed the 2024-2025 check; at 10% risk/trade +433% with a 44% max drawdown
and losing 2024 and 2025. Both options and drawdowns were shown on a decision card.

## Decision
The owner chose "10% (rủi ro cao)". For paper research the directional futures
sleeve uses `config/research/futures_search_2026_10_16/owner_risk_10pct.yaml`
(conviction `ultra_high`, base risk 10%).

## Unchanged
Paper only; no orders, testnet or keys. Leverage 2x per strategy config, max 5x;
order notional <= 2x equity; 5% rolling-24h daily-loss breaker; mandatory
stop-loss; 30% liquidation buffer invariant; 60-minute data-gap kill switch.
`config/default_config.yaml` defaults are not changed; the setting is opt-in per run.

## Consequences
Expected drawdowns of 40%+ in paper results. Any move beyond paper needs a new
explicit owner authorization and plan (AGENTS.md).
