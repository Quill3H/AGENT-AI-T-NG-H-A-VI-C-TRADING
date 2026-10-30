# Local PAPER runtime

This is a paper-only loopback application. It uses public Binance USD-M price
data after an explicit connection/start request. It never submits exchange or
testnet orders and needs no trading credentials. Simulated fills, fixed funding
and retrospective replay do not establish profitability or market validation.

Build the existing frontend from `crypto-paper-agent/web-preview` with
`npm ci` then `npm run build`. From `crypto-paper-agent`, run:

```powershell
python scripts/run_local_paper_web.py --port 8765 --open-browser
```

Open `http://127.0.0.1:8765`. The archived evidence and deterministic browser
demo remain available. **Connect local PAPER view** reads `/api/state` and the
closed-only `/api/chart?symbol=BTCUSDT&interval=1m`. It does not start an account.
**Start PAPER**, **Pause PAPER**, **Resume PAPER**, and **Stop PAPER** send explicit
requests; the view displays only the backend-confirmed state. While connected,
the view refreshes every five seconds. A failed request marks the last confirmed
account snapshot and disables actions until a successful account refresh.
Public-chart errors are shown separately and do not block account controls.
When the backend writer is busy, starting is blocked; pause, resume and stop
remain available so their request time can be durably recorded. A pending
operation is displayed as pending until the backend confirms its application.

For frontend development, `npm run dev` proxies `/api` to the same loopback
backend on port 8765. No market data is fetched when the page initially loads.

The backend persists an account under `data/paper_accounts/windows-paper-v3` by
default. Keep that directory unchanged across restarts. `--journal-dir` selects
a different explicit account directory; do not point it at an unrelated
account. Existing intent, exact recovery, reconciled exposure and risk gates
control resumption. Starting an existing or ambiguous account cannot silently
reset it. The server binds only to loopback and rejects cross-site controls.

The account is valued at its last reconciled closed 15m candle. Current public
prices are separate provisional observations; unknown or stale values remain
unknown. The displayed chart contains closed 1m candles and reports the chart
source UTC time. The bounded recent realization count is not a completed
position lifecycle count or a full ledger total; `/api/history` pages the
persisted history.

`FIXED_SIMULATED` funding is a predetermined paper assumption, not observed
historical funding. Research scores are diagnostics. Automatic replacement
promotion stays blocked until an independent evidence path and a declared risk
contract are implemented. Positive simulated PnL or a client-provided
`historical_verified` flag cannot allocate replacement capital.

The repository includes Windows launcher/task-management scripts, but running
the Python command above does not install an OS task. Real Scheduled Task
installation, reboot recovery, continuous public-feed observation and economic
acceptance require separate verification. Fixture-driven loopback tests do not
establish those operational results.
