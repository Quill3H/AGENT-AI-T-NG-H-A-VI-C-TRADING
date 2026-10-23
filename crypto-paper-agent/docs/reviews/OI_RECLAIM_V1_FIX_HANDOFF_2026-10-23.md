# btc_oi_contraction_reclaim_v1: fixes for Codex review F1-F4 (2026-10-23)

**AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED.** Implementer: Claude. Reviewer of record: Codex
(`REVIEW-CHO-CLAUDE-OI-RECLAIM-V1-2026-10-22.md`, verdict REQUEST_CHANGES on code `5fdda7c`,
report `ab1ad81`). Paper only; no order path, credential or real money. Not a gate acceptance.

## Identity
- Branch `claude/project-thread-bla4me`, based on `claude/project-thread-uiqlsn` at `ab1ad81`.
- Engine/accounting fix (locked for the rerun): `ce7ce676ce8683f04af21ef7b64249579a4c01ee`.
- Results/docs: the commit after `ce7ce67` on the same branch (see Git history).
- Strategy rules, thresholds, sizing, windows and scenarios are unchanged from `5fdda7c`
  (shock 2 ATR, OI -1%, reclaim 25%, RR 1.5, stop/target, cooldown, confirmation, 0.5% risk).
- Inputs (sha256, identical to the 5fdda7c run): `BTCUSDT_perp_15m.parquet` 42bdf78d...,
  `BTCUSDT_perp_funding.parquet` 445298b9..., `BTCUSDT_metrics_raw.csv.gz` 5b110ec9...,
  manifest 65c5ded0..., config `btc_oi_contraction_reclaim_v1.yaml` df90000d... (full hashes in
  `runs/oi-reclaim-v1-ce7ce67/data_check.json`).

## Changes (diff `5fdda7c..ce7ce67`: oi_reclaim.py, reproduce_oi_reclaim.py, performance_summary.py, tests)

**F1 risk.** The simulator now owns a project `CircuitBreakerState` (from `config/default_config.yaml`,
daily loss 5% from the strategy config): rolling 24h cashflow window, 3-loss streak halves risk,
3 wins in a row restore it, 24h lock. Cashflows go to a ledger and to the breaker at event time:
entry cost (fee + slippage) at the fill, each funding payment at its 15m open, exit cashflow at
the exit. A lock tripped by any cashflow closes the open position at that open
(`CIRCUIT_BREAKER_LOCK`); that forced close is booked as a cashflow only and not counted in the
streak, matching `PaperBroker`. Entries require `is_trading_allowed` and pass
`check_all_invariants` (tier `low` <= 1%, leverage 1x, notional, margin, liquidation before stop,
breaker, news filter as configured: disabled). The estimated liquidation price is stored per trade
and an open at or below it exits as `LIQUIDATION` (at 1x long it is 0, so unreachable). `lock_hours`
other than 24 is refused. Per-trade check: ledger sum == trade net P&L; per-run: cash == start +
ledger.

**F2 data.** `data_issues()` checks, for the window `[start, end)`: every 15m open present, OHLC
finite and > 0, every 00/08/16 UTC funding time present, every funding rate finite. Any issue
raises `DataQualityError` before a result exists; `_hold` re-checks bar continuity and scheduled
funding as it walks. The CLI's `evaluate()` turns a data error, or an OI snapshot missing at a
price shock, into `DATA_QUALITY_FAILED` with `scored: false`; such rows have no top-level metrics
(only `diagnostic` when the run completed), and are not written to the research ledger.

**F3 equity.** The curve is rebuilt from the ledger at every 15m close: cashflows known by that
close + the open position marked at the close. Funding shows in equity the bar it is paid.
`stats()` computes drawdown on the 15m curve (no resample). Intrabar STOP/TARGET exits are stamped
at the close of the bar (`exit_time = bar open + 15m`, `exit_bar_open`, `intrabar_estimated =
True`); gap, time-stop and breaker exits stay at the open, where they are known.

**F4 report.** `curve_summary(..., final_equity=)` writes the settled final equity onto the last
in-window point (the snapshot stamped exactly at `end` is still dropped, so no empty year/month).
`stats()` asserts `final - start == sum(ledger cashflows) == sum(trade net P&L)`.

## Regressions
12 tests added or changed in `tests/test_oi_reclaim.py`, red on `5fdda7c`, green on `ce7ce67`
(`runs/oi-reclaim-v1-ce7ce67/regression_red_at_5fdda7c.log`):
- F1: 4 consecutive losses -> 4th trade risk 0.25%; funding -0.2 x notional trips the breaker
  and closes at that open; a forced close is not a streak loss; gap loss > 5% blocks the next
  entry (breaker lock count 1) and `lock_hours=1` is refused.
- F2: removing the stop candle raises (was TIME_STOP); empty funding, a dropped 16:00 event,
  NaN funding and inf OHLC raise; CLI returns DATA_QUALITY_FAILED without metrics for a missing
  bar and with `diagnostic` only for missing OI.
