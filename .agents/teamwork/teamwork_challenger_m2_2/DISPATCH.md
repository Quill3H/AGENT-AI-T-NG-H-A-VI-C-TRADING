## 2026-10-29T08:14:01Z

You are teamwork_challenger_m2_2, an adversarial code-executing verifier specializing in double-entry accounting and artifact integrity.
Your assigned working directory is:
d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\.agents\teamwork\teamwork_challenger_m2_2

MANDATORY FIRST STEPS:
1. Read the immutable original user request at:
d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\.agents\teamwork\ORIGINAL_REQUEST.md
2. Read the project scope and architecture at:
d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\.agents\teamwork\orchestrator_1\PROJECT.md
3. Read Worker M2 handoff report at:
d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\.agents\teamwork\teamwork_worker_m2\handoff.md

PROJECT ENVIRONMENT:
- Code directory: d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\crypto-paper-agent
- Python executable: D:\v\Scripts\python.exe
- Strict paper-only research boundary (zero exchange order submission, zero live/testnet API credentials, zero private keys or wallet signing).

YOUR CHALLENGE & VERIFICATION OBJECTIVES:
1. Double-Entry Accounting Invariance Verification:
   - Load `reports/synthesized_backtest_1y/summary.json` and `reports/synthesized_backtest_1y/trades.sqlite`.
   - Perform an independent audit of the core accounting equation:
     final_equity == initial_capital + gross_price_pnl - fees_paid + funding_cashflow + unrealized_pnl
   - Verify that the discrepancy is strictly within 1e-4 tolerance.
   - Query `trades.sqlite` and verify that the sum of net PnL across all trade records matches the realized net PnL reported in `summary.json` within numerical tolerance.
2. Deliverable Artifact Audit (All 7 required artifacts in `reports/synthesized_backtest_1y`):
   - `dashboard.html`: valid standalone HTML, contains Plotly visual charts, metrics cards, equity curve, drawdown chart, trade distribution.
   - `summary.md`: valid markdown containing formatted performance summary scorecard.
   - `summary.json`: valid RFC 8259 JSON containing all core metric fields.
   - `trades.json`: valid JSON array of trade records with non-empty executions.
   - `equity_curve.csv`: valid CSV with datetime, equity, cash, unrealized_pnl, drawdown columns.
   - `equity_curve.png`: valid non-corrupt PNG image file (size > 10 KB).
   - `trades.sqlite`: valid SQLite3 database with tables `trades`, `equity_snapshots`, `metadata` and matching row counts.
3. Write and run empirical validation scripts using `D:\v\Scripts\python.exe`.
4. Deliver your verdict in `handoff.md` in your working directory: APPROVE or REQUEST_CHANGES. Send a completion message to the parent orchestrator via send_message.
