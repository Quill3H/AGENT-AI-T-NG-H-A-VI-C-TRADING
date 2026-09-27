# G0–G4 Public Market Validation Implementation Plan

**Goal:** Establish trustworthy settlement/lifecycle accounting before evaluating three chronological market horizons.

**Architecture:** Keep directional/PPO execution in PaperBroker and funded spot/perpetual baskets in their existing simulator. Enforce exact settlement provenance at both consumers and the ingestion readiness boundary. Preserve raw realization records while deriving completed-position statistics separately.

**Tech stack:** Python 3.12, pandas, pytest, Parquet, existing SQLite reports and Gymnasium/SB3 runtime; no new dependency required for G0.

**Spec:** Current user G0–G4 delegation, `PLANNER_HANDOVER.md`, master spec Section 4.6, ADR0007/0009/0011/0012. New PM organization supersedes the old reviewer routing. PM coordinates; separate Tester and Independent Reviewer issue their own results. The author does not accept or merge.

**Execution:** Sequential implementation in this task, fail-first tests, then minimal fixes. User explicitly permits safe G0 work without waiting for QA/reviewer. No additional execution-style approval is required.

## Baseline and constraints

- Repository: Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING.
- Branch: `codex/g0-market-validation`, from `c81dc4e5ec7588f2958da319ca709f13e97ad95f` (old documentation B).
- Old code A: `23f94376215a7fca69c8a7606e34139bc21d090c`.
- Preserve existing `.serena/`, other user changes, and main. No main merge or force push.
- Public data only; no live/testnet, credentials, money, paid data/cloud.
- Handoff each gate with full code A and docs B SHAs, commands, observed results, manifest/checksums and artifact locations. QA must check out A explicitly; their worktrees may begin at main.
- Profits are not acceptance criteria. Old performance numbers are not newly verified evidence.

## Resource budget and cutoff policy (before market experiments)

- G0/G1: offline fixtures, zero downloaded market bytes, existing Python runtime; at most 2 CPU threads, 2 GiB new evidence/scratch, 30 minutes wall time per verification batch. Network tests separately identified and bounded to 10 minutes.
- G2–G4 initial collection ceiling: 2 GiB downloaded compressed bytes, 8 GiB total new raw/normalized/output disk, 2 concurrent public requests, 3 attempts per object, 30 seconds per request, 30 minutes per acquisition batch. Cache hash-verified objects; never retry indefinitely. Stop the batch on a budget ceiling or untrusted source response and report partial coverage. Check available disk before collection. Do not delete unrelated data to meet a budget.
- Research runs: at most 2 CPU threads, no GPU/cloud, 30 minutes wall time per batch. Initial PPO ceiling 100,000 timesteps per fold and 3 folds; no automatic increase or hyperparameter search. Record actual elapsed time, rows/bytes, model/config identities and the reason for any curtailed run.
- Historical benchmark remains 2021-01-01 through 2026-09-01. Report separately 2021–2023 and 2024–2026-09-01 using only actual covered windows; disclose missing years/intervals. Bounded sample windows do not constitute the full benchmark.
- Holdout is strictly after 2026-09-01 through the last fully closed UTC bar supported by source data. Resolve exact cutoff per timeframe from source inspection, then write freeze manifest before reading final holdout results. No fixed wall-clock date is substituted for bar closure evidence.
- Freeze code/config/risk/fees/slippage before evaluation. PPO scaler fits train only, validation precedes freeze, holdout evaluated afterward. Record each fold's train cutoff, fitted model and scaler hashes; different fitted models are not identical models.
- Distinguish near-current historical replay from observations collected after freeze. Missing historical data, unclosed bars or failed integrity gates are BLOCKED/NOT_VERIFIED for that scope, not silent forward-fill.

## Review focus

1. Reusing source funding 08:00 at row16:00, including changed rates, must fail before mutation; funding0 with exact source remains valid.
2. Gap partial exit before funding settles only remaining quantity; full gap exit does not require irrelevant funding.
3. Three partial realization rows form one completed position; mixed signs must aggregate before win/expectancy/SQN. An unfinished position contributes cash PnL but not a completed trade sample.
4. Lifecycle identities must not merge separate positions/accounts or accept a final slice without the preceding quantities; legacy untagged whole trades remain supported, ambiguous legacy partials fail closed.
5. Report/SQLite/JSON totals reconcile to all realized slices even when primary trade metrics exclude unfinished lifecycles.

## G0a: settlement identity

Files: `src/execution/paper_broker.py`, `src/strategies/funding_arbitrage.py`, `src/data_layer/fetcher.py`, `tests/test_g0_settlement_lifecycle.py`.

