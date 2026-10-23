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

## Results (run at frozen 5fdda7c; SEEN_DATA_RETROSPECTIVE; AUTHOR_REPORTED)

Outputs: `docs/research/runs/oi-reclaim-v1-5fdda7c/` (summary.json sha256 e0c3b846...,
data_check.json, every scenario's event audit and trades, the OI manifest); hourly equity CSVs in
`/mnt/project-files/research-runs/oi-reclaim-v1-5fdda7c/`.

| Window | Scenario | Status | Trades | Return % | Max DD % | Win % | Net $ | Price $ | Fees $ | Slippage $ | Funding $ |
|---|---|---|---|---|---|---|---|---|---|---|---|
| W1 | every OI scenario (6 + lag 60) | DATA_QUALITY_FAILED | 0 | 0.0 | 0.0 | | 0 | 0 | 0 | 0 | 0 |
| W1 | price_only_no_positive | OK | 0 | 0.0 | 0.0 | | 0 | 0 | 0 | 0 | 0 |
| W2 | base, costs x2 (actual and no_positive) | OK | 0 | 0.0 | 0.0 | | 0 | 0 | 0 | 0 | 0 |
| W2 | delay15m_actual | OK | 2 | 1.24 | 0.31 | 100 | 123.59 | 138.45 | 8.75 | 5.25 | -0.86 |
| W2 | delay15m_no_positive | OK | 2 | 1.24 | 0.31 | 100 | 123.59 | 138.45 | 8.75 | 5.25 | -0.86 |
| W2 | price_only_no_positive | OK | 0 | 0.0 | 0.0 | | 0 | 0 | 0 | 0 | 0 |
| W2 | oi_lag60_no_positive | OK | 0 | 0.0 | 0.0 | | 0 | 0 | 0 | 0 | 0 |

Funnel, no_positive base (W1 / W2): complete 1h bars 26,281 / 24,097 (none incomplete); price
shocks 271 / 289; OI missing 3 / 0; OI not contracting 140 / 193; events 128 / 96; skipped by
cooldown 17 / 9 (by an open position 0 / 0); accepted 111 / 87; cancelled by a 15m low below
low_s 64 / 56; expired without confirmation 26 / 12; confirmation signals 21 / 19; rejected at the
fill open: RR 15 / 11, below the reclaim level 4 / 6, stop-entry-target order 2 / 2; cost gate 0;
entries 0 / 0. Price-only control: signals 39 / 40, entries 0 / 0 (RR 31 / 24).

**Verdict: no trades.** With the rules as written, v1 opened no position in 69 months at base
and double costs, with or without the OI condition, and with OI 60 minutes late (the lag stress
changes nothing, as the spec expected, because the first confirmation bar closes an hour after
the event). This is not a success. The binding gate is the reward/risk check at the fill: the
fill must be at or above the 25% reclaim level, so T - E is at most 75% of the drop, while E - S
is at least 25% of the drop plus 0.25A plus the shock bar's lower wick; RR >= 1.5 then needs
roughly drop >= A + 4 x wick, which real shock bars with a wick rarely meet. Most events end
earlier, when price makes a new low within two hours (120 of 198 accepted events).

The one-bar-later entry (delay stress) traded twice in W2 (2024-12-30 and 2025-04-16, both hit
the target, +$123.6, 52% / 100% of the gain in the largest one / two trades). That is a
sensitivity result on 2 trades, below the 30-trade floor, and not a candidate: the spec forbids
picking a variant after the runs. W1 stays DATA_QUALITY_FAILED: of the three events without OI,
the price-only run shows 2021-11-26 cancelled and 2021-12-04 expired (neither could trade
whatever OI said); 2021-09-07 15:00 was blocked by cooldown there and is undetermined.

No thresholds were tuned after these runs. Forward paper is not proposed; the owner decides
whether a v2 with a different, pre-registered entry geometry is worth specifying.

## Fix and rerun at ff64ed7 (Codex review 2026-10-22, REQUEST_CHANGES F1-F4)

Codex reviewed 5fdda7c / ab1ad81 (`REVIEW-CHO-CLAUDE-OI-RECLAIM-V1-2026-10-22.md`) and reproduced
four defects in the simulator and its report. All are fixed at **ff64ed7**; no v1 parameter and
no line of the config changed (shock 2A, OI -1%, reclaim 25%, RR 1.5, stop/target, cooldown,
confirmation, cost gate, risk 0.5%, 1x, lot/tick, costs). AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED.

- **F1 risk.** The simulator now uses the project `CircuitBreakerState` and `check_all_invariants`
  (as the broker and carry simulator do). Entry costs, every funding payment and the exit are
  booked at their own time in the rolling 24h ledger (5% of equity -> 24h lock); a lock while a
  position is open closes it at that bar's open (`CIRCUIT_BREAKER_LOCK`, cashflow booked, not
  counted in the streak, as in the broker); only a closed trade's net P&L moves the streak
  (3 losses -> risk x0.5, 3 wins in a row -> x1). Entries go through the invariants (stop side,
  1x leverage, "normal" 2% tier ceiling, actual stop risk <= budget, margin, notional <=
  min(project 2x, v1 1x) equity, liquidation buffer). The old calendar-day counter is gone; the
  breaker's lock is fixed at 24h, so `lock_hours` must stay 24.