- F3: funding paid appears in equity at that bar's close; curve = start + ledger + mark; target
  exit stamped at the bar close, gap exit at the open.
- F4: END_OF_WINDOW trade: reported final equity == final cash (was 9,997.31 vs 9,994.62);
  a window ending 2023-12-31 has only year 2023 and month 2023-12.

Fixture note: real windows are whole UTC days with funding at 00/08/16, so the test helper now pads
fixtures to the day end with flat bars and supplies a zero-rate 8h funding schedule; the
END_OF_WINDOW case uses a shock late on the last day (the reviewer's probe construction).

## Tests (Python 3.12.3, Linux, this container)
- Before the change, same environment: `pytest -m "not network"` 666 passed, 4 skipped, 5 deselected.
- At `ce7ce67`: 677 passed, 4 skipped, 5 deselected (`runs/oi-reclaim-v1-ce7ce67/tests_full_ce7ce67.log`). Network tests not run.

## Rerun (ce7ce67, SEEN_DATA_RETROSPECTIVE, AUTHOR_REPORTED)
Command:
```
python scripts/reproduce_oi_reclaim.py --data-dir <binance-vision-usdm-forward> \
  --oi <BTCUSDT_metrics_raw.csv.gz> --oi-manifest <BTCUSDT_metrics_raw_manifest.json> \
  --frozen-commit ce7ce676ce8683f04af21ef7b64249579a4c01ee \
  --out-dir docs/research/runs/oi-reclaim-v1-ce7ce67
```
Outputs per window x scenario in `docs/research/runs/oi-reclaim-v1-ce7ce67/`: `*_events.csv`,
`*_trades.csv`, `*_cashflows.csv` (entry, funding, exit at event time) and
`*_equity_15m.csv.gz`. `summary.json` sha256 2ab941cf..., `data_check.json` cd0278f2...
(the curves were written to a scratch `--curve-dir` and copied in; the run is byte-identical
to a dry run made before the commit, except `frozen_commit`). `data_check.json` now carries
`trading_data_issues` per window: empty for W1 and W2 (no missing 15m bar, no missing or
non-finite scheduled funding).

| Window | Scenario | Status | Trades | Final equity | Return % | Max DD % (15m) | Funding $ |
|---|---|---|---|---|---|---|---|
| W1 | 6 OI scenarios + lag60 | DATA_QUALITY_FAILED (3 shocks without OI) | (diagnostic 0) | | | | |
| W1 | price_only_no_positive | OK | 0 | 10,000.00 | 0.00 | 0.00 | 0 |
| W2 | base / cost2x, actual and no_positive | OK | 0 | 10,000.00 | 0.00 | 0.00 | 0 |
| W2 | delay15m_actual / _no_positive | OK | 2 (both TARGET, intrabar) | 10,123.590891951 | 1.24 | 0.43 | -0.86 |
| W2 | price_only_no_positive, oi_lag60_no_positive | OK | 0 | 10,000.00 | 0.00 | 0.00 | 0 |

Reconciliation, W2 delay15m: final 10,123.590891951171 = 10,000 + ledger 123.590891951171 =
sum of trade net P&L; matches the reviewer's independent replay (123.590891951). 15m drawdown
0.4299093913%, equal to the reviewer's funding-aware 15m figure. Exit times move from the bar
open to its close (2024-12-31 08:45, 2025-04-17 07:45). No breaker lock and no risk halving in
any run. The funnel counts are unchanged from 5fdda7c.

## Wording corrections taken from the review
- W1 is DATA_QUALITY_FAILED: "no trade in 69 months" is not valid evidence for W1. Scored
  evidence is W2 only (33 months).
- W2 has 460 missing 5m OI snapshots, 41 of them on the hour. The correct claim is only that
  no OI snapshot needed at the W2 price shocks was missing; OI coverage and data sufficiency
  for a decision are different things.
- The reclaim-25% and RR-1.5 gates do not contradict each other mathematically. With
  D = Cprev - close_s and lower wick w, a feasible entry exists when w + 0.25A <= 0.25D. The
  reviewer counts 30/111 (W1) and 28/87 (W2) accepted events with a feasible interval, but only
  1/21 and 3/19 confirmed signals: the entry window is narrow and the 1h confirmation usually
  arrives after price has moved past it or fallen below the reclaim level. Analyse this before
  any v2; v1 thresholds are not changed.

## Not done / limits
- The full OI source (2,130 ZIP checksums) is still AUTHOR_REPORTED; this pass reused the same
  raw file (same sha256), it did not re-download.
- Funding cashflow still uses the 15m open as mark; no historical mark price.
- Intrabar fills at the stop/target level are estimates (no tick data); the label now says so.
- Old 5fdda7c results stay in `runs/oi-reclaim-v1-5fdda7c/` and its 16 ledger rows are voided
  (reason recorded), not deleted. The delay variant is not a candidate.
- Next: Codex re-review of `5fdda7c..ce7ce67` and these outputs. Only after that, a separate
  pre-registered v2 spec, if the owner wants one.
