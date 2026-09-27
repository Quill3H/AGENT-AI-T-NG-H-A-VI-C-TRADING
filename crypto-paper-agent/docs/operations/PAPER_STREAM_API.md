# Local PAPER stream backend API

Scope: backend contract for the separate Antigravity UI branch. This is a local
research simulation, not an exchange account or native TradingView result.
Only Trend Following 4h signal / 15m paper execution is active. BTC, ETH and
SOL share one simulated 10,000 USDT account. No trading key or order endpoint.

## Endpoints

Bind: `127.0.0.1:8765`. `GET /api/health` reports service/session/connection.
`GET /api/state` is the complete UI view. `POST /api/start` starts a new
session only when status is `IDLE`; repeated calls do not create a second
account or socket. `POST /api/stop` terminates the session without pretending
open positions were filled or closed; repeated calls are harmless. POST has no
body. Cross-origin browser access is restricted to loopback port 5173 or the
same server port. An Antigravity dev server on another port needs a same-origin
proxy or an explicit backend allowlist review.

`status` values: `IDLE`, `SCANNING`, `WAITING_SYNC`, `WAITING_CONNECTION`,
`QUARANTINED`, `STOPPED`, `RECOVERY_REQUIRED`. Only `SCANNING` plus
`risk_gate.admission_open=true` may receive new simulated orders. Even then,
only three matching closed 15m candles validated against public REST reach the
broker. `WAITING_SYNC` means incomplete cross-symbol confirmation or
post-reconnect baseline. `RECOVERY_REQUIRED` is intentionally read-only:
exact restoration of in-memory broker/strategy state is not implemented.

The UI must render backend values as-is; it must not compute PnL, synthesize
prices, fills, orders or strategy names. `chart[].provisional=true` and
`markets[symbol].forming_15m` are display-only. Trading decisions use closed
REST-confirmed 15m candles and causal 4h features. `source_time_utc` is the
REST server-time observation; `received_at_utc` is local receipt. Stream events
have separate `event_time_utc`, `available_at_utc` and `received_at_utc` in the
append-only journal. All API timestamps are UTC ISO-8601. Missing values are
`null`, not inferred. Do not label a paper next-open bar fill as executable
live-market fill.

`account`: `initial_equity_usd`, `wallet_usd`, `equity_usd`,
`available_margin_usd`, `reserved_collateral_usd`, `unrealized_pnl_usd`,
`breaker_locked`. `orders[]` includes broker order status, fill price,
quantity, fee, slippage and rejection reasons. `pending_orders[]`,
`open_positions[]`, `trades[]` and `funding_events[]` are broker-derived.
`risk_gate` carries admission status/reason. Historical lists are bounded for
the UI (`orders` to 30), while the journal retains full batch states and raw
decision inputs. The UI should show `risk_note` about simulated ETH/SOL
maintenance brackets.

See `paper_stream_state.schema.json` for the machine-readable state contract
and `paper_stream_api_examples.json` for four **illustrative synthetic**
responses: normal, disconnected, blocked data and restart. The failure
examples show only the fields that change or matter for the failure; they are
not full captured responses. None is market or performance evidence.

## Windows operation

From `crypto-paper-agent` in a PowerShell terminal, install Python dependencies
once into `.venv-paper` using `uv pip install --python .venv-paper\Scripts\python.exe
-r requirements.txt` (or the project's existing environment plus
`websocket-client>=1.8,<2`). No `npm install` or build runs at service start.

Manual backend-only run:

```powershell
.\scripts\windows\run-paper-server.ps1 -Port 8765
```

The script checks for an existing listener on 8765, then runs
`scripts/run_local_paper_web.py`; output goes to
`data/paper_sessions/logs/paper-server.log`. The backend can run without a
built static UI; the `/api/*` routes remain available. The UI may be served
separately by Antigravity. Browser tabs can close without stopping the server.
For this separate backend worktree, pass `-PythonPath` pointing to a compatible
existing `.venv-paper\Scripts\python.exe`, or create a virtual environment in
the backend worktree. The scheduled-task installer accepts the same parameter.

Optional login task (current Windows user, restart up to three times after a
process failure):

```powershell
.\scripts\windows\install-paper-task.ps1
Start-ScheduledTask -TaskName CryptoPaperResearchBackend
Get-ScheduledTask -TaskName CryptoPaperResearchBackend
.\scripts\windows\uninstall-paper-task.ps1
```

The task runs the server, not `POST /api/start`; opening the UI can call Start.
Use the **same** `-JournalDir` on every launch when a nondefault persistent
journal is used, including manual and scheduled starts. Do not point a new
worktree at an empty journal and treat it as a continuation of an account.
Stop the task or server process to stop the service. `POST /api/stop` only stops
the paper session. The login task is not installed by default.

If a prior journal exists on restart, the backend returns `RECOVERY_REQUIRED`;
it never creates another 10,000 USDT account. Preserve the JSONL file for
manual audit. A pending `PAPER_INPUT` without a `PAPER_BATCH` means the last
state is uncertain. There is no operator "resume" or reset endpoint in this
branch. Exact replay/reconciliation is a remaining engineering gate.

## Known limits and evidence

- The Binance public WebSocket feed must be reachable on the user's network.
  REST success alone does not verify stream availability. No stream means no
  new paper orders.
- A skipped gap is journaled and allowed only with no open or pending paper
  exposure, a contiguous REST source window and fresh 4h warmup. No
  retrospective fills or signals are invented. Other gaps quarantine.
- Closed-bar paper fills are evaluated after a full bar, not exchange-matched
  executable fills. Funding remains fail-closed on missing/late provenance.
- There is no demonstrated profitability, independent acceptance or real-money
  readiness. See the backend handoff for exact test and network outcomes.
