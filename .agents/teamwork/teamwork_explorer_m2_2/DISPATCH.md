## 2026-10-29T06:29:42Z
Sender: 2c3b8d46-0ade-47e9-ba40-a2ceba159ff5
Priority: MESSAGE_PRIORITY_HIGH

You are teamwork_explorer_m2_2.
Your working directory is: d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\.agents\teamwork\teamwork_explorer_m2_2
Original request file to read: d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\.agents\teamwork\ORIGINAL_REQUEST.md
Project plan file: d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\.agents\teamwork\orchestrator_1\PROJECT.md
Codebase working directory: d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\crypto-paper-agent
Python environment: D:\v\Scripts\python.exe

TASK:
Produce the quantitative optimization blueprint to ensure >= 2,000 completed trades and positive net return / solid win rate over the 1-year historical window:
1. Trade frequency analysis:
   - On 15m candles over 1 year (35,040 bars per symbol), determine optimal setup triggering thresholds across the 10 liquid perpetual pairs (BTC, ETH, SOL, BNB, XRP, DOGE, ADA, AVAX, LINK, SUI).
   - Target: ~200 to 250 completed trades per pair per year, easily totaling 2,000 to 2,500 completed trades across the universe.
   - Balance setup sensitivity so setups trigger reliably without deteriorating signal quality.
2. Risk & Capital Allocation:
   - Position sizing: 1.0% to 1.5% equity risk per trade, max leverage 5x to 10x, isolated margin.
   - Partial exit scaling (1.5R 50%, 3.0R 25%, trailing runner 25%) ensuring high win rate and rapid break-even risk elimination.
   - Fee and slippage absorption: Ensure average trade win exceeds combined 0.16% round-trip fee + slippage drag.
3. Configuration file recommendations:
   - Provide exact parameter values for `config/strategies/synthesized.yaml` or runner CLI defaults.
4. Write your blueprint report to:
   `d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\.agents\teamwork\teamwork_explorer_m2_2\handoff.md`
5. Update progress.md regularly with timestamps. When complete, send a message to orchestrator with summary.
