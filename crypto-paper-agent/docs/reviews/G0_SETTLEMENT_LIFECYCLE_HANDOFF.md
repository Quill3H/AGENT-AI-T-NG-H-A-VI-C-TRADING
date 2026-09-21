# G0 settlement and completed lifecycle handoff

## Identity and authority

- Branch: `codex/g0-market-validation`.
- Code A: `2c9a4d0985fc9eafd29386482793425c26d47835`.
- Plan commit: `b6915c98a460d242530b2e302b34d7855300ff18`.
- Baseline old code A: `23f94376215a7fca69c8a7606e34139bc21d090c`; old docs B: `c81dc4e5ec7588f2958da319ca709f13e97ad95f`.
- New docs B is a documentation/evidence-only child of A; its full SHA is supplied in the final PM handoff (a commit cannot embed its own SHA).
- Main remains `e970337d504563e5987a4db6b5c06c635bf7244b`; no merge/force push.
- PM coordinates Tester and Independent Reviewer. This report is author execution evidence, not independent acceptance. User decides acceptance/merge.

## Behavioral contract

### Funding

An existing position surviving gap exits can settle only when funding source timestamp equals the current settlement boundary. Reusing/revising source08 at row16 raises `ValueError` containing `FUNDING_SOURCE_EVENT_MISMATCH`, before account/position/history/breaker/clock mutation. It is not skipped and presented as a paid16:00 settlement. An exact-source zero rate is valid. Existing future/stale/type/readiness error contracts remain distinct.

Basket simulation validates the entire input before running; an invalid full frame leaves its breaker untouched. Broker streaming tests first settle08 successfully, then reject16 atomically. Distinct source16 remains payable. Full gap exits precede funding; gap partial exits settle the remaining quantity. Funding never creates a completed trade by itself.

`funding_readiness` in the data layer is shared with the public-sample preparation script, including resampled5m/15m/4h and basket inputs. Past rates may remain observations between boundaries; missing exact boundary events are unready. This does not solve duplicate/revised raw archives, all cache gaps or OI freshness; those remain G2 work.

### Completed lifecycles and raw cash records

Every new Position has a real lifecycle ID from position_id and original quantity, including direct construction outside normal fills. Each exit TradeRecord retains a distinct raw row ID and metadata lifecycle_id/lifecycle_quantity/lifecycle_complete. Raw slices remain in the trade ledger/SQLite/trades JSON; no slice is discarded to manufacture a win rate.

Primary trade count, win/loss rate, expectancy, USD-based SQN, direction counts, completion-order streaks and benchmark comparison use completed lifecycles. R is aggregate net PnL divided by aggregate allocated initial risk; slice R values are not averaged. Unfinished lifecycles are excluded from the primary sample. All their realized cash amounts remain in ledger reconciliation and `realization_slices` diagnostics. Backtest total_net_pnl is ledger cash PnL; completed_lifecycle_net_pnl is the completed sample's net PnL. Expectancy uses the latter sample.

The new helper rejects inconsistent identities, missing/duplicated slices, invalid terminal markers and quantity mismatches. Legacy closed-input dictionaries with explicit position_id group by run/symbol/position; caller declares that markerless legacy list closed. Untagged legacy full trades remain individual samples. A legacy partial without identity fails closed. A markerless historical list cannot independently prove completeness; do not use it as verified lifecycle evidence. R is unmeasured for multi-slice legacy groups without initial risk.

No schema additions were made to the strict top-level trades.json export. Lifecycle evidence is retained in SQLite metadata and raw broker records; summary metrics disclose the sample unit. Historical serialized partials lacking identity need explicit migration/reconstruction, not guessed grouping.

## Code scope

