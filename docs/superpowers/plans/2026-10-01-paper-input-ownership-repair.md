# Paper Input and Account Ownership Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. The owner's direct-work instruction overrides the subagent-driven alternative: execute inline, without subagents, on the existing checkout.

**Goal:** Close proven input, cache and duplicate-writer blockers before funding/storage/replay work.

**Architecture:** Reuse BacktestEngine, Parquet cache and LocalPaperSession. Require strict volume and complete cache cadence before consumption; use a lifetime OS account lock independently of the HTTP port. Historical probes retain their assertions and receive only a corrected relocated application root.

**Tech Stack:** Python 3.12, pytest, pandas, pyarrow, sqlite3 (subsequent slice), Windows msvcrt / POSIX flock.

**Spec:** `docs/superpowers/specs/2026-10-01-windows-paper-replay-design.md`, S0 and sections 4/6/10. Owner approved 2026-10-01.

## Global Constraints

- PAPER/RESEARCH only; no keys, signing, live/testnet orders or paid resources.
- BTCUSDT/ETHUSDT/SOLUSDT; shared initial 10,000 imaginary USDT; never reset existing capital.
- UTC internally; no lookahead; signal close -> next eligible open.
- Preserve strategy, stop-loss, maximum 5x leverage, fees/slippage and Circuit Breaker semantics.
- No main merge, force-push, rebase or squash. Preserve pre-existing INDEX/audit/workflow changes.
- No operator account is started, migrated or overwritten during tests. Use temporary test accounts.
- Windows task install/reboot/public stream/continuous operation are separate verification gates.

## File Map and Slice Boundary

| File | Responsibility |
| --- | --- |
| `crypto-paper-agent/src/backtest/engine.py` | Fail before feature preparation for invalid volume |
| `crypto-paper-agent/src/data_layer/cache_manager.py` | One exact completeness rule shared by metadata/load |
| `crypto-paper-agent/src/data_layer/fetcher.py` | Treat a failed cache load as a miss, not len(None) |
| `crypto-paper-agent/src/paper/account_lock.py` (new) | Nonblocking OS lifetime ownership, canonical directory aliases |
| `crypto-paper-agent/src/paper/live_session.py` | Claim before writer inspection/resume; release on shutdown; reject post-shutdown writes |
| `crypto-paper-agent/src/paper/durable_journal.py` | Recognize only the reserved lock marker, not arbitrary files |
| `crypto-paper-agent/src/paper/local_server.py` | Claim before auto-resume, terminate transport before releasing account |
| `crypto-paper-agent/tests/test_backtest_engine.py` | Invalid volume and zero-volume regressions |
| `crypto-paper-agent/tests/test_cache_integrity.py` (new) | Cadence, boundary, duplicate and cache-miss fallback tests |
| `crypto-paper-agent/tests/test_paper_account_lock.py` (new) | Same/different ports, direct session, aliases, process death, post-shutdown guard |
| `crypto-paper-agent/tests/test_paper_resume.py` | Existing exact-resume tests release preceding owner before restart |
| `docs/history/reviews/test_stage_04_review_{05,06,07}.py` | Correct application root only |
| `docs/PROJECT_STATE.md` and new S0 evidence report | Current bounded implementation and honest remaining gates |

Not delivered by S0: fixed funding, compact SQLite, full outage replay, trial research, new controls or Windows task changes. S1-S5 remain required and are not claimed complete. Each receives a separate implementation plan after inspecting its concrete interfaces; do not implement them from prose alone.

## Task 1: Validate volume before backtest mutation

**Interface:** `BacktestEngine.validate_dataset(df: Any, name: str) -> None`, existing API.

- [x] Add parameterized regression for NaN, positive/negative Inf, -1, bool, numpy bool and numeric text. A mixed object column preserves input types. Construct the engine with a real broker and assert no account/order state changes.

