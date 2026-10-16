# Windows API and web handoff implementation plan

## Current publication checkpoint - 2026-10-17

Implementation and regression files are included in the GitHub candidate.
Use the [current handoff](../../handover/2026-10-17-github-checkpoint.md) for
the repaired code SHA, fresh offline/web/build results and remaining gates.
The older combined verification checklist below is historical: unperformed
clean-checkout/browser/public/scheduled-operation checks remain NOT_VERIFIED.
Independent review and owner acceptance remain pending.

## Prior execution addendum - 2026-10-02

S5 implementation is present as an **AUTHOR_SELF_REVIEWED candidate**. Later
express owner permission allows helper agents; the inline-only instruction and
task checklists below are preserved as the original plan, not final acceptance.
Helper contributions do not make testing/review independently accepted.

- [x] Responsive API v3 read snapshots, null stale current prices, truthful
  account/source/replay timestamps, history pages and asynchronous control
  operations are connected to the compact causal session.
- [x] Immutable OPERATOR_REQUEST acceptance time is captured before the longer
  writer wait; atomic OPERATOR_INTENT application drains at safe batch/promotion
  boundaries. Unsupported/unverified controls are refused, not silently applied.
- [x] V3 JSON schema and six backend-generated SYNTHETIC examples are present;
  existing UI renders backend funding/trial/intent/operation rather than PnL math.
- [x] Windows one-writer launch/account lock, hidden logon task/retries, manager
  status/log/pause/resume/StopBot/DisableAndStop/uninstall and launcher verification
  scripts/tests are present. No automatic per-boot npm install/UI build.
- [x] Operations/API documents explain new separate 10,000 imaginary USDT
  `windows-paper-v3` profile, preserved legacy data and manual no-sleep settings.
- [ ] Final repaired code SHA and same-commit focused/full/clean/API/web/build/
  browser/Windows/public results: pending root finalization; checkpoint
  `c89333516f9032155923375a876d0350deb6c267` is earlier, not final evidence.
- [ ] Owner-profile startup and optional announced task registration: separate
  post-verification actions, not yet assumed. No power setting has been changed.
- [ ] Actual task/logon, machine reboot, power loss, 24/7 public operation and
  full mobile acceptance: NOT_VERIFIED. The existing wide UI requires scrolling.

Earlier disk exhaustion is historical; later read-only C: free-space check
reported 4.34 GB. QA's G: TEMP/TMP override was process-local; no global temp
deletion or permanent setting change. Report zero real signals/orders honestly;
separate actual public observations from synthetic fills and UI fixtures.

> **For agentic workers:** Use superpowers:executing-plans inline; no subagents.

**Goal:** Run the compact causal PAPER account independently of tabs, with responsive loopback controls and inspectable Windows operations.

**Architecture:** The v3 session replaces the server's new-account adapter, retaining the legacy verifier. A single command worker serializes controls; a published read snapshot keeps health/state responsive during history/research work and closes admission while busy. The stream owns public transport only. UI retains its existing layout and renders authoritative v3 fields.

**Tech Stack:** Python HTTP/SQLite, PowerShell Scheduled Tasks, React/Vite, pytest/Vitest, browser verification.

**Spec:** `docs/superpowers/specs/2026-10-01-windows-paper-replay-design.md`, sections 9-10.

## Global constraints

- Loopback only; no keys, live/testnet orders, wallet, paid resources or main merge.
- Keep owner evidence/dirty files. Test using temporary accounts, never an implicit owner reset.
- Start/pause/resume/stop are idempotent; Stop keeps transport until reconciled STOPPED.
- No npm/build per boot. Task install/power changes require telling the owner first.
- Current price must be fresh public data, replay is labeled and cannot claim realtime uptime.

## Task 1: Responsive session and stream admission

**Files:** `crypto-paper-agent/src/paper/replay_session.py`, `compact_store.py`, `public_stream.py`; `tests/test_paper_replay_recovery.py`.

