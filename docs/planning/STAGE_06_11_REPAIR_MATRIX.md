# Stage 6–11 repair requirement matrix

Authority: user task 2026-09-21 authorizes continuous implementation through PPO and branch push. Historical stop-before-7 / optional-RL instructions are superseded. No main merge, force push, credentials, live/testnet or paid resources.

Final code under test: `23f94376215a7fca69c8a7606e34139bc21d090c`. All implemented rows: **IMPLEMENTED AND AUTHOR_TESTED — PENDING INDEPENDENT REVIEW**. Results: [repair report](../reviews/STAGE_06_11_REPAIR_REPORT.md), [actual evidence](../reviews/evidence/stage-06-11-repair/).

| Finding / requirement | Cause | Production repair / decision | Regression / actual evidence |
|---|---|---|---|
| Offline CLI loads network for supported strategy | Breakout incorrectly used as unsupported fixture | Invalid argparse strategy rejected before I/O; cached offline subprocesses with timeouts | `test_backtest_engine.py::test_cli_invalid_strategy_fails_clearly`; full offline, clean checkout |
| Calendar str vs Path / cross-root / content identity | Filename exclusion discarded semantics | Content SHA, portable placeholder; repeat canonicalization stable | `test_trade_logger.py::test_calendar_identity_idempotent_and_path_equivalent`, `test_enabled_news_calendar_identity_uses_content_digest` |
| Calendar changes between identity and report | Multiple filesystem reads | `snapshot_run_config` uses digest of exact bytes parsed by filter; shared frozen calendar in CLI/folds/PPO | `test_snapshot_uses_parsed_bytes_after_source_changes`; final config audit |
| Custom config metadata lies about source | Hardcoded default path | repo-relative config or `<CONFIG_PATH>`; ISO aware UTC supported | `test_stage_06_integration.py::test_cli_end_to_end_with_report_generation`; four external CLI executions |
| JSON / Markdown / SQLite / run ID diverge | Different normalization or output roots | Shared canonical config, deterministic identity, cross-root tests | `test_config_identity_is_cross_root_and_sensitive_to_fees`, `test_deterministic_run_id_across_invocations` |
| Exact artifact hash mismatch on Windows | CRLF output vs LF hashed string | Atomic UTF-8 LF output matches bytes and SQLite payload | `test_comparison.py::test_research_manifest_matches_exact_file_and_sqlite_bytes`; observed pre-fix failure in saved PPO evaluate test, corrected pass |
| Benchmark claims overstated | Historical author report treated as verified | ADR0009 numbers explicitly AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED; dynamic strategy ranges and sample-unit label | ADR0009, `test_smc_liquidity_sweep.py`, report audit; historical replay NOT_VERIFIED |
| Breakout LONG/SHORT not demonstrated | Inadequate fixtures / names | Separate real opposite direction setups and completed broker trades | `test_real_long_short_retest_and_duplicate_event`, `test_breakout_broker_logger_report_nonempty_and_fill_risk` |
| Immediate/duplicate/future signal | Missing event identity and valid historical baseline | Previous-only volume, breakout→retest state, repeated event ignored, reversal rejected | `test_breakout_waits_for_retest_and_builds_rrr_two_order`, `test_invalid_historical_volume_cannot_be_skipped_in_baseline`, `test_future_perturbation_preserves_orders` |
| Retest invalidation/timeout/conflict | Under-tested state transitions | Retest close, volume, timeout and position/pending conflicts gate setup | `test_long_breakout_fakeout_invalidation`, `test_setup_timeout_high_volume_retest_and_pending_conflict` |
| Fill SL/TP and risk/margin | Must check actual fill, not signal estimates | Broker preserves absolute SL/TP and validates fill bounds; no forced RRR rewrite | `test_breakout_broker_logger_report_nonempty_and_fill_risk`, `test_breakout_request_rejected_by_shared_gate` |
| Basket spends capital twice | Unfunded independent notionals | Matched q constrained by spot cost + perp collateral + both fees; total stop-risk budget | `test_capital_never_double_spent_and_excess_requested_rejected`, `test_two_leg_hand_oracle_negative_distinct_settlements` |
| Basket bypasses gates | Standalone price arithmetic | Existing invariant/news/breaker/maintenance adapter, atomic both-leg admission; ADR0011 | `test_locked_basket_admission_has_no_half_position`, `test_forced_paired_unwind` |
| Funding counts arbitrary rows | No settlement identity/provenance | Explicit observed vs settled values; UTC unique schedule, 24h source freshness, readiness; duplicate rejected pre-mutation | `test_time_and_funding_provenance_fail_before_mutation`, distinct-negative-settlement oracle |
| Basket malformed money / empty/no-entry / unrealized | Missing domain/schema | Strict bool/NaN/Inf numeric validation; valid result schema; force-close costs and open-end unrealized | `test_invalid_money_rejected`, `test_malformed_config`, `test_empty_no_entry_and_open_end_schema` |
| Basket lacks production runner/report | Helper only | Dedicated + main basket CLI, cash ledger and portable transactional reports | `test_funding_deterministic_replay_and_persisted_identity`, public `cli-basket.txt` |
| SMC midpoint impossible on creation bar | Same-bar midpoint containment | Causal sweep→BOS/displacement→FVG available→resting later limit | `test_fvg_before_retest_has_no_fill_and_limit_expires`, LONG/SHORT E2E |
| SMC OB absent or ignored / backdated swings | Feature availability undefined | Confirmed levels; last opposite body before structure break; configurable directional OB distance confluence | `test_swing_confirmation_and_order_block_body_not_backdated`, `test_order_block_confluence_changes_admission` |
| SMC 5m/1m only labels | Fixed engine cadence | Actual configured signal/execution durations and overlapping-candle rejection | `test_long_short_completed_5m_1m_trade_with_partial_accounting`; all four CLI caches |
| Partial exits metadata only | No broker quantity/accounting support | Real 40% at 1.5R, 30% at 3R, 30% trailing; proportional collateral/fee/funding allocation | `test_partial_then_funding_preserves_cash_collateral_and_streak`, SMC both directions |
| Same-bar limit profit / BE / ambiguity | OHLC ordering unknown | Next-bar limit, no same-bar intrabar TP; stop wins; post-close BE, next-open exit if crossed | `test_limit_wait_expiry_and_no_same_bar_profit`, `test_same_bar_stop_wins_over_partial_tp_and_invalid_partial_is_atomic` |
| Partial funding/breaker corruption | Realization needs lifecycle accounting | Gap partial before funding uses remainder; per-slice cashflow once; final position streak once | `test_gap_partial_occurs_before_settlement_quantity`, `test_partial_cashflow_can_lock_and_force_remainder` |
| Invalid partial price may mutate cash | Large SHORT R target <=0 | Reject nonfinite/nonpositive actual-fill target before fee debit | `test_nonpositive_partial_target_rejects_before_cash_mutation` |
| SMC invalidation and no-lookahead | Temporal setup not retained | Setup timeout/invalidation; no backdated OB/swing/FVG | `test_setup_timeout_and_invalidation`, `test_future_perturbation_preserves_features_signals_orders_trades` |
| OOS time reversal / overlap | Unvalidated splitter | Sorted unique UTC, positive integral sizes, test step >= test length | `test_walk_forward_rejects_unsorted_duplicate_non_utc`, `test_split_sizes_and_overlap_fail_closed` |
| OOS metric name mismatch | `net_pnl` helper vs engine | Strict `total_net_pnl` contract | `test_compare_requires_engine_metric_contract`, `test_walk_forward_no_train_test_overlap_and_oos_aggregate` |
| OOS only helper / contamination | Missing orchestration and boundary policy | Four independent accounts; fixed rules; past warm-up; no positions carried; forced closing costs | `test_four_strategy_workflow_real_execution_and_artifacts`, synthetic/public `smoke.txt`, `cli-all.txt` |
| PPO always raises / price toy | Stub with no execution model | Real Gymnasium PaperBroker adapter, SB3 PPO CPU train/save/load/evaluate script | `test_gym_reset_step_checker_contract`, `test_real_ppo_train_save_load_and_final_holdout`, public256 smoke + external evaluate |
| RL bypass / reward violations wrong | Action not tied to gate, price loss mislabeled | Broker request with stop; rejected/invalid action penalty; realized net/initial - .5*incremental DD - violations | `test_actions_cannot_bypass_risk_and_realized_reward_matches_ledger`, `test_scaler_train_only_and_invalid_action_is_penalized` |
| RL train/test leak / missing metadata | No scaler boundary/model identity | Train-only scaler, strict chronology, holdout unused in train, seeded deterministic load replay, data/model/report checksums | `test_future_perturbation_preserves_observations_and_actions`, `ppo.report.json`, `ppo.manifest.json`, evaluate-only equality |
| False completion claims / subset pass | Old evidence reused | Full A gates and independent clean checkout; exact logs; no acceptance wording | offline356+skip2, network5, R05=26/R06=11/R07=3; PENDING INDEPENDENT REVIEW |

## Remaining criteria

| Criterion | Status | Reason |
|---|---|---|
| Full intended historical-window benchmark / nonempty directional public benchmark | PARTIAL / NOT_VERIFIED | Only bounded three-day public input, one-day comparison OOS; no parameter tuning to force trades |
| PPO profitability / generalization | NOT_VERIFIED | 256-step smoke loss-making; engineering evidence only |
| Independent approval of Stage 6–11 | PENDING INDEPENDENT REVIEW | Author execution is not independent review |
| Shared-capital portfolio | NOT_IMPLEMENTED | Stage10 uses documented independent accounts; no pooled-equity claim |
| Whole-position statistics for partial exits | PARTIAL | Realizations accounted correctly; statistical sample remains slices |
| Environment blocker | NONE OBSERVED for executed gates | Dependency install, public download and network tests succeeded |
