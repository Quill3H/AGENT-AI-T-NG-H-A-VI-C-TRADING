# Recovery repair and UI-only integration — 2026-09-27

AUTHOR_SELF_REVIEWED / INDEPENDENT_REVIEWER_NOT_VERIFIED. Candidate for review,
not gate acceptance, economic validation or real-money readiness.

## Exact identities

- Requested backend base: `6bdaa0dd1d91d329a3983311088aeb33ac0c2fa7`.
- Repaired backend branch: `codex/paper-stream-backend`,
  `37bf75796ade54c18827811dbd58a0b629539f25`.
- UI checkpoint requested: `c44f6b2e5d6d5a023463f1a205716f1867e7075c`.
  GitHub contained a newer explicit review fix, used as UI source:
  `bab1f92371a520151a5dbfe04349dc9e3265ae01`.
- Integration branch: `codex/paper-futures-integration`.
- Code-under-test commit: `a2b49c0500de2c1675fe35a34305114b007d3fb2`.
- Documentation commit: see Git history and final handoff; this document does
  not invent its own SHA.
- Main remains `fe1c1330d913e78239db575ff8433cf069fe1b01`.

No whole web-app branch merge. Imported only App.jsx, App.test.jsx,
CandlestickChart.jsx and styles.css. The latter two match the UI source exactly.
The web branch's persistence.py, local_server.py, live_session.py, entrypoint
and autostart scripts were not imported. There is no persistence.py in this
candidate. Backend live_session.py is the repaired WebSocket implementation;
run_local_paper_web.py is unchanged from the backend base. The integration merge
joins only the backend's follow-up snapshot isolation fix, not the web branch.
No core broker, strategy or risk configuration changed.

## Findings reproduced and resolved

| Severity | Confirmed defect | Repair and evidence |
| --- | --- | --- |
| High | Orphan state JSON, missing checkpoint, empty/torn journal could initialize or display default 10,000 | DurableJournal requires checkpoint/journal checksum, identity and view agreement. Inconsistent evidence returns RECOVERY_REQUIRED with null financial values; original bytes remain unchanged. Thirteen initial regression cases failed before repair. |
| High | Restart could lose the distinction between known historical exposure and unknown current account | All stored accounts are read-only. Complete durable views preserve positions, pending orders, fees, funding and breaker view; no broker is restored. Unknown evidence reports recovery.account_known=false. Ninety-day downtime tests do not make any REST request. |
| High | Symbol close mismatch disabled session callback processing but left a healthy socket feeding an inert bot | Explicit reconnect_required propagates to transport, which closes the socket and uses its reconnect loop. Terminal quarantine/recovery closes the stream. Tests cover callback closure, partial-batch discard, reconnect and duplicate processing. |
| High | Closed stream prices were not reconciled with REST before execution | Compare closed-bar times/OHLCV before broker mutation; disagreement quarantines. Synthetic broker test still enters, exits and reconciles accounting. |
| Medium | Snapshot object referenced mutable provisional market data | Freeze a JSON copy for durable checkpoints. Regression demonstrated that provisional updates otherwise made a valid restart lose its historical view. |
| Medium | Malformed Origin port crashed HTTP handler; API exceptions used another state shape | Reject malformed Origin and transfer-encoded/body POSTs. Failed action returns full state and HTTP 503. Real loopback HTTP tests exercise these paths. |
| Medium | Windows port precheck alone has a concurrent-start race | Server socket uses exclusive Windows bind, no address reuse. A second bind fails before constructing a session; launcher exits 2 on occupied port without creating an account. |
| Medium | UI substituted unknown collateral/PnL with zero and breaker with normal; Stop unavailable during disconnect | Minimal contract adaptation preserves null, shows unknown breaker, permits Stop while WAITING_CONNECTION, and reads canonical collateral field. No layout redesign. |
| Medium | Imported chart had zero height because JSX class did not select existing flex layout | Added existing center-panel class; browser assertion reproduced height 0, then measured 898 x 768.5. Existing CSS unchanged. |
| Low | Static strategy label claimed it was running during recovery; 90-minute candle statistics labeled 24h | Labels now describe configured strategy and supplied candle window. No new price/PnL calculation or strategy change. |

## Final commands and results

Commands below run from crypto-paper-agent unless noted. Python executable was
the existing primary checkout's `.venv-paper/Scripts/python.exe` (Python 3.12.14).
QA dependencies: websocket-client 1.9.2, jsonschema 4.26.0; schema validator
dependencies are pinned in requirements-repair-lock.txt. Browser probe additionally
used Playwright 1.63.0 and installed Edge 154.0.4258.37.

| Exact command / action | Result |
| --- | --- |
| `python -m pytest -p no:cacheprovider -q` on code-under-test SHA | 503 passed, 0 failed, 2 skipped, 0 deselected, 183.74 s. Includes all 5 network tests. Two existing Gymnasium warnings. |
| `npm test -- --reporter=dot` in web-preview on same SHA | 18 passed, 0 failed, 2 files, 6.17 s |
| `npm run build` in web-preview on same SHA | Vite build passed, 23 modules, 306 ms |
| `python scripts/verify_paper_integration.py --output-dir data/paper_sessions/qa-a2b49c0 --seconds 25` on same SHA | API/start/stop/restart and browser recovery lock passed. Public stream BLOCKED; no frame. 0 simulated orders / 0 trades. |
| Windows lifecycle tests, included in full suite | Actual CLI from external CWD, two process startups using corrupt evidence, no reset; actual PowerShell launcher duplicate-port rejection passed. |
| PowerShell AST parse of three scripts/windows files | 0 parse errors |
| JSON Schema validation, included in full suite | Live generated states and five full committed synthetic examples pass schema plus timestamp format checks. |
| `git diff --check 6bdaa0d..HEAD` | Passed |

