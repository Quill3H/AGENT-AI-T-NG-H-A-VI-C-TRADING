# Round 18: btc_oi_contraction_reclaim_v1 (2026-10-22)

Paper only, BTCUSDT USDⓈ-M perpetual, long or flat, one account, 1x. The owner handed over a
written spec (`PHUONG-AN-MOI-BTC-OI-RECLAIM-V1-GIAO-CLAUDE.md`, 2026-10-22) for Claude to
implement and Codex to review. This file pre-registers the run; results are AUTHOR_REPORTED and
both windows are SEEN_DATA_RETROSPECTIVE, not a final test.

## Duplicate check (before code)
Branch `claude/project-thread-uiqlsn` at a3a1681 (clean), `origin/main` fe1c133. No strategy,
config or ledger entry uses an OI-contraction event: OI appears only in the trend strategy's
rising-OI confluence (`src/features/oi_features.py`) and in the metrics downloader. Round 8's C3
`flush_buy` bought drops with EMA/RSI/ATR and failed; this rule is a different event definition
and is not a rename. The Codex ETH-BTC branch named in the spec is not on GitHub and is not used.

## Rules (src/strategies/oi_reclaim.py, config/research/oi_reclaim_2026_10_22/btc_oi_contraction_reclaim_v1.yaml)
Exactly the spec, sections 4-5: 1h bars built only from four closed 15m bars; event when
`Cprev - close_s >= 2A` (A = mean of the 14 true ranges before s) and
`OI(t)/OI(t-1h) - 1 <= -1%` on `sum_open_interest` (contracts) at the two exact snapshots, usable
at `t + 15 min`; 24h cooldown, no new event while a position is open; confirmation on the 1h bars
closing at t+1h / t+2h (close > open and close >= close_s + 25% of the drop), only when OI was
already usable at that close; a 15m low below low_s cancels; fill at the open of the first 15m bar
opening strictly after the signal is usable; re-check at that open (reclaim level, low_s, S < E < T,
RR >= 1.5, gross move to T > 2x round-trip cost on the rounded quantity); stop low_s - 0.25A,
target Cprev, 24h time stop, stop first when both are hit in one 15m bar, gaps fill at the worse
open; risk 0.5% of equity including round-trip costs to the stop, then notional <= equity, lot
0.001, tick 0.1, min notional 100 USDT (today's filters assumed for the past); project daily-loss
breaker 5% kept. Costs taker 0.05% + slippage 0.03% per side; funding from every source event,
cashflow = -qty x 15m open x rate (no historical mark price: the trade open approximates mark).

Accounts `actual` and `no_positive` are separate simulations (no_positive drops each positive
funding cashflow and keeps every payment; equity, size and breaker follow that account).

## Data checks done before any performance run
- OI: Binance Vision daily metrics BTCUSDT 2020-12-01..2026-09-30, downloaded on the owner's
  device (`downloader_vision_metrics_raw.py`), 2,130 of 2,130 days present, every zip matched its
  `.CHECKSUM`, one header for all days. Stored under
  `/mnt/project-files/market-data/binance-vision-metrics-btcusdt/` (raw rows + manifest with
  each zip's sha256).
- Rows are not time-sorted inside files (5,494 backward steps): parsed as UTC and sorted. 150
  days hold every row twice (98,160 exact duplicate rows, no conflicting value): collapsed.
- 473 rows on 23 days carry `sum_open_interest = 0`: invalid, dropped, never filled.
- Coverage of the 5m grid: W1 314,746 / 315,360 (614 missing, 45 missing on the hour); W2
  288,692 / 289,152 (460 missing, 41 on the hour). Nothing is interpolated or carried forward.
- **Three W1 price shocks have no OI snapshot at t or t-1h** (2021-09-07 15:00, 2021-11-26
  09:00, 2021-12-04 06:00 UTC; the rows are absent from Binance's files). By the spec, W1 is
  reported as **DATA_QUALITY_FAILED**; its numbers are shown only as a labelled diagnostic, not as
  evidence. W2 has no missing OI at any price shock.
- 15m BTC perp bars: no gaps 2020-09..2026-10-17; 15 zero-volume bars from the source are kept.
- Funding: 6,715 BTC events, all on the 8h schedule in these windows.

**Disclosure.** These checks counted price shocks (condition 1) per window and which have OI
(W1 271 shocks, W2 289; 128 and 96 with OI <= -1% before cooldown). No confirmation, entry or P&L
was computed before this commit. Unit tests use synthetic bars; the script was smoke-tested on
synthetic data only.

## Runs (fixed now; scripts/reproduce_oi_reclaim.py)
W1 2021-01-01..2023-12-31 and W2 2024-01-01..2026-09-30, each: actual and no_positive at base
costs, at costs x2, and with entry one 15m bar later; PRICE_ONLY control (no OI condition,
no_positive, base costs); OI usable 60 minutes late (no_positive, base costs). No threshold is
tuned afterwards. Reading rules from the spec section 8: < 30 completed trades = not enough
evidence; no_positive loss after costs = v1 fails in that window; profit only in actual = fails
the funding rule; positive but costs x2 negative = not robust to costs.