- [x] Add fail-first regressions for source08→row16 replay/revision in both execution consumers, exact-source zero funding and ingestion readiness at a missing boundary.
- [x] Run the regression file against baseline and preserve failing output.
- [x] Require source time equal to the settlement boundary for a surviving position. Do not reuse an observation as settlement. Keep existing no-future/no-stale validations for non-settlement observations.
- [x] Keep preflight validation before mutation; preserve gap exits, partial-before-funding and pending-close ordering.
- [x] Run focused broker/funding/data regressions and historical probes.

## G0b: lifecycle statistics

Files: `src/execution/paper_broker.py`, `src/execution/order_models.py`, new `src/report/lifecycles.py`, `src/report/metrics.py`, `src/report/generator.py`, `tests/test_g0_settlement_lifecycle.py`.

- [x] Add fail-first 3-slice/1-position, mixed-win-loss, unfinished lifecycle, repeated symbol, malformed identity/quantity and persistence/report tests.
- [x] Tag every new realization with immutable lifecycle identity/original quantity and terminal marker in metadata, preserving raw TradeRecord/JSON schema.
- [x] Add `completed_lifecycles(trades)` returning aggregated completed records; fail closed on ambiguous partials, duplicate/late terminals and inconsistent original quantity. Recompute lifecycle R from aggregate risk, never average slice R.
- [x] Primary counts/win rates/expectancy/SQN consume completed lifecycles; separate `realization_slices` statistics preserve all raw cash amounts. Long/short and benchmark comparisons use the same lifecycle unit.
- [x] Ledger reconciliation continues to consume all slices including unfinished positions. SQLite stores raw rows plus primary run metrics; report labels distinguish rows and trades.
- [x] Run focused then full offline suite; preserve all failures. Network suite explicitly NOT_RUN per G0/G1 PM constraint.

## G1: execution gate

- [x] Run full offline and historical Review05/06/07 probes on exact code A.
- [x] Exercise deterministic LONG/SHORT and partial replay with nonempty fills, zero/repeated/distinct funding, partial and final ledger reconciliation.
- [x] Create evidence SHA256 manifest; document synthetic provenance and no market raw data in G0/G1. Route A/B to PM and Tester. Only their own replay can be called independent verification.

## G2: data-integrity gate (subsequent implementation checkpoint)

- [ ] Extend ingestion/cache tests for internal gaps, stale OI, missing taker flags, duplicate/conflicting source records, reversal and exact funding boundary coverage.
- [ ] Retain raw source URL/license if available, market/instrument/timeframe, UTC coverage, last closed bar, fetched_at, source version, normalization policy, missing intervals and raw SHA256.
- [ ] Implement bounded collection/cache with checksums and explicit covered windows before market replay. Preserve distinct spot and perpetual data.

## G3: chronological comparisons (depends on G0/G1 and usable G2 scope)

- [ ] Freeze experiment manifest and run four independent equal-capital strategy accounts, cash/buy-and-hold baselines, fixed costs and cost sensitivity.
- [ ] Report per-year/fold/regime and period completed trades, slices, net PnL/return/DD/exposure/fees/slippage/funding, win/expectancy/SQN with sample limitations/uncertainty.
- [ ] Mark NO_TRADES/INSUFFICIENT_DATA and uncovered ranges explicitly. Never sum independent fold equity as a portfolio.

## G4: untouched recent holdout (depends on freeze and coverage)

- [ ] Derive and record exact closed-bar cutoffs before holdout results; freeze train/validation choices, code/config/model/scaler/dataset identities.
- [ ] Run bounded evaluation and distinguish replay from forward observations. Report scoped blockers without fabricating data or optimizing to holdout.

## Handoff and stopping rules

G0/G1 is independently reviewable and will be handed off before larger experiments. G2–G4 remain planned until their own implementation/verification and budget checkpoint. A is code/tests/scripts; B is a documentation-only child with results and manifest. No claim that merely planning a gate completes it. PM receives the exact branch and A/B SHAs; user decides acceptance/merge.

Latest product steering via PM: an explicit initial futures rulebook precedes learning; evaluate on historical years not used for learning before prospective public realtime data with simulated paper orders. Product Owner/Business Analyst must define primary strategy, learning boundary, measurable effectiveness and live-paper workflow. Do not implement a realtime connector or change scope before that product contract and G0/G1 acceptance. No private/live/testnet orders are authorized; no holdout tuning or profitability claim. The three-horizon benchmark and resource ceilings above remain unchanged.

Author execution checkpoint: code A2c9a4d0985fc9eafd29386482793425c26d47835 passed382 offline (2 skips/5 network deselected), historical26/11/3, and nonempty LONG/SHORT synthetic replay. Checked boxes denote author execution/deliverables only; independent acceptance remains pending. Evidence: docs/reviews/G0_SETTLEMENT_LIFECYCLE_HANDOFF.md.
