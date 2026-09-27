# Local paper stream backend handoff - 2026-09-27

Status: **AUTHOR_SELF_REVIEWED / REVIEWER_NOT_VERIFIED**. This handoff is for
the backend branch `codex/paper-stream-backend`, based on
`codex/local-paper-scanner` checkpoint `46ce69a06ed390f242af862f21468c6eb9bd3f5e`.
It is not G5 acceptance, economic validation, profitability evidence or live
trading readiness. The owner decides whether to accept this gate.

## Delivered

- Added strict Binance USD-M combined kline stream parsing for BTCUSDT,
  ETHUSDT and SOLUSDT. The parser validates stream identity, interval geometry,
  OHLC, event/receipt/availability timestamps, close flag and stale/future
  payloads. Forming 1m/15m bars are display-only; only a complete same-open
  closed 15m set can call the existing `PaperBroker.process_batch` path.
- Added read-only `websocket-client` transport with ping, exponential reconnect
  and a 15-second no-fresh-event watchdog. Connection loss, invalid payload,
  symbol-time disagreement and source gaps close admission before mutation.
- Added REST bounded gap reconciliation. With no position/pending order,
  contiguous fresh public data is journaled as `PAPER_GAP_SKIPPED`, strategy
  state is rebaselined and no historical fill/signal is invented. Any open or
  pending exposure during an unverifiable gap quarantines the session.
- Journal records are flushed and `fsync`'d. Closed stream inputs are recorded
  before batch processing; batch and stop snapshots include the API state.
  Existing journals restart as `RECOVERY_REQUIRED` (read-only), preserving the
  last snapshot and never resetting the paper balance or duplicating orders.
- Added `/api/health`, loopback-only CORS for the Antigravity dev server,
  explicit connection/risk gate, funding, order, position, collateral, fee,
  pending-order and trade fields. UI must render these values and never compute
  PnL or create a fill.
- Added backend-owned API schema/examples and Windows launcher plus optional
  Scheduled Task install/uninstall scripts. The task checks port 8765,
  restarts up to three times, writes logs and does not run npm/build on startup.
- No web-preview source, Antigravity branch or `main` was modified.

## Evidence

Python: existing checkout environment `G:\GITHUB\AGENT-AI-T-NG-H-A-VI-C-TRADING\crypto-paper-agent\.venv-paper\Scripts\python.exe`, with
`websocket-client==1.9.2` installed for this run. The backend worktree has no
tracked `data/raw` or paper journal artifact.

| Command | Result |
| --- | --- |
| `.venv-paper\Scripts\python.exe -m pytest -p no:cacheprovider tests/test_local_paper_session.py tests/test_local_paper_stream.py tests/test_local_paper_server.py -q` | 29 passed, 0 failed, 2.8 s (final focused run) |
| `.venv-paper\Scripts\python.exe -m pytest -p no:cacheprovider -m "not network" -q` | 459 passed, 2 skipped, 5 deselected, 2 existing Gymnasium warnings, 149.23 s |
| `.venv-paper\Scripts\python.exe -m pytest -p no:cacheprovider -m network -q` | 5 passed, 461 deselected, 23.35 s |
| JSON parse for `paper_stream_state.schema.json` and `paper_stream_api_examples.json` | passed; `jsonschema` package unavailable, so schema semantic validation was not run |
| PowerShell AST parse for Windows scripts | 3 files, 0 parse errors |
| Public REST `/fapi/v1/time` | 200; server time returned and clock gate passed |
| Public WebSocket `/stream` and `/ws` observation | `ENVIRONMENT_BLOCKED`: connection opened but no frame arrived within 8-15 s; `WebSocketTimeoutException` |
| Live server on `127.0.0.1:18765` | REST warm-up loaded all 3 symbols; API returned 10,000 USDT, 0 orders/trades; no stream frame, remained `WAITING_SYNC` and admission closed |
| Stop/repeated stop | `STOPPED`, second stop idempotent; 0 orders/trades |
| Restart same journal | `RECOVERY_REQUIRED`, same session ID/equity, admission false, no new order |
| Synthetic strategy -> broker -> stop -> accounting | 1 simulated LONG filled/stopped; `verify_accounting_invariants()` passed |

The earlier checkpoint's web UI build/browser QA is not repeated here. This
branch has not been merged or pushed to `main`. No independent Tester or
Reviewer has accepted the changes.

## Known limits / remaining gates

- The public WebSocket was unavailable from this environment; no prospective
  market order was observed. The service correctly refuses admission without
  fresh closed events. A Tester should repeat the observation on a network that
  permits Binance Futures WebSocket traffic and inspect journal timestamps.
- Exact in-memory broker/strategy restoration is deliberately not implemented;
  restart is safe but requires manual reconciliation. Do not delete or reuse a
  prior journal to bypass this gate.
- Funding remains fail-closed. A position spanning a funding boundary with
  missing/late exact provenance quarantines; no funding is backdated.
- Public kline-only feed does not provide OI/CVD. Existing optional feature
  fallback remains unchanged and is not a claim of observed OI/CVD.
- Paper next-open bar fills are not contemporaneous executable exchange fills.
  ETH/SOL maintenance brackets remain conservative simulation assumptions.
- No native TradingView Strategy Tester report was used. No profitability,
  convergence, generalization, production readiness or real-money claim is
  made.

## Safety

Only unauthenticated public `GET` market-data endpoints and a public market
WebSocket are used. There is no Binance order/testnet endpoint, API key,
wallet/private key, signing or withdrawal operation. The system remains
PAPER/RESEARCH only.

Code-under-test commit: `d06216195821231a60bf1dd9ee6b5e5129333bfc`.
Documentation commit: see Git history after the documentation commit; do not
replace it with a guessed SHA.
