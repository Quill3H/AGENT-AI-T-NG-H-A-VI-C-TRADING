# Local FUTURES PAPER API v3

Source baseline: candidate `c89333516f9032155923375a876d0350deb6c267`, branch
`codex/windows-paper-replay`. This describes the implementation contract, not
independent acceptance or economic validation. The final verification report
is the [2026-10-17 handoff](../../../docs/handover/2026-10-17-github-checkpoint.md),
which pins the repaired code-under-test SHA and fresh results.

The HTTP service binds only to `127.0.0.1:8765`. Public Binance USD-M Futures
prices are real market observations; capital, orders, fills, positions, funding
and PnL are **simulation**. No trading keys, exchange orders or testnet routes
exist. BTCUSDT/ETHUSDT/SOLUSDT share one account, not three 10,000 USDT accounts.

## Account and compatibility

The owner authorized a new separate `windows-paper-v3` experiment with an
initial 10,000 imaginary USDT, stored by default in
`data/paper_accounts/windows-paper-v3`. Legacy `data/paper_sessions` is not
deleted, renamed or silently used as its starting capital. A custom path is
reported as `<CUSTOM_ACCOUNT>`; persisted artifacts do not expose machine paths.
There is no HTTP reset, deposit, withdrawal, strategy override or caller-score
promotion endpoint.

`paper.sqlite3` and `paper-account.identity.json` are an indivisible account
identity/evidence set, protected by a lifetime OS writer lock. Atomic commits
save canonical closed inputs, events and the full machine checkpoint together.
Uncommitted work is not promoted into account watermarks. Missing/orphaned,
torn, corrupt, conflicting or unknown evidence fails closed. No 10,000 USDT
is invented when restoration is uncertain. Compatible saved state restores
positions, pending entries/closes, costs, settlement markers, strategy/risk
state and all processing boundaries before full chronological gap replay.
An unverifiable legacy account remains blocked; a narrow checked v2 migration
is not a general recovery guarantee or permission to erase public funding debt.

The older [PAPER_STREAM_API.md](PAPER_STREAM_API.md) and v2 schema/examples
remain relevant to legacy evidence only. Do not use their synchronous controls,
unbounded history or public-observed funding assumptions for the v3 server.

## Routes and HTTP behavior

| Route | Response and semantics |
| --- | --- |
| `GET /api/health` | 200 service snapshot, API version, server PID, status, intent, operation, source/API times, connection/recovery/risk/error; 200 is not admission approval |
| `GET /api/state` | 200 complete v3 UI snapshot, including unknown/blocked/busy state |
| `POST /api/start` | 202 asynchronous start/recovery request; never reset an existing account or revive terminal STOPPED |
| `POST /api/pause` | 202 asynchronous persisted PAUSED intent; protective handling and modeled funding continue |
| `POST /api/resume` | 202 asynchronous RUNNING intent on the same eligible nonterminal trial |
| `POST /api/stop` | 202 asynchronous STOPPING intent; do not claim closure until STOPPED/reconciled |
| `GET /api/history?cursor=0&limit=100` | 200 append-only event page; integer cursor >= 0, integer limit 1..500 |
| `GET /api/chart?symbol=BTCUSDT&interval=1m&limit=90` | 200 public chart candles; BTC/ETH/SOL, 1m/15m/4h, supported numeric limit 1..500; display-only |

POST accepts **no body**; a body or transfer encoding is 400. Invalid Host or
disallowed cross-site control Origin is 403, an unknown route 404, and queue/
shutdown refusal 503 with state/error. Allowed browser origins are HTTP
localhost/127.0.0.1 on this server port or 5173; a UI dev server on another port
needs a same-origin proxy or an explicitly reviewed allowlist change.
GET responses are not cross-origin permission to submit controls. API JSON is
uncached (`Cache-Control: no-store`), finite and contains no NaN/Inf.

