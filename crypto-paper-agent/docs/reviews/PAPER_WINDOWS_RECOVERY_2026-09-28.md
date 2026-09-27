# Windows paper backend recovery handoff

Status: `AUTHOR_SELF_REVIEWED / INDEPENDENT_REVIEWER_NOT_VERIFIED`. This is a
review candidate; the owner decides acceptance. The system remains a local
Binance USD-M **paper/research** simulator.

## Git identity

- Branch: `codex/paper-windows-recovery`
- Code and tests commit: `c47249258756f6f3c7e5deb3352438add32cd2cf`
- Base integration commit: `2118e2cae327b005b314fc801db1a9fcafcc6149`
- `main` is untouched at `fe1c1330d913e78239db575ff8433cf069fe1b01` at the start of this work.
- Documentation commit is the later commit in this branch and is recorded by Git.

## Confirmed repair

The backend now writes a version-2, JSON-only machine checkpoint with every
durable state view. It includes broker account and ledger values, deterministic
ID counters, positions, pending orders and closes, funding idempotency keys,
circuit-breaker state and clock, and each Trend strategy setup/watermark. A
strict allowlist decoder rebuilds those objects and re-runs accounting
invariants before exposing the broker.

`LocalPaperSession.reconcile_resume()` validates the checkpoint against the
config hash and saved API view, checks current closed Binance public 15m bars for
BTC/ETH/SOL, and enters `WAITING_CONNECTION` until a fresh synchronized stream
batch. Exposure, pending orders, funding obligations, stale or misaligned bars,
legacy evidence, torn writes and accounting mismatch remain
`RECOVERY_REQUIRED`; no 10,000 USDT reset, position inference, duplicate fill or
backdated funding is possible. Flat accounts may use the existing no-trade
rebaseline path only when its REST window is contiguous and current.

The HTTP server attempts this exact resume at startup. Its process shutdown
records `PROCESS_STOP` and preserves resumable status; `POST /api/stop` remains
an idempotent terminal bot stop. The Windows launcher retains exclusive port
binding and the scheduled task uses one journal path with restart retries.

## Files changed

Code/test commit: `src/paper/recovery_state.py`, `src/paper/durable_journal.py`,
`src/paper/live_session.py`, `src/paper/local_server.py`,
`tests/test_paper_resume.py`, `tests/test_local_paper_server.py`, and
`start-paper-web.cmd`.

Documentation commit: `docs/operations/PAPER_STREAM_API.md`,
`docs/operations/PAPER_STREAM_RECOVERY_V2.md`,
`docs/operations/LOCAL_PAPER_WEB.md`, and the saved implementation plan.

## Tests

All commands used the existing Windows Python 3.12.14 environment
`.venv-paper\Scripts\python.exe` from `crypto-paper-agent`.

| Command | Result |
| --- | --- |
| `python -m pytest -p no:cacheprovider -m "not network" -q` | `505 passed, 2 skipped, 5 deselected`, 198.05 s |
| `python -m pytest -p no:cacheprovider -m network -q` | `5 passed, 507 deselected`, 18.42 s |
| Focused recovery/API/session tests | `64 passed`, 10.64 s |
| PowerShell AST parse of `scripts/windows/*.ps1` | 3 scripts parsed, 0 errors |
| `git diff --check` | pass before code commit |

The regression tests cover flat restart, open position, pending order, funding
and long gap, corrupt/torn checkpoint, repeated restart, duplicate stream,
occupied Windows port, API health/start/stop and source failure. The five
network tests passed in this environment; this does not establish 24/7 stream
availability or profitability.

## Windows operation

Use the same `-JournalDir` on every manual and scheduled launch:

```powershell
cd crypto-paper-agent
.\scripts\windows\run-paper-server.ps1 -Port 8765 -PythonPath '.venv-paper\Scripts\python.exe' -JournalDir 'D:\paper-data\session'
.\scripts\windows\install-paper-task.ps1 -PythonPath '.venv-paper\Scripts\python.exe' -JournalDir 'D:\paper-data\session'
Start-ScheduledTask -TaskName CryptoPaperResearchBackend
Get-ScheduledTaskInfo -TaskName CryptoPaperResearchBackend
Get-Content data\paper_sessions\logs\paper-server.log -Wait
Stop-ScheduledTask -TaskName CryptoPaperResearchBackend
.\scripts\windows\uninstall-paper-task.ps1
```

The service is independent of the browser. Set Windows plugged-in sleep to
`Never` manually in Settings; no script changes power settings. `POST
/api/stop` stops the simulated bot but does not remove the service task.

## Remaining limits

Legacy version-1 journals have no exact machine image and require a separately
reviewed migration. A hard power loss is recoverable only up to the last
committed checkpoint; an in-flight journal mutation is intentionally locked.
Exact restoration has not been independently reviewed. Actual Windows logout,
reboot and Task Scheduler retry behavior on the owner's machine remains
`NOT_VERIFIED`. Public WebSocket observations are bounded test evidence, not a
24/7 paper result. No profitability, economic validation, live order, testnet,
credential or private-key claim is made.
