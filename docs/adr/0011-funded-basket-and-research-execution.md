# ADR 0011 — Funded basket execution

Status: IMPLEMENTED POLICY — PENDING INDEPENDENT REVIEW (repair task 2026-09-21).

Funding uses explicit synchronized spot/perp price observations, never synthetic
spot substituted from futures. Both legs execute atomically at the next observed
timestamp after an APR decision. These are sampled market quotes, not invented
intrabar candles; price gaps incur market slippage. Settlement is processed before
new entry, with readiness and source timestamps. Input duplicates (even identical)
are rejected before state mutation. Cadence must not omit settlement boundaries.

Spot purchase plus 1x short collateral and both entry fees must fit available cash.
Matched quantity is capped by cash and the sum of both legs' stop risks under the
existing normal tier budget and breaker multiplier. Explicit excessive notional is
rejected, not silently scaled. The short also passes check_all_invariants with
available margin reduced by the spot purchase and fee. The existing breaker,
news filter and tier liquidation solver are reused. Conservative additional
basket admission never relaxes the existing risk policy.

Either leg stop, short maintenance breach, two distinct negative settlements, or
breaker lock causes paired market unwind. Funding is collateral cashflow, not
additional spendable free cash. Fees, realized price PnL and funding enter the
breaker cash ledger once; the complete basket outcome updates streaks once.
Force-close pays exit fees; an open final basket retains unrealized PnL explicitly.

This adapter has a separate basket ledger/report schema because spot inventory is
not an isolated futures TradeRecord. No shared-capital portfolio is implemented;
Stage 10 compares independent accounts on common time coverage.
# G0 settlement provenance addendum — 2026-09-22

Code A `2c9a4d0985fc9eafd29386482793425c26d47835`, pending independent review: settlement cashflow requires source funding_time equal to the row settlement boundary. Reused or revised source08 at row16 raises FUNDING_SOURCE_EVENT_MISMATCH; the basket prevalidates the entire input before advancing breaker/account state. Deduplication uses source event time. Observed funding can remain a past feature but cannot authorize a new settlement. Shared data-layer/public-sample readiness marks missing exact events unready. This supersedes any age-only interpretation of settlement readiness in prior text.