History is 400 for invalid cursor/limit and 503 when the account writer is
busy or evidence is unverified. Chart validation failure is 400 and source
failure is 503, with `{"error": "..."}`; a chart failure does not submit orders.
The chart response is `{symbol, interval, server_time_utc, candles}` with
`time_utc`, OHLC and `provisional`. A forming candle may be included; it never
becomes an input to a closed-bar decision.

## Asynchronous controls

Every accepted POST returns a full state plus `operation`:

```json
{
  "id": "control-1",
  "name": "pause",
  "status": "PENDING",
  "error": null,
  "requested_at_utc": "2026-10-02T00:00:00+00:00",
  "completed_at_utc": null
}
```

This fragment is explanatory synthetic data, not a full state or a trading
result. Poll state/health until operation is APPLIED, FAILED or CANCELLED;
PENDING/RUNNING and HTTP 202 mean queued/in progress only. APPLIED means the
command was handled, not that a signal traded or recovery has passed every
gate. Check persisted `operator_intent`, `status`, `recovery`, `error` and
`risk_gate` as well. STOPPING may need subsequent eligible execution batches
to close exposure safely; without valid data it remains STOPPING.

Repeated current in-progress commands are coalesced and durable intent changes
are idempotent. An already terminal STOPPED account remains terminal, including
after Start. Use Pause/Resume for reversible control. The operation object is
the latest command in the current process, not a durable per-request results
API; its ID is not a financial account identity and can change after restart.
Persisted intent/events, session/trial IDs and processing watermarks are the
recovery authority. The worker is serialized and rejects a full queue; do not
flood it or assume button-click time is the persisted effective control time.

## State and rendering contract

Validate against [paper_replay_state_v3.schema.json](paper_replay_state_v3.schema.json).
Important fields:

| Field | Meaning |
| --- | --- |
| `api_version`, `mode` | Always 3 and PAPER_RESEARCH |
| `session_id`, `account_profile`, `config_sha256` | Account/profile/config identity; no implicit new session after restart |
| `api_time_utc` | Response creation time, not a market or financial valuation time |
| `source_time_utc`, `received_at_utc` | Last public REST server observation and processing/receipt information; may be null or historical |
| `connection` | Connected flag, source/error, last event receipt and reconnect requirement; a connected socket alone does not permit orders |
| `current_prices[symbol]` | Backend quote validity, price, kind and event as-of time; invalid/stale => price null |
| `markets[symbol]` | Last closed mark/as-of and forming-candle metadata; forming data is display-only |
| `account_as_of_utc`, `valuation_kind` | Last reconciled closed 15m valuation boundary and LAST_RECONCILED_CLOSED_15M, not a browser-tick equity calculation |
| `account` | Broker initial equity, wallet/equity, free/reserved collateral, unrealized PnL and breaker state; unknown => null |
| `operator_intent` | null before allocation, otherwise RUNNING, PAUSED, STOPPING or STOPPED |
| `execution_mode`, `replay` | null/REALTIME/REPLAY and catch-up target, processed/remaining batch counts |
| `backend_busy` | Reconciliation/research writer busy; published checkpoint is read-only, risk admission false, current prices unavailable |
| `recovery`, `error` | Required/account-known/reconciled/view plus precise reason; empty exposure arrays do not prove zero exposure when UNKNOWN |
| `risk_gate` | Admission_open/reason/halted; true is only one admission precondition, not proof of an approved trade |
| `strategy`, `recipe`, `trial_id` | Actual active rulebook and version/formula/config/source identity; not all catalog candidates |
| `trials`, `research` | Failed/active trial history, targets, allocations, cumulative supplied imaginary capital and causal research verdict/used holdouts |
| `orders`, `pending_orders`, `open_positions`, `trades`, `funding_events` | Broker-derived execution/accounting views; no client-generated financial values |
| `history` | Event page endpoint/page size and declared whole_position sample unit |

