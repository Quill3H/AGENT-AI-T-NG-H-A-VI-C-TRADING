Exploratory research to synthesize an optimal trading strategy from existing repository solutions (TrendFollowing, BreakoutRetest, SMCLiquiditySweep, FundingArbitrage, PPO RL) targeting positive returns or a solid win rate, and run a 1-year backtest on 15m/4h timeframes with at least 2,000 trades accompanied by visual data under paper-only constraints.

Working directory: d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\crypto-paper-agent
Integrity mode: development

## Requirements

### R1. Research and Synthesize Existing Strategies
Analyze existing strategies and models in the repository (TrendFollowingStrategy, BreakoutRetestStrategy, SMCLiquiditySweepStrategy, FundingArbitrageSimulator, and PPO Reinforcement Learning). Synthesize an optimal trading approach that demonstrates positive net return or a solid win rate while strictly maintaining paper-only research boundaries (no live/testnet orders, no private keys or wallet credentials).

### R2. High-Sample 1-Year Backtest Execution
Execute a 1-year backtest yielding at least 2,000 trades on 15m/4h timeframes across major pairs (such as BTC, ETH) or liquid perpetual futures using available local or public market data.

### R3. Visual Reporting and Performance Metrics
Generate visual data and reporting for the backtest results (such as an interactive HTML dashboard or static charts accompanied by summary metrics) illustrating equity curve, drawdown, and trade statistics.

## Acceptance Criteria

### Execution & Sample Size
- [ ] The backtest executes across a 1-year historical window on 15m/4h timeframes and logs at least 2,000 completed trades.
- [ ] Backtest script runs end-to-end without unhandled errors using the project environment (`D:\v\Scripts\python.exe`).

### Performance
- [ ] Backtested strategy produces a positive net return or a favorable win rate aligned with its risk/reward structure.

### Safety & Compliance
- [ ] The synthesized solution and backtest pipeline remain strictly paper-only (zero exchange order submission, zero live/testnet API secret creation, zero wallet signing).

### Visual Deliverables
- [ ] Visual performance outputs (equity curve, drawdown profile, trade distribution metrics) are generated and accessible for review.