Earlier RED runs were preserved in tool history: 13 recovery/reconnect failures;
4 additional disk/transport/bool failures; malformed-Origin failure and missing
server factory; stream-vs-REST mismatch; three REST numeric/future cases;
snapshot mutation; UI unknown/Stop/strategy label; actual chart height 0.
These were followed by green focused runs before integration.

## Public observation and browser evidence

The 25-second bounded attempt obtained public REST warmup for BTC/ETH/SOL but
no validated WebSocket kline frame. Admission remained closed in all 24 API
observations. This is BLOCKED live-feed validation, not a successful realtime
trading experiment. The unchanged funding fail-closed policy remains binding.

- Session: `20260927T164429-e670d8d0`.
- Config SHA-256: `cef9da4753e541bff374ddb237348861b82013c47e47ede9d203d0594c6bf63f`.
- Journal SHA-256 after stop/restart:
  `daf31a366dd74c56b8e6c9decb8054d4e20d32f9936a9b9f847a5be7e272086c`.
- Local evidence directory: `data/paper_sessions/qa-a2b49c0/` contains raw journal,
  checkpoint, API responses, server log, evidence.json and two browser PNGs.
  Raw market data and images are local artifacts, not claimed Git-synchronized.
- Browser: no JavaScript page errors; one console/network
  `net::ERR_CONNECTION_REFUSED` from an API poll during the deliberate process
  restart (delivered in the after_restart phase). UI subsequently fetched state,
  rendered the prior account and disabled Start. This error is disclosed, not
  counted as a clean uninterrupted-network run.
- Existing operator listener on 127.0.0.1:8765 was preserved. QA used an isolated
  loopback port. Reading the operator's legacy journal directory returned
  RECOVERY_REQUIRED/UNKNOWN without modifying it.

## Files and API handoff

Backend: src/paper/durable_journal.py (new), live_session.py, local_server.py,
public_stream.py. Tests: test_paper_recovery_review.py, test_paper_api_examples.py,
test_paper_windows_lifecycle.py (new), test_local_paper_session.py,
test_local_paper_server.py, test_local_paper_stream.py. QA reproduction:
scripts/verify_paper_integration.py. Dependency manifests: requirements.txt and
requirements-repair-lock.txt. UI: four files named above, with minimal App
contract fixes and corresponding tests.

Contract: docs/operations/PAPER_STREAM_API.md,
paper_stream_state.schema.json, paper_stream_api_examples.json. Plan:
docs/superpowers/plans/2026-09-27-paper-recovery-review-repair.md.
Financial fields are USDT simulation; market quotes are public USD-M Futures.
`recovery.view=LAST_DURABLE_SNAPSHOT` is historical, unreconciled evidence.
`UNKNOWN` means money/exposure cannot be established; do not substitute zero.

## Windows run / stop / removal

Build UI once using `npm ci` and `npm run build` in web-preview. Use the repaired
backend checkout, not the primary UI branch's Python server. In crypto-paper-agent:

```powershell
.\scripts\windows\run-paper-server.ps1 -Port 8765 -PythonPath '<existing venv python.exe>' -JournalDir '<existing operator journal directory>'
```

An occupied port is refused. Do not start another account with an empty directory
as a workaround. The legacy operator journal is deliberately read-only until an
explicitly reviewed migration/reconciliation is available. For an independent
QA account, choose an explicitly labeled NEW directory and unused port.

`POST /api/stop` stops the session and retains open positions. Ctrl+C in a manual
server stops the process. Optional login task: install-paper-task.ps1 accepts
the same PythonPath/JournalDir; Start-ScheduledTask/Stop-ScheduledTask operate
CryptoPaperResearchBackend. uninstall-paper-task.ps1 removes that task while
preserving journals/logs. No automatic npm/build runs through this launcher.
Task registration, actual Windows logout/reboot and scheduler retries were not
performed on the owner's machine; only script syntax and executable startup,
restart, API and duplicate-port behavior were checked.

Rollback: stop the candidate server/task, keep the complete journal directory,
and switch back to a previously reviewed code branch in a clean checkout.
Do not launch the rejected web persistence.py implementation against this account.
No main merge or force push is part of this handoff.

## Remaining limits and next reviewer

Exact running-broker restoration remains NOT_IMPLEMENTED by design; the owner
explicitly permits read-only recovery when exact reconstruction is unavailable.
No resume/reset endpoint exists. Complete deletion of all account evidence or
pointing at a different empty directory cannot be distinguished from first use;
preserve backups and the configured journal path. Checksums detect inconsistency,
not a malicious actor rewriting both files. Journal verification currently reads
the complete journal per append; long-running journal compaction/performance is
future work and must preserve the evidence chain.

Live-feed/network verification is BLOCKED. Exact funding provenance across a
boundary can quarantine an otherwise active paper session; no approximation or
backdating was added. Bar-based fills and conservative ETH/SOL maintenance
brackets remain simulation limits. Windows login-trigger behavior is NOT_VERIFIED.
Mobile redesign and visual polish remain owned by Antigravity.

Independent Reviewer should inspect the code-under-test SHA, rerun corruption /
open-position / funding / reconnect cases, and repeat a bounded public stream
observation on a working network. No independent acceptance, profitability or
real/testnet trading claim is made. No key, wallet, signing or order endpoint used.
