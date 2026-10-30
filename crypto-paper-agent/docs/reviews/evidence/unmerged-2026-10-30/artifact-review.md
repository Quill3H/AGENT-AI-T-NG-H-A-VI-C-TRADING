# Current-main synthesized artifact verification — 2026-10-30

Verifier: independent artifact_verification agent. Scope: offline paper research only; no market download, no main/ref/GitHub mutation. Source exported by git archive from d4cc137e819d579e2446d01a0972d3ceb5997f6e. Python: repository .venv/Scripts/python.exe, Python 3.12.14; pandas-ta unavailable, documented pure-pandas fallback used.

## Identity and preservation
Seven original artifacts copied from output/synthesized-retest-2026-10-29/repo/crypto-paper-agent/reports/synthesized_backtest_1y. All seven SHA256/byte sizes match; identity.json records source paths and exact hashes. Production and original artifact bytes preserved. Artifact summary reports code_commit_sha=4e3a6192bcebdf548906b88fb578e14156f27eb5; this is an artifact-reported identity, not proof that its source matched that commit. Current source SHA256s recorded independently in artifact-audit.json. Audit I/O and archive identity adapted in copies only; no assertions weakened.

## Executed verification
- Current source: tests/test_synthesized_strategy.py + tests/test_adversarial_m2_audit.py + tests/test_adversarial_m2_empirical.py: **44 passed in 20.90s**, no skip/exclusion. artifact-suites.log / artifact-suites.xml.
- Read-only independent artifact/cache audit: exit0; SQLite integrity_check=ok. artifact-audit.log / artifact-audit.json.
- Independent current-source contract probes: **6 failed, 2 passed in 2.40s**. Failures retained verbatim in review-probes.log / review-probes.xml; original assertions unchanged.
- Current-source cross-symbol causality reproduction: exit0, all defect-demonstration assertions pass. cross-symbol.json / cross-symbol.log.
- Initial worker full-year tests/test_e2e_synthesized_backtest.py: **INTERRUPTED without exit marker**, full 2025-01-01..2026-01-01 window; PYTEST_FAST_E2E unset; allow_network=False; fresh isolated caches from deterministic synthetic generator. Collected20 tests. e2e.log / e2e.xml / e2e.exit when finished. This is a synthetic engineering replay, not market/economic validation.

Commands use the pinned repository .venv runtime, immutable exported source package as CWD, and -m pytest with unique --basetemp/--junitxml targets. Full exact launched commands are in execute-commands.txt.

## Independent ledger findings
6,455 completed lifecycles / 10,892 realization slices; final equity8,719.665616475051 from100,000. Gross=-46,319.855664844305, fees44,916.96411454944, funding=-43.51460413103372, net=-91,280.33438352478. Reconciliation difference=-1.6916601452976465e-10. Max drawdown92.60192214798693%; PF0.7504314820396867; lifecycle win rate49.20216886134779%; expectancy=-14.141027789856668. Even zero-fee same-fill path remains negative (-46,363.37); stated maker0.02% vs taker0.05% saves26,950.18, not >35,000, and remains -64,330.16. This fee sensitivity assumes identical fills and does not model maker executability.

## Blockers
1. **P1: cross-symbol future close changes earlier fills.** Runner scripts/run_synthesized_backtest.py:293-298 processes a complete candle per symbol before next symbol; paper_broker.py:807-808 sizes using shared current equity and917 stamps open_time. Holding both requests and ETH candle fixed, BTC01:15 close100→110 changes ETH01:00 quantity197.01326797544215→200.8959149700307. Within-symbol Causal4hCache tests do not catch this portfolio lookahead.
2. **P1: historical provenance claim unsupported/misleading.** All OHLCV rows in each of the ten original15m datasets exactly equal current deterministic seed42 synthetic generator. Twenty cached datasets checked; 4h closes also match generator per prior pinned comparison, but full4h OHLCV is not byte/equality identical and is not claimed as such here. Original summary data_provenance says Binance/auto and does not disclose synthetic. universe_loader.py:619-632 silently falls back and writes synthetic frames into ordinary cache paths. Structural artifact pass cannot establish real historical validity.
3. **P1: acceptance permits economically failed/risk-violating path.** tests/test_e2e_synthesized_backtest.py:198-202 accepts win_rate>=40% even if net/expectancy negative and PF<1. Lines213-219 allow a95% drawdown ceiling in full mode. Both gates accept this92.60%DD/-91.28% original path. Passing the suite cannot honestly be labeled economic or project risk acceptance.
4. **P2: funding evidence is fabricated/defaulted and filter fails open.** runner.py:235-238 replaces missing/NaN funding with0.0001. SynthesizedStrategy._apply_funding_filter lines732-738 approves missing/invalid/nonfinite funding; fresh probe confirms enabled filter approves{}. All4,816 original funding records have0.0001. The tiny observed funding cannot establish successful avoidance of actual historical carry.
5. **P2: handoff describes different runtime and inaccurate benefits.** Current loaded parameters ADX20, partial exits1R/50% and2R/25%, leverage2.5, versus handoff ADX25 and1.5R/60%,2.5R/25%. Handoff fee saving >35k is unsupported; initial checkpoint funding wording also conflicts with actual-43.51. Original source is preserved; docs should be corrected separately by owning agent.

## Verdict
**Structural artifact suite: VERIFIED_PASS (44/44). Independent acceptance: REQUEST_CHANGES / NOT_ACCEPTED.** No profit, historical validation, production readiness or broad engineering gate acceptance follows. Full E2E completion will be recorded below without weakening this verdict unless the cited blockers are actually repaired and independently verified.

## Additional artifact-to-cache provenance join

Fresh read-only join verifies **10892/10,892 original realization-slice entry prices** equal the corresponding known-synthetic15m cache open at recorded entry_time plus/minus exact3bps adverse slippage (relative tolerance1e-11, absolute1e-8), across all10 symbols. This links the reported executions themselves to the synthetic price path, rather than merely observing a current cache. Evidence: artifact-cache-link.json/log and link_artifacts_to_cache.py. Original handoff pair contribution counts also disagree with independent SQLite counts (details in artifact-audit.json).


## Root-session full-year completion

The initial worker lost its session due to usage limits and had no running Python process or exit marker. The root reran the unchanged full-year command with PYTEST_FAST_E2E unset, allow_network=False, fresh e2e-root-fixtures, and identical pinned exported source. **20 passed in 1534.66s (25m34s), exit0**; no tests excluded. Logs e2e-root.log/xml/exit. This is a synthetic engineering replay; the REQUEST_CHANGES acceptance verdict remains. After completion, all seven ORIGINAL SHA256 values were rechecked and unchanged.
