# Project: Optimal Synthesized Trading Strategy & 1-Year Backtest (>=2,000 Trades)

## Architecture
- **Layer 1: Data & Universe Pipeline (`src/data_layer/`)**:
  - Ingests 1-year historical OHLCV data on 15m and 4h timeframes for liquid perpetual futures (BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT, XRPUSDT, DOGEUSDT, ADAUSDT, AVAXUSDT, LINKUSDT, SUIUSDT) via public REST API / data.binance.vision / ccxt.
  - Caches to lightweight local Parquet files in `data/raw/binance/`.
  - Zero API keys or private credentials (100% public, paper-only).

- **Layer 2: Synthesized Multi-Regime Strategy (`src/strategies/synthesized.py`)**:
  - **Macro 4h Regime Engine**: Classifies market into Bullish Trend, Bearish Trend, or Ranging/Chop using 4h EMAs, ADX, and volatility.
  - **Micro 15m Execution & Multi-Setup Engine**:
    - Trend-continuation (EMA pullbacks + breakout-retest) during trending regimes.
    - SMC Liquidity Sweeps (liquidity grab + MSS + FVG entry) during ranging/chop regimes.
    - Funding rate / basis sentiment filter derived from `FundingArbitrageSimulator`.
    - PPO RL Conviction Arbiter (`src/research/rl_env.py` meta-controller) for risk scaling / signal filtering.
  - **Risk & Execution Rulebook**:
    - 1-2% account risk per trade.
    - Multi-target take-profit (1.5R partial 50%, 3.0R target 25%, trailing EMA runner 25%).
    - Swing low/high protective stops with strict stop-loss geometry validation (`stop < c` for long, `stop > c` for short).
    - Strict maximum 1 concurrent position per symbol.

- **Layer 3: Backtest Engine & Paper Broker (`src/backtest/engine.py`, `src/execution/paper_broker.py`)**:
  - Event-driven 5-phase causal loop driven by 15m candles with 4h macro alignment.
  - Realistic taker fee (0.05%), adverse slippage (0.03%), isolated margin, and funding cashflow reconciliation.
  - Double-entry accounting reconciliation ($10^{-4}$ tolerance).

- **Layer 4: Reporting & Interactive Visualization (`src/report/`)**:
  - Enhanced metrics in `src/report/metrics.py`: Sortino ratio, trade duration stats, long/short breakdown.
  - Standalone HTML Dashboard Generator in `src/report/html_dashboard.py` outputting `dashboard.html` with interactive Chart.js/SVG charts:
    - Equity curve with High Watermark
    - Underwater Drawdown profile
    - PnL and R-multiple distribution histograms
    - Key metrics summary scorecard
    - Filterable trade log table
  - Standard artifacts: `summary.json`, `summary.md`, `trades.json`, `equity_curve.csv`, `equity_curve.png`, `trades.sqlite`, and `dashboard.html`.

