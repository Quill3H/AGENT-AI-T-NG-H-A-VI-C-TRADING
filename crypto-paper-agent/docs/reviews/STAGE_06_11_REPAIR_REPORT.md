# Stage 6–11 repair pass — author handoff

Status: **IMPLEMENTED AND AUTHOR_TESTED — PENDING INDEPENDENT REVIEW**.
Performance: **AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED**. No acceptance is claimed.

## Authority and exact code identity

- Repository: `Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING`.
- Branch: `codex/stage-06-to-11-completion`.
- Baseline: `2236e839529cbcfb31cfd399107617f0b541e907`.
- Previously reviewed implementation: code `7bcf77ef7f4204d8b5a360b354073ddac6581cfb`, docs `1488d9a6865a80e6f979407de356d38ac80259ee`.
- **Final code/test/script commit A: `23f94376215a7fca69c8a7606e34139bc21d090c`**.
- B is the documentation-only child of A containing this report. Resolve its full SHA with `git rev-parse codex/stage-06-to-11-completion` at handoff and confirm `git rev-parse B^` equals A. The delivered reviewer prompt records the actual full B SHA after commit creation; a commit cannot embed its own future content hash.
- Main remained `e970337d504563e5987a4db6b5c06c635bf7244b`; no merge or force push authorized.
- User task dated 2026-09-21 explicitly authorizes continuous Stage 6–11 implementation, including real PPO, small commits, isolated dependency installation and branch push. Historical stop-before-7 and optional-RL instructions are superseded for this task. No live/testnet, keys, money, paid data or cloud resources were used.

Repair commits in review order: `04d69b0` (calendar/Breakout), `0c35df7` (funded basket), `1fe9c12` (SMC/partial broker), `4a8f5de` (workflow/PPO), `33e6c5b` (final production regression and artifacts), A (correct raw-cache smoke schema). A includes all prior repairs. The earlier 33e6c5b verification is diagnostic, superseded by final verification below.

## Architecture and implemented behavior

Public/cache data → strict UTC validation → past-only indicators/strategy state → OrderRequest → PaperBroker risk/margin/news/breaker admission → next-bar execution, settlement and ledger → reconciled report/SQLite. Trend and Breakout use 4h/15m; SMC uses actual 5m/1m data. Funding basket uses its own explicit spot inventory + short collateral ledger and the existing risk gate/breaker adapter (ADR 0011). Walk-forward resets four independent accounts each fold. Gymnasium exposes broker state and sends actions through the same broker; SB3 PPO is installed and exercised on CPU.

| Stage | Implemented | Evidence and status |
|---|---|---|
| 6 | Frozen parsed calendar bytes, portable and idempotent config identity, truthful custom config reference, UTC ISO CLI dates, LF artifact bytes matching SHA/SQLite, dynamic timeframe/range labels | `test_trade_logger.py`, `test_stage_06_integration.py`, `test_comparison.py::test_research_manifest_matches_exact_file_and_sqlite_bytes`; IMPLEMENTED AND AUTHOR_TESTED |
| 7 | Causal Breakout → later retest, valid past volume baseline, duplicate guard, LONG/SHORT, timeout/invalidation/conflict and actual gate rejection | `test_breakout_retest.py`; both synthetic directions have 1 fill + 1 closed trade through CLI/report; IMPLEMENTED AND AUTHOR_TESTED |
| 8 | Matched funded spot/perp basket, atomic admission, aggregate stop budget, schedule/provenance validation, fees/funding ledger, paired emergency/breaker/negative-funding unwind | `test_funding_arbitrage.py`, dedicated + main CLI, public basket; IMPLEMENTED AND AUTHOR_TESTED |
| 9 | Confirmed sweep/BOS/CHoCH/OB/FVG state, resting midpoint limit, 40/30/30 exits, proportional accounting, BE then tightening trailing | `test_smc_liquidity_sweep.py`, `test_partial_execution.py`; both directions 1 fill + 3 realization slices on actual 5m/1m fixtures; IMPLEMENTED AND AUTHOR_TESTED |
| 10 | Sorted disjoint folds, last 20% of train window reserved validation, fixed rules, past warm-up, fresh accounts and costed close, four-strategy CLI and OOS reports | `test_comparison.py`, synthetic/public workflow, main `--strategy all`; implementation AUTHOR_TESTED; full intended historical-window performance PARTIAL / NOT_VERIFIED |
| 11 | Gymnasium checker, 16D causal observation with train scaler, four actions via broker, real SB3 PPO, train/evaluate/save/load, no-trade + fixed MA baseline, frozen metadata and checksums | `test_rl_env.py`, public 256-step CPU run and independent evaluate-only CLI; IMPLEMENTED AND AUTHOR_TESTED; useful learned policy NOT_VERIFIED |

