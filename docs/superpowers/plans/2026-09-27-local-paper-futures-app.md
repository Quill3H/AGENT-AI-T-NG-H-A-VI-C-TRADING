# Local Paper Futures App — Execution & Integration Plan

**Date:** 2026-09-27  
**Branch:** `codex/local-paper-futures-app`  
**Mode:** PAPER / RESEARCH ONLY (No live orders, no trading credentials, no testnet)

---

## 1. Objective

Deliver a productionized local desktop web app for automated Binance USD-M Futures paper trading:
1. **Capital & Autonomy:** Starting with simulated 10,000 USDT. The bot autonomously generates, executes, and closes paper orders according to the fixed Trend Following strategy (4h/15m) and existing risk limits. No manual confirmation for simulated orders.
2. **Safety Boundary:** Strict paper-only execution. No orders sent to Binance, no exchange API keys, no testnet keys.
3. **Data Authenticity:** Real public Binance Futures data for BTC, ETH, SOL from the Python backend (`live_session.py`). Zero `Math.random()` simulation in the browser. Clear distinction between running (provisional) candles and closed candles. Accurate UI labeling: Trend Following is running on live data; other strategies are historical/dormant.
4. **Backend Integration:** Full two-way sync with `/api/state`, `/api/start`, `/api/stop`. Support multi-symbol candlestick feeds (BTC, ETH, SOL) with public WebSocket enhancement.
5. **Single-Instance & Watchdog:** Windows autostart on user login, automatic restart on process failure, port conflict prevention (single instance lock).
6. **State Persistence & Safe Recovery:** Persist session journal, equity, wallet, margin, orders, and positions. On restart, do NOT silently reset equity to 10,000 USDT or assume positions were closed. If state cannot be safely verified across downtime, halt paper order intake and quarantine with an operator notification.
7. **Resilient UX:** Explicit connection states (Connecting / Online / Data Stale / Server Error / Quarantined / Stopped), non-blocking auto-reconnect, no "Not Responding" hangs.

---

## 2. Architecture & File Scope

```
crypto-paper-agent/
├── src/
│   └── paper/
│       ├── live_session.py       <-- Add multi-symbol 1m chart klines, state persistence & safe recovery
│       ├── local_server.py       <-- Port collision check / single instance lock, clean error handling
│       └── persistence.py        <-- State snapshot & recovery validator
├── scripts/
│   ├── run_local_paper_web.py    <-- Watchdog loop with auto-restart, single-instance verification
│   ├── install_windows_autostart.ps1 <-- Setup Windows Startup shortcut / Task
│   └── uninstall_windows_autostart.ps1 <-- Remove Windows Startup shortcut
├── web-preview/
│   ├── src/
│   │   ├── App.jsx               <-- Connect to backend /api/state, WebSocket stream, connection states
│   │   ├── CandlestickChart.jsx  <-- Lightweight-charts v5 with live WS + backend klines
│   │   └── App.test.jsx          <-- Comprehensive frontend tests
│   └── vite.config.js            <-- Proxy /api to backend port 8765
├── tests/
│   ├── test_local_paper_server.py
│   ├── test_local_paper_session.py
│   └── test_paper_persistence.py  <-- Test safe recovery across restarts & data gap quarantine
└── start-paper-web.cmd            <-- One-click Windows runner with watchdog & port check
```

---

## 3. Implementation Steps

- [x] Step 0: Merge backend branch `codex/local-paper-scanner` with `codex/web-preview-binance-dark-ui`.
- [ ] Step 1: Implement state persistence and safe recovery in `src/paper/persistence.py` and `live_session.py`.
- [ ] Step 2: Add multi-symbol 1m klines support (BTC, ETH, SOL) in `live_session.py` to feed the chart.
- [ ] Step 3: Implement single-instance lock and watchdog loop in `local_server.py` and `run_local_paper_web.py`.
- [ ] Step 4: Update `web-preview` (`App.jsx`):
  - Poll `/api/state` with non-blocking fetch + AbortController.
  - Implement Binance public WebSocket stream for live klines with fallback.
  - Remove all browser-side `Math.random()` simulation.
  - Display accurate strategy status: Trend Following (Live Paper); Breakout/SMC/Funding (Historical Sample).
  - Add connection banner states (Connecting, Live, Data Stale, Server Error, Quarantined).
  - Handle Start/Stop API triggers.
- [ ] Step 5: Implement Windows Autostart scripts (`install_windows_autostart.ps1`, `uninstall_windows_autostart.ps1`) and enhance `start-paper-web.cmd`.
- [ ] Step 6: Write Python and React tests verifying state recovery, gap quarantine, and API contracts.
- [ ] Step 7: Run verification on Windows (test server start, web UI, process kill/restart, network glitch, state retention).
- [ ] Step 8: Capture visual evidence, document operational instructions, and commit.
