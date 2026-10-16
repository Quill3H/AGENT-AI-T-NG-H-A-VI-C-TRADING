# Compact transactional paper store implementation plan

## Current publication checkpoint - 2026-10-17

Implementation and regression files are included in the GitHub candidate.
Use the [current handoff](../../handover/2026-10-17-github-checkpoint.md) for
the repaired code SHA, fresh offline/web/build results and remaining gates.
The older combined verification checklist below is historical: unperformed
clean-checkout/browser/public/scheduled-operation checks remain NOT_VERIFIED.
Independent review and owner acceptance remain pending.

## Prior execution addendum - 2026-10-02

S2 implementation is present as an **AUTHOR_SELF_REVIEWED candidate**, not
independent acceptance. The owner later expressly authorized helper agents;
that supersedes the original inline-only restriction without deleting it.
Helper contributions remain author-side work. The original checklist below
preserves planned RED/GREEN actions, not final repaired-commit test evidence.

- [x] `compact_store.py` implements one-owner WAL/FULL transactions, canonical
  input/event roots, immutable account identity and compact exact checkpoint.
- [x] Post-checkpoint repairs add authenticated generation/batch commit metadata
  and durable OPERATOR_REQUEST/OPERATOR_INTENT receipt/application integrity.
- [x] Strict identity/orphan/corruption/crash/revision tests are present in
  `test_paper_compact_store.py` and `test_paper_store_commit_integrity.py`.
- [x] Exact typed runner restore and narrowly checked legacy migration seam
  exist with recovery/exposure/partial-position regressions. Unprovable legacy
  balances, indicator seed or funding debt stay RECOVERY_REQUIRED.
- [ ] Final repaired code SHA and frozen corruption/crash/restore/full/clean
  results: pending root finalization. Earlier checkpoint
  `c89333516f9032155923375a876d0350deb6c267` is not final-code evidence.

The owner approved a NEW separate `data/paper_accounts/windows-paper-v3`
10,000-imaginary-USDT account, not migration/reset of legacy capital. Account
startup remains a separately reported action after final verification. No
legacy deletion, reset endpoint or inferred power-loss durability is authorized.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline; no subagents.

**Goal:** Persist canonical inputs, compact events and a latest exact checkpoint atomically without resetting or overwriting legacy accounts.

**Architecture:** `PaperStore` owns a versioned SQLite transaction under the existing OS ownership lock. Inputs and events are immutable/checksummed with a chained committed root. A single latest checkpoint stores active machinery; historical records are separate from it. The causal runner consumes this store in S3; legacy JSONL remains read-only.

**Tech Stack:** stdlib sqlite3, SHA256, existing typed pack/unpack, pytest on Windows.

**Spec:** `docs/superpowers/specs/2026-10-01-windows-paper-replay-design.md`, sections 4, 6.

## Global constraints

- WAL, synchronous FULL, foreign keys, schema version; no silent empty-account fallback.
- Inputs/events/checkpoint/watermark have one transaction. No ticks/forming bars or repeated raw envelopes.
- Original legacy files remain unchanged. Missing/torn/corrupt/ambiguous evidence blocks.
- One OS lifetime owner independent of HTTP port. No main merge or unrelated changes.

## Task 1: Store integrity and atomicity

**Files:** Create `crypto-paper-agent/src/paper/compact_store.py`; test `crypto-paper-agent/tests/test_paper_compact_store.py`.

**Interfaces:** `PaperStore(directory, ownership=None)`, `inspect() -> dict | None`, `commit(account_id, config, inputs, events, machine, batch_id) -> dict`, `inputs(symbol, interval) -> list`, `events(after=0, limit=100) -> dict`, `close()`.

- [ ] Tests: create/inspect exact checkpoint; identical overlap adds no input; revision conflicts; transaction rollback preserves last machine and rows; damaged DB/checksum/deleted row blocks; account ownership mandatory; event cursor stable.

```python
before = store.inspect()
with pytest.raises(ValueError):
    store.commit('account-1', {}, [revised_bar], [], {}, 'revision')
assert store.inspect() == before
assert len(store.inputs('BTCUSDT', '15m')) == 1
```

- [ ] Run RED: `python -m pytest tests/test_paper_compact_store.py -q`.
- [ ] Implement SQL tables for immutable inputs/events and one checked checkpoint with account/config identity, sequence/root/count, compact machine JSON, atomic BEGIN IMMEDIATE/commit/rollback, strict open modes and evidence detection.

```python
connection.execute('BEGIN IMMEDIATE')
try:
    # Immutable row conflicts abort before replacing the checkpoint.
    connection.commit()
except BaseException:
    connection.rollback()
    raise
```

- [ ] Run GREEN, kill a Windows writer inside an open transaction in the fault-injection test, reopen last verified commit, then full offline suite before committing this milestone.

## Task 2: Exact migration seam (completed with S3 runner)

**Files:** `crypto-paper-agent/src/paper/replay_session.py`, `crypto-paper-agent/src/paper/recovery_state.py`; test `crypto-paper-agent/tests/test_paper_replay_recovery.py`.

**Interfaces:** `PaperReplaySession.reconcile_resume()` loads a v3 compact machine or verifies legacy v2 using `restore_session(legacy, payload, saved_view)` under the original config, reconstructs the retained causal seed, and records `LEGACY_MIGRATION`. No v1 migration and no balance-only restore.

- [ ] Test byte-for-byte preservation of legacy files, exact financial/risk/order/funding state, no duplicate migration, and missing warmup/legacy source revisions blocking before allocation.

```python
assert legacy_journal.read_bytes() == original_journal
assert resumed.broker.wallet_balance == original_wallet
assert resumed.state()['status'] == 'RECOVERY_REQUIRED'  # if exact seed cannot be proved
```

- [ ] Run RED, implement verification-first migration and commit only after complete typed comparison, then GREEN plus v2 compatibility tests.

Self-review: new database creation is allowed only in a verified empty directory; an existing database with no committed account is not a new account. Preserve evidence on every error. No automatic deletion or reset endpoint.
