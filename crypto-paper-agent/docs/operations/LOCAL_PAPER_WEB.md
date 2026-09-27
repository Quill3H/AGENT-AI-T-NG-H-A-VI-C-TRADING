# Local Paper Web

This is a local, prospective **PAPER/RESEARCH** observation tool. It does not
connect a trading account, use exchange credentials, place live/testnet orders,
or imply that any strategy is profitable. The hosted static preview remains an
archived evidence viewer and does not run this scanner.

## Start on Windows

From the repository root, run `start-paper-web.cmd 8765` (or double-click it
with the default port described below). It builds the web app, starts a
loopback-only server, and opens `http://127.0.0.1:8765/`. Opening that local
page starts one idempotent paper session. The terminal shows a public BTCUSDT
1m candlestick chart, BTC/ETH/SOL 15m closed prices, account state, open
positions, recent order statuses, completed realization rows, and timestamps.

For a different port, pass the port as the argument. Stop admission with the
**Dừng mô phỏng** button; close the server window with Ctrl+C to stop the
service. Closing the browser tab alone does **not** stop the server. Restarting
the service creates a new session; earlier journals remain under
`data/paper_sessions/` and are intentionally excluded from Git.

If launching manually, from `crypto-paper-agent/`:

```powershell
uv venv .venv-paper --python 3.12
uv pip install --python .venv-paper\Scripts\python.exe pandas numpy requests loguru pyyaml
cd web-preview
npm ci
npm run build
cd ..
.\.venv-paper\Scripts\python.exe scripts\run_local_paper_web.py --open-browser
```

## Execution contract

- Source: Binance public USD-M perpetual `/fapi/v1/time`, `/fapi/v1/klines`
  and `/fapi/v1/fundingRate` only. No order endpoint exists in this service.
- BTC chart may show a **provisional** 1m candle. It is display-only.
  Signals use fully closed 4h candles, with the existing fixed Trend Following
  rulebook; execution is simulated by PaperBroker on the next closed 15m bar.
- Startup 4h/15m data is warm-up/baseline, **not** retrospectively traded.
  New BTC/ETH/SOL 15m bars are accepted together in event-time order. Missing,
  duplicate, gapped, stale, malformed or mismatched data stops or delays
  admission. Source receipt, exchange server time, event time, config hash,
  raw warm-up and each raw input batch are recorded in the JSONL journal.
- A startup source failure remains visible as QUARANTINED until the local
  service is restarted. No order is admitted from a partially initialized
  session.
- PaperBroker owns sizing, stop-loss, max-5x leverage, margin, fee, slippage,
  funding and circuit-breaker accounting. ETH/SOL use an explicitly
  **simulated conservative** maintenance bracket (2% MMR, max $5,000 notional),
  not an exchange-verified venue bracket. This limits fill/liquidation fidelity.
  Exact funding source provenance is mandatory; a missing or millisecond-late
  settlement event quarantines the session rather than backdating it. The
  scanner observes fully closed 15m bars. If a paper position spans a funding
  boundary, a settlement record first retrieved after that boundary is also
  rejected as unavailable at event time. This can end a session with an open
  paper position; the local REST scanner does not yet provide event-time
  funding capture and must not invent an on-time settlement.
- Stop ends observation and cancels pending orders. Any open paper position is
  retained in the terminal state without pretending to fill a market exit at
  an unobserved price. No position or trade is carried into a new session.

The local status is author-tested, not independently reviewed. Zero trades are
normal if the fixed rulebook has no fresh valid signal. Historical replay,
near-current candles, and prospective observations are displayed separately;
none of them establishes future returns or economic validation.
