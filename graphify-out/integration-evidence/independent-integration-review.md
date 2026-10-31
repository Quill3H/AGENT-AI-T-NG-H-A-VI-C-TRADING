# Independent cache and RL integration review — 2026-10-31

What this change does: cache completeness now requires every expected timestamp rather than endpoint/count tolerance, and fetch orchestration uses the frame actually loaded instead of trusting a separate metadata hit. RL admission checks whole candle intervals inside and between partitions and keeps saved evaluation after the validation interval.

Reviewer: graph_semantic_c, independent of both cache and RL implementation. Route: ponytail-review with direct connected-source inspection and fresh scoped verification. This is review of current uncommitted working bytes on `main`, base HEAD `3f76782ca49626dc14daed6afd2fc36998fecead`; the base commit alone does not identify these changes. No production code, tests, Git index, refs or commits were changed by this reviewer. Expected load: local, offline research workflows and their current CLI callers, not concurrent multi-writer cache operation.

## Findings

No actionable finding in the reviewed change. Verdict: **Ship within this integration scope.** This does not accept an engineering/economic project gate or verify a complete PPO installation.

The cache review traced `load_from_cache`, `has_complete_cache`, index conversion and Parquet metadata handling, `fetch_all`, its public fetch functions and merge path, and the `run_backtest.py` offline/auto-fetch callers. The loader and metadata check share a strict expected-index oracle. Missing interior bars, duplicate/off-grid/NaT/out-of-order indexes and missing endpoints cannot pass by retaining the outer endpoints or exceeding a count threshold. Named datetime indexes and inclusive bar-open windows with a partial final interval are handled. A cache file disappearing or returning no usable frame cannot reach `len(None)`, and incomplete newly fetched OHLCV is rejected before saving or merging. The existing funding readiness/source-time functions and FetchError behavior were retained. This review did not reinterpret sparse or jittered funding observations as exact scheduled events, and did not test real exchange responses.

The RL review traced dataset validation, market-vector/scaler ownership, environment reset/step, training partition admission, saved manifest/config/timeframe checks, dataset-manifest open-time conventions, and train/evaluate CLI callers. A 15-minute bar at 00:15 ends at 00:30: validation beginning at 00:20 is rejected even though its open timestamp follows the train open. Equality at a previous candle's close is admitted. Saved evaluation rejects overlap with validation, not merely training. Internal short-spaced bars are rejected; larger gaps remain gaps and are not fabricated into candles. No scaler fitting, model construction, loading or training was used as a substitute for the interval checks.

The test changes preserve existing assertions. The real PPO smoke is explicitly skipped without SB3, and quickstart checks Gymnasium, SB3 and Torch before its complete PPO workflow. Four available Gymnasium-only environment tests still execute. The new eight interval-boundary cases mock only unavailable training/loading entrypoints and deliberately raise if those entrypoints are reached; their passing result proves admission behavior, not a successful PPO run.

## Fresh independent execution

Runtime: repository `.venv/Scripts/python.exe`, Python 3.12.14, pytest 9.1.1, Windows. Availability inspected before execution: Gymnasium present, Stable-Baselines3 absent, Torch absent. No model training, network request, package installation, market download, account operation or trading action ran.

From `eth-btc-research/crypto-paper-agent`:

```powershell
../.venv/Scripts/python.exe -X utf8 -m pytest tests/test_cache_integrity.py tests/test_rl_interval_boundaries.py tests/test_rl_env.py tests/test_quickstart.py -q -rs --tb=short --basetemp ../../tmp/ic31 --junitxml ../../tmp/graphify-20261030/independent-integration-tests.xml
```

Result: **31 passed, 2 skipped, 2 warnings in 3.24s; exit 0.** Breakdown: cache integrity 19 passed, RL interval admission 8 passed, existing Gymnasium environment tests 4 passed. The real PPO train/save/load test and complete quickstart were the two dependency skips; no cases were deselected. The warnings are Gymnasium's ignored `check_env(warn=...)` argument and inability to test alternate render modes without an environment spec. Complete log and JUnit XML are adjacent to this report.

The root author's `full-core-final.log`/`.xml`/`.exit` were read: **1435 passed, 6 skipped, 5 deselected, 2 warnings in 202.78s; exit 0.** This is inspected author-run evidence, not a full-core rerun by this reviewer. It must not be added to the 31 scoped passes as though the cases were disjoint.

## Limits and identity

Not checked: real SB3/Torch model training/save/load, complete quickstart, optional-runtime package installation, network/public feed behavior, real historical-data provenance, full-year replay, frontend or Windows lifecycle, concurrent multi-process cache writers, remote publication, owner acceptance or profitability. No claim that a strict cache index validates all OHLCV values or establishes dataset provenance; downstream dataset and evidence contracts remain necessary.

The review used the current working directory, not an isolated snapshot. Source hashes below identify the observed bytes at final review; this reviewer does not claim that a before-test immutable snapshot was taken. Recheck these identities before commit if concurrent authors modify the scoped files.

- src/data_layer/cache_manager.py: `60e5f64c43b68175bb88ffdad3dbe0a92317d12fb60476637f9197d7da4f00b1`
- src/data_layer/fetcher.py: `9d7c40372846a259a3a72a50f65bb44db7d5660d8d2041f1f365e8dd44d41ae6`
- src/research/rl_env.py: `3fac0c0410de990a8585d1c03bbf055d78ca67c39fab49bc470231825ccb7cce`
- tests/test_cache_integrity.py: `1afa3c4284131e3e7419eebb06ec0342763990f9c2722374ccacdedf8e4a2049`
- tests/test_rl_interval_boundaries.py: `ee879afb49f110da7d5b88316c8e37b50b14bbdcdfa27429875ba24cf6b02fde`
- tests/test_rl_env.py: `d0e67879a9553249b484abb89715dade0c79649ee4e6778bfd62c866433bd081`
- tests/test_quickstart.py: `9322ed805f2cb4cf809e9e77036a37340751b94122b31468dc91328b06d4d8e3`
