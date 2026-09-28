# Local paper safety integration — plan, 2026-09-28

Base: `codex/local-paper-futures-app` at `4dcb271`. Candidate: `codex/local-paper-safety-recovery-integration`.

1. Reproduce old journal reset on corrupt `persistent_state.json`; integrate the durable v2 journal, typed recovery and public market transport from `codex/paper-windows-recovery`. Fail closed on old/corrupt evidence.
2. Reproduce restart that enters `WAITING_CONNECTION` without starting the transport worker; start worker automatically on recoverable state. Keep terminal states inert.
3. Preserve BTC/ETH/SOL charts and show a live quote only while the frontend socket is fresh; label recent closed candles separately. Use Binance's routed `/market` stream endpoint.
4. Update Windows startup instructions, project state and branch inventory. Do not touch live/testnet trading, strategy logic, `main`, or remote branch deletion.
5. Run focused and full offline Python tests, UI tests/build, static checks; record environmental skips and limits. Commit and open a reviewable PR against the base.
