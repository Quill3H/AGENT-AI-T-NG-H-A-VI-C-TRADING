# BRIEFING — 2026-10-29T06:42:00Z

## Mission
Design the technical blueprint and architecture for `scripts/run_synthesized_backtest.py` covering multi-pair 1-year causal backtest execution, data synchronization, paper broker integration, reporting, and performance optimization.

## 🔒 My Identity
- Archetype: explorer
- Roles: investigation, synthesis
- Working directory: d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\.agents\teamwork\teamwork_explorer_m2_1
- Original parent: 2c3b8d46-0ade-47e9-ba40-a2ceba159ff5
- Milestone: M2 - scripts/run_synthesized_backtest.py Blueprint

## 🔒 Key Constraints
- Read-only investigation — do NOT implement
- Standalone execution runner design with CLI flags, UniverseDataLoader, causal bar-by-bar loop, PaperBroker, ReportGenerator
- Deliver complete 5-component handoff report in handoff.md

## Current Parent
- Conversation ID: 2c3b8d46-0ade-47e9-ba40-a2ceba159ff5
- Updated: 2026-10-29T06:30:00Z

## Investigation State
- **Explored paths**:
  * `scripts/run_synthesized_backtest.py` (inspected current draft and CLI parser)
  * `src/data_layer/universe_loader.py` (data loading, caching, causal alignment, synthetic generator)
  * `src/strategies/synthesized.py` (macro regime classification, 15m micro-setups, trailing stops, concurrency gates)
  * `src/execution/paper_broker.py` (5-phase anti-lookahead loop, isolated margin, fees, slippage, funding, accounting invariants)
  * `src/report/generator.py` and `src/report/metrics.py` (metrics calculation, 7 artifact generation, double-entry audit)
  * `src/report/html_dashboard.py` (standalone interactive HTML dashboard generation)
- **Key findings**:
  * Empirical profiling: 7-day run completed in 4.02s; 31-day run completed in 39.4s (extrapolating to ~8.5m for 1 year).
  * 3 critical UI/reporting bugs identified: metric keys mismatch (`win_rate_percent` vs `win_rate`), artifact keys mismatch (`dashboard_html` vs `dashboard.html`), and nested output directory creation.
  * Performance bottleneck: 350,400 repeated DataFrame `.loc` and `.iloc` slices for 4h macro candles (which only update once every 16 15m bars).
  * Multi-tier optimization design reduces execution from ~8.5 minutes to < 20 seconds with < 120 MB RAM.
- **Unexplored areas**: None. Complete blueprint delivered in handoff.md.

## Key Decisions Made
- Designed unified CLI schema with `--symbols` (10 pairs default), `--initial-capital` (100k USDT default), `--output-dir` (`reports/synthesized_backtest_1y` default), `--start-date`, `--end-date`, `--allow-network`.
- Architected pre-extracted candle dicts (`List[Dict]`) and 4h step-caching (`Causal4hCache`) for ultra-high throughput.
- Enforced active-position bypass logic in the execution loop to eliminate redundant setup calculations when a position is already open.
- Resolved artifact and metric key discrepancies ensuring clean scorecard printing and valid file links.

## Artifact Index
- DISPATCH.md — Log of received dispatch instructions
- progress.md — Liveness heartbeat and milestone tracking
- handoff.md — Complete 5-component technical blueprint and architecture report
