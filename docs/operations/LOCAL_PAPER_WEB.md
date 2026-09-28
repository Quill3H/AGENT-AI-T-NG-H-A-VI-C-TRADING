# Local Futures Paper Web — Windows

This is a local BTC/ETH/SOL USD-M Futures **simulation** using public Binance
market data. The initial account is 10,000 imaginary USDT. It has no trading
credentials or exchange order endpoint. Closing the browser tab does not stop
the backend. The Windows computer must remain on, awake and connected for
continuous observation.

## First run

Run `start-paper-web.cmd` from the repository root, optionally with a port
(`start-paper-web.cmd 8765`). It prepares a local Python environment, installs
the public WebSocket client if needed, builds the web bundle if missing, starts
the loopback server and opens `http://127.0.0.1:8765/`. On a genuinely new
journal, press **Khởi động bot** once. The backend then runs independently of
the browser tab.

The journal defaults to `crypto-paper-agent/data/paper_sessions`. Use the
**same** directory on every manual and scheduled launch. Existing
`persistent_state.json` and old JSONL evidence are deliberately locked as
`RECOVERY_REQUIRED`; preserve them for a separately reviewed migration.
Never remove or rename them merely to get another 10,000 USDT account.

## Start at Windows logon

After first-run dependencies and web build are present, run these commands
from `crypto-paper-agent` in PowerShell:

```powershell
.\scripts\windows\install-paper-task.ps1 -PythonPath '.venv-paper\Scripts\python.exe'
Start-ScheduledTask -TaskName CryptoPaperResearchBackend
Get-ScheduledTaskInfo -TaskName CryptoPaperResearchBackend
Get-Content data\paper_sessions\logs\paper-server.log -Wait
```

If the first run used a custom journal directory, pass the same
`-JournalDir 'D:\paper-data\session'` to the installer. A task starts when
that Windows user logs on. Actual logout/reboot and retry behavior on the
owner's Windows machine is not yet verified. The scripts do not disable sleep;
configure Windows to stay awake when plugged in for continuous observation.
`Stop-ScheduledTask` stops the service; `POST /api/stop` stops the simulated
bot but leaves HTTP running. Uninstall with
`.\scripts\windows\uninstall-paper-task.ps1` without deleting the journal.

Do not launch a second process with the same journal. The listener rejects
a duplicate port; a different port does not protect from duplicate writers.
The scheduled launcher does not install packages or rebuild the UI.

## Market, recovery and display

- The backend receives public Binance Futures `/market` WebSocket BTC/ETH/SOL
  1m and 15m klines. Only synchronized and REST-validated closed 15m events
  feed its paper broker; public REST also supplies 4h strategy data and funding
  provenance. Browser events cannot submit paper or exchange orders.
- The browser separately uses public `/market/ws/...@kline_1m` for display.
  It shows a live quote only while that socket receives fresh events. When the
  socket stops, a recent backend closed-candle price is labeled **REST nến
  đóng**. If stale/unreachable, the current price is unavailable. Chart
  history never becomes a current quote by itself.
- A v2 journal/checkpoint preserves the account, positions, orders, funding
  markers and risk state. A clean restart attempts exact restore and starts
  the stream worker automatically; order admission waits for fresh synchronized
  data. The stop button is terminal for that account. Incomplete, corrupt or
  old evidence, or an unprovable exposure gap, fails closed in
  `RECOVERY_REQUIRED` without an automatic account reset.

See [stream API](../../crypto-paper-agent/docs/operations/PAPER_STREAM_API.md)
and [recovery limits](../../crypto-paper-agent/docs/operations/PAPER_STREAM_RECOVERY_V2.md).
This build is a candidate pending real Windows restart and long-running stream
observation. A visible price or passing test does not establish trading
returns or 24/7 availability.
