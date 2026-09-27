# High-priority review repair — author handoff, 2026-09-27

Status: **AUTHOR_SELF_REVIEWED / INDEPENDENT_REVIEWER_NOT_VERIFIED**. This is a paper/research correction, not economic validation or owner acceptance. Base `main` and `origin/main` were both `fe1c1330d913e78239db575ff8433cf069fe1b01` after fetch. The primary checkout contained unrelated web-preview edits and `.serena/`; they were left untouched. Work was isolated on `codex/review-high-priority-data-fixes`.

## Review finding disposition

| Finding | Author result | Boundary |
| --- | --- | --- |
| F1, broker multi-symbol intrabar close/time reversal | Fixed for the explicit `process_batch` path: all same-open admissions precede all close phases, canonical symbol order, atomic shadow commit, conservative cross-symbol open/close marks, and preserved caller-supplied breaker identity. A breaker lock at a shared funding boundary now waits for both symbols' valid settlement cashflows before force-close. Direct sequential `process_candle` rejects a breaker-time reversal **before mutation**. | Existing sequential same-open calls without a future breaker event remain legacy behavior; callers needing multi-symbol causal replay must use `process_batch`. Independent review of this contract is still required. |
| F2, overlapping candle/partition intervals | Fixed: broker stores per-symbol close watermark; RL episode/train/validation/holdout/evaluate-only reject overlapping half-open intervals. Gaps remain permitted and must be reported separately. | This is interval validation, not proof of predictive quality or absence of every form of leakage. |
| F3, stale OI | Fixed: backward merge carries `oi_source_time` and `oi_available`; OI older than one mapped OI sampling period becomes NaN, activating the approved optional/strict behavior. | Source index is the repository's OI source/availability-time assumption. Independent receipt/publish time is not present in the historical cache and is not fabricated. |
| F4, missing taker-side volume | Fixed: six-field OHLCV keeps taker-buy as NaN. CVD remains NaN from the first missing/invalid cumulative delta; the RL CVD presence mask is 0. | No 50/50 proxy is presented as observed flow. Re-seeding CVD after a gap would require a separate declared policy. |
| F5, special-mode dates | Explicit `--start`/`--end` now return `UNSUPPORTED_DATE_RANGE` before output for `funding_arbitrage` and `all`; pre-slice inputs with provenance instead. | Other special-mode options such as `--no-report` were not audited/fixed in this slice. |
| F6, directional dataset-content identity | **OPEN.** Run ID/report still lack a content hash of the exact post-filter directional inputs; do not treat identical run ID as proof of identical data. | Separate report/artifact contract repair needed. |
| F7, README/checkpoint drift | **OPEN.** No broad documentation rewrite in this correctness slice. | Update after separate reviewer checks actual feature status. |

## UI handoff contract

The checked synthetic example is [`evidence/review-high-priority-fixes/ui-example.json`](evidence/review-high-priority-fixes/ui-example.json). It is generated conceptually from the deterministic test `tests/test_review_high_priority_fixes.py::test_ui_example_matches_synthetic_replay`; that test compares the example's account, trade, fill, time and breaker fields with an actual PaperBroker run. No value is a market observation or performance claim.

UI consumers should treat the following fields as required in this version:

| Field | Meaning and display rule |
| --- | --- |
| `schema_version`, `evidence_status`, `disclaimer` | Show `SYNTHETIC_OFFLINE_DEMO` and `PAPER/RESEARCH` visibly; never label the fixture as live, historical OOS or independently accepted. |
| `as_of_utc` | UTC close time of the latest completed synthetic bar; this is not wall-clock current time. |
| `source.venue`, `market_type`, `symbols`, `timeframe`, `market_data_sha256`, `market_observation` | Source identity. A null SHA means there is no immutable public dataset identity for this fixture. Do not imply one. |
| `input_quality.open_interest`, `cvd`, `funding` | Each has `available` and nullable `source_time_utc`. Missing means *unknown*, not measured zero. For actual merged OI frames, use `oi_source_time` and `oi_available`; only show a rate/feature as observed when its availability condition passes. |
| `account`, `execution`, `risk` | Reconciled simulated state, event counts and breaker flag. Monetary fields are USDT; the sample deliberately has zero configured fees/slippage and must not be compared to real fills. |
| `replay.kind`, `replay.test` | Exact local reproduction entry point. |

For real research artifacts, the UI must read the repository's existing report/manifest/ledger contract, verify checksums, show source/coverage/gaps and use the result's actual `as_of` time. This fixture is not a substitute for F6's missing directional dataset-content identity.

## Verification and limits

The author used the isolated `%TEMP%/codex-architecture-qa-20260927` Python 3.14.7 environment. The new regression file was observed failing before fixes for F1–F5. From `crypto-paper-agent/` on code commit `d6c639d000b1544003bffe63a382b73846550bd5`:

- `python -m pytest -p no:cacheprovider -m "not network" -q`: **431 passed, 2 skipped, 5 deselected, 0 failed**, 171.80 s. The two skips require optional `pandas-ta`; two existing Gymnasium warnings remain.
- `python -m pytest -p no:cacheprovider docs/reviews/test_stage_04_review_05.py docs/reviews/test_stage_04_review_06.py docs/reviews/test_stage_04_review_07.py -q`: **40 passed, 0 failed**, 1.38 s; Review05/06/07 split **26/11/3**.
- `python -m pytest -p no:cacheprovider tests/test_review_high_priority_fixes.py -q`: **19 passed, 0 failed**, 7.86 s on the same code tree before the documentation commit. The synthetic UI fixture is one of those tests.

Network tests and new market downloads are outside this repair slice and are **NOT_RUN**; no live/testnet order or credential was used.

Self-review specifically inspected funding exact-source preflight, risk/stop admission, breaker timestamp and cashflow ordering, invalid-input mutation, LONG/SHORT protective marks, RL partition boundaries, OI/CVD missingness and the special CLI early return. The explicit batch API is a new causal path, not a claim that every legacy multi-symbol caller now uses it. A separate Tester and Independent Reviewer must assess the final SHA before any gate acceptance.