Detailed finding→cause→fix→test mapping: [repair matrix](../planning/STAGE_06_11_REPAIR_MATRIX.md).

## Final gates actually executed on A

Python 3.12.14 in a separate environment; `requirements-repair-lock.txt` contains tested runtime package pins. Gymnasium 1.3.0, stable-baselines3 2.9.0, torch 2.14.0. Formatter was installed separately and is not a runtime dependency. CPU only; seed 42.

Run from `crypto-paper-agent/` with that environment's Python:

```text
python -m pytest -p no:cacheprovider -m "not network" -q
python -m pytest -p no:cacheprovider -m network -q
python -m pytest -p no:cacheprovider docs/reviews/test_stage_04_review_05.py -q
python -m pytest -p no:cacheprovider docs/reviews/test_stage_04_review_06.py -q
python -m pytest -p no:cacheprovider docs/reviews/test_stage_04_review_07.py -q
```

| Gate | Actual result on A | Log in `evidence/stage-06-11-repair/` |
|---|---|---|
| Full offline | **356 passed, 2 skipped, 5 deselected**, 111.13s | `offline.txt` |
| Network | **5 passed, 358 deselected**, 22.51s | `network.txt` |
| Historical Review 05 | **26 passed** | `review-05.txt` |
| Historical Review 06 | **11 passed** | `review-06.txt` |
| Historical Review 07 | **3 passed** | `review-07.txt` |
| Detached clean checkout A, full offline | **356 passed, 2 skipped, 5 deselected**, 111.14s | `clean-offline.txt` |
| Nonempty external-CWD custom-config CLI, four synthetic directions | **4 exit codes 0**, actual fills/closed realizations | `external-cli.txt`, `external_cli_results.json` |
| Main basket + all CLI, evaluate-only PPO script | **3 exit codes 0**, loaded holdout result identical | `research-cli.txt`, `research_cli_results.json` |
| Artifact audit | 76 JSON, 128 portable text artifacts, 13 manifests, 17 report SQLite stores, 21 PNG signatures, 6 data digests; **0 absolute paths** | `artifact-audit.txt`, `artifact_audit.json` |

Two skips are existing optional pandas-ta reference checks; they were not converted to passes. Two Gymnasium warnings concern ignored `warn` parameter and unavailable alternate render-mode tests (no environment registration spec). No tests/assertions were removed or weakened to obtain these results. Historical review probes are outside the default `testpaths=tests` and were therefore run separately. No caller detection was added.

The audit recomputed exact report/model hashes from disk, research JSON/SQLite byte equality, canonical config hash across JSON/SQLite, trade count and terminal CSV equity, plus public dataset identities. Originals remain in the local evidence bundle; committed log copies replace machine path prefixes for portability. The committed evidence JSONs are unchanged copies of actual results.

## Data, observed results and interpretation

The bounded public sample is BTCUSDT **2024-01-01–2024-01-03**, three days, with **4,320 separate spot and perpetual 1m candles each**. Actual URLs, market types, ZIP/CSV hashes and frame digests are in `public_dataset_manifest.json`. Resampled 5m/15m/4h use genuine public perpetual OHLCV; basket uses separate spot/perp **open quotes available at the row time**, not futures substituted as spot. Observed funding is matched strictly to the past; settlement provenance uses backward source matching. Gaps are counted, not silently hidden.

Public comparison uses Jan 1 warm-up/train window and Jan 2 OOS. Common coverage is conservatively bounded by all series; incomplete final common folds are omitted. Three directional strategies produced **0 trades, 0 PnL** under unchanged default rules. Funding completed **1 basket, -25.18825656 USDT**. This short window does not validate historical strategy performance; no parameters were tuned to force trades or profit.

Synthetic nonempty fixtures, separate from public results:

| Fixture | Fills | Closed realizations | Net PnL USDT |
|---|---:|---:|---:|
| Breakout LONG | 1 | 1 | 388.5477 |
| Breakout SHORT | 1 | 1 | 387.4512 |
| SMC LONG | 1 | 3 | 449.2124 |
| SMC SHORT | 1 | 3 | 448.7951 |

Funding hand oracle: matched quantity 40 at spot/perp entry 100, capital 10,000, notional 4,000 per leg; funding -0.0044, gross price PnL -8, fees 8.044, final equity **9983.9516**. This is a deterministic test oracle, not market performance.

