## 2026-10-29T04:41:01Z
You are teamwork_explorer_m1_2.
Your working directory is: d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\.agents\teamwork\teamwork_explorer_m1_2
Original request file to read: d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\.agents\teamwork\ORIGINAL_REQUEST.md
Project plan file: d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\.agents\teamwork\orchestrator_1\PROJECT.md
Survey 2 handoff: d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\.agents\teamwork\teamwork_explorer_survey_2\handoff.md
Codebase working directory: d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\crypto-paper-agent
Python environment: D:\v\Scripts\python.exe

TASK:
Produce the precise implementation specification and technical blueprint for `src/data_layer/universe_loader.py` and unit tests in `tests/test_universe_loader.py`:
1. Design the `UniverseDataLoader` architecture:
   - Target universe: 10 liquid perpetual pairs (BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT, XRPUSDT, DOGEUSDT, ADAUSDT, AVAXUSDT, LINKUSDT, SUIUSDT).
   - Timeframes: 15m (execution time series, 35,040 bars/year) and 4h (macro regime time series, 2,190 bars/year).
   - Historical window: 1 full continuous calendar year (e.g. 2024-10-01 to 2025-10-01 or 2025-01-01 to 2026-01-01).
   - Storage format: Lightweight Parquet files under `data/raw/binance/<symbol>/<timeframe>.parquet`.
   - Ingestion methods:
     * Fetch from public Binance REST API (`/fapi/v1/klines`) and/or `data.binance.vision` without API keys.
     * Include deterministic fallback generator for offline testing/environments that creates realistic, multi-timeframe synthetic OHLCV with correlated market dynamics, ensuring tests always pass offline without external network dependency.
   - Data validation & alignment:
     * Enforce strict timestamp monotonicity, no duplicate timestamps, positive volume, high >= low, high >= max(open, close), low <= min(open, close).
     * Multi-timeframe causal alignment: ensures 4h bars are only available at or after their close timestamp to prevent any lookahead bias in 15m loops.
2. Outline exact class signatures, methods, configuration parameters, and error handling.
3. Design unit test suite (`tests/test_universe_loader.py`) verifying schema, caching, fallback generation, and alignment.
4. Write your complete blueprint report to:
   d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\.agents\teamwork\teamwork_explorer_m1_2\handoff.md
5. Update progress.md regularly with timestamps. When complete, send a message to orchestrator with summary.
