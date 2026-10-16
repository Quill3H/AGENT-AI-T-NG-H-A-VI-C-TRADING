# Local Futures PAPER Web on Windows - v3

This is a local PAPER/RESEARCH simulation using public Binance USD-M Futures
data for BTCUSDT, ETHUSDT and SOLUSDT. It has no trading credentials, wallet,
live order or testnet order connection. Closing the browser does not stop the
backend. The computer must be on, awake and connected for current observation.
Outage replay is labeled REPLAY, not continuous live operation.

Documentation baseline: candidate `c89333516f9032155923375a876d0350deb6c267`
on `codex/windows-paper-replay`. Final verification and code-under-test SHA
are recorded in the [2026-10-17 handoff](../handover/2026-10-17-github-checkpoint.md);
this runbook is not independent acceptance.

## Account identity and preserved history

The owner explicitly approved a **new, separate experimental account**, initially
10,000 imaginary USDT. The default directory is:

```text
crypto-paper-agent/data/paper_accounts/windows-paper-v3
```

This is not continuation of old capital. The former
`crypto-paper-agent/data/paper_sessions` directory and its results remain
unchanged. Do not delete, rename or overwrite that evidence to make a bot start.
All manual and scheduled launches of this new account must use the same
directory. `-JournalDir` / `--journal-dir` selects an account, not a reset button.

The new account uses `paper.sqlite3`, immutable `paper-account.identity.json`
and the OS-backed `.paper-owner.lock`. Closed decision inputs, financial/risk/
trial events and checkpoints are retained once with checksums. Display ticks
and forming-candle updates are not archived on every receipt. There is no
automatic deletion of decision inputs or failed-trial history.

Missing, torn, corrupt, inconsistent or unknown account evidence means
`RECOVERY_REQUIRED`: preserve the directory and show its reason; new paper
orders are blocked. Unknown balances are `null`, never an invented zero or
10,000. Restarts do not allocate new capital. A valid account restores broker,
positions, pending orders, fees, funding, risk state and processing watermarks,
then replays every missing interval causally. A short recent REST window is not
used to declare an entire outage safe.

Legacy migration is narrowly checked and is not a general repair command.
Balance-only legacy evidence, reseeded indicators or unknown historical funding
must remain blocked pending separate reconciliation. The owner's separate v3
account authorization does not authorize resetting or repairing the old account.

## First manual run

From the repository root, double-click `start-paper-web.cmd`, or run:

```powershell
.\start-paper-web.cmd
```

