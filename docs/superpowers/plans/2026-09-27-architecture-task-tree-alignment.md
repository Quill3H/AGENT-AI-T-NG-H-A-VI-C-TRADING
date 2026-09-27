# Architecture and task-tree alignment implementation plan

> Inline execution in this conversation; the owner explicitly prohibits sub-agents. This is a scoped reconciliation, not a new engineering or economic-validation gate.

**Goal:** Make the architecture/task tree agree with current ADRs and executable paths, and replace fabricated browser replay deltas with a traceable committed simulation artifact.

**Architecture:** Keep the broker, funded-basket adapter and report pipeline semantics unchanged unless a concrete failing regression proves an error. Document control-flow and data-flow separately. The web preview reads a committed synthetic broker equity CSV and validates its schema/chronology before charting it.

**Tech stack:** Python/pytest; React/Vite/Vitest; Mermaid/Markdown.

**Spec:** `docs/planning/PRODUCT_CHARTER_AND_GATE_SPEC.md`, ADR 0007/0009/0010/0011/0012, master spec.

## Global constraints

- PAPER/RESEARCH only; no live/testnet orders, credentials or profitability claims.
- Preserve UTC/availability chronology, sizing/stop/risk admission before account mutation, fee/funding/collateral accounting and idempotency.
- Do not modify strategy parameters or declare independent gate acceptance.
- Do not merge into `main`; preserve untracked `.serena/`.

## Owned files and actions

1. Trace source paths in `src/data_layer`, `src/features`, `src/backtest`, `src/execution`, `src/risk`, `src/research`, `src/logging`, `src/report` and `web-preview/src`. Classify each of six user-reported relations as diagram/doc/code discrepancy with source references.
2. Test-first web defect: strengthen `web-preview/src/App.test.jsx` to assert chart endpoints and timestamps equal the checked-in `docs/reviews/evidence/g0-2c9a4d0/replay/LONG/equity_curve.csv` after line-ending normalization, and that arbitrary initial equity cannot rescale the result. Run `npm test -- --run` to observe the old failure.
3. Replace the hard-coded delta generator in `web-preview/src/lib/replay.js` with strict parsing of that source CSV; update `web-preview/src/App.jsx` labels to say historical synthetic broker artifact, not a browser-generated simulation. Keep the app read-only and show artifact path/code SHA. Run focused Vitest and build.
4. Create `docs/architecture/architecture-and-task-tree.md` with Mermaid source, the six-way reconciliation table, dependency-ordered group tasks, deliverables, acceptance criteria and explicit pending evidence/gates. Correct the stale Stage roadmap in `README.md` without asserting independent approval.
5. Run relevant Python pytest probes and the offline suite if the pinned runtime is available; review the full diff for every order path, secret/order endpoints, lookahead claims, stale numbers and user-local files. Commit on `codex/architecture-task-tree-alignment`; do not merge `main`.

## Stop rule

If a production-path defect cannot be reproduced or the source artifact cannot be verified, do not change broker/strategy semantics. Record the discrepancy and missing evidence rather than inventing a fix or market result.
