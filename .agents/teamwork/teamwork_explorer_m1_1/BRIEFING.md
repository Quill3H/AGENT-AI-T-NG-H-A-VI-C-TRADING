# BRIEFING — 2026-10-29T04:49:00Z

## Mission
Produce the precise implementation specification and technical blueprint for `src/strategies/synthesized.py` and unit tests in `tests/test_synthesized_strategy.py`.

## 🔒 My Identity
- Archetype: explorer
- Roles: investigator, synthesizer
- Working directory: d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\.agents\teamwork\teamwork_explorer_m1_1
- Original parent: 2c3b8d46-0ade-47e9-ba40-a2ceba159ff5
- Milestone: M1 — Synthesized Strategy Specification & Blueprint

## 🔒 Key Constraints
- Read-only investigation — do NOT implement
- Strictly causal, zero future reference, paper-only compliance
- Adhere to `BaseStrategy` (`src/strategies/base_strategy.py`) interface and event-driven paper execution
- Multi-regime routing: 4h EMA 50/200 + ADX/volatility, 15m Trend pullbacks / Breakout retests / Chop SMC sweeps
- Funding rate sentiment filter, PPO conviction arbiter (gating 0/1/2/3 risk levels), multi-target exit logic (1.5R partial + breakeven SL, 3.0R TP, trailing EMA runner)

## Current Parent
- Conversation ID: 2c3b8d46-0ade-47e9-ba40-a2ceba159ff5
- Updated: 2026-10-29T04:49:00Z

## Investigation State
- **Explored paths**:
  - `src/strategies/base_strategy.py`, `trend_following.py`, `breakout_retest.py`, `smc_liquidity_sweep.py`, `funding_arbitrage.py`
  - `src/execution/order_models.py`, `paper_broker.py`
  - `src/features/indicators.py`, `smc_features.py`
  - `src/backtest/engine.py`
  - `tests/test_trend_following_strategy.py`, `test_breakout_retest.py`
- **Key findings**:
  - Established complete class signatures and methods for `SynthesizedStrategy`.
  - Designed Wilder ADX calculation and 4h Macro Regime Classifier.
  - Designed 3 micro-setup engines on 15m execution bars (Pullback, Breakout-Retest, SMC Sweep).
  - Formulated Funding Sentiment Filter and PPO Conviction Arbiter with 4 risk tiers.
  - Formulated Multi-target partial exit (1.5R / 3.0R / EMA runner) and breakeven stop loss logic.
  - Designed 17-point unit test matrix for `tests/test_synthesized_strategy.py`.
- **Unexplored areas**: None for M1 specification scope.

## Key Decisions Made
- Architecture decouples 4h macro regime classification from 15m execution setups to achieve >=2,000 trades/year with positive expectancy.
- Handled both 3-arg and 5-arg signatures in `on_candle_close` to ensure backward compatibility.
- Stop losses strictly set at causal swing extremes and trailing stops enforce tightening-only.

## Artifact Index
- `DISPATCH.md` — Inbound message log
- `BRIEFING.md` — Situational awareness and persistent memory
- `progress.md` — Heartbeat and activity progress
- `handoff.md` — Complete technical blueprint and test suite specification report