---

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | 1-Year 15m/4h Historical Data Downloader/Loader | Public Kline downloader & Parquet cache across 10 liquid perpetual pairs covering 1 full year without API keys | M1 | Survey 2 |
| 2 | Data Integrity & Alignment Verification | Multi-timeframe bar alignment and missing-bar validation across 15m execution bars and 4h macro bars | M1 | Survey 2 |
| 3 | 4h Macro Regime Classifier | Classifies trend/chop market regime using 4h EMAs, ADX, and volatility | M1 | Survey 1 |
| 4 | 15m Multi-Setup Synthesis Engine | Blends Trend Following pullbacks, Breakout-Retest, and SMC Liquidity Sweeps routed by market regime | M1 | Survey 1 |
| 5 | Funding & Basis Sentiment Filter | Incorporates funding rate sentiment from FundingArbitrageSimulator to avoid counter-trend basis risk | M1 | Survey 1 |
| 6 | PPO RL Conviction Arbiter | Meta-controller evaluating setup conviction to scale risk or veto low-probability setups | M1 | Survey 1 |
| 7 | Multi-Target Risk & Trailing Exit System | Implements 1.5R partial TP (move SL to BE), 3.0R take-profit, and EMA trailing runner | M1 | Survey 1 |
| 8 | Sortino Ratio & Trade Duration Metrics | Enhances `src/report/metrics.py` with Sortino ratio, duration stats, and long/short PnL split | M1 | Survey 3 |
| 9 | Standalone Interactive HTML Dashboard | Generates self-contained `dashboard.html` with responsive charts and metrics scorecard | M1 | Survey 3 |
| 10 | 1-Year High-Sample Backtest Runner | End-to-end backtest CLI executing 1-year backtest yielding >=2,000 trades on 15m/4h | M2 | Survey 2 |
| 11 | Performance & Trade Frequency Gate | Verifies >=2,000 completed trades, positive net return, and solid win rate / profit factor | M2 | Original Request |
| 12 | Paper-Only Boundary & Accounting Audit | Verifies zero live/testnet credentials/orders and strict $10^{-4}$ accounting reconciliation | M2 | Original Request |

---

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Core System Implementation (Data Pipeline, Synthesized Strategy, Enhanced Metrics & HTML Dashboard) | `src/data_layer/universe_loader.py`, `src/strategies/synthesized.py`, `src/report/html_dashboard.py`, `src/report/metrics.py` and 94 passing tests | none | DONE |
| M2 | High-Sample 1-Year Backtest Execution & E2E Validation | `scripts/run_synthesized_backtest.py`, 1-year backtest execution (>=2,000 trades), visual report generation, accounting audit | M1 | IN_PROGRESS |

---

## Interface Contracts
### `src/data_layer/` ↔ `src/strategies/`
- OHLCV dataframe indexed by UTC timestamp, columns: `open`, `high`, `low`, `close`, `volume`.
- 15m dataframe synchronized with 4h macro dataframe (anti-lookahead: 4h candle only available after 4h close).

### `src/strategies/synthesized.py` ↔ `src/execution/paper_broker.py`
- Inherits `BaseStrategy`.
- Methods:
  - `on_candle_close(candle_15m: Dict, history_15m: pd.DataFrame, candle_4h: Optional[Dict], history_4h: Optional[pd.DataFrame], broker_state: BrokerState) -> Optional[OrderRequest]`
  - `update_trailing_stop(candle_15m: Dict, broker: PaperBroker) -> None`
- Returns standard `OrderRequest`: `symbol`, `direction` (BUY/SELL), `order_type` (MARKET/LIMIT), `quantity`, `stop_loss_price`, `take_profit_price`.

### `src/report/` ↔ `src/backtest/engine.py`
- `ReportGenerator.generate_all(run_id, config, metrics, broker, custom_output_dir=None, db_path=None)` returns dictionary of 7 artifact paths including `dashboard.html`.

---

## Code Layout
- `src/data_layer/universe_loader.py` (M1: historical data loading and caching) [VERIFIED DONE]
- `src/strategies/synthesized.py` (M1: synthesized strategy engine) [VERIFIED DONE]
- `src/report/html_dashboard.py` (M1: interactive dashboard generator) [VERIFIED DONE]
- `src/report/metrics.py` (M1: Sortino, duration, long/short metrics) [VERIFIED DONE]
- `scripts/run_synthesized_backtest.py` (M2: 1-year high-sample backtest runner) [PENDING]
- `tests/test_universe_loader.py` (M1 unit tests) [PASSED]
- `tests/test_synthesized_strategy.py` (M1 unit tests) [PASSED]
- `tests/test_html_dashboard.py` (M1 unit tests) [PASSED]
- `tests/test_adversarial_m1.py` (M1 regression & adversarial probes) [PASSED]
- `tests/test_adversarial_dashboard_accounting.py` (M1 dashboard probes) [PASSED]
- `tests/test_e2e_synthesized_backtest.py` (M2 E2E acceptance tests) [PENDING]