**Interfaces:** `state()` is nonblocking, cached while the single account writer is busy. `history(cursor,limit)` provides stable pages. Stream callbacks validate numeric fields, event/receipt/availability and duplicate revisions at the decision seam.

- [ ] RED: stalled REST keeps GET state responsive and admission closed; stale/future/revised event blocks before mutation; mismatched symbol batches require reconnect.

```python
assert elapsed < 1
assert state['backend_busy'] is True
assert state['risk_gate']['admission_open'] is False
```

- [ ] GREEN: verified committed snapshots only, no concurrent account writes; chart fetching cannot hold the execution lock. Store full receipt integrity independently of canonical duplicate identity.
- [ ] Run focused session/stream/store tests and the full offline suite.

## Task 2: Loopback command worker and v3 contract

**Files:** `src/paper/local_server.py`, `tests/test_paper_replay_server.py`, existing server/integration tests, `scripts/run_local_paper_web.py`.

**Interfaces:** `/api/start`, `/api/pause`, `/api/resume`, `/api/stop` accept no body. Commands return applied state or 202/PENDING with a stable operation ID; `/api/state`/health expose completion/failure. `/api/history?cursor=0&limit=100` never accepts metrics/promotion. Existing host/origin/body protections remain.

- [ ] RED: slow Start returns promptly, duplicate Start does not allocate twice, pause survives restart, Stop does not kill the feed before closing exposure, malformed history returns400, source failure remains visible, shutdown serializes worker ownership.

```python
assert reply.status_code in (200, 202)
assert len(account_start_events) == 1
assert state['api_version'] == 3
```

- [ ] GREEN: wire `PaperReplaySession`, one bounded command worker, persistent service shutdown without changing bot intent. Add explicit API failure/status fields.
- [ ] Publish v3 JSON Schema and backend-generated synthetic examples (normal/disconnected/data-blocked/restart/recovery/paused/replay). Validate every example with jsonschema.

## Task 3: Windows lifecycle and truthful UI

**Files:** `scripts/windows/run-paper-server.ps1`, `install-paper-task.ps1`, `uninstall-paper-task.ps1`; new `manage-paper-task.ps1`; `tests/test_paper_windows_lifecycle.py`; web contract/display components and tests only (no redesign).

**Interfaces:** manager `Status`, `Logs`, `Pause`, `Resume`, `StopBot`, `DisableAndStop`, `Uninstall`; task current-user logon, hidden, IgnoreNew, three crash retries. DisableAndStop disables before stopping service and preserves account. UI broker-owned trial/equity/current-price/funding/replay fields.

- [ ] RED: actual Windows duplicate port/account writer, process termination/restart, preserved SQLite/evidence; PowerShell parses and never installs without explicit command. Web tests for202, STOPPING, paused/funding/trial labels and null stale prices.
- [ ] GREEN: hidden launch, account-local startup logs, bounded retries, no capital reset. StopBot remains different from task disable/service termination.
- [ ] Run `npm test`, `npm run build`; serve a temporary verified account, inspect browser desktop/mobile main flow and errors.

## Task 4: Frozen candidate and evidence

**Files:** scoped ADR, API/operations docs, `docs/PROJECT_STATE.md`, completion/self-review evidence (leave dirty INDEX alone).

- [ ] Run real public WS/REST on Windows with temporary paper account; record0orders if no signal, BLOCKED if transport fails.
- [ ] Self-review all order/storage/control paths; fix Critical/High, record remaining limits.
- [ ] Commit explicit code/test files, verify that SHA with offline/network/historical/web/build/clean-checkout/external-CWD gates. Documentation pins code-under-test SHA. Push scoped branch only, no force/main merge.
- [ ] Handoff exact SHAs/files/commands, local URL, task install/status/log/disable/uninstall and power-settings instructions, with unverified checks clearly labeled.
