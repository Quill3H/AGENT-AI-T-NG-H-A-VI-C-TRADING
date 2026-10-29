# E2E Test Infra: Optimal Synthesized Strategy & 1-Year Backtest

## Test Philosophy
- Opaque-box, requirement-driven derived strictly from ORIGINAL_REQUEST.md.
- Multi-tier testing hierarchy (Tiers 1-4).

## Feature Inventory & Test Coverage
| # | Feature | Source (Requirement) | Tier 1 | Tier 2 | Tier 3 |
|---|---------|---------------------|:------:|:------:|:------:|
| 1 | 1-Year Historical Data Pipeline | R2 | 5 | 5 | ✓ |
| 2 | Multi-Timeframe Causal Alignment | R1, R2 | 5 | 5 | ✓ |
| 3 | 4h Macro Regime Classifier | R1 | 5 | 5 | ✓ |
| 4 | 15m Dynamic Multi-Setup Engine | R1 | 5 | 5 | ✓ |
| 5 | Funding & Sentiment Filter | R1 | 5 | 5 | ✓ |
| 6 | PPO Conviction Arbiter | R1 | 5 | 5 | ✓ |
| 7 | Multi-Target Risk & Trailing Exit | R1 | 5 | 5 | ✓ |
| 8 | Sortino & Duration Metrics | R3 | 5 | 5 | ✓ |
| 9 | Standalone HTML Dashboard | R3 | 5 | 5 | ✓ |
| 10 | 1-Year High-Sample Backtest Runner | R2 | 5 | 5 | ✓ |
| 11 | Performance & Trade Frequency (>=2,000 trades) | Acceptance Criteria | 5 | 5 | ✓ |
| 12 | Paper-Only Boundary & Double-Entry Accounting | Safety & Compliance | 5 | 5 | ✓ |

## Test Architecture
- Test Runner: `D:\v\Scripts\python.exe -m pytest tests/`
- Directory Layout:
  - `tests/test_universe_loader.py` (Unit tests M1)
  - `tests/test_synthesized_strategy.py` (Unit tests M2)
  - `tests/test_html_dashboard.py` (Unit tests M3)
  - `tests/test_e2e_synthesized_backtest.py` (E2E acceptance tests M4)

## Real-World Application Scenarios (Tier 4)
| # | Scenario | Features Exercised | Target |
|---|----------|--------------------|--------|
| 1 | Full 1-Year Multi-Pair Backtest on 15m/4h | All features 1–12 | >= 2,000 completed trades, zero lookahead, positive return/solid win rate |
| 2 | High-Volatility Stress Test (Flash crash / rally) | Regime switch, stops, liquidation | Stop loss strictly respected, no margin call or negative balance |
| 3 | Extended Ranging / Chop Regime | SMC sweeps, breakeven exits | Capital preservation, false breakout exploitation |
| 4 | Accounting Invariant Reconciliation | Cashflow, fees, funding, PnL | $10^{-4}$ tolerance holds across all trades |
| 5 | Standalone HTML Dashboard Visual Audit | File structure, Chart.js payload | HTML file self-contained, opens cleanly in any browser |

## Coverage Thresholds
- Tier 1: >=5 test cases per feature
- Tier 2: Boundary & corner cases (zero volume, NaN funding, slippage extremes, single-bar reversals)
- Tier 3: Cross-feature interactions (Regime change while in position, partial TP + trailing stop)
- Tier 4: Real-world 1-year backtest execution verification
