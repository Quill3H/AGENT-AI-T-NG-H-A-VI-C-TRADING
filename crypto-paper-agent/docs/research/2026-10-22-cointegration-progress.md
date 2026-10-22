# Execution ledger — ETH–BTC cointegration v1

Plan: docs/superpowers/plans/2026-10-22-eth-btc-cointegration-v1.md
Owner specification: approved plan in this chat, 2026-10-22.
Base SHA: a3a1681c4762a88bfa2dc9adced07be64f4f6ee6.
Route: executing-plans + TDD; domain-specific unavailable skills handled by direct
inspection and the existing broker/risk contracts. No gate acceptance implied.

Preflight: model -> scheduler (closed-time indexed snapshots); account -> scheduler
(shared wallet, event-cashflow accounting); runner -> reporting (pair lifecycles).
All interfaces must preserve this single-account ownership.

Setup: cloned the owner-selected branch into the chat workspace; original
checkout and sources untouched. Dependency setup underway. Local market search
found only synthetic checked-in fixtures, no ETH/BTC historical market datasets.

Task 1: model tests written and missing-feature failure observed before code;
causal 540-bar formation, exact Engle–Granger and I(1), fixed weekly AR model,
crossings and SMA ATR implemented. statsmodels 0.15 return-container notice is
suppressed narrowly; numerical warnings still invalidate the formation.

Task 2: 10 initial shared-account tests passed, including a hand-checked pair
net result 90.320015 USDT. Shared capital and existing invariant/news/liquidation
helpers and CircuitBreakerState are reused. No core broker semantics changed.

Task 3: replay, source checksum validation, offline reproduction CLI and strict
data preflight implemented. 438 monthly source ZIP hashes matched sidecars,
2020-09 through 2026-09, ETH/BTC 4h/15m/funding; raw archives preserved outside
Git. Current exchangeInfo lot rules are explicitly historical assumptions.

Ruling: quantities use provided lot steps and reject a rounding imbalance above
1% of pair gross notional; exact irrational OLS beta cannot generally be
represented in two finite exchange lot grids. This is a conservative admission
guard chosen before inspecting historical returns, not a fitted parameter.

Ruling: holding cap is an elapsed deadline from the actual first fill; the exit
is scheduled at entry and executes at the first 15m open at the deadline. It
must not wait an additional 4h signal interval. Regular z exits remain strictly
after their signal close; a weekly reset cannot carry the old model forward.

Independent reviewer reproduced three P2 issues (stale exit ownership, aborted
entries counted as completed evidence, and delayed time cap), plus an annual
boundary reporting issue. Each has a failing regression followed by a fix and
passing rerun. Reviewer independently reran 23 core tests after the first three
fixes. Additional coverage: second-leg abort, nonzero funding recomposition,
funding-triggered breaker, missing enabled news filter and year boundary.

Historical initial results are preliminary and will be superseded by an exact
final-code rerun; no strategy threshold changed in response to those results.

Baseline: 640 passed, 4 skipped, 5 network deselected, 2 failed with this Windows
runtime (comparison SQLite long output path; stage06 '--config <CONFIG_PATH>'
assertion). An earlier default-temp attempt had 102 setup errors because its
sandbox temp root was inaccessible; a writable explicit basetemp resolved them.
The final complete suite uses a shorter chat-local basetemp to separate that
path limitation from strategy changes. No pre-existing production files fixed.

Final focused verification: 44 passed (5 new test modules), Python3.12.14.
Independent reviewer final source verdict: no outstanding P1/P2 in reviewed
scope; 24 account/replay tests rerun independently, 4.68s. Economic results are
not independently accepted. Annual-boundary regression is now included.

Final complete offline suite: 686 passed, 4 skipped, 5 network deselected,
99.46s. Both previously observed baseline path failures disappeared with the
shorter writable Windows basetemp; no production workaround was introduced.
Ledger adapter maps completed_pairs to the existing completed_trades column;
one observation in this strategy is one completed two-leg pair.
