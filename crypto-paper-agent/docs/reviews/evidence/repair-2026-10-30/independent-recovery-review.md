# Independent recovery composition review - 2026-10-30

Reviewer: repair_review agent, against uncommitted repair on main base 56382df63f0a58ba249d39b005ad97e90cd30150. Read-only production/frontend review; no source/script edits or commits. Root owns full core/year replay and Windows process lifecycle runs.

## Finding

P2: LocalPaperPanel.jsx disables all Start/Pause/Resume/Stop buttons when state.backend_busy is true. The backend explicitly supports durable request-time Pause/Stop admission while the account writer performs replay/research. The UI therefore prevents the operator from using those controls during a potentially long backfill/research operation. Keep Start blocked while busy, but allow supported durable Pause/Stop with a valid account contract and surface the pending operation.

The same global blocked condition includes chart errors. Promise.all couples /api/state and /api/chart; a public chart failure prevents a fresh healthy local account snapshot from being adopted and disables Pause/Stop despite a running local account. Separate chart-read errors from account/command availability. Preserve visible stale-snapshot status, and do not let public chart availability govern operator Stop/Pause.

First frontend follow-up separated chart errors and removed backend_busy from Pause/Resume/Stop blocking, but Promise.allSettled still awaited both reads before publishing state and clearing busy. An unresolved chart request therefore still blocked controls despite an already-returned valid account snapshot. The read paths must publish independently and chart loading must not gate account command admission. This is particularly relevant because backend get_chart waits on the session writer lock during research/replay.

## Fresh independent tests

From crypto-paper-agent:

```powershell
$env:PYTHONUTF8='1'
../.venv/Scripts/python.exe -m pytest tests/test_paper_replay_recovery.py tests/test_paper_recovery_review.py tests/test_paper_store_commit_integrity.py tests/test_paper_request_time_controls.py tests/test_paper_research_control_race.py tests/test_paper_scheduled_partial_restore.py tests/test_paper_futures_api_contract.py tests/test_local_paper_server.py tests/test_paper_replay_server.py -q --tb=short --basetemp ../../tmp/recovery-review-1030
```

Result: **85 passed in 32.28s**, no skips/deselections. Loopback HTTP tests use offline/injected public sources, not live market data or exchange actions.

## Source review

- OS account ownership lock persists for the process lifetime and is independent of port ownership; recovery never silently creates fresh capital over orphan evidence.
- Compact store binds immutable account/config identity to SQLite, verifies checksum roots, canonical input keys and commit chains, and commits checkpoint/inputs/events together. Persist/adopt occurs after successful commit; partial failures leave recovery-required evidence.
- Current main broker gap policy is a static checked timedelta; supported microseconds serialize exactly. Compact restore checks broker field set, risk configuration, typed ledgers, accounting/exposure reconciliation, funding event watermarks, transients and synchronized runner/broker processing clocks.
- Current synchronized broker scheduling is preserved. Replay forks candidate machine state and uses one batch across symbols; controls accepted durably under the storage lock are drained before the next financial commit. Research promotion is blocked absent an independently supported evidence/risk contract, including fixed-simulated funding. Existing positive numerical diagnostics do not allocate fresh capital through the session API.
- HTTP listens on 127.0.0.1, validates Host and mutating Origin, rejects bodies/unrecognized controls, and serves paths resolved under frontend dist. /api/chart returns the closed-only PR5 contract with source_time_utc and keeps provisional current prices separate.
- Frontend opt-in requires explicit Connect and explicit command clicks; it has no mount-time Start and preserves existing main app content. The busy/chart control issue above remains to fix and independently recheck.

Limits: this is scoped engineering review and tests, not full formal verification, owner gate acceptance, historical profitability or prospective uptime evidence. Actual Windows lifecycle was root-run, not rerun by this reviewer. Full-year synthetic replay is diagnostic only. Original static artifact claims remain false evidence and must be corrected by an errata, never rewritten to manufacture a pass. Initial verdict: CHANGES_REQUIRED for the frontend controls finding.

## Final follow-up

The frontend now uses separate account/control and chart request pending state. Account refresh awaits only /api/state, while a fully caught independent refreshChart publishes candles/loading/errors separately. Start remains blocked during backend_busy; Pause/Resume/Stop work with a valid account snapshot while the writer is busy. Public chart 502, malformed/provisional data or an unresolved chart request cannot suppress a healthy account snapshot or prevent those durable commands. Account/command failure still retains a visibly stale snapshot and requires a successful refresh before further actions. Pending backend operation status is displayed without claiming application success.

Reviewed the connected implementation and the new busy-writer, failed-chart and unresolved-chart tests. Fresh independent `npm.cmd test`: **13 passed in two test files**, no skipped tests, duration 1.30s. Fresh independent `npm.cmd run build`: **exit 0**, 19 modules transformed. Backend source remained untouched during this follow-up.

Final scoped verdict: **no remaining actionable finding** in this recovery/API/frontend review. The original P2 finding and first incomplete follow-up are preserved above as review history. The 85 offline backend passes and 13 frontend passes validate this implementation scope only; the limits above remain.

Reviewed SHA256 identities:

```text
src/paper/causal_runner.py 5f78a695366016f52e95ce62995cd888c6192ad8fd0e487ddb1a4fe20d0f4912
src/paper/replay_session.py a964e4ffe834bfca4db35c690213a6137126d7a65fd7ee6613bcff19ca914a1e
src/paper/recovery_state.py 62b6e8ba4decffaf1460f6e3ef5d2e0694bf2a2f908cccc53b3077dbe328dfaf
src/paper/compact_store.py 0eef217191b926af4a4747305e11734f13208fc6c34f1a0a35f53d3591f9416e
src/paper/local_server.py b580995d4592f998b8b95197eceec44c308d51b9b5563fea98a0fe70b715c79e
web-preview/src/LocalPaperPanel.jsx 9574fce29ffde49b35e7487615296ff0ba6f7b4a1fb48ebafdd9e2f8f1e8d0e9
```
