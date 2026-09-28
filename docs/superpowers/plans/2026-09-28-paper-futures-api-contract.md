# Paper Futures Backend Contract — Scoped Plan

Base: `codex/local-paper-futures-app` at `d1cd95a726e12245ede22326e05b09990975ccd6`.
Branch: `codex/paper-futures-api-contract`.
Mode: paper/research only; public Binance USD-M market data; no credentials or
exchange order endpoint.

## Gate

Verify the local paper session contract for Trend Following 4h closed-candle
signals and next-open 15m simulated execution, then expose a read-only chart
endpoint and an inspectable backend decision state.

## Ownership and files

- `crypto-paper-agent/src/paper/live_session.py`: deterministic chart reader/cache,
  per-symbol decision state, and journal-correlated decision snapshots.
- `crypto-paper-agent/src/paper/local_server.py`: strict `/api/chart` query
  validation and source-error responses.
- `crypto-paper-agent/src/paper/recovery_state.py`: persist and restore decision
  state without weakening legacy recovery checks.
- `crypto-paper-agent/tests/`: integration and API regression tests using a
  deterministic fake public source.
- `docs/operations/LOCAL_PAPER_WEB.md` and
  `crypto-paper-agent/docs/operations/PAPER_STREAM_API.md`: operator/API contract,
  strategy/chart separation, and Windows verification limits.

## Verification

Run the focused paper/API tests, then the offline Python suite. Report the exact
interpreter, pass/skip/deselected counts, and any Windows-only or live-stream
checks that remain `NOT_VERIFIED`. Push the branch without force and open a PR
targeting `codex/local-paper-futures-app`; do not merge it into `main`.
