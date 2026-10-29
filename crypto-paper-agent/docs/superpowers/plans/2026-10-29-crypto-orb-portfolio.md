# Crypto ORB portfolio implementation plan

> Execute inline with executing-plans; one fresh independent review at the end.

**Goal:** Extend the existing offline Backtest Lab for crypto ORB + FVG, unrestricted daily entries, at most four simultaneous positions and explicit sample-size checks.

**Architecture:** An additive portfolio mode uses the existing PaperBroker and its risk/accounting rules. Synchronize broker phases across symbols before any intrabar outcome can influence another symbol's opening fill. Keep existing batch mode compatible.

**Tech Stack:** Existing Python, pandas, PyYAML, pytest; no new runtime package.

**Spec:** Owner instructions in this chat, and `../../../../output/crypto-orb-10pairs-2026-10-29/PROTOCOL.md` (research parameters, with broker-semantics addendum in the delivered documentation).

## Global constraints

- Crypto USDT perpetuals only. Multiple trades/day; one position/symbol; max four portfolio positions including reserved pending slots.
- 60 completed trades per full 7-day week and 240 per full calendar month are reporting targets, never permission to weaken signals.
- Closed 1m signals, next-open fills; common equity, fees, funding, stop-first ambiguity, circuit breakers retained.
- Output/cache outside source and data; immutable inputs, identity hashes; paper only.
- Reuse the clean isolated `eth-btc-research` checkout at base `47fdd6dbd6817ba251c6507186052fae48e51eb2`; no merge/push or main integration.

## Review focus

- Simultaneous entries and intrabar exits must not create a fifth position or opening lookahead.
- Pending orders reserve capacity and later valid signals can enter again after exit.
- Missing/duplicate/nonfinite bars or funding must fail closed; funding source milliseconds preserved.
- Empty or short samples must report unmet targets, including empty weeks/months.
- Old batch runner/cache behavior must remain compatible.

## Task 1: Causal broker batches and hard capacity

Files: `src/execution/paper_broker.py`, `tests/test_crypto_orb_portfolio.py`.

- [x] Write failing tests for max four, reserved pending capacity, same-time fills preceding intrabar results, transactional batch validation, and single-symbol parity.
- [x] Add `process_batch(candles)` with shared phase barriers, and validated optional `execution.max_concurrent_positions` (default unchanged for existing callers).
- [x] Run new tests plus existing broker/risk regressions.

## Task 2: Portfolio research runner and CLI

Files: `scripts/run_crypto_orb_portfolio.py`, `scripts/backtest_lab.py`, `config/research/crypto_orb_portfolio.yaml`, `tests/test_crypto_orb_portfolio.py`, `docs/research/crypto-orb-portfolio.md`, `docs/operations/BACKTEST_LAB.md` (discovery link).

- [x] Write failing tests for causal signals, no daily entry ceiling, coverage/rejections and sample-count reporting (completed trades rather than signals).
- [x] Implement verified monthly Vision ZIP input, full minute continuity and independent 15m audit, actual archived funding events, fixed causal ordering, risk/notional sizing and shared broker loop.
- [x] Add `--portfolio-config` alongside existing mutually exclusive `--batch`; preserve old mode and fingerprint new inputs/code/config.
- [x] Run scoped and default suite; record skips/failures. Run the ten-coin September 2026 base/stress replay and ledger reconciliations.
- [x] Obtain separate review, fix material findings, deliver code, exact command and real sample counts. No economic/gate acceptance claim.

## Execution ledger

- Plan/spec authorized by owner request to change the tool; no repeated design approval needed.
- Preserve existing repo risk gates. Ruling: target and sizing reference signal close, not an unknown next open; existing broker adverse fills/gap/funding conventions govern execution and will be disclosed.
- Independent review reproduced future-data influence through whole-month OHLC tick inference. Ruling: freeze each daily increment using only the completed 15-minute opening range, before entry; whole-month grid remains audit-only. Add future-mutation replay regression, invalidate prior output as preliminary, rerun both predeclared cost cases; no profit-based parameter selection.
- Independent reviewer verified the repaired future-mutation and prefix invariance; no material findings open. Review evidence is output/crypto-orb-10pairs-2026-10-29/independent-review.md (outside Git). A separate Tester owns the full-suite and final-ledger evidence; owner acceptance remains pending.
- Final offline full-suite: 728 passed, 3 failed, 4 skipped, 5 network deselected. All three failures were SQLite report DB opening errors under a deep temporary path; fresh short-path retry of exactly those three passed (22.70s), with no source edits. Default network-enabled attempt was interrupted after four observed network-test failures; endpoint failure causes remain NOT_VERIFIED. Do not call the default suite fully passing.
- Final causal replays: base 1,140 closed trades, net -3315.1143215224774 USD; stress 1,101, net -5207.41341609275 USD. Both peak four; independent ledger checks matched source identities, funding, fees, equity, drawdown, capacity and sample counts. Sep 21–27 base 238/stress 226. Base repeated from cache with identical run ID/economics. Ten-symbol all-September source audit passed. Full reproduction/report under output/crypto-orb-10pairs-2026-10-29/BAO_CAO.md. Local uncommitted changes only.