The convenience launcher prepares missing dependencies, builds a missing UI
bundle and opens [the local web console](http://127.0.0.1:8765/). An existing
valid account is restored automatically. For a proven empty account, use the
web start control or `StartBot` below once. Repeating Start does not reset it.
The convenience launcher stays attached to its console: closing that console
terminates the service, unlike closing the browser tab.

Backend-only run, from `crypto-paper-agent`, using the existing environment:

```powershell
.\scripts\windows\run-paper-server.ps1 -Port 8765
```

This logs to `data\paper_accounts\windows-paper-v3\logs\paper-server.log` and
requests initial start only for a proven empty account. Persisted pause,
terminal stop or recovery failure is not overridden. The launcher refuses an
occupied port before account writes; the account lifetime lock also rejects a
second writer on another port or through an alias. Never delete a lock marker
to bypass this check. Process death releases the OS lock without deleting data.

The backend-only and scheduled launchers do not run `npm install` or build the
UI. If source UI changes, build deliberately once from
`crypto-paper-agent/web-preview` with `npm ci` if needed and `npm run build`.
Without a built bundle the API still works, but the web page is unavailable.
Use the project's `.venv-paper\Scripts\python.exe`; do not mix global Python
environments with a saved account's recipe/indicator convention.

## Install optional start at Windows logon

The following commands are operator actions, not actions this document has
performed. No Scheduled Task or power setting is installed or changed merely
by using this runbook. From `crypto-paper-agent`:

```powershell
.\scripts\windows\install-paper-task.ps1 -PythonPath '.venv-paper\Scripts\python.exe'
Start-ScheduledTask -TaskName CryptoPaperResearchBackend
.\scripts\windows\manage-paper-task.ps1 -Action Status
```

The task runs hidden as the current interactive Windows user, at that user's
logon, with at most three crash retries one minute apart. It is not an admin
service and does not start before user logon. Task-level `IgnoreNew`, exclusive
port binding and account ownership prevent concurrent writers. If a task with
the same name exists, the installer refuses to overwrite it; inspect its
account and remove it explicitly before changing registration.

For a custom approved account, pass the same `-JournalDir` absolute directory to
the installer, manual launcher and log-management commands. Do not select a
new empty directory to pretend an existing account continued. Installation
does not guarantee network access, 24/7 operation or power-loss durability.

## Status, logs and bot controls

Run these from `crypto-paper-agent`:

```powershell
.\scripts\windows\manage-paper-task.ps1 -Action Status
.\scripts\windows\manage-paper-task.ps1 -Action Logs
Get-Content -LiteralPath 'data\paper_accounts\windows-paper-v3\logs\paper-server.log' -Tail 100 -Wait
.\scripts\windows\manage-paper-task.ps1 -Action Pause
.\scripts\windows\manage-paper-task.ps1 -Action Resume
.\scripts\windows\manage-paper-task.ps1 -Action StartBot
.\scripts\windows\manage-paper-task.ps1 -Action StopBot
```

`Status` reads task state and `/api/health`. Logs retain startup/source/storage
errors. Control HTTP 202 means **queued**, not completed. Inspect
`/api/state.operation`, `operator_intent`, `status`, `error` and `risk_gate`;
do not treat an accepted request as proof of a fill, closure or successful
recovery. While the writer is busy, the API publishes a read-only checkpoint
and blocks admission rather than hanging or fabricating current prices.

| Action | Effect |
| --- | --- |
| StartBot | Start a proven empty account or attempt valid recovery; never reset capital or restart a terminal trial |
| Pause | Persist PAUSED; block entries while protective handling and modeled funding continue |
| Resume | Restore RUNNING on the same eligible trial after data/risk gates; cannot revive STOPPED |
| StopBot | Persist STOPPING, cancel/block entries and close through eligible paper execution; STOPPED only after reconciliation |
| DisableAndStop | Disable automatic task relaunch, then terminate only the verified backend service at the selected loopback port |
| Uninstall | Disable/stop and remove task registration; account data and logs remain |

An applied stop can remain STOPPING while prices or recovery inputs are
unavailable. It does not invent an exit at a stale price. StopBot leaves the
HTTP service available and is terminal for that trial; StartBot does not
silently allocate a replacement. Use Pause/Resume for a reversible pause.

To turn the service off and prevent the scheduled task from starting it again:

```powershell
.\scripts\windows\manage-paper-task.ps1 -Action DisableAndStop
```

This is distinct from closing a tab or pressing StopBot. For a planned outage,
first Pause and wait for its persisted operation to apply if new entries must
remain paused after restart. Disabling/stopping the process alone preserves
the last durable intent; a later deliberate service launch can replay a
previously RUNNING trial. If the port belongs to an unverified process, the
manager disables the task but refuses to terminate that process.

To remove auto-start without removing financial history:

```powershell
.\scripts\windows\uninstall-paper-task.ps1
```

If deliberately re-enabling an installed task later, inspect its registration
and account first, then use `Enable-ScheduledTask` and `Start-ScheduledTask`.
No installer/removal step deletes the legacy or new account directory.

## Market, funding and trial display

The backend receives public 1m/15m Futures WebSocket events, uses public
paginated REST to reconcile closed 15m batches and 4h signals, and processes
BTC/ETH/SOL on one shared paper account. Forming candles are display-only.
A 4h closed signal may execute no earlier than the following 15m open. Replay
does not expose downloaded future bars to earlier decisions. Reconnect clears
incomplete symbol batches and blocks prospective admission until verified
catch-up and a fresh synchronized stream batch are available.

API `current_prices` is authoritative for current quote validity. Stale,
disconnected, future/invalid or busy state returns `price=null, valid=false`;
chart history and `last_closed_15m_price` must not be relabeled live.
Account equity is valued at `account_as_of_utc`, the last reconciled closed
15m boundary, not continuously marked by browser ticks. The browser's own
public chart socket is visualization only and cannot control paper decisions.

This named experiment uses **FIXED_SIMULATED** funding: positive 0.01% per
settlement at 07:00, 15:00 and 23:00 UTC+07:00 (00:00, 08:00, 16:00 UTC).
LONG pays and SHORT receives on eligible position notional using the declared
`CANDLE_OPEN` proxy. This is not observed Binance funding; real-source funding
provenance rules in other modes remain fail-closed. Fees, slippage, collateral,
liquidation, mandatory stops, maximum 5x leverage and Circuit Breakers remain.

Trend Following is the initial rulebook. Breakout & Retest can be promoted only
by the bounded causal research gates; SMC/PPO and Funding Arbitrage are not
active in this account. Do not label registered candidates active strategies.
Equity strictly below 5,000 marks the trial FAILED; exactly 5,000 does not.
At or above 15,000, TARGET_REACHED is recorded once and the same trial continues.
Neither event is an independent profitability verdict. A replacement 10,000
imaginary USDT allocation requires a reconciled failed trial and eligible
research, with all previous losses/trials and total supplied capital visible.
Sparse/failed research means no automatic capital reset or forced trades.

## Windows sleep and storage

To keep this PC awake **while plugged in**, open Windows Settings, search for
`Power & battery` / `Power & sleep`, then open the screen/sleep timeout section.
Set the plugged-in **sleep** timeout to **Never**. The screen-off timeout can
stay enabled. Wording varies by Windows version; do not change battery behavior
or lid-close behavior unintentionally. A closed laptop lid may still suspend
the process depending on its separate setting. These are explicit operator
changes; the project does not change them automatically. Replay can catch up
after sleep but cannot make the intervening simulated fills actual live fills.

The C: system disk reached zero free space during candidate QA; tests were
rerun using only process-local TEMP/TMP on G:. No global temporary files were
deleted and no permanent environment settings were changed. Maintain free
space on both Windows and the account drive; storage failures must stay
blocked rather than silently losing a checkpoint. An occupied port, busy
account or missing environment is reported in logs; inspect before retrying.

For backup, disable/stop the service first and preserve the **entire** account
directory, including SQLite WAL/SHM files if present and the identity file.
Copying only a live `paper.sqlite3` file is not a verified backup. Do not edit
checksums, truncate a journal or downgrade code against a newer account store.
An incompatible config/source/recipe restore stays RECOVERY_REQUIRED. Task
removal is the operational rollback; code rollback requires verified storage
compatibility and does not authorize a new account/reset.

## Contract and remaining verification

See the [v3 API contract](../../crypto-paper-agent/docs/operations/PAPER_REPLAY_API_V3.md),
[schema](../../crypto-paper-agent/docs/operations/paper_replay_state_v3.schema.json)
and [six synthetic examples](../../crypto-paper-agent/docs/operations/paper_replay_api_examples_v3.json).
These examples are fixtures, not market results. The prior
[v2 contract](../../crypto-paper-agent/docs/operations/PAPER_STREAM_API.md)
is retained for legacy evidence and is not this server's API.

Actual task installation/logon, machine reboot, power-loss durability and
24/7 public operation remain NOT_VERIFIED unless separately recorded with
runtime evidence. Short public-price reception or fixture restart tests do not
prove those checks. Full 360-day empirical research/promotion is not established
by fixture gates. ETH/SOL maintenance brackets are conservative simulated
assumptions, not venue-verified brackets. The existing desktop-oriented UI
retains a wide layout; small screens require horizontal scrolling. This is
an experimental candidate, not production-ready or independently accepted.