- **F2 data.** `Simulator.preflight` fails the run (`DataQualityError`) before anything is
  simulated if a 15m bar from the first ATR input (start - 16h) to the window end is missing, off
  grid, non-finite or inconsistent, if any 00/08/16 UTC funding settlement in the window is
  missing or non-finite, or if there is no funding table. Missing funding is never zero and a
  missing bar is never "stop not touched". The CLI marks such runs `DATA_QUALITY_FAILED` with no
  metrics; runs with price shocks lacking OI snapshots are also `DATA_QUALITY_FAILED`, their
  numbers kept only under `diagnostic_not_scored`, and the ledger records both with stage
  `data-quality-failed` and no metrics (never `validation`).
- **F3 equity.** The equity curve is built at every 15m close from the cashflow ledger (entry,
  funding in the bar it is paid, exit) plus the open position marked at the close. Max drawdown
  is on those 15m closes with the start equity as the first peak (intrabar lows are not seen, so
  it is still a lower bound). Intrabar stop/target exits are stamped at the bar close
  (`exit_time`, when the fill is known) with `exit_bar` = the bar's open.
- **F4 settlement.** The summary keys each 15m value by its bar open, so the window-end close
  (END_OF_WINDOW settlement) stays inside the window and its own year/month; the run and the
  report both fail if final equity != start + trades' net P&L != start + ledger cashflows (1e-6).

Tests: 12 regressions (`test_f1_*` .. `test_f4_*` in `tests/test_oi_reclaim.py`; the fix
commit message says 13 by mistake), all red on ab1ad81
(`runs/oi-reclaim-v1-ff64ed7/logs/oi-tests-red-on-ab1ad81.log`) and green at ff64ed7. Five fail
on behaviour and reproduce Codex's numbers (TIME_STOP instead of a breaker close, a 3% risk entry
accepted, open-equity funding 0 vs -3.362865, reported 9,997.31 vs cash 9,994.62 twice); seven
fail on names the fix adds (risk_multiplier, DataQualityError, run_scenario, drawdown_pct,
exit_bar, cashflows), whose old behaviour Codex's probes already showed (4th loss still at 0.5%,
a dropped stop bar -> TIME_STOP, empty funding -> funding 0). The
existing fixtures now carry zero-rate 8h funding and start the window on the second day (ATR
history); the old `lock_hours=1` check became a check that the 24h lock covers the blocked fill.
Full offline suite at ff64ed7: 680 passed, 2 skipped, 5 network deselected (`logs/`).

Rerun: same inputs, same sha256 as the first run (`data_check.json`), outputs in
`docs/research/runs/oi-reclaim-v1-ff64ed7/` (summary.json sha256 1a904892...; per scenario
events / trades / cashflows CSVs; the W2 delay 15m equity curves), all 15m curves in
`/mnt/project-files/research-runs/oi-reclaim-v1-ff64ed7/equity-15m/`. The 5fdda7c ledger rows are
voided (kept, marked superseded) and the rerun recorded at ff64ed7.

| Window | Scenario | Status | Trades | Return % | Max DD % (15m) | Net $ | Funding $ |
|---|---|---|---|---|---|---|---|
| W1 | 6 OI scenarios + OI lag 60 | DATA_QUALITY_FAILED (3 shocks without OI) | not scored | | | | |
| W1 | price_only_no_positive | OK | 0 | 0.00 | 0.00 | 0 | 0 |
| W2 | base, costs x2 (actual / no_positive), OI lag 60, price only | OK | 0 | 0.00 | 0.00 | 0 | 0 |
| W2 | delay15m_actual / no_positive | OK | 2 | 1.24 | **0.43** (was 0.31) | 123.59 | -0.86 |

Funnels and rejects are identical to the first run in every scenario (the fixes change accounting
and risk, not the rules); the breaker never locked and every trade ran at risk x1. The delay
trades keep their fills and P&L (net 123.590892, as Codex replayed); their TARGET exits are now
stamped 15 minutes later (bar close). Drawdown 0.4299% equals Codex's funding-aware 15m figure.
Both 15m/funding preflights passed (no bar or settlement missing in W1 or W2).

Corrections to the text above (Codex): W1 is DATA_QUALITY_FAILED, so "no position in 69 months"
holds only for W2 plus the W1 price-only control; W1's OI scenarios are not evidence. W2 has 460
missing 5m OI snapshots (41 on the hour); what holds is that no W2 price shock lacks its two OI
snapshots, not that W2 OI coverage is complete. And reclaim 25% and RR 1.5 are not mutually
exclusive: ignoring tick/slippage, with D = Cprev - close_s and wick w, a valid entry exists when
w + 0.25A <= 0.25D; with tick and entry slippage, 30/111 (W1) and 28/87 (W2) accepted events had
a feasible entry range but only 1/21 and 3/19 signals still had one at the signal. The narrow
entry range after a 1h confirmation, not a contradiction, is what removes the trades. No v2 and
no delay variant is proposed from this; that needs a new pre-registered spec.