| File | Change |
|---|---|
| src/execution/paper_broker.py | Exact-source preflight/settlement key; immutable original quantity at normal entry; ID/completion on exit rows |
| src/execution/order_models.py | Original quantity and real lifecycle ID for direct Position construction; TradeRecord described as a realization |
| src/strategies/funding_arbitrage.py | Exact boundary validation and source event key |
| src/data_layer/fetcher.py | Shared boundary-aware funding readiness |
| scripts/prepare_public_research_sample.py | Shared readiness applied to raw/resampled/basket preparation |
| src/report/lifecycles.py | Completed group validation/aggregation and completion ordering |
| src/report/metrics.py | Primary lifecycle statistics, raw slice diagnostics, unchanged ledger basis |
| src/report/generator.py | Explicit completed-lifecycle versus realization-slice labels |
| tests/test_g0_settlement_lifecycle.py | New behavioral oracles and offline external-CWD/ZIP preparation tests |
| scripts/verify_g0_replay.py | Offline LONG/SHORT SMC and distinct/reused funding replay with saved inputs and checksums |

## Regression matrix

| Path | Author test |
|---|---|
| Broker08 success → source08 reused/revised/zero at16 | test_broker_reused_or_revised_source_rejected_atomically; exact error and state equality |
| Basket reused/revised source | test_basket_reused_or_revised_source_rejected_before_simulation; exact error and untouched breaker |
| Valid distinct/zero funding; no manufactured trade | test_exact_distinct_zero_settlement_remains_valid; replay CLI distinct funding hand oracle1.6 |
| Missing source16 in preparation | test_merge_observation_is_not_missing_settlement_readiness; test_public_preparation_marks_missing_boundary_unready_offline across1m/5m/15m/4h/basket |
| Direct Position full/force/partial-final/breaker close | test_direct_position_lifecycle_identity_across_close_paths |
| Three slices / one completed position / weighted risk | test_three_slices_one_lifecycle_with_sum_risk_not_mean_slice_r |
| Mixed legacy A +10,+10,-30 / B +5 | test_metrics_group_explicit_position_identity_before_classification:2 trades,50%wins,expectancy-2.5,SQN-0.3333,net-5 |
| Unfinished position | test_unfinished_position_cash_reconciles_but_is_not_completed_trade:0 trades,75 realized,54 unrealized |
| Completion-order streaks / identity scope | test_completion_order_drives_streak_not_first_partial_time; test_legacy_lifecycle_identity_is_scoped_to_run_and_symbol |
| Missing/duplicate slices, malformed marker/original quantity | test_corrupt_lifecycle_records_fail_closed |
| Legacy ambiguous partial | test_legacy_partial_without_identity_is_not_assumed_complete |
| SQLite raw slices and completed run metrics | test_report_persists_raw_slices_and_labels_completed_positions, both complete/open-ended |
| Actual directional fills from strategy | existing test_long_short_completed_5m_1m_trade_with_partial_accounting and new external-CWD replay CLI |
| Prior accounting/causality/CB contracts | full offline suite and separate Review05/06/07 historical probes |

The frozen QA baseline probe and supplemental V2 are independently owned. Author tests and this matrix are not sole acceptance criteria. Reviewer should challenge malformed metadata, incomplete groups, accounting drift and source revisions beyond these fixtures.

## Verification and evidence

Exact-A commands/results, runtime metadata and SHA256 map are in `evidence/g0-2c9a4d0/`. Local originals: `G:/CODEX/g0-validation-2c9a4d0/`. `commands.json` records argv/exit/elapsed per command. `runtime.json` identifies Python/packages and requirements-repair-lock.txt digest. `checksums.json` covers logs and replay artifacts; replay/checksums.json independently covers replay inputs/outputs.

The evidence bundle contains39 checksummed files, approximately504kB including its checksum map and Git attributes. Outer checksums.json SHA256: `6c3b84fe6cb3163bb8233c3cda6436a481f645ada8ef54d8b499d9352e967b22`. Local `.gitattributes` disables text transformations so raw/input/log byte checksums survive another checkout. It and the checksum map itself are not entries in the outer map. Market raw archive/model artifacts from previous tasks are not included or claimed verified here.

