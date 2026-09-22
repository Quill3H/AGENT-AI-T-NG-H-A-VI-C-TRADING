# G2 Binance public-data diagnostic — 2026-09-22

**AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED.** This is a narrow G2 data-integrity slice, not G2 acceptance, a native TradingView Strategy Tester result, an economically validated strategy, or prospective paper trading. All HTTP was public/read-only; all order effects stayed in local simulation. No testnet/live order, trading credential, wallet, or money was used.

Code-under-test commit: `d4afed6d365b3e435e79a772f7de912ee4a39b11` (`codex/g2-binance-funding-coverage`). Documentation commit: see Git history and final handoff. Parent documentation checkpoint: `4b26525cc0c12b73b47d93242b218e24674f1ea6`; parent code checkpoint: `51b039b5e1b4ec0b649e9d2604a93a83f01b0a73`. `main` was observed at `e970337d504563e5987a4db6b5c06c635bf7244b` and was not changed.

## Decision and implementation

ADR 0011 requires an exact source funding timestamp and readiness at a nominal 00:00/08:00/16:00 UTC settlement boundary. The August 2026 Binance archive and public REST endpoint agree on millisecond timestamps that sometimes occur **after** the nominal boundary. Rounding or backdating them would introduce unavailable information. The existing broker/simulator therefore remains fail-closed. This commit only adds `funding_settlement_coverage` to `dataset_manifest.json`: expected boundaries, exact-ready boundaries, missing candle rows, post-boundary source events within the next minute, maximum delay, and explicit UTC unready boundaries. It validates both the basket row and the raw funding event before marking a boundary exact. It does not change cashflow timing, risk policy, or the four-strategy comparison.

Code/test files: `src/research/artifacts.py`, `scripts/prepare_public_research_sample.py`, `tests/test_public_data_pipeline.py`. The regression suite includes exact, delayed, absent, missing-candle, source-mismatch and mocked-archive cases. The first test run failed at collection because the new function did not exist; focused tests passed after implementation. Author self-review caught two potential overclaims and corrected them before code freeze: renamed a general “replay eligible” flag to `exact_funding_coverage_complete`, and required the raw source event independently of the basket flag. Coverage is calculated before output-directory creation to avoid partial output on coverage validation failure. No new Critical/High finding remains in this scoped diff; independent review is still required.

## Bounded archived sample

Reproduction from `crypto-paper-agent/` (or an external CWD using the absolute script path):

```text
python scripts/prepare_public_research_sample.py --start 2026-08-20 --days 7 --retries 2 --output <NEW_PUBLIC_DIRECTORY> --allow-network
python scripts/run_funding_arbitrage.py --input <NEW_PUBLIC_DIRECTORY>/basket.parquet --source "Binance Vision public archives" --output <NEW_OUTPUT_DIRECTORY>
```

The seven *fully closed* UTC days are 2026-08-20 00:00 through 2026-08-26 23:59. The public Vision download read seven spot 1m, seven USD-M perpetual 1m, and one monthly funding ZIP; all 15 ZIP SHA-256 values matched Binance's adjacent `.CHECKSUM` files. A second clean-checkout/external-CWD download produced the same 15 source ZIP hashes and all six normalized dataset hashes. The USD-M public funding REST endpoint returned 21 events with timestamps matching the monthly archive's 21 events in this range. These are author checks, not independent verification.

| Dataset | Rows | Gaps | Logical SHA-256 |
| --- | ---: | ---: | --- |
| Perpetual 1m | 10,080 | 0 | `af2ceb7553600f75f4663a3b9ab75c2371ff86aebbac7800d33c74ee367159be` |
| Spot 1m | 10,080 | 0 | `c86f0f8ff669840a85b24acc9664b829d300dd0133bd311bcf50f681dcd438ba` |
| Synchronized basket 1m | 10,080 | 0 | `da3c2fe65e98c317b001000a7379e56e1c5676cd3d7dea063a72e783497d4747` |
| Perpetual 5m | 2,016 | 0 | `292be9058a0234d204bcadc0826fdeb1f1aecc6f89e38fb69b042e57da7bd70c` |
| Perpetual 15m | 672 | 0 | `1925a0aa2ededb0b6e4f9d365a82d9201ebab171026abc69119a0ac29750ffbd` |
| Perpetual 4h | 42 | 0 | `95dbd2f16db1eee2b0bdf6ab0865b070463b1fae9444406f712b659312e40d63` |

Clean-checkout `dataset_manifest.json` file SHA-256: `bbe41d896e16802e547b4ba8076f69579bbba6a890355b34efb785b482784ba7c`. It contains no absolute machine path. Spot and perpetual quotes are distinct, not a duplicated leg.

