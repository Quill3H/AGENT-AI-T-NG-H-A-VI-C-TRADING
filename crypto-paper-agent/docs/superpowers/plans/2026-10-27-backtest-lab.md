# Backtest Lab Implementation Plan

> For agentic workers: use superpowers:executing-plans inline, then separate tester and reviewer.

**Goal:** One offline command runs named strategy/config variants, reuses identical results, and writes a comparison.

**Architecture:** Add a thin batch CLI over run_vision_backtest.run and run_vision_carry.run. Keep broker, strategy, funding and risk semantics unchanged. Cache by content identity, not filenames or Git HEAD alone.

**Tech Stack:** Existing Python, pandas, PyYAML, pytest; standard-library JSON/CSV/hashlib.

**Spec / approved design:** Owner approved the preceding chat proposal on 2026-10-27: reuse fixed data, vary existing strategies/configs, save identical results, compare metrics; defer GUI. Input is a YAML list of explicitly named jobs and date windows. Output is JSON, CSV and a readable Vietnamese Markdown table. Existing directional registry plus funding_arbitrage are supported; specialized OI and shared-account cointegration workflows keep their own runners. No automatic optimization, holdout selection, downloads or trading.

## Global constraints

- sources/ remains read-only. No new dependencies or network operations.
- Work only in the clean existing eth-btc-research checkout, branch codex/eth-btc-cointegration-v1, base b6ccff26a538f65eec1b2206bdf424aca62b8968; no merge or push.
- A single implementation scope: new runner, example, tests and usage/evidence docs.
- All runs are labelled retrospective research; no economic gate acceptance.
- Code identity covers actual Python/config/requirements bytes, runtime package versions and Python version. Data identity hashes all root Parquet/JSON files, including peers. Config identity includes resolved effective settings and external signal-file bytes.
- Hash inputs before execution and again before publishing cache/report. Input mutation fails closed. Cache entries carry a payload checksum; corrupt entries rerun. Failed runs never become cached success.
- New output directory required; cache outside input/code directories. Preserve originals.

## Review focus

Data edits with preserved filenames; dirty source changes; config/cost/date changes; corrupt cache and failures; missing/truncated data and output overwrite. Pin each with tests. Full input hashing is deliberately conservative and still required on cache hits; concurrent input edits are unsupported and detected at the final check.

## Task 1: runner and evidence

- [x] Write failing tests for content invalidation, cache reuse/corruption, failure rows, validation and actual broker parity.
- [x] Observe missing-module assertions fail.
- [x] Add scripts/backtest_lab.py, config/research/backtest_lab.example.yaml and docs/operations/BACKTEST_LAB.md.
- [x] Run focused tests, small real local replay twice, existing runner-related tests and offline suite.
- [x] Separate Tester and Independent Reviewer inspect the finished change; resolve important findings and record exact evidence.

## Execution ledger

- Ruling: reuse the existing clean research checkout rather than creating another copy; scope is additive and isolated from main.
- Ruling: fixed explicit jobs are the smallest useful batch interface; a parameter sweep is represented by multiple YAML jobs, without an optimizer.
- Ruling: universal caching applies to the two existing summary-returning runners only. Shared-account pair and OI runners must retain their distinct execution contracts.
- Ruling: add a four-line README pointer for discoverability; no behavior change.
- Separate tests found Windows path length and missing carry funding seed defects; reproduced then fixed with regression tests. Reviewer also found mixed-prefix directory protection; reproduced then fixed by canonicalizing every safety operand consistently.
- Initial full suite hit existing SQLite/report path limits using a deep fixture root. All three failures passed unchanged when rerun with a shorter fixture root. Final complete offline suite: 705 passed, 4 skipped, 5 network deselected, exit 0.
- Final evidence and exact commands: docs/reviews/BACKTEST_LAB_2026_10_27.md. Local delivery only; no commit, merge or push, no economic acceptance.