```python
bad = df_15m.copy()
bad["volume"] = bad["volume"].astype(object)
bad.iloc[0, bad.columns.get_loc("volume")] = True
before = (broker.wallet_balance, list(broker.order_history), list(broker.account_snapshots))
with pytest.raises((TypeError, ValueError), match="volume"):
    BacktestEngine(config, df_4h, bad, strategy, broker=broker)
assert (broker.wallet_balance, broker.order_history, broker.account_snapshots) == before
```

- [x] Run red: combined volume/cache selection documented in the evidence report, from `crypto-paper-agent`. Observed failure: DID NOT RAISE for invalid volume.
- [x] Extend the numeric validation loop to OHLCV. Reject bool/numpy bool/non-real values before conversion; require finite volume >= 0 and finite OHLC > 0.

```python
from numbers import Real
if col_data.map(lambda x: isinstance(x, (bool, np.bool_)) or not isinstance(x, Real)).any():
    raise TypeError(f"Dataset {name} column '{c}' contains non-numeric or boolean values.")
invalid = arr < 0 if c == "volume" else arr <= 0
if invalid.any():
    raise ValueError(f"Dataset {name} column '{c}' contains invalid sign values.")
```

- [x] Run green: regression and full `tests/test_backtest_engine.py` and `tests/test_breakout_retest.py` in the full offline gate.
- [x] Stage only engine/test files. Commit after the full offline milestone gate required by AGENTS.md, not before.

## Task 2: Agree on complete cache coverage and safe miss fallback

**Interfaces:** Existing `has_complete_cache(...) -> bool`, `load_from_cache(...) -> Optional[pd.DataFrame]`, `fetch_all(...) -> Dict[str, pd.DataFrame]`. Bounds remain inclusive bar-open timestamps; cache must contain every requested cadence slot. No tolerance admits a missing bar.

- [x] Write real Parquet tests with 200 fifteen-minute slots, retaining endpoints but dropping 1 or 50 middle slots. Both metadata and load must reject. Add duplicates/off-grid/boundary/named-index cases and an exact-complete positive case.

```python
idx = pd.date_range("2024-01-01", periods=200, freq="15min", tz="UTC")
frame = pd.DataFrame({"close": 100.0}, index=idx).drop(idx[50:100])
save_to_cache(frame, str(tmp_path), "binance", "BTCUSDT", "15m", "ohlcv")
assert not has_complete_cache(str(tmp_path), "binance", "BTCUSDT", "15m", "ohlcv", idx[0], idx[-1])
assert load_from_cache(str(tmp_path), "binance", "BTCUSDT", "15m", "ohlcv", idx[0], idx[-1]) is None
```

- [x] Run red: `.\.venv-paper\Scripts\python.exe -m pytest -p no:cacheprovider tests/test_cache_integrity.py -q --tb=line`. Endpoint-only check and one-percent tolerance failed.
- [x] Use the same sufficiency predicate for both readers. Preserve arbitrary named DatetimeIndex metadata. Refuse duplicates, NaT, unsorted or missing slots.

```python
expected = pd.date_range(since, until, freq=timeframe_to_timedelta(timeframe))
return len(expected) > 0 and df_slice.index.equals(expected)
```

- [x] Make each fetch_all branch fetch when its actual loaded frame is None, even if metadata previously claimed a hit; test all three data types using only external fetching doubles and real merge/cache paths. Reject an incomplete OHLCV result before strategy consumption; never invent funding or OI observations.
- [x] Run green: cache integrity, data layer (offline), public pipeline, CLI/backtest and Stage 6 integration tests in the full offline gate. Reserve atomic Parquet writes/source revisions for the storage slice; do not silently claim these fixed.
- [x] Stage only cache/fetcher/test files; commit with Task 1 after the milestone gate.

## Task 3: Lifetime account ownership across ports and processes