Funding coverage: **21 expected, 11 exact-ready, 10 unready; all 10 unready source events arrived 1–6 ms after the nominal boundary; 0 missing basket candle rows**. `exact_funding_coverage_complete=false`. The full seven-day funding CLI returned `ERROR [INVALID_INPUT]: funding_readiness must be True at settlement` (exit 2) and created no output. A deliberately *integrity-selected*, nonrepresentative 2026-08-22 UTC one-day slice had 3/3 exact boundaries and ran the basket simulator with 0 entries, 0 PnL, 10,000 USDT final equity, and accounting invariants verified. This is not a profitable or representative sample.

Fixed-rule full-window directional diagnostics on the same seven-day data, without parameter changes: Trend 0 fills/0 completed positions/0 PnL; Breakout 0/0/0; both final equity 10,000 USDT and accounting reconciliation verified. SMC **FAIL_CLOSED** at 2026-08-25T00:00:00Z because funding was not ready; no final SMC metric was asserted. The Trend/Breakout window has only 42 four-hour bars, missing OI, and no actual taker-buy field (CVD falls back to 50% volume). These are constrained diagnostics, not a four-strategy OOS ranking. The full canonical 2021–2026 history, untouched holdout and prospective paper observation remain NOT_RUN/NOT_VERIFIED.

## Near-current public REST snapshot

Read-only command:

```text
python scripts/fetch_market_data.py --symbol BTCUSDT --interval 15m --kline-limit 500 --funding-limit 100 --output-dir <NEW_CACHE_DIRECTORY> --allow-network
```

At 2026-09-22T16:38:12Z the cache held 500 UTC BTCUSDT perpetual 15m rows from 2026-09-17T11:45 to 2026-09-22T16:30, 0 gaps/duplicates, plus 100 funding events. The 16:30 candle was *still open* and was excluded. The remaining 499 closed candles ended at 16:15; their 16 expected funding boundaries had 9 exact timestamps and 7 delayed by 2–7 ms, with none missing. Parquet file SHA-256 values: 15m OHLCV `45a7005c27689ba807587236fd344ce40026acb256cf52f6af7e1dc14e5ee109`; funding `35b548d4487181e4f1b3510371cc1b2a2eb40dd971e9ef1476d776ce64204141`. This REST cache does not preserve raw HTTP payloads or a source-response manifest, contains no synchronized spot/1m execution data, and was **not** treated as a prospective paper session or used for an executable-fill claim.

## Verification on exact code commit

Runtime: pinned external QA Python 3.12.14, pytest 9.1.1, pandas 3.0.6; no fresh package install in this gate. From `crypto-paper-agent/`:

| Command | Author result |
| --- | --- |
| `python -m pytest -p no:cacheprovider tests/test_public_data_pipeline.py tests/test_g0_settlement_lifecycle.py -q` | 30 passed in 8.15 s (pre-commit final focused behavior) |
| `python -m pytest -p no:cacheprovider -m "not network" -q` | 412 passed, 2 skipped, 5 deselected, 2 warnings in 128.32 s on commit A |
| `python -m pytest -p no:cacheprovider docs/reviews/test_stage_04_review_05.py docs/reviews/test_stage_04_review_06.py docs/reviews/test_stage_04_review_07.py -q` | 40 passed in 1.91 s: Review05 26, Review06 11, Review07 3 |
| `python -m pytest -p no:cacheprovider -m network -q` | 5 passed, 414 deselected in 16.64 s |

The two skips are optional `pandas-ta` tests; Gymnasium emitted two non-fatal API/registration warnings. An external-CWD invocation on a detached clean A with no `--allow-network` returned `NETWORK_DISABLED` and created no output; the authorized seven-day invocation succeeded with identical source/dataset hashes. The original user checkout's unrelated `AGENTS.md`, `.serena/` and planning file changes were not touched.

## Open decisions and next owner

1. **Owner/PM decision required before any policy change:** preserve ADR 0011 exact-boundary semantics and accept partial eligible windows, or design/approve event-time settlement on the first available later candle with explicit accounting and no lookahead. This commit deliberately does neither reinterpretation nor parameter tuning.
2. G2 is incomplete: preserve raw REST payload/version and fetch timestamp, validate OI/taker fields and all cache gaps/duplicates, add broader historical coverage, then freeze chronological experiments before G3/G4.
3. Separate Tester should replay code A, verify the 15 source checksums and 21 funding timestamps, and run artifact/accounting checks. Independent Reviewer should audit the source-availability decision and report semantics. PM records their verdict; only the owner accepts a gate. No self-acceptance or `main` merge.
