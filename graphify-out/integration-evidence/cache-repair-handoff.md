# Selective cache-integrity repair handoff — 2026-10-30

Parent-authorized exclusive scope: two current-main production modules and the original branch regression module. Base main `3f76782ca49626dc14daed6afd2fc36998fecead`. No index/ref/commit/GitHub mutation, market data download, real order, owner account or OS task action.

## Change

- `src/data_layer/cache_manager.py`: validate monotonic, unique, non-NaT UTC datetime indices before slicing; recognize the actual single Parquet index from pandas metadata (including `open_time`); require every inclusive bar-open slot through the requested end rather than endpoint-only/99-percent completeness. Partial final intervals correctly use their contained final bar open.
- `src/data_layer/fetcher.py`: use the actual loaded frame as the hit/miss decision for OHLCV/OI/funding, eliminating the metadata/read race and `len(None)`. Validate fetched OHLCV completeness **before writing cache or admitting merged input**. Existing `FetchError`, OI/source availability and one-second funding settlement/decision protections remain unchanged.
- `tests/test_cache_integrity.py`: exact byte-for-byte export of the original PR6 module (nineteen assertions/cases) without weakened expectations or new skips.

Only the three files above are owned by this worker. `git diff --check` for production scope is clean; production diff is 31 insertions / 38 deletions. No other caller edits were required by the tests run.

## Fresh verification

RED original module against unchanged main: **17 failed, 2 passed in 2.02s**, output `cache-integrity-main.log`; external copy `test_cache_integrity_remaining.py` is preserved. Failures establish gaps/malformed index/endpoints, named-index lookup, metadata-to-read race and incomplete fetched admission.

GREEN source and old original assertions:

```text
python -m pytest tests/test_cache_integrity.py tests/test_data_layer.py tests/test_fetcher_fail_closed.py tests/test_fetcher_public_only.py tests/test_input_fidelity.py tests/test_public_data_pipeline.py tests/test_vision_dataset.py tests/test_universe_loader.py tests/test_synthesized_input_contract.py -q --tb=short -m 'not network' --basetemp ../../tmp/graphify-20261030/cache-green-fixtures --junitxml=../../tmp/graphify-20261030/cache-green.xml
105 passed, 5 network deselected in 5.51s
```

Actual CLI and settlement callers:

```text
python -m pytest tests/test_stage_06_integration.py tests/test_g0_settlement_lifecycle.py -q --tb=short -m 'not network' --basetemp ../../tmp/graphify-20261030/cache-callers-fixtures-2 --junitxml=../../tmp/graphify-20261030/cache-callers-2.xml
36 passed in 31.59s
```

These two scopes do not overlap: 141 distinct passing tests, no skips, five network tests deselected. XML/logs remain beside this handoff. An initial caller command named nonexistent `test_stage_05_integration.py`, so collected zero tests/exit4; that failed invocation is retained in `cache-callers.log`, not counted as test evidence.

## Limits

Parent owns fresh-context independent review and final full-core integration. Full-year synthesized E2E, live/public runtime, browser, RL and actual venue data authenticity were not run by this worker and are not implied by cache-contract success. Strict exact-cadence cache admission can cause a cache miss/refetch where an older 99-percent heuristic had declared a partial input complete; that is the intended fail-closed change. Source declarations and old synthetic evidence cannot become historical proof through this repair.

Exact source SHA256s:

- `crypto-paper-agent/src/data_layer/cache_manager.py`: `60e5f64c43b68175bb88ffdad3dbe0a92317d12fb60476637f9197d7da4f00b1`
- `crypto-paper-agent/src/data_layer/fetcher.py`: `9d7c40372846a259a3a72a50f65bb44db7d5660d8d2041f1f365e8dd44d41ae6`
- `crypto-paper-agent/tests/test_cache_integrity.py`: `1afa3c4284131e3e7419eebb06ec0342763990f9c2722374ccacdedf8e4a2049`
