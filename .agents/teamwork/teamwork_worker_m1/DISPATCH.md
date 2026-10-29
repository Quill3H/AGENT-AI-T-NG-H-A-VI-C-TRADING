## 2026-10-29T04:50:00Z
Sender: 2c3b8d46-0ade-47e9-ba40-a2ceba159ff5
Priority: MESSAGE_PRIORITY_HIGH

You are teamwork_worker_m1.
Your working directory is: d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\.agents\teamwork\teamwork_worker_m1
Original request file to read: d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\.agents\teamwork\ORIGINAL_REQUEST.md
Project plan file: d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\.agents\teamwork\orchestrator_1\PROJECT.md
Codebase working directory: d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\crypto-paper-agent
Python environment: D:\v\Scripts\python.exe

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

BLUEPRINT SPECIFICATIONS TO IMPLEMENT:
Read the 3 detailed handoff reports created by the M1 Explorers:
1. Strategy Blueprint: d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\.agents\teamwork\teamwork_explorer_m1_1\handoff.md
2. Data Pipeline Blueprint: d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\.agents\teamwork\teamwork_explorer_m1_2\handoff.md
3. Dashboard & Metrics Blueprint: d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\.agents\teamwork\teamwork_explorer_m1_3\handoff.md

EXCLUSIVE FILE OWNERSHIP:
You own and will implement the following files in `crypto-paper-agent`:
- `src/data_layer/universe_loader.py`
- `tests/test_universe_loader.py`
- `src/strategies/synthesized.py`
- `config/strategies/synthesized.yaml`
- `tests/test_synthesized_strategy.py`
- `src/report/metrics.py` (add Sortino ratio, trade duration statistics, long/short Net PnL and Profit Factor)
- `src/report/html_dashboard.py` (standalone HTML dashboard generator)
- `src/report/generator.py` (integrate dashboard.html as artifact #7 with 100% backward compatibility)
- `tests/test_html_dashboard.py`

IMPLEMENTATION INSTRUCTIONS:
1. Implement `UniverseDataLoader` in `src/data_layer/universe_loader.py` and unit tests in `tests/test_universe_loader.py` per Blueprint 2:
   - 10 liquid perpetual pairs (BTC, ETH, SOL, BNB, XRP, DOGE, ADA, AVAX, LINK, SUI).
   - 15m and 4h data loading with Parquet caching in `data/raw/binance/<symbol>/<timeframe>.parquet`.
   - Public Binance API fetcher + deterministic multi-asset synthetic fallback for 100% offline testing.
   - Causal multi-timeframe alignment ensuring 4h bars are not visible before their close time.
2. Implement `SynthesizedStrategy` in `src/strategies/synthesized.py`, config in `config/strategies/synthesized.yaml`, and unit tests in `tests/test_synthesized_strategy.py` per Blueprint 1:
   - Inherits `BaseStrategy`.
   - Multi-Regime classification: 4h Trend Bull, Trend Bear, Chop/Ranging.
   - Multi-Setup routing on 15m candles: Trend pullbacks, Breakout-retest, SMC Liquidity Sweeps with MSS.
   - Funding rate sentiment filter and PPO conviction arbiter.
   - Multi-target exit: 1.5R partial TP (move SL to BE), 3.0R TP, and EMA trailing runner for remaining balance.
3. Implement `HTMLDashboardGenerator` in `src/report/html_dashboard.py`, enhance `src/report/metrics.py`, integrate into `src/report/generator.py`, and create unit tests in `tests/test_html_dashboard.py` per Blueprint 3:
   - Standalone `dashboard.html` with modern dark institutional styling, Chart.js charts, native vector SVG fallback for offline machines, scorecard, filterable trade table, and embedded JSON data.
   - Metrics additions: Sortino ratio, duration stats (hours/bars for wins, losses, all), long/short split.
   - Backward compatibility: preserve existing 6 artifact keys and verify existing tests pass.
4. Execute tests in `crypto-paper-agent` using `D:\v\Scripts\python.exe`:
   `D:\v\Scripts\python.exe -m pytest tests/test_universe_loader.py tests/test_synthesized_strategy.py tests/test_html_dashboard.py tests/test_report_generator.py tests/test_report_metrics.py -v`
   Ensure ALL tests pass with 0 failures.
5. Write your handoff report to:
   d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\.agents\teamwork\teamwork_worker_m1\handoff.md
   Documenting: changes made, files touched, test execution commands, outputs, and verification results.
6. Update progress.md regularly with timestamps. When complete, send a message to orchestrator confirming completion.
