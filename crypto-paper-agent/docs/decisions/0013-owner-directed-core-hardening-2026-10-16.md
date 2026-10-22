# ADR 0013 — Owner-directed core hardening and method search (2026-10-16)

Status: IMPLEMENTED — AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED. The owner
(zhilie meng) authorized rewriting core code, relaxing strategy rules and
choosing defaults, and asked to be consulted only on critical issues. Paper
simulation only; no exchange order path, testnet or credential was added.

Changes to earlier policy, each with its reason:

1. **Funding events snap to the settlement boundary (ADR 0011 G2 question).**
   Binance Vision `calc_time` lands 0–47 ms after 00/08/16 UTC (2020-09..2026-09).
   An event at most 1 s after a boundary settles at that boundary; the source time
   is kept as `funding_source_time`. Later events still fail closed.
   (`src/data_layer/vision_dataset.py`)
2. **Basket emergency stop uses the hedged basket, not each leg.** ADR 0011's
   "either leg stop" closed a delta-neutral basket on any 2% BTC move, although
   the legs offset each other. The stop now fires when combined spot+perp price
   P&L reaches −`stop_pct` of spot notional. Liquidation, two negative
   settlements and breaker lock are unchanged. `simulate(stop_after_exit=True)`
   lets `src/research/carry.py` run baskets back to back with one breaker.
3. **Hard cap on one order's notional**: `risk.max_notional_pct_of_equity: 2.0`
   (`INVARIANT_FAIL_MAX_NOTIONAL_EXCEEDED`). Optional; absent means no cap.
4. **Kill switch.** `PaperBroker.engage_kill_switch(time, reason)` cancels pending
   orders, closes every position at the last mark with slippage
   (`ExitReason.KILL_SWITCH`) and halts the session. With
   `risk.max_data_gap_minutes: 60`, a candle arriving after a longer silence
   engages it at that candle's open (`DATA_GAP`).
5. **SMC default risk 5% → 2%.** One 5% loss equalled the whole 5% daily breaker.
6. **Fetcher fails closed.** OHLCV and funding chunks raise `FetchError` after
   retries or on exchange errors instead of returning an empty list that the
   caller treated as the end of data.

Method search, protocol and results: `docs/research/2026-10-16-method-search.md`.
