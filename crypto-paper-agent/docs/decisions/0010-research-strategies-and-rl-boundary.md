# ADR 0010 — Research execution, walk-forward and real PPO

Status: IMPLEMENTED POLICY — PENDING INDEPENDENT REVIEW. Updated 2026-09-21.
Supersedes the original optional/stub RL boundary in this ADR for the current user-authorized Stage6–11 repair pass. No risk policy is relaxed.

## Execution boundary

Trend/Breakout/SMC and RL submit requests to PaperBroker. Funding uses the explicit funded basket adapter in ADR0011 because spot inventory is not an isolated futures position. Every path retains admission, stop-risk, margin, news, liquidation and breaker enforcement. No credentials, live or testnet endpoints are present in these execution paths.

## Walk-forward

Require UTC sorted unique timestamps and positive integral train/test/step sizes; step must be at least the test size. The last 20% of each pre-OOS window is reserved validation; fixed rule parameters are not tuned on either validation or OOS. Warm-up uses only earlier closed bars and confirmed SMC levels. No warm-up positions/setups are carried into OOS; each fold starts fresh capital and closes open positions with fees/slippage at the boundary.

Four separate accounts run on their common available interval (4h/15m Trend and Breakout; 5m/1m SMC; timestamped spot/perp quotes). No shared budget or portfolio is claimed. Fold net PnL uses engine `total_net_pnl`; aggregate sums experimental PnL and shows mean independent-fold return, not compounded account equity. Coverage, sample count, folds, configuration and data checksums are persisted.

## Gymnasium and PPO

`RiskAwareTradingEnv` wraps PaperBroker, with Discrete(4): hold, LONG, SHORT, close. Observation is 16-dimensional: four relative OHLC values, log-volume, OI delta/funding/CVD when supplied, three presence masks, normalized equity/free margin, position direction, breaker multiplier and drawdown. Missing market features are masked. Supplied features must be causal at their candle close. A scaler is fitted on the train partition only and loaded unchanged for validation/holdout.

The closed current candle determines an action for the next execution candle. Entries include a stop and go through actual broker rejection. Manual close is queued and processed after gap/settlement according to the broker. Episode terminates at data end or insolvency/halt; terminal positions are force-closed with costs. A locked breaker remains enforced and rejected actions incur penalty.

Reward units are dimensionless:

`realized_net_USDT / initial_USDT - 0.5 * max(0, current_fractional_DD - previous_fractional_DD) - 1.0 * invalid_or_rejected_action`

Realized slices already include allocated entry/exit fees and funding; these are not rewarded again as cashflows. Drawdown uses marked equity and penalizes each increase; recovering then falling again can incur another penalty. It is not a one-time maximum-drawdown score. Stop/slippage/gap losses after valid admission are not automatically labeled risk violations.

SB3 PPO is real: CPU MlpPolicy, n_steps64, batch32, n_epochs2, learning_rate0.0003, seed42 by default. Requested timesteps are bounded but SB3 rounds to rollout batches; actual count is recorded. Explicit strictly chronological train/validation/final-holdout partitions; no tuning on holdout. Model ZIP, model/report checksums, train scaler, seed, hyperparameters, config, data identities and validation/holdout results persist. Save/load must reproduce identical deterministic holdout results. Existing output identities are not silently overwritten.

`train_ppo.py` trains and evaluates; `evaluate_ppo.py` loads the model/scaler without fitting. Evaluation validates model and metadata checksums, config identity, timeframe and time-after-training boundary. Fixed no-trade and causal MA5/20 baselines use the same broker/cost model. A short training smoke validates operation, not profitability or model quality.

## Evidence and limits

See Stage6–11 repair report and matrix. Final code A and actual gates are recorded there. Tests use Gymnasium/SB3 checker, real CPU training, persistence/load replay and external evaluate CLI. The three-day public sample and fixed-rule OOS run are AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED; full historical evaluation and policy generalization remain NOT_VERIFIED. The requested RL implementation is no longer described as optional or a stub.
