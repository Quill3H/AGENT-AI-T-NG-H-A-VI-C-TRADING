# Survey 3 Handoff Report: Visual Reporting, Charting Tools, and Performance Metrics

**Agent**: `teamwork_explorer_survey_3`  
**Milestone**: Survey & Architectural Analysis  
**Repository Working Directory**: `d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\crypto-paper-agent`  
**Python Environment**: `D:\v\Scripts\python.exe`  
**Date**: 2026-10-29  

---

## 1. Observation

### 1.1 Existing Reporting and Visual Dashboard Modules
1. **Report Generator Core (`src/report/generator.py`)**:
   - `ReportGenerator.generate_all(run_id, config, metrics, broker, custom_output_dir=None, db_path=None)` (lines 222–383) is the primary engine for creating backtest artifacts in `reports/<run_id>/`.
   - By default, it generates exactly **6 standard artifacts**:
     1. `summary.json` (lines 304–361): Canonical RFC 8259 JSON (`ensure_ascii=False`, `allow_nan=False`, `sort_keys=True`) recording all metrics, configuration hash (`config_hash`), code commit SHA (`code_commit_sha`), reproduction command, and accounting reconciliation.
     2. `summary.md` (lines 378–380, 504–678): Human-readable Markdown summary with 4 sections (Executive Summary, Accounting Reconciliation & Risk Audit, Trade Statistics, Disclosures & Benchmark Caveats).
     3. `trades.json` (lines 363–365): Master Spec Section 4.6 standardized trade records exported via `TradeLogger.export_trades_json`.
     4. `equity_curve.csv` (lines 368–370, 385–416): Tabular time series containing columns: `timestamp`, `equity`, `wallet_balance`, `unrealized_pnl`, `margin_used`, `available_balance`, `drawdown_usd`, `drawdown_pct`.
     5. `equity_curve.png` (lines 373–375, 417–503): Dual-panel plot rendered via `matplotlib` (using non-interactive `Agg` backend):
        - Top panel (ratio 2.5): Account Equity curve, High Watermark line (dashed green), and Initial Capital line (dotted gray).
        - Bottom panel (ratio 1.0): Underwater Drawdown percentage area fill (`#d62728` red fill to 0).
     6. `trades.sqlite` (lines 271–301): SQLite database containing 6 relational tables: `runs`, `orders`, `trades`, `funding_events`, `account_snapshots`, and `run_metrics`.
   - Accounting invariant reconciliation (`_validate_accounting`, lines 89–167) verifies:
     $$\text{final\_equity} = \text{initial\_equity} + \text{gross\_price\_pnl} - \text{fees} + \text{funding\_cashflow} + \text{unrealized\_pnl}$$
     with a strict numerical tolerance of $1\times 10^{-4}$ USDT. If this invariant fails, report generation aborts and raises an `AssertionError` before writing visible artifacts.

2. **Web Preview Console (`web-preview/`)**:
   - Directory contents: `package.json`, `vite.config.js`, `vercel.json`, `index.html`, `src/App.jsx`, `src/data/evidence.js`, `src/lib/replay.js`.
   - Technology stack: React 19.3.0 + Vite 8.3.1.
   - Origin: Timeboxed 2-hour task (`docs/planning/2026-09-25-two-hour-web-preview.md`) created for safe public preview on Vercel.
   - Behavior: Reads hardcoded static evidence from `src/data/evidence.js` (lines 1–43) and renders an SVG equity chart using synthetic offline replay (`src/lib/replay.js`). It is **not** hooked dynamically into `run_backtest.py` or `ReportGenerator`.

3. **Research Run Artifacts (`src/research/artifacts.py` & `src/research/workflow.py`)**:
   - `persist_basket` (lines 181–221): Persists funding arbitrage results to `equity_curve.csv`, `equity_curve.png` (single-panel matplotlib line plot), `summary.md`, and `research.sqlite`.
   - `persist_research_run` (lines 121–179): Writes `{name}.report.json`, `config.canonical.json`, `manifest.json`, and records run payloads to `research.sqlite`.
   - `run_comparison` (in `workflow.py`, lines 25–196): Manages walk-forward folds across strategies and saves `fold_reports.csv`, `aggregate_oos.csv`, and individual fold artifacts.

