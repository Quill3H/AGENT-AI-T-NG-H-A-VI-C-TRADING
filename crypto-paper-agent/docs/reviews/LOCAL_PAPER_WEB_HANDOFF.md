# Local paper web handoff — 2026-09-27

Status: **AUTHOR_SELF_REVIEWED / REVIEWER_NOT_VERIFIED**. This is a local
paper/research UI candidate, not G5 acceptance or economic validation.

## Identity and scope

- Branch: `codex/local-paper-scanner`; base `main`:
  `fe1c1330d913e78239db575ff8433cf069fe1b01`.
- Code-under-test commit:
  `e4de532a0871dce0869dd3924e195b69ad067c37`.
  Core Python/web code and tests were committed at
  `d8fd92815bd389c5fa792220f434009e8aac9921`; the later code commit
  only corrects Windows batch control flow after `npm.cmd`.
- Documentation commit: see the next commit in Git history and the final
  handoff. Do not substitute a guessed self-SHA.
- Changed code: `src/paper/`, `scripts/run_local_paper_web.py`, local
  launcher, focused Python tests, and `web-preview/` app, chart, tests and
  dependencies. Changed docs: this report, the local operation guide,
  implementation plan, PROJECT_STATE and PLANNER_HANDOVER.
- Source/venue: unauthenticated Binance public USD-M perpetual REST, BTCUSDT,
  ETHUSDT and SOLUSDT. Signals: fixed Trend Following 4h close. Broker replay:
  next closed 15m candle, with existing sizing, stops, margin, fees, slippage,
  circuit breaker and funding controls. No PPO/model is used.
- Browser-observed session: `20260927T123944-e77a262f`, config SHA-256
  `cef9da4753e541bff374ddb237348861b82013c47e47ede9d203d0594c6bf63f`,
  raw warm-up/baseline input SHA-256
  `a0da29221c2cd92dcbf6c7f2706f51a507d480800622919da3fc57a9b373d4e6`.
  The ignored local JSONL journal holds raw inputs; it is not synchronized by
  Git or represented as historical OOS evidence.

## Tests actually run by the author

| Check | Outcome |
| --- | --- |
| `.venv-paper\Scripts\python.exe -m pytest -p no:cacheprovider tests/test_local_paper_session.py tests/test_local_paper_server.py -q` | 16 passed, 0 failed |
| `.venv-paper\Scripts\python.exe -m pytest -p no:cacheprovider -m "not network" -q` | 447 passed, 2 skipped, 5 deselected, 2 existing Gymnasium warnings, 107.13 s |
| `.venv-paper\Scripts\python.exe -m pytest -p no:cacheprovider -m network -q` | 5 passed, 448 deselected, 21.47 s |
| `npm test` in `web-preview/` | 9 passed in 2 files |
| `npm run build` in `web-preview/` | Vite build passed |
| `git diff --cached --check` on code A | No whitespace errors |
| `cmd /c .\start-paper-web.cmd` without a port argument | Build passed, local server listened on 127.0.0.1:8765, browser opened, `/api/state` returned SCANNING |

Chromium local QA at `http://127.0.0.1:8765/`: desktop 1440x900 and mobile
390x844 displayed a nonblank BTC candle chart, all three 15m watch prices,
the PAPER account, zero-trade ledger and current source/receipt timestamps.
The local page auto-started; Stop changed the status to STOPPED. No page,
console or failed-network errors remained; no horizontal overflow at either
viewport. The Codex in-app browser lost its auth token after initial load, so
the full interaction pass used local Chrome through Playwright. This was
browser QA by the author, not an independent review.

## Self-review and limits

- Confirmed one order-admission path in the new service:
  `TrendFollowingStrategy.on_candle_close -> PaperBroker.submit_order`.
  No new exchange order endpoint, testnet, key or wallet code exists. The
  public source allowlists only time, kline and funding GET endpoints; HTTP
  service binds to `127.0.0.1` and rejects non-loopback Host/Origin.
- Fixed author-found issues: double-click launcher empty port and missing
  Windows `call` after npm, non-loopback
  Host acceptance, late-observed funding backdating, transient startup error
  disappearing from UI, narrow desktop chart, wrong active nav and favicon 404.
  Regression tests cover the data/risk failures.
- No prospective completed trade occurred in browser QA (0 trades). Synthetic
  tests exercise three-symbol batches and broker accounting; they do not prove
  that the fixed rulebook will generate a future market signal.
- The broker's next-open 15m fill is evaluated when that candle has closed.
  It is a bar-based paper simulation, not contemporaneous executable exchange
  fill evidence. Funding observed after its boundary cannot be backdated;
  a position spanning that boundary may quarantine the session. Venue
  maintenance brackets for ETH/SOL are conservative simulation assumptions.
  OI/CVD are not supplied by this local public kline feed; the strategy's
  configured optional OI fallback is retained.
- A closed browser tab does not stop the background service. The user should
  press Stop or close the server terminal. See
  `docs/operations/LOCAL_PAPER_WEB.md`. No real funds or exchange orders
  were used. No profitability, production readiness or independent acceptance
  is claimed.

Next owner: separate Tester should replay a longer prospective session and
audit journal/accounting; Independent Reviewer should inspect funding
availability, fill timing, risk gates and UI evidence labels. The owner decides
whether to accept a later gate or change the event-time data architecture.
