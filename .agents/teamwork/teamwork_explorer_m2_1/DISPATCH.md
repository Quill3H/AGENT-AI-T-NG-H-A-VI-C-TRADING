## 2026-10-29T06:29:31Z

From: 2c3b8d46-0ade-47e9-ba40-a2ceba159ff5
Priority: MESSAGE_PRIORITY_HIGH

Task:
Produce the technical blueprint and architecture for `scripts/run_synthesized_backtest.py`:
1. Design the standalone execution runner:
   - CLI flags: `--symbols` (defaults to 10 liquid pairs: BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT, XRPUSDT, DOGEUSDT, ADAUSDT, AVAXUSDT, LINKUSDT, SUIUSDT), `--initial-capital` (e.g. 100,000 USDT), `--start-date`, `--end-date` (1 full continuous year), `--output-dir` (defaults to `reports/synthesized_backtest_1y`), `--allow-network` (flag to fetch public klines or use deterministic synthetic generator).
   - Data loading: Use `UniverseDataLoader` to obtain synchronized 15m and 4h series for each pair.
   - Execution loop: Step causally bar-by-bar across 15m execution candles; for each symbol, pass 15m candle close and the latest closed 4h candle to `SynthesizedStrategy.on_candle_close`.
   - PaperBroker execution: isolated margin, taker fee 0.05%, adverse slippage 0.03%, funding settlement every 8h.
   - Reporting: Invoke `ReportGenerator.generate_all` to emit all 7 artifacts including `dashboard.html`.
2. Ensure performance optimization: Must complete 1-year multi-pair backtest efficiently without memory bloat.
3. Write your blueprint report to:
   `d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\.agents\teamwork\teamwork_explorer_m2_1\handoff.md`
4. Update progress.md regularly with timestamps. When complete, send a message to orchestrator with summary.
