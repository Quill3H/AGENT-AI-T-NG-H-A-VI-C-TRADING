## 2026-10-29T04:41:12Z
You are teamwork_explorer_m1_3.
Your working directory is: d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\.agents\teamwork\teamwork_explorer_m1_3
Original request file to read: d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\.agents\teamwork\ORIGINAL_REQUEST.md
Project plan file: d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\.agents\teamwork\orchestrator_1\PROJECT.md
Survey 3 handoff: d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\.agents\teamwork\teamwork_explorer_survey_3\handoff.md
Codebase working directory: d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\crypto-paper-agent
Python environment: D:\v\Scripts\python.exe

TASK:
Produce the precise implementation specification and technical blueprint for `src/report/html_dashboard.py`, additions to `src/report/metrics.py`, and unit tests in `tests/test_html_dashboard.py`:
1. Design `HTMLDashboardGenerator` (`src/report/html_dashboard.py`):
   - Generates standalone, self-contained `reports/<run_id>/dashboard.html` without requiring external npm/Vite builds or active backend servers (opens directly by double-clicking in browser).
   - Embedded responsive dark financial UI theme (Tailwind-like modern CSS styling).
   - Interactive charts using lightweight embedded Chart.js (or SVG fallbacks):
     * Interactive Equity Curve with High Watermark & initial balance line.
     * Underwater Drawdown percentage area chart.
     * Monthly & weekly return bars.
     * PnL ($) and Realized R-multiple distribution histograms.
     * Scorecard displaying: Total Net Return %, Win Rate %, Profit Factor, Max Drawdown %, Daily Sharpe Ratio, Sortino Ratio, Total Trades (highlighting >=2,000 threshold), Long/Short Win Rates.
     * Filterable, sortable Trade Log table with trade ID, symbol, direction, entry/exit time, entry/exit price, size, PnL, R-multiple, and exit reason.
   - Embeds complete RFC 8259 raw JSON dataset in `<script id="backtest-data" type="application/json">` for transparency and auditability.
2. Design additions to `src/report/metrics.py`:
   - `calculate_sortino_ratio`: Downside deviation with target return = 0 or risk-free rate, annualized with $\sqrt{365}$.
   - Trade duration statistics: average, median, and max duration in hours/bars for winning trades and losing trades.
   - Long vs Short breakdown: Long Net PnL, Short Net PnL, Long Profit Factor, Short Profit Factor.
3. Design integration into `ReportGenerator.generate_all`:
   - Automatically generates `dashboard.html` as the 7th standard artifact in `reports/<run_id>/`.
   - Backward compatibility: ensures existing 6 artifact keys and all 18 existing report tests in `tests/test_report_generator.py` pass without regression.
4. Design unit tests (`tests/test_html_dashboard.py`):
   - Verifies dashboard file creation, validity, HTML tags, embedded JSON parsing, and chart element presence.
5. Write your complete blueprint report to:
   d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\.agents\teamwork\teamwork_explorer_m1_3\handoff.md
6. Update progress.md regularly with timestamps. When complete, send a message to orchestrator with summary.