Exact-A author verification completed:

| Command | Observed result | pytest time |
|---|---|---|
| Full offline | 382 passed,2 skipped,5 deselected,2 warnings; exit0 | 428.12s |
| Review05 | 26 passed; exit0 | 13.49s |
| Review06 | 11 passed; exit0 | 1.67s |
| Review07 | 3 passed; exit0 | 1.27s |
| External-CWD replay | LONG1 completed/3 slices and SHORT1 completed/3 slices, accounting verified; distinct funding1.6, wrong-source rejected with exact code; exit0 | wrapper15.281s |

The2 skips are existing optional pandas-ta comparisons;2 warnings come from Gymnasium checker deprecation/render-spec availability. Network tests were excluded explicitly. Full offline includes the synthetic PPO128 train/save/load/evaluate regression. Replay synthetic net PnL is449.2124 LONG and448.7951 SHORT; these are fixture outputs, not market performance.

Earlier development results are intentionally preserved:15 failed/1 passed before core repair; full intermediate1 failed/371 passed/2 skipped/5 deselected because direct Position lacked lifecycle quantity; that production path was fixed without altering the existing funding-zero assertion. Report test authoring initially used an incorrect JSON nesting; the corrected test then failed on missing lifecycle labels before the report fix. These are development failures, not evidence of a final pass.

Reproduce in an isolated Python3.12 environment with `requirements-repair-lock.txt` (includes Gymnasium/SB3/CPU Torch). Set PYTHONDONTWRITEBYTECODE=1 and OMP_NUM_THREADS/OPENBLAS_NUM_THREADS/MKL_NUM_THREADS=2. From crypto-paper-agent:

```text
python -m pytest -p no:cacheprovider -m "not network" -q -o addopts=
python -m pytest -p no:cacheprovider -q -o addopts= docs/reviews/test_stage_04_review_05.py
python -m pytest -p no:cacheprovider -q -o addopts= docs/reviews/test_stage_04_review_06.py
python -m pytest -p no:cacheprovider -q -o addopts= docs/reviews/test_stage_04_review_07.py
python scripts/verify_g0_replay.py --output-dir <NEW_EMPTY_DIRECTORY>
```

Replay can run from an external CWD using the script's absolute path. Generated Parquet inputs are synthetic and saved before execution; their byte hashes are in the manifest. No market raw files, archive downloads, current-market observation or economic benchmark is claimed. Network tests, full historical market data, market holdout and market PPO experiments are NOT_RUN in G0/G1. The offline suite includes an actual128-timestep PPO synthetic training/save-load/evaluate regression; that test is not a new market performance experiment.

## Remaining gates and risks

G0 is implemented for author verification and independent review; G1 evidence is bounded offline execution. Neither is self-accepted. G2–G4 remain planned: cache continuity, OI max age, missing-taker flags, raw source revisions, exact data coverage, bounded collection, cost sensitivity/uncertainty and a frozen untouched holdout. Primary SQN retains the existing USD sample definition (minimum2 nonconstant completed samples); it is descriptive and not statistical evidence of strategy quality. Three synthetic slices or one completed trade do not validate a market strategy.

Plan/budgets were sent to PM before implementation; no large market runs took place. Old public/PPO artifacts are historical AUTHOR_REPORTED evidence, not newly verified by this repair. Keep branch separate from main. Final routing is author → PM → Tester/Independent Reviewer → user decision.

PM relayed the product vision while G0 was running: explicit initial futures rulebook, learning from allowed training data, evaluation on historical years not used for learning, then prospective public-data paper operation only after a product effectiveness gate is defined and met. Product Owner/Business Analyst will define the primary strategy, learning boundary, measurable effectiveness gate and live-paper workflow. This is not authorization for realtime connector implementation or live/testnet/private orders. Preserve the2021-01-01→2026-09-01 benchmark; never tune to historical holdout. Further implementation waits for product contract and G0/G1 acceptance per the latest PM delegation.