All timestamps are UTC ISO-8601. Source event time, local receipt, simulated
batch time and response creation time are distinct and must not be collapsed.
Stored replay events carry `simulated_at_utc` and actual `processed_at_utc`.
Do not substitute API time for a stale market's as-of time. A fresh quote
requires valid connected source receipt within 15 seconds; false validity
must render unavailable, not the last chart close as current price.

`account.equity_usd = wallet_usd + unrealized_pnl_usd`, and
`available_margin_usd = wallet_usd - reserved_collateral_usd` in this broker.
The UI displays these backend values; it must not double-add collateral,
subtract fees/funding a second time, or re-mark PnL from chart ticks. Wallet
already includes booked realized PnL and costs. The broker's own accounting
invariants are authoritative. ETH/SOL use explicitly simulated conservative
maintenance brackets, not verified Binance venue brackets.

`status` and `operator_intent` are separate:

| Status | UI/decision interpretation |
| --- | --- |
| IDLE | No allocated account/bot started; monetary values are unknown/null |
| SCANNING | Closed-bar processing active; still requires fresh data, RUNNING intent and all risk gates |
| WAITING_SYNC | Await matching validated cross-symbol closed stream boundary; no prospective admission |
| WAITING_CONNECTION | Disconnected or restored/catching up but waiting for fresh public data; no prospective admission |
| RECOVERY_REQUIRED | State/integrity cannot be proven; preserve evidence, show reason and block new paper orders |
| STOPPING | Entry admission closed; reconcile queued closes at valid modeled execution opportunities |
| STOPPED | Terminal reconciled operator stop; HTTP can remain available without restarting the trial |

PAUSED is an intent, not a separate connection status: the socket may remain
connected/SCANNING while entries are blocked and protection/funding continue.
During exact restore, initial RECOVERY_REQUIRED plus operation PENDING/RUNNING
can be a transient pre-restore state; wait for the operation result without
treating it as success or automatically resetting the account.

## Causality, execution and funding

Initial strategy is `trend_following`: closed 4h signals and next 15m open
paper execution. A forming 1m/15m candle never generates a closed-bar signal.
Chart symbol/timeframe controls do not change the strategy. Breakout & Retest
is only activated by eligible bounded research promotion; SMC, PPO and Funding
Arbitrage are not active in this account. Fees/slippage, mandatory stops, 5x
maximum leverage, news policy, Circuit Breakers and liquidation remain broker
responsibilities.

Restoration fixes a public catch-up target and obtains every missing closed
interval with pagination, validates synchronized symbol/timeframe coverage,
and advances exactly one chronological batch. Histories exposed to decisions
contain only bars available by that simulated boundary, including causal
indicator seeds and setup state. Downloading a future suffix does not allow
decisions to see it. Duplicate identical inputs/events are idempotent;
conflicting revisions, timestamp reversals or ambiguous financial state fail
closed. Reconnect clears partial symbol groups, replays gaps and waits for
fresh synchronized verification before prospective admission.

The named experiment funding model is `FIXED_SIMULATED`, version `fixed-001`,
rate `0.0001`, UTC hours `[0, 8, 16]`, local hours `[7, 15, 23]`, timezone
`UTC+07:00`, proxy `CANDLE_OPEN` and recorded effective time. On eligible
position notional, LONG cashflow is negative and SHORT positive. For 10,000
USDT **position notional**, one settlement pays/receives 1 imaginary USDT;
account equity is not position notional. Broker phase ordering and retained
settlement keys prevent duplicate funding after retry or restart. This is
predetermined simulated configuration, not a fabricated public funding
observation. Other public-source funding modes retain fail-closed provenance.

## Trials and research

At reconciled boundaries, equity strictly below 5,000 marks FAILED once,
blocks/cancels entry requests and reconciles remaining exposure. Equity at
least 15,000 records TARGET_REACHED once while the same trial continues.
Exactly 5,000 is not failure. Non-finite/unknown equity is recovery failure,
not an automatic trial event or reset. Thresholds are not relaxed per-trade
risk or a replacement for Circuit Breakers.

