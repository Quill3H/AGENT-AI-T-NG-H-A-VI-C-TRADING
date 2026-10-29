## 2026-10-29T04:40:51Z
You are teamwork_explorer_m1_1.
Your working directory is: d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\.agents\teamwork\teamwork_explorer_m1_1
Original request file to read: d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\.agents\teamwork\ORIGINAL_REQUEST.md
Project plan file: d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\.agents\teamwork\orchestrator_1\PROJECT.md
Survey 1 handoff: d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\.agents\teamwork\teamwork_explorer_survey_1\handoff.md
Codebase working directory: d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\crypto-paper-agent
Python environment: D:\v\Scripts\python.exe

TASK:
Produce the precise implementation specification and technical blueprint for `src/strategies/synthesized.py` and unit tests in `tests/test_synthesized_strategy.py`:
1. Design the `SynthesizedStrategy(BaseStrategy)` architecture:
   - Inherits `BaseStrategy` (`src/strategies/base.py`).
   - Inputs: 15m candle close + 15m history, 4h candle close + 4h history, `broker_state`.
   - Multi-Regime classification: 4h EMA 50/200, 4h ADX or volatility regime (Trend Bull, Trend Bear, Chop/Ranging).
   - Multi-Setup routing:
     * In Trend Bull/Bear: 15m Micro-Trend EMA pullbacks (EMA 20/50 retest) and 15m Breakout-Retest (20-bar high/low).
     * In Chop/Ranging: 15m SMC Liquidity Sweeps (hunting swing highs/lows + MSS + FVG).
   - Funding Rate sentiment filter: avoid longing when funding rate is exorbitantly positive; avoid shorting when deeply negative.
   - PPO Conviction Arbiter: heuristic conviction scoring or model weight gating (0: VETO, 1: 1% risk, 2: 2% risk, 3: 5% risk).
   - Multi-target exit logic: 1.5R partial TP (move SL to breakeven), 3.0R TP target, and EMA trailing runner for remaining balance.
   - Causal integrity: strictly causal, zero future reference, stop loss set at closed swing extreme.
2. Outline exact class signatures, methods, configuration defaults, and edge cases.
3. Design the unit test suite (`tests/test_synthesized_strategy.py`) to verify all states, regime switches, order requests, and paper-only compliance.
4. Write your complete blueprint report to:
   d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\.agents\teamwork\teamwork_explorer_m1_1\handoff.md
5. Update progress.md regularly with timestamps. When complete, send a message to orchestrator with summary.
