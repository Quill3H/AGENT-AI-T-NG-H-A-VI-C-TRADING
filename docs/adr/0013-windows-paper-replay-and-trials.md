# ADR 0013: Scoped Windows PAPER replay and trial lifecycle

Date: 2026-10-01. Status: Accepted product/technical direction by the owner;
implementation remains AUTHOR_SELF_REVIEWED, not independent acceptance.

## Authority and scope

The owner approved the [Windows design](../superpowers/specs/2026-10-01-windows-paper-replay-design.md)
and separately authorized a new, isolated 10,000 imaginary USDT account, keeping
all legacy history. This ADR applies to the local `windows-paper-v3` experiment
only. No permission for live/testnet orders, exchange credentials, main merge,
paid infrastructure or profitable-trading claims follows from it.

## Decisions

1. New accounts use `PaperReplaySession`, `CausalRunner` and `PaperStore` under
   one OS-backed writer lock. SQLite WAL/synchronous FULL atomically commits
   canonical inputs, financial/trial events and the latest exact checkpoint.
   An immutable, fsynced `paper-account.identity.json` precedes the first DB
   write. Missing/torn/mismatched identity or DB, and orphan evidence require
   reconciliation, never deletion, guessed exposure or another allocation.
2. Restart verifies typed broker/strategy/risk machinery, financial ledgers,
   funding keys, order sequence and processing boundaries. Every missing
   interval is paginated and replayed chronologically through the same broker.
   A short recent-window sample cannot prove an outage safe. Closed signals
   affect only subsequent eligible opens; downloaded future suffixes cannot
   become signal history, account marks or strategy selections.
3. Funding for this experiment is explicitly `FIXED_SIMULATED`: positive
   rate 0.0001 for BTC/ETH/SOL, UTC 00/08/16, displayed as UTC+7 07/15/23.
   Existing broker open-price proxy and phase ordering remain. Predetermined
   rates are configuration, not fabricated public observations. All other
   public-observed/basket modes retain exact provenance fail-closed.
4. Initial trial uses unchanged Trend Following (closed 4h / 15m execution).
   Breakout & Retest is a versioned research candidate, not already active.
   SMC, PPO and Funding Arbitrage are excluded from automatic selection in
   this experiment. Strategy/risk parameters are frozen.
5. Equity strictly below 5,000 marks FAILED, blocks entries and queues modeled
   closure. Equity at least 15,000 records TARGET_REACHED once and continues
   the same trial. Neither threshold overrides daily/streak breakers, 5x
   leverage or mandatory stops. This is not an economic certification.
6. A replacement allocation requires flat accounting reconciliation and a
   causally available, validated immutable recipe. Retain final/parked equity
   and detailed prior-trial ledgers; record cumulative capital injected.
   Restart, failed research or operator Stop cannot silently allocate a trial.
7. Bounded research uses a frozen catalog (max eight; currently two),
   180/90/90-day train/validation/holdout partitions and three 30-day holdout
   accounts. Freeze one selection before claiming holdout. Require at least
   30 completed positions overall, five per fold, positive aggregate
   expectancy, positive PnL in two folds, <=20% drawdown/fold and nonnegative
   aggregate PnL under doubled fee/slippage. The ten-minute evaluation budget,
   interrupted/used holdout or insufficient data cannot permit promotion.
8. Pause durably blocks new entries, not protection/funding. Resume keeps the
   trial. Stop proceeds through STOPPING to reconciled terminal STOPPED;
   no force-filled closure or implicit replacement. Service shutdown is
   separate. Startup restores intent and replays its effective timeline.
   HTTP controls are serialized asynchronous operations.
9. Default new profile: `crypto-paper-agent/data/paper_accounts/windows-paper-v3`.
   Legacy `data/paper_sessions` is unchanged. Migration requires exact provable
   financial state and feature seed; insufficient legacy evidence remains
   RECOVERY_REQUIRED. The owner authorized a separate new account, not this
   legacy migration or transfer of old capital/results.

## Evidence and limits

Earlier code checkpoint: `c89333516f9032155923375a876d0350deb6c267`.
The repaired code-under-test SHA and current evidence are recorded in the
[2026-10-17 handoff](../handover/2026-10-17-github-checkpoint.md)
and [operations](../operations/LOCAL_PAPER_WEB.md). Synthetic execution is not
market performance evidence. Fixed funding is not an exchange estimate or
arbitrage-edge evidence. No independent economic gate or 24/7 operation is
accepted by this ADR. Task/logon/reboot and sustained operation must be reported
separately from unit, actual Windows process and short public-stream checks.
