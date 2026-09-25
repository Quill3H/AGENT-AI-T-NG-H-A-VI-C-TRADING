# Web preview implementation plan — 2026-09-25

Gate: `web-preview` only. Branch: `main`. Timebox: two hours.

## Scope and ownership

- Add a standalone React/Vite application under `crypto-paper-agent/web-preview/`.
- Present committed research evidence without changing trading, risk, execution,
  accounting or model code.
- Add a deterministic, browser-only synthetic replay interaction. It must not
  contact an exchange or imply an executable fill or profit.
- Commit the owner-approved preview task contract alongside the implementation.
- Preserve `.serena/` and every unrelated local file.

## Delivery slices

1. Build the read-only PAPER/RESEARCH dashboard from committed evidence.
2. Add focused rendering, copy-safety and deterministic-replay tests.
3. Run test, build, dependency audit and a scoped secret/live-order scan.
4. Run the built app locally; verify desktop/mobile rendering, the replay flow,
   console output and network activity in a real browser.
5. Deploy only a provider preview when an existing authenticated CLI is
   available; otherwise report the exact authentication blocker.
6. Commit/push `main`, then confirm local `HEAD` equals `origin/main`.

## Evidence boundary

All product claims are labelled as author-reported/reviewer-not-verified or
not-verified. Browser/build checks performed in this task are author checks,
not independent acceptance. Completing this UI does not complete engineering
or economic validation of the trading project.
