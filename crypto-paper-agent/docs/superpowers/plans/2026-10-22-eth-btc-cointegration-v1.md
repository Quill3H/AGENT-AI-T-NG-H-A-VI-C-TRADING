# ETH–BTC cointegration v1 implementation plan

> Required workflow: superpowers:executing-plans and test-driven-development.

Goal: implement the owner's approved 2026-10-22 specification, paper only.
Base: a3a1681c4762a88bfa2dc9adced07be64f4f6ee6, isolated local branch
codex/eth-btc-cointegration-v1. No changes to synced sources or shared branches.

## Contract

ETH price = alpha + beta * BTC price + residual, fixed regression direction.
Monday 00:00 UTC: fit exactly 540 closed 4h bars (90 days), OLS intercept;
Engle–Granger p < .01; ADF levels p >= .05 and differences p < .05;
all tests trend c, maxlag 12, autolag AIC. beta > 0, residual sample SD > 0,
AR(1) phi in (0,1), half-life in [3,42] 4h bars. Freeze model for the week.
Cross from abs(z)<2 to [2,4): short ETH/long BTC; symmetric negative direction.
Execute strictly later at the next 15m open; revalidate direction, z and costs.
Exit abs(z)<=.5 or >=4, ceil(3*half-life) capped at 42 bars, or next weekly
boundary. Rearm only following a closed 4h bar in abs(z)<2.

One shared 10,000 USDT account, at most one pair, 1x, total notional <= equity;
ETH q / BTC beta*q with lot rounding disclosed. Risk <= .005*equity after
existing breaker multiplier, simultaneous leg-stop losses + roundtrip costs.
Stops 3*SMA(TR,14) on 4h. Both taker .0005 and adverse slippage .0003 per fill;
gross expected convergence to .5 sigma must exceed twice roundtrip costs.
Run normal funding and independently compounded no-positive-funding accounts,
each at costs 1x and 2x. Never use funding for signals. Preserve gate/news/
liquidation/margin/breaker behavior using existing risk components.

## Tasks and verification

1. Tests first for causal model, known AR residual, nonstationary rejection,
   weekly cutoff and ATR. Add src/strategies/eth_btc_cointegration.py.
2. Tests first for shared wallet, hand accounting, funding clipping/idempotency,
   invariants, pair stops/failed leg and rounding. Add src/execution/pair_account.py.
3. Tests first for causal scheduler, strict fills, frozen weeks, gaps, replay,
   end close and delay stress. Add src/research/cointegration.py and CLI.
4. Run offline baseline/full suite, CLI smoke and bounded historical replay if
   source datasets are available; save Vietnamese report, manifest and ledger.
5. Fresh-context review of the whole change, fix important findings, rerun tests.

## Decisions and limits

- Source index labels are OPEN times: a 4h bar becomes available at index+4h.
- Price-level spread is used (not log prices), so fixed-q price PnL is exactly
  q*change(spread) while both legs are open.
- Pair-level wins/losses update breaker streak once; fees/funding/realizations
  update its rolling cashflow window once, without double counting.
- Lot metadata must be explicitly supplied with source identity for history;
  current exchange filters must be labelled assumptions, not historical facts.
- Stop partner closes next 15m open, not at a fictitious simultaneous extreme.
- Historical windows are half-open [2021-01-01,2024-01-01) and
  [2024-01-01,2026-10-01); both are seen-data retrospective diagnostics.
- No market data found locally is not a zero-trade result. Missing data produces
  DATASET_UNAVAILABLE, no performance claim and a runnable reproduction command.
