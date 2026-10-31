# Main coverage audit — 2026-10-30

Read-only independent branch audit. Current main: `3f76782ca49626dc14daed6afd2fc36998fecead`. Remote refs fetched from origin; main was clean at audit start. No production edit, merge, cherry-pick, GitHub mutation, market-data download, account/OS action or trading occurred. This is a source/contract audit, not gate acceptance.

## Answer to “all merged”

It is **not accurate to say every branch/PR is merged**. 9 of 18 non-main remote branch tips are ancestors of main. PR #5 and draft PR #6 remain open, both targeting `codex/local-paper-futures-app`, not main. Main commit 3f76782 contains their reviewed API/recovery composition, while deliberately preserving later main risk protections and the existing archived UI. Branch ancestry remains separate.

Ancestral merged branches:

- `origin/claude/project-thread-hz26f3` `d5a42ce478f68b8d932b5bb33a85d99e59dd736f`
- `origin/claude/project-thread-jrmpfx` `7bebd39a473dd5f6758f09015c6ca63a71dbbf44`
- `origin/claude/project-thread-ryvuyt` `fd466ace0b021e25155e6e5bcd6dabe30cf0a9d7`
- `origin/claude/project-thread-secv2t` `1ce0e3e40dac8a5ce8877017ec0fbf9791b4c847`
- `origin/claude/project-thread-uiqlsn` `ab1ad81ea8f8275e34803298ea1c7ad5c222a45a`
- `origin/codex/backtest-lab` `95af0a28d25b9dbcb7bdef83d33d01af025073b9`
- `origin/codex/eth-btc-cointegration-v1` `05a396f1f1568639e7fb86524c27c861e829386e`
- `origin/codex/external-repo-research` `89f16afa5616d3ed601fb8d224458f114b34f6a0`
- `origin/codex/research-qa-hardening` `f7650e3b7406a27fa64845b43bb0e9b06350c442`

## Genuine remaining correctness scope

### P1 — common cache integrity still absent

`origin/codex/windows-paper-replay` contains additive commit d021857 (`fix(paper): validate input coverage and enforce account writer ownership`). Its cache tests are absent on main. The exact original `tests/test_cache_integrity.py` was exported unchanged to `test_cache_integrity_remaining.py` outside production and executed against main:

```text
../.venv/Scripts/python.exe -m pytest ../../tmp/graphify-20261030/test_cache_integrity_remaining.py -q --tb=short --basetemp ../../tmp/graphify-20261030/cache-fixtures
17 failed, 2 passed in 2.02s
```

The 17 failures cover middle gaps with retained endpoints (1 or 50 missing observations across OHLCV/OI/funding), incorrect handling of a named `open_time` Parquet index, duplicate/off-grid/missing-boundary/out-of-order/NaT indices, stale metadata hit followed by actual cache miss (`len(None)` for OHLCV/OI/funding), and incomplete freshly fetched OHLCV admitted to merged research input. Original assertions and the complete RED log remain in this audit directory.

Selective implementation scope: `src/data_layer/cache_manager.py` (validate index and exact expected cadence including end boundaries; honor stored Parquet index metadata) and `src/data_layer/fetcher.py` (trust actual loaded frame, validate complete OHLCV before admission). **Do not replace fetcher wholesale from PR6**: that old version removes main's `FetchError` fail-closed behavior and one-second funding timestamp tolerance. Existing main protections and as-of OI provenance must remain.

### Optional RL correctness remains NOT_VERIFIED

`origin/codex/review-high-priority-data-fixes` at ffbc14b adds `_validate_candle_intervals` to `src/research/rl_env.py`, validates non-overlap within episodes, compares train/validation/holdout candle *close* boundaries, and disallows evaluating a saved PPO on the validation interval. Main only compares partition opens and saved evaluation after the training open endpoint. These are genuine additive leakage safeguards, not a superseded patch. Prior audit did not integrate them because gymnasium/PPO extras were unavailable; no fresh RL execution was attempted in this audit. The branch test modification removes main's optional import skip and must not be imported blindly.

## Functionally covered and superseded histories

- PR5 `cfc65046c13efd05d5a99eb63ace7368af0be73b`: closed-only chart/source UTC, per-symbol decision metadata, recovery/schema contract are selectively present in main. Current `/api/chart` accepts 1m/15m/4h; protected current-main recovery and request-time controls are retained. The new LocalPaperPanel uses BTC 1m only, so the richer branch UI is not claimed present.
- PR6 `b293ee1ce7a69fce6068816161e4c459e4b719b9`: causal replay, durable journals, typed recovery state, input ownership, trials/research diagnostics, simulated funding, lifecycle/launcher tests and API are selectively composed in main 3f76782. Later fixes reject unverified promotion; old positive diagnostics cannot allocate. The common cache integrity patch above remains genuinely absent.
- `origin/claude/project-thread-bla4me` `c0ca8dd95789f10bf18bf0e2745719d07e7a5c50`: pre-F5 alternate OI research history. Main already contains the reviewed stricter F5 behavior. The original audit demonstrated an unsafe 1% -> 5% loss-limit replacement and delayed exit on the alternate. Preserve historical run artifacts, do not overwrite main strategy with that old implementation.
- Older local-paper/stream/integration/windows branch histories predate the PR6 causal/recovery composition. Their legacy broker must not replace current broker guards. Their dated reports remain historical evidence, not a current acceptance verdict.

## Actually absent feature/operations helpers

These are not silently declared “merged” by the selective repair:

- Rich terminal `CandlestickChart.jsx`, timeframe selector, strategy signal/order marker display from `origin/codex/web-chart-timeframes-and-signals` `1876b134684be6e925d954c4bd3635b61d33fcdc`; main has a preserved archived chart/demo and a minimal current local PAPER table/control panel. The backend chart intervals exist, but this complete current UI does not.
- Windows `install-paper-task.ps1` / `uninstall-paper-task.ps1` are not in main. Main has launcher/management scripts and fixture lifecycle tests. Importing script source is distinct from actually installing or running a persistent task; this audit performed neither.
- `scripts/verify_paper_integration.py` and `scripts/verify_paper_public_runtime.py` are absent. They are optional author diagnostics requiring real public feed/browser runtime; existing root checks are fixture-driven and do not establish live soak/reboot evidence.
- PR6 v3 API examples/doc and historical moved docs are absent in main. Main has the current operation guide/schema and tests. Historical doc layout must not replace current authoritative checkpoint/AGENTS paths.
- Old UI evidence JSON/CSV files and retired branch snapshots are history, not missing live trading functionality.

## Recommended sequence

1. Integrate and independently verify the narrow common cache fix before calling remaining correctness work complete.
2. Resolve the optional RL leakage patch under declared dependency/test scope; preserve NOT_VERIFIED if not run.
3. Explicitly disposition optional richer UI/OS helper scope; do not use a wholesale obsolete branch merge merely to obtain ancestry.
4. Record branch dispositions alongside Graphify. Graphify can fully index current main without asserting that every old branch or operational/economic gate was accepted.

Full tip SHAs and per-branch added-path inventories are in `main-coverage-audit.json`. The original cache probe is the only test execution performed by this auditor; prior full-core/recovery/year outcomes are source-reported in the committed repair report and were not rerun here.