PPO public train Jan 1, validation Jan 2, untouched final holdout Jan 3, 256 training steps (no holdout tuning), save/load result equality:

| Holdout policy | Net PnL USDT | Closed trades | Rejected/invalid actions |
|---|---:|---:|---:|
| PPO smoke | -477.11246108 | 60 | 1318 |
| No-trade | 0 | 0 | 0 |
| Fixed causal MA5/20 using same broker | -478.76004202 | 75 | 333 |

Many invalid/repeated or locked-state actions are penalized; they are not forbidden actions executed through a risk bypass. This short untrained policy is operational evidence only. Evaluation includes terminal forced-close costs. The full report contains validation, per-step action lists, scaler, seed, hyperparameters, dataset identities and model digest.

## Reproduction

From a clean checkout of A, create a separate Python 3.12 environment and install `requirements-repair-lock.txt`. Use a fresh output folder for each run; PPO refuses overwrite and research persistence rejects conflicting payload identities.

```text
python scripts/prepare_public_research_sample.py --output <PUBLIC_DATA_DIR>
python scripts/verify_research_smoke.py --output <FRESH_ARTIFACT_DIR> --public-dir <PUBLIC_DATA_DIR>
python scripts/run_walk_forward.py --help
python scripts/run_funding_arbitrage.py --help
python scripts/train_ppo.py --train <TRAIN_PARQUET> --validation <VALIDATION_PARQUET> --holdout <HOLDOUT_PARQUET> --config <CONFIG_PATH> --output <FRESH_PPO_DIR> --timesteps 256 --seed 42
python scripts/evaluate_ppo.py --model-dir <PPO_DIR> --input <HOLDOUT_PARQUET> --config <SAME_CONFIG_PATH> --output <FRESH_EVAL_DIR>
python run_backtest.py --strategy all --comparison-data-dir <PUBLIC_DATA_DIR> --config <CONFIG_PATH> --output-dir <FRESH_ALL_DIR> --source "Binance Vision public archives"
python run_backtest.py --strategy funding_arbitrage --basket-input <PUBLIC_DATA_DIR>/basket.parquet --config <CONFIG_PATH> --output-dir <FRESH_BASKET_DIR> --source "Binance Vision public archives"
```

The bounded downloader defaults to the sample above. `verify_research_smoke.py` creates OHLCV/funding cache fixtures and portable YAML templates. For each `smc_long`, `smc_short`, `breakout_long`, `breakout_short`, copy its YAML outside the artifact tree, replace `<RAW_DATA_DIR>` with `<FRESH_ARTIFACT_DIR>/cli-cache/<fixture>`, then run the corresponding strategy from an external CWD:

```text
python <PROJECT_ROOT>/run_backtest.py --strategy smc_liquidity_sweep --config <CUSTOM_CONFIG_PATH> --no-fetch --output-dir <FRESH_CLI_DIR> --run-id smc_long
```

PPO partitions are consecutive 1,440-row slices of `1m.parquet`; preserve the same config plus `research.source: Binance Vision public archives` for exact reproduction. The persistent smoke script performs this split itself. For a fresh clean test checkout: `git worktree add --detach <CLEAN_DIR> 23f94376215a7fca69c8a7606e34139bc21d090c`, then run the offline command in its `crypto-paper-agent/` directory.

## Remaining limitations and review priorities

1. **P1 — independent review pending.** Invasive broker partial exits require independent scrutiny of accounting, funding/stop ordering, breaker re-entrancy and zero mutation on rejection. Passing author tests is not acceptance. Risk limits were preserved, not relaxed.
2. **P1 — PARTIAL historical evidence.** Full configured 2021-01-01→2026-09-01 data coverage and 2021–2023 benchmark replay were not run. Historical +21.01%/16-trade figures remain AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED. Public directional nonempty performance has not been established.
3. **P2 — metrics sample units.** SMC TradeRecords are partial realization slices. Win rate, expectancy, SQN and counts treat these slices as rows; they are not independent complete positions. `sample_unit` states this. Aggregating whole positions before statistical evaluation is future work; benchmark ranges are descriptive only.
4. **P2 — execution model.** SMC uses OHLC conservative ordering and taker fees even for limit entry; no queue priority, order-book depth or partial entry fills. BE is effective only after candle close; if price already crossed BE, next-open close is queued. Basket evaluates synchronized quotes, not unobserved intrabar spot paths, and intentionally permits one completed basket per simulation. These constraints are in ADR 0011/0012.
5. **P2 — fixed-rule comparison.** Four independent reset accounts; no shared-capital portfolio, cross-strategy exposure allocation, optimization or compounding. Validation is reserved but unused for rule tuning. `total_net_pnl` is summed across fold experiments and mean return divided by independent starting capital; it is not one account's return.
6. **P2 — PPO quality NOT_VERIFIED.** CPU smoke is short, loss-making, and insufficient for learning claims. No profitable model, convergence, generalized policy or production readiness is claimed. Missing OI/CVD/funding observations use explicit masks; no footprint/DOM feed is implemented. Public OI/CVD availability is incomplete.
7. **P3 — precision/platform scope.** Data sample timestamps are at minute resolution; frame CSV digest currently formats microseconds, so submicrosecond timestamps are not covered by distinct-identity evidence. Tests ran on Windows/Python 3.12 with the pinned environment; other platforms are NOT_VERIFIED. Optional pandas-ta reference checks remain skipped.