**New interface:** `AccountOwnershipLock(directory: str | Path)`, `acquire() -> None`, `assert_owned() -> None`, `release() -> None`. Busy acquisition raises `AccountInUseError(RuntimeError)`. Read-only inspection does not acquire or grant writer rights. Direct session start/resume and server startup must acquire before writer inspection.

- [x] Write failing tests: two real servers on port=0 sharing one temporary account, path aliases, two direct sessions, repeated shutdown, stale-owner writes and a child process killed while owning the account. Check financial bytes before/after denied ownership.

```python
first = create_server(port=0, source=FakeSource(), journal_dir=tmp_path)
try:
    with pytest.raises(RuntimeError, match="account.*in use"):
        create_server(port=0, source=FakeSource(), journal_dir=tmp_path / ".")
finally:
    first.server_close()
```

- [x] Run red: `.\.venv-paper\Scripts\python.exe -m pytest -p no:cacheprovider tests/test_paper_account_lock.py -q --tb=short`.
- [x] Implement one reserved `.paper-owner.lock` byte-lock file. Resolve directory aliases, acquire nonblocking (Windows msvcrt/POSIX flock), hold file descriptor for lifetime. Never unlink the lock while held/releasing. OS process death releases the lock. Ignore this exact marker only as operational metadata; do not ignore other unknown files.

```python
# Windows: lock one byte at offset zero for the entire owner lifetime.
stream.seek(0)
msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
# POSIX: flock(stream.fileno(), LOCK_EX | LOCK_NB).
```

- [x] Require ownership in `_journal`, claim before start/resume, and prevent a shutdown session from reactivating or writing. On server teardown close/join stream worker before shutdown and account release. If worker termination cannot be confirmed, fail closed rather than permitting another writer. Only genuine resume tests release the prior owner; read-only corrupt-account probes remain read-only.
- [x] Run green: ownership tests plus all existing paper tests in the full offline gate. Actual Windows subprocess tests pass; alternate directories remain independent.
- [x] Stage explicit production/test files only; commit after Task 4/full offline gate.

## Task 4: Restore historical probe routing and verify checkpoint

**Interface:** Historical probes import actual `crypto-paper-agent/src` and load actual application config from their new document location.

- [x] Run red: combined historical probes returned 40 failures from missing `docs/config/default_config.yaml`.
- [x] Correct ROOT in all three files, without touching financial assertions:

```python
ROOT = Path(__file__).resolve().parents[3] / "crypto-paper-agent"
```

- [x] Run each probe separately and record pass/fail counts. Run full offline `.\.venv-paper\Scripts\python.exe -m pytest -p no:cacheprovider -q -m "not network"`.
- [x] Adversarial self-review: invalid data before mutation, all cache types, exclusive ownership before auto-resume, worker shutdown races, direct write/restore paths, unknown evidence, no capital reset. New High teardown and late-callback findings covered with red/green tests.
- [x] `git diff --check`, inspect exact staged file list, commit S0 production/tests. Rerun full offline and historical probes on that code commit. Update plan progress and PROJECT_STATE with exact code SHA and limitations. Preserve unrelated dirty files.

## Execution Record

Code commit: `d021857731752f8d8fe34d6bde032358f5d946d7`. On-commit offline gate:
556 passed, 2 skipped, 5 deselected, 2 pre-existing Gymnasium warnings, 136.51s.
Historical probes: 26/11/3 passed. Detailed commands, red failures, Windows
process/HTTP evidence and unverified gates are in `docs/reviews/2026-10-01-paper-s0-repair.md`.
Documentation is committed separately. S1-S5 are not implemented by this plan.

## Plan Self-Review

This scoped plan covers S0 and the misplaced historical test gate only. It does not change accounting formulas, public funding provenance, strategy parameters, or the approved S1-S5 requirements. File/interfaces are existing except the explicitly defined account lock. Failed ownership is not account corruption and does not authorize an account reset. Runtime code is reviewed against the newer approved spec, not the old audit plan. Full spec completion requires S1-S5 and their separate acceptance evidence.
