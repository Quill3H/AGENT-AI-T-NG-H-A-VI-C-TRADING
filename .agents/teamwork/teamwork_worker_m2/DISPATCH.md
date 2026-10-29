## 2026-10-29T06:46:32Z
You are teamwork_worker_m2.
Your working directory is: d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\.agents\teamwork\teamwork_worker_m2
Original request file to read: d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\.agents\teamwork\ORIGINAL_REQUEST.md
Project plan file: d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\.agents\teamwork\orchestrator_1\PROJECT.md
Codebase working directory: d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\crypto-paper-agent
Python environment: D:\v\Scripts\python.exe

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

BLUEPRINT SPECIFICATIONS TO IMPLEMENT:
Read the 3 detailed handoff reports created by the M2 Explorers:
1. Runner Architecture Blueprint: d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\.agents\teamwork\teamwork_explorer_m2_1\handoff.md
2. Quantitative Optimization Blueprint: d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\.agents\teamwork\teamwork_explorer_m2_2\handoff.md
3. E2E Acceptance Test Blueprint: d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\.agents\teamwork\teamwork_explorer_m2_3\handoff.md

EXCLUSIVE FILE OWNERSHIP:
You own and will implement the following files in `crypto-paper-agent`:
- `src/risk/invariant_checks.py` (add leverage brackets for all 10 liquid perpetual symbols)
- `config/strategies/synthesized.yaml` (configure 10 symbols, leverage brackets, and optimized parameters)
- `src/strategies/synthesized.py` (implement ATR stop-loss floor and setup tuning)
- `scripts/run_synthesized_backtest.py` (optimized 1-year backtest runner with <25s runtime and corrected keys)
- `tests/test_e2e_synthesized_backtest.py` (E2E acceptance test suite covering AC 1 to 5)

TASKS:
1. Update `src/risk/invariant_checks.py` and `config/strategies/synthesized.yaml`:
   - Support `leverage_brackets` for all 10 liquid perpetual symbols (`BTCUSDT`, `ETHUSDT`, `SOLUSDT`, `BNBUSDT`, `XRPUSDT`, `DOGEUSDT`, `ADAUSDT`, `AVAXUSDT`, `LINKUSDT`, `SUIUSDT`) to eliminate the 30,130 `EXECUTION_REJECT_SIZING_ERROR` rejections!
2. In `src/strategies/synthesized.py`:
   - Add the ATR-based stop distance floor: `stop_distance >= max(delta_structure, 1.2 * atr, 0.008 * price)` to eliminate margin rejections and fee drag.
   - Tune setup parameters per Blueprint 2 so that the 10-pair universe generates ~2,000 to 2,500 completed trades across 1 year with positive mathematical expectancy and solid win rate.
3. In `scripts/run_synthesized_backtest.py`:
   - Apply Blueprint 1 optimizations (pre-extracted candle dicts, 4h step-caching) so the 1-year 10-pair backtest runs in <30 seconds.
   - Correct dictionary key lookups (`win_rate`, `sharpe_ratio`, `total_net_pnl`, `max_drawdown_pct`, `dashboard.html`, `summary.md`, `trades.sqlite`).
4. Implement `tests/test_e2e_synthesized_backtest.py` per Blueprint 3:
   - Module-scoped fixture running the 1-year backtest.
   - Assert all 5 Acceptance Criteria:
     * AC 1: Logs >= 2,000 completed trades across 1-year historical window on 15m/4h.
     * AC 2: Runs end-to-end without unhandled errors via `D:\v\Scripts\python.exe`.
     * AC 3: Positive net return or favorable win rate / profit factor.
     * AC 4: Strictly paper-only (zero exchange calls, zero secrets).
     * AC 5: Visual deliverables exist and are valid (`dashboard.html`, `summary.md`, `equity_curve.png`, `summary.json`, `trades.json`, `equity_curve.csv`, `trades.sqlite`).
     * Invariant: Double-entry accounting reconciliation invariance ($10^{-4}$ tolerance).
5. Run the backtest script and test suite using `D:\v\Scripts\python.exe`:
   `D:\v\Scripts\python.exe scripts/run_synthesized_backtest.py`
   `D:\v\Scripts\python.exe -m pytest tests/test_e2e_synthesized_backtest.py -v`
   Ensure the backtest logs >= 2,000 trades, achieves positive return/favorable win rate, and the E2E tests pass.
6. Write your handoff report to:
   `d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\.agents\teamwork\teamwork_worker_m2\handoff.md`
7. Update progress.md regularly with timestamps. When complete, send a message to orchestrator.