4. **Python Visualization Libraries Inspection**:
   - Executed package availability probe:
     `D:\v\Scripts\python.exe -c "for pkg in ['matplotlib', 'plotly', 'streamlit', 'pandas', 'numpy']: ..."`
   - Result:
     ```
     matplotlib 3.11.2 (INSTALLED)
     pandas 3.1.0 (INSTALLED)
     numpy 2.5.4 (INSTALLED)
     plotly: NOT installed (No module named 'plotly')
     streamlit: NOT installed (No module named 'streamlit')
     ```
   - Conclusion: Neither `plotly` nor `streamlit` is installed in the active virtual environment `D:\v\Scripts\python.exe`. Only `matplotlib` (v3.11.2) is available in Python.

---

### 1.2 Performance Metrics Calculation Audit (`src/report/metrics.py`)

| Metric Category | Current Implementation in `src/report/metrics.py` | Status & Formula / Logic |
| :--- | :--- | :--- |
| **Equity Curve** | Tracked via `broker.account_snapshots` at each execution bar; exported to `equity_curve.csv` | **Implemented**: Records timestamp, equity, wallet balance, margin used, drawdown. |
| **Peak-to-Valley Drawdown** | `calculate_max_drawdown` (lines 123–167) | **Implemented**: $\text{Peak}_t = \max(\text{initial}, \max_{s \le t} \text{Eq}_s)$, $\text{DD}_{\text{usd}} = \text{Peak} - \text{Eq}$, $\text{DD}_{\%} = \frac{\text{DD}_{\text{usd}}}{\text{Peak}} \times 100$. |
| **Win Rate / Loss Rate** | `calculate_trade_metrics` (lines 170–327) | **Implemented**: Uses completed position lifecycles (`completed_lifecycles`). $\text{WinRate} = \frac{\text{Wins}}{N}\times 100$, $\text{LossRate} = \frac{\text{Losses}}{N}\times 100$. |
| **Profit Factor** | `calculate_trade_metrics` (lines 280–284) | **Implemented**: $\frac{\sum \text{Wins}}{\sum |\text{Losses}|}$. Strict edge-case: returns `None` (JSON null) when total losses = 0. |
| **Expectancy ($ & R)** | `calculate_trade_metrics` (lines 285–291) | **Implemented**: $\text{Exp}_{\text{usd}} = \text{mean}(\text{net\_pnl})$, $\text{Exp}_R = \text{mean}(R_{\text{realized}})$. |
| **Realized RRR** | `trade_stats["average_realized_rrr"]` | **Implemented**: Average of per-trade realized R-multiples ($R = \frac{\text{net\_pnl}}{\text{initial\_risk}}$). |
| **Daily Sharpe Ratio** | `calculate_daily_sharpe` (lines 47–121) | **Implemented**: Equity resampled to 1D UTC calendar days, daily returns $r_t = \frac{E_t - E_{t-1}}{E_{t-1}}$, $\text{Sharpe} = \sqrt{365} \times \frac{\bar{r}_t - r_f/365}{\sigma(r_t, \text{ddof}=1)}$. |
| **Sortino Ratio** | *Not present anywhere in repository* | ❌ **MISSING**: Downside deviation ratio is not computed. |
| **Trade Duration** | *Not computed in trade metrics* | ❌ **MISSING**: `TradeRecord` has `entry_time` and `exit_time`, but average/median/max trade duration is not aggregated. |
| **Long / Short Breakdown** | `calculate_backtest_metrics` (lines 401–410) | ⚠️ **PARTIAL**: Computes `long_trades_count`, `short_trades_count`, `win_rate_long`, `win_rate_short`, but lacks Long Net PnL, Short Net PnL, and Long/Short Profit Factor. |
| **Calmar Ratio** | `calculate_backtest_metrics` (lines 418–421) | **Implemented**: $\frac{\text{total\_return\_pct}}{\text{max\_drawdown\_pct}}$. |
| **System Quality Number** | `calculate_trade_metrics` (lines 292–300) | **Implemented**: $\text{SQN} = \sqrt{N} \times \frac{\bar{x}}{\sigma_x}$. |
| **Streaks** | `calculate_trade_metrics` (lines 222–226, 255–269) | **Implemented**: `max_consecutive_wins`, `max_consecutive_losses`. |
| **Accounting Invariants** | Lines 446–484, `_validate_accounting` | **Implemented**: Strict double-entry reconciliation between broker ledger and report metrics. |

---

