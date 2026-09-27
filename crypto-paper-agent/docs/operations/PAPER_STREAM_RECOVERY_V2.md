# Paper stream recovery v2

This supplement is part of the `/api/state` and `/api/health` contract.

## Restart states

The backend stores a version-2 machine checkpoint beside the JSONL journal. It
contains the paper broker ledger, pending orders, open positions, order and
trade IDs, funding idempotency keys, circuit-breaker clock and streak, and the
Trend strategy setup/watermarks. The checkpoint is accepted only when its
checksum, config hash, accounting equations and rendered API state all agree.

On a normal Windows process or task restart, startup performs this sequence:

1. Read the existing checkpoint and journal without rewriting either file.
2. Rebuild the broker and strategy objects from the typed data-only checkpoint.
3. Fetch public closed USD-M 15m bars for BTCUSDT, ETHUSDT and SOLUSDT. The
   bars must be current, ordered, synchronized, and at or after the saved
   watermark.
4. If the boundary is exact, report `WAITING_CONNECTION` and wait for one new
   synchronized WebSocket batch before setting `SCANNING`.
5. If a gap is present, only a flat account with no pending order and no
   funding obligation may use the documented no-trade rebaseline path. Any
   open exposure, pending order, missing funding event, stale source or
   accounting mismatch remains `RECOVERY_REQUIRED`.

`RECOVERY_REQUIRED` has `risk_gate.admission_open=false`; financial values are
`null` when the saved account cannot be trusted. The backend never creates a
new 10,000 USDT account, drops an old position, fills a pending order from a
recent candle window, or backdates funding. Legacy version-1 evidence has no
machine checkpoint and remains locked until a separately reviewed migration.

## Stop versus process shutdown

`POST /api/stop` is an operator action that ends the paper session and retains
open exposure in a terminal `STOPPED` state. It is idempotent and does not
close positions at an invented price.

Closing the backend process or Scheduled Task writes a `PROCESS_STOP` checkpoint
without changing the paper session to `STOPPED`. The next service start can
therefore attempt exact recovery. A hard power loss leaves the last committed
checkpoint; an incomplete `PAPER_INPUT` or torn checkpoint fails closed.

## Windows checklist

Run the backend independently of the browser:

```powershell
cd crypto-paper-agent
.\scripts\windows\run-paper-server.ps1 -Port 8765 -PythonPath '.venv-paper\Scripts\python.exe' -JournalDir 'D:\paper-data\session'
```

Install the optional logon task once, using the same journal path:

```powershell
.\scripts\windows\install-paper-task.ps1 -PythonPath '.venv-paper\Scripts\python.exe' -JournalDir 'D:\paper-data\session'
Start-ScheduledTask -TaskName CryptoPaperResearchBackend
Get-ScheduledTaskInfo -TaskName CryptoPaperResearchBackend
Get-Content data\paper_sessions\logs\paper-server.log -Wait
Stop-ScheduledTask -TaskName CryptoPaperResearchBackend
.\scripts\windows\uninstall-paper-task.ps1
```

The launcher refuses an occupied port and never initializes a second account.
The task is configured to ignore duplicate instances and retry a failed
process. It does not install dependencies or run `npm` at startup. The browser
may close while the backend continues on `127.0.0.1:8765`.

To keep the machine awake while plugged in, open **Settings > System > Power &
battery > Screen and sleep** and set the plugged-in sleep timeout to **Never**.
This is an operator instruction; the project scripts do not change Windows
power settings. Confirm the setting manually before relying on overnight paper
observation.

All market data remains public Binance USD-M data. All account values and
orders remain simulated. No API key, wallet, signing, live order or testnet
operation is used.