A new 10,000 imaginary USDT allocation requires a flat reconciled failed
trial, causal eligible recipe/verdict and exactly-once allocation event. A
breaker lock is not bypassed; pause/stop inhibits promotion. Cumulative
`trials.total_capital_injected_usd`, allocations, old failed trials and their
losses remain visible. Do not concatenate trial balances into a fictitious
continuously compounding portfolio or call TARGET_REACHED proof of an edge.

Research uses frozen recipes/formulas/config, 180/90/90-day chronological
train/validation/holdout windows, three isolated 30-day holdout folds, minimum
completed-position evidence, drawdown/net expectancy and doubled-cost gates.
A final holdout is claimed before evaluation and cannot be reused for a
runner-up. No new recipe is backdated into earlier replay. No external HTTP
caller supplies scores or force-promotes. An insufficient, blocked or exhausted
round produces a verdict, not capital. The implemented gate is not evidence
that a real full 360-day study has already completed or found a winner.

## History and synthetic integration examples

State retains the most recent 100 orders/trades/funding records; this is not
permission to drop durable account history. `/api/history` returns
`{"items": [...], "next_cursor": null|integer}`. Each item has its stable
SQLite `cursor`, `key`, `kind` and event-specific payload. Request after the
last cursor, follow `next_cursor`, and stop at null for that snapshot. Later
polls can use the last seen item cursor to fetch appended events.
Ledger events include trial ID and record ID; order status revisions may have
multiple immutable event payloads. Do not count them as separate orders/trades
or use raw event-row count as sample size. Declared account sample unit is
`whole_position`; research promotion uses `completed_position_lifecycle`.

[paper_replay_api_examples_v3.json](paper_replay_api_examples_v3.json) contains
six full backend-generated states, labeled
`SYNTHETIC_API_EXAMPLES_NOT_MARKET_RESULTS`:

- `empty_unallocated`: no account allocation and null monetary values.
- `normal_public_fixture`: fixture-derived public-shaped prices and actual
  simulated broker state, not a public market performance result.
- `disconnected`: no valid current prices and no prospective admission.
- `paused`: persisted pause intent while existing exposure remains managed.
- `restart_replayed_paused`: full fixture outage replay, preserved intent and
  modeled funding without capital reset.
- `recovery_required`: torn fixture database, unknown financial state and
  admission blocked.

Generate these fixtures from `crypto-paper-agent` in a disposable test area,
not an operator account:

```powershell
.\.venv-paper\Scripts\python.exe scripts\generate_paper_replay_examples.py --output docs\operations\paper_replay_api_examples_v3.json
.\.venv-paper\Scripts\python.exe -m pytest -p no:cacheprovider tests\test_paper_replay_contract.py tests\test_paper_replay_server.py -q
```

Generation calls actual synthetic session transitions and validates the schema;
it writes examples only and does not prove public execution, uptime or returns.
These are reproducibility commands, not a claim this document itself ran them.
Full verification results belong in the pinned completion/review evidence.

## Windows/service boundary and limitations

See the [Windows runbook](../../../docs/operations/LOCAL_PAPER_WEB.md) for manual
launch, optional hidden logon task, status/logs, Pause/Resume/StopBot,
DisableAndStop and Uninstall. StopBot ends the paper trial while HTTP remains;
DisableAndStop disables relaunch and terminates only a verified service. Closing
a browser has no backend effect. A deliberate subsequent service launch honors
the last durable intent, so pause before service shutdown if desired.

No task installation or power-setting change is performed by publishing this
contract. Actual task/logon/machine reboot, power loss and 24/7 operation require
separate runtime evidence and otherwise remain NOT_VERIFIED. A short public
WebSocket observation is not proof of a real signal or trade: report 0 orders
when no signal occurred and use separately labeled fixtures for execution.
The wide desktop UI has horizontal scrolling on small screens. This remains
PAPER/RESEARCH, not production-ready, profitable or independently accepted.