### 1.3 Testing Verification
Ran the existing test suite:
```powershell
cd 'd:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\crypto-paper-agent'
D:\v\Scripts\python.exe -m pytest tests/test_report_generator.py tests/test_report_metrics.py
```
- **Result**: `18 passed in 1.63s`.
- In `tests/test_report_generator.py` (lines 144–156), the test asserts:
  ```python
  expected_keys = [
      "summary.json",
      "summary.md",
      "trades.json",
      "equity_curve.csv",
      "equity_curve.png",
      "trades.sqlite",
  ]
  for key in expected_keys:
      assert key in artifacts, f"Missing artifact key '{key}'"
  ```
  This is an inclusion check (`in artifacts`), not an exact set length check. However, backward compatibility requires that existing keys and file paths are never renamed or broken.

---

## 2. Logic Chain

1. **Premise 1 (R3 Scope & Acceptance Criteria)**:
   - R3 requires: "Generate visual data and reporting for the backtest results (such as an interactive HTML dashboard or static charts accompanied by summary metrics) illustrating equity curve, drawdown, and trade statistics."
   - Acceptance Criteria: "Visual performance outputs (equity curve, drawdown profile, trade distribution metrics) are generated and accessible for review."
   - It must execute in the project environment (`D:\v\Scripts\python.exe`) without complex external server processes.

2. **Premise 2 (Environment Constraints)**:
   - `D:\v\Scripts\python.exe` contains `matplotlib`, `pandas`, and `numpy`.
   - `plotly` and `streamlit` are **not installed**. Installing Streamlit requires a persistent daemon server (`streamlit run`) which cannot be directly opened as an offline file.
   - The React frontend in `web-preview/` requires Node.js/Vite build steps and is designed for static hosting on Vercel, making it impractical as a direct zero-config desktop output for standard CLI backtests.

3. **Premise 3 (Current Capabilities vs Missing Elements)**:
   - Current backtest execution (`run_backtest.py`) generates a static 2-panel PNG (`equity_curve.png`), CSV data (`equity_curve.csv`), and JSON data (`summary.json`, `trades.json`).
   - Missing from visual outputs:
     - Interactive zooming / hovering over the equity curve.
     - Visual trade distribution metrics: trade PnL histogram, R-multiple histogram, win/loss trade duration scatter plot, exit reason breakdown donut/pie chart.
     - Standalone interactive HTML dashboard that operators can double-click and open in any web browser without running a web server.
   - Missing from metrics calculation:
     - Sortino Ratio (annualized downside deviation).
     - Trade Duration statistics (average, median, max duration for winning and losing trades).
     - Separate Long vs Short Net PnL and Profit Factor.

4. **Inference & Architectural Recommendation**:
   - The optimal architecture for R3 is a **Self-Contained Standalone HTML Dashboard Generator** (`src/report/html_dashboard.py`), integrated cleanly into `ReportGenerator`.
   - When a backtest finishes, `ReportGenerator` produces `reports/<run_id>/dashboard.html` in addition to the existing 6 artifacts.
   - `dashboard.html` embeds:
     1. Inline CSS with a modern dark-theme financial dashboard styling (matching the design system in `web-preview/src/styles.css`).
     2. Embedded JSON data payload (`summary.json`, `equity_curve.csv` points, `trades.json` records).
     3. Responsive client-side charts powered by Chart.js (or Lightweight Charts) via public CDN with fallback to pure inline SVG/Canvas for 100% offline environments.
     4. Interactive tabs/sections:
        - **KPI Overview Cards**: Total Return, Net PnL, Max Drawdown, Sharpe, Sortino, Win Rate, Profit Factor, Expectancy.
        - **Equity & High Watermark Chart**: Interactive line chart with hover tooltips and date ranges.
        - **Underwater Drawdown Profile**: Responsive area chart showing drawdown depth and peak-to-trough valleys.
        - **Trade Distribution & Histograms**: PnL distribution histogram (green wins / red losses) and R-multiple distribution.
        - **Duration & Execution Analysis**: Trade holding time vs PnL scatter plot, and exit reason breakdown.
        - **Filterable Trade Log**: Searchable, paginated table of closed positions.
        - **Risk & Accounting Invariants**: Live audit panel showing double-entry balance reconciliation and Circuit Breaker state.
   - This architecture requires **zero new Python pip dependencies**, **zero daemon background servers**, satisfies all R3 Acceptance Criteria, and preserves 100% of existing Stage 6 test invariants.

