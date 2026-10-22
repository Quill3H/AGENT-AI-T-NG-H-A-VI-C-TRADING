# ADR 0015 — ETH/BTC price-convergence research, 2026-10-22

Status: owner approved implementation of the fixed experiment in this chat;
engineering/economic gate acceptance is pending. Parent branch:
claude/project-thread-uiqlsn, base a3a1681c4762a88bfa2dc9adced07be64f4f6ee6.

## Decision

Add a separate shared-wallet pair workflow for ETH-on-BTC price-level
cointegration. Preserve the existing directional workflows and risk policies.
The exact accepted model, timing and threshold rules are in
docs/superpowers/plans/2026-10-22-eth-btc-cointegration-v1.md.

Funding is never an entry feature or an income thesis. Two independent account
reruns are mandatory: actual funding, and every positive funding cashflow
forgone while every negative one remains. Wallet, isolated collateral, margin,
future quantity and breaker state each evolve from that account's cashflows.

Use the existing invariant/news/liquidation helpers and CircuitBreakerState.
One pair is one streak outcome; each realized cashflow is counted once in the
rolling loss window. No global broker change or permission to trade is implied.

## Numerical and execution rulings

OLS beta cannot generally be represented exactly on two exchange lot grids.
Round both quantities downward and reject if BTC hedge rounding error, valued
at its entry quote, exceeds 1% of total pair gross notional. This conservative
guard was chosen before inspecting historical returns; it is disclosed and
not optimized. Current observed lot rules and inherited maintenance brackets
are explicit historical assumptions, not reconstructed historical schedules.

The holding cap is an elapsed deadline from the first fill, scheduled at entry;
execute at its first available 15m open. Do not wait an extra four-hour close.
Signals otherwise execute strictly later than their availability. A protective
stop ends one leg; the partner closes on the next available open. A delayed
second-leg rejection aborts the first at the next observed executable quote.

Funding follows ADR0013 nominal timestamp snapping (<=1s) only for cash
settlement; source timestamps are retained. No funding value enters formation
or decisions. All supplied extra settlement events are processed. Missing
baseline 00/08/16 events fail preflight. Funding valuation uses last-trade bar
opens as a proxy, disclosed separately from genuine mark-price history.

## Limits

The two historical windows are seen-data retrospective diagnostics, not new
OOS. No threshold search, pair substitution, leverage increase or tuning is
allowed after seeing the results. Price signals, shared-account accounting,
execution assumptions and data quality are separately auditable. Passing tests
or obtaining positive historical PnL never implies economic acceptance.