There is no observed environment blocker for these gates. Acceptance, economic usefulness and the full historical benchmark remain open. Next authorized handoff is independent review of A/B; no main merge or next phase was performed.

## Exact source pointers at A

- [src/logging/trade_logger.py:116](https://github.com/Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING/blob/23f94376215a7fca69c8a7606e34139bc21d090c/crypto-paper-agent/src/logging/trade_logger.py#L116) — `def canonicalize_config`.
- [src/logging/trade_logger.py:168](https://github.com/Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING/blob/23f94376215a7fca69c8a7606e34139bc21d090c/crypto-paper-agent/src/logging/trade_logger.py#L168) — `def snapshot_run_config`.
- [src/features/news_calendar.py:121](https://github.com/Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING/blob/23f94376215a7fca69c8a7606e34139bc21d090c/crypto-paper-agent/src/features/news_calendar.py#L121) — `def load_calendar`.
- [src/strategies/breakout_retest.py:25](https://github.com/Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING/blob/23f94376215a7fca69c8a7606e34139bc21d090c/crypto-paper-agent/src/strategies/breakout_retest.py#L25) — `class BreakoutRetestStrategy`.
- [src/strategies/funding_arbitrage.py:58](https://github.com/Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING/blob/23f94376215a7fca69c8a7606e34139bc21d090c/crypto-paper-agent/src/strategies/funding_arbitrage.py#L58) — `class FundingArbitrageSimulator`.
- [src/strategies/funding_arbitrage.py:146](https://github.com/Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING/blob/23f94376215a7fca69c8a7606e34139bc21d090c/crypto-paper-agent/src/strategies/funding_arbitrage.py#L146) — `def simulate`.
- [src/features/smc_features.py:11](https://github.com/Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING/blob/23f94376215a7fca69c8a7606e34139bc21d090c/crypto-paper-agent/src/features/smc_features.py#L11) — `class SMCFeatureTracker`.
- [src/strategies/smc_liquidity_sweep.py:32](https://github.com/Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING/blob/23f94376215a7fca69c8a7606e34139bc21d090c/crypto-paper-agent/src/strategies/smc_liquidity_sweep.py#L32) — `class SMCLiquiditySweepStrategy`.
- [src/execution/paper_broker.py:341](https://github.com/Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING/blob/23f94376215a7fca69c8a7606e34139bc21d090c/crypto-paper-agent/src/execution/paper_broker.py#L341) — `def process_candle`.
- [src/execution/paper_broker.py:956](https://github.com/Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING/blob/23f94376215a7fca69c8a7606e34139bc21d090c/crypto-paper-agent/src/execution/paper_broker.py#L956) — `def _execute_exit`.
- [src/research/workflow.py:25](https://github.com/Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING/blob/23f94376215a7fca69c8a7606e34139bc21d090c/crypto-paper-agent/src/research/workflow.py#L25) — `def run_comparison`.
- [src/research/rl_env.py:74](https://github.com/Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING/blob/23f94376215a7fca69c8a7606e34139bc21d090c/crypto-paper-agent/src/research/rl_env.py#L74) — `class RiskAwareTradingEnv`.
- [src/research/rl_env.py:251](https://github.com/Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING/blob/23f94376215a7fca69c8a7606e34139bc21d090c/crypto-paper-agent/src/research/rl_env.py#L251) — `def train_ppo`.
- [src/research/rl_env.py:367](https://github.com/Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING/blob/23f94376215a7fca69c8a7606e34139bc21d090c/crypto-paper-agent/src/research/rl_env.py#L367) — `def evaluate_saved_ppo`.
- [src/research/artifacts.py:56](https://github.com/Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING/blob/23f94376215a7fca69c8a7606e34139bc21d090c/crypto-paper-agent/src/research/artifacts.py#L56) — `def persist_research_run`.