---

## 3. Caveats

1. **Offline CDN Dependency vs Inlining**:
   - If `dashboard.html` references Chart.js via CDN (`https://cdn.jsdelivr.net/...`), it requires internet access upon opening in the browser. If true air-gapped offline operation is required, the minified library can be inlined directly into the Python generator template, or pure HTML5 Canvas / SVG rendering can be used.
2. **Trade Sample Size Scaling**:
   - For Acceptance Criteria R2 (2,000+ trades over a 1-year window), embedding 2,000 trades in JSON inside `dashboard.html` is lightweight (~200 KB to 500 KB), which loads instantaneously in modern browsers without performance degradation. However, for 50,000+ trades, data downsampling or pagination in the HTML table is recommended.
3. **Paper-Only Integrity & Disclosures**:
   - All visual dashboards must prominently display `PAPER / RESEARCH`, `AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED`, and include explicit disclaimers that simulated slippage and historical performance do not guarantee live trading profitability.

---

## 4. Conclusion

1. **Existing Baseline**:
   - The repository has an institutional-grade reporting foundation in `src/report/generator.py` and `src/report/metrics.py`, producing 6 artifacts (`summary.json`, `summary.md`, `trades.json`, `equity_curve.csv`, `equity_curve.png`, `trades.sqlite`) with strict accounting invariant enforcement ($10^{-4}$ tolerance).
2. **Identified Gaps**:
   - Metrics gaps: Missing Sortino Ratio, trade duration metrics, and complete Long vs Short PnL separation.
   - Visual reporting gaps: The current visual output is limited to a static matplotlib PNG (`equity_curve.png`). The React console in `web-preview/` is detached and hardcoded for Vercel preview.
3. **Recommended Action Plan for Acceptance Criteria R3**:
   - **Step 1 (Metrics Extension)**: Add `calculate_sortino_ratio`, trade duration metrics (`avg_trade_duration`, `median_trade_duration`), and Long/Short PnL breakdown to `src/report/metrics.py`.
   - **Step 2 (HTML Dashboard Generator)**: Implement `src/report/html_dashboard.py` providing `generate_html_dashboard(out_dir, metrics, snapshots, trades) -> Path`.
   - **Step 3 (ReportGenerator Integration)**: Call the HTML dashboard generator in `ReportGenerator.generate_all`, saving `reports/<run_id>/dashboard.html` as artifact #7.
   - **Step 4 (Verification)**: Ensure all 18 existing report and metrics tests pass, add unit tests for `dashboard.html` generation and Sortino calculation, and verify the rendered HTML in a web browser.

---

## 5. Verification Method

To independently verify the observations, metrics calculations, and reporting pipeline:

1. **Verify Existing Report & Metrics Test Suite**:
   ```powershell
   cd 'd:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\crypto-paper-agent'
   D:\v\Scripts\python.exe -m pytest tests/test_report_generator.py tests/test_report_metrics.py -v
   ```
   *Expected outcome*: 18 passed tests in < 2 seconds.

2. **Verify Python Environment Package Availability**:
   ```powershell
   D:\v\Scripts\python.exe -c "for pkg in ['matplotlib', 'plotly', 'streamlit']: mod = __import__(pkg) if pkg in sys.modules or __import__('importlib.util').util.find_spec(pkg) else None; print(pkg, 'OK' if mod else 'MISSING')"
   ```
   *Expected outcome*: `matplotlib OK`, `plotly MISSING`, `streamlit MISSING`.

3. **Inspect Existing Artifacts & Schema**:
   Inspect existing generated report artifacts in:
   - `docs/reviews/evidence/g0-2c9a4d0/replay/LONG/summary.json`
   - `docs/reviews/evidence/g0-2c9a4d0/replay/LONG/trades.json`
   - `docs/reviews/evidence/g0-2c9a4d0/replay/LONG/equity_curve.png`
   Confirm presence of `accounting_reconciliation`, `candle_counts`, `data_provenance`, and RFC 8259 compliance.

4. **Invalidation Conditions**:
   - If `dashboard.html` requires running a background Python web server (like FastAPI, Flask, or Streamlit), this violates the zero-overhead standalone review requirement.
   - If adding `dashboard.html` breaks the strict accounting invariant verification or alters existing RFC 8259 `summary.json` schemas, the implementation must be rejected.
