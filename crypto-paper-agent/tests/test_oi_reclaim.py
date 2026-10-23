"""btc_oi_contraction_reclaim_v1 (src/strategies/oi_reclaim.py, src/data_layer/oi_metrics.py).

Synthetic 15m bars: 40 quiet hours around 100 (true range 1, so A = 1), then a shock hour that
closes 3 lower (>= 2A), then a reclaim hour. OI is a constant 1000 contracts except where a test
changes it. Funding is a zero rate at every 00/08/16 UTC settlement unless a test sets one; the
window runs from the second fixture day (the first day is ATR history) to the last full day."""
import math

import numpy as np
import pandas as pd
import pytest

from src.data_layer import oi_metrics as om
from src.strategies import oi_reclaim as orc

T0 = pd.Timestamp("2024-03-01", tz="UTC")
Q = pd.Timedelta("15min")
H = pd.Timedelta("1h")


def quiet(hours, price=100.0):
    idx = pd.date_range(T0, periods=4 * hours, freq="15min")
    return pd.DataFrame({"open": price, "high": price + 0.5, "low": price - 0.5, "close": price}, index=idx)


def put_hour(frame, start, bars):
    """bars: four (o, h, l, c) tuples for the hour opening at start."""
    for k, bar in enumerate(bars):
        frame.loc[start + k * Q, ["open", "high", "low", "close"]] = bar


SHOCK = T0 + 40 * H  # shock hour opens here, closes at t = SHOCK + 1h


def scenario(hours=80, reclaim_close=97.9):
    b = quiet(hours)
    put_hour(b, SHOCK, [(100, 100.2, 99, 99), (99, 99, 98, 98), (98, 98, 97, 97.5), (97.5, 97.6, 96.9, 97)])
    c1 = SHOCK + H  # confirmation hour 1
    put_hour(b, c1, [(97, 97.4, 96.95, 97.3), (97.3, 97.6, 97.2, 97.5), (97.5, 97.8, 97.4, 97.7), (97.7, 98.0, 97.6, reclaim_close)])
    after = c1 + H  # fill bar opens at c1 + 1h + 15m (strictly after the signal at c1 + 1h)
    for k in range(4 * (hours - 42)):
        when = after + k * Q
        b.loc[when, ["open", "high", "low", "close"]] = (97.9, 98.2, 97.7, 97.9)
    return b


def oi_series(b, drop_at_t=-0.02):
    idx = pd.date_range(b.index[0], b.index[-1] + Q, freq="5min")
    oi = pd.Series(1000.0, index=idx)
    t = SHOCK + H
    oi[t] = 1000.0 * (1 + drop_at_t)
    return oi


def settlements(b, rate=0.0):
    idx = pd.date_range(b.index[0].floor("D"), b.index[-1] + Q, freq="8h")
    return pd.DataFrame({"funding_rate": rate}, index=idx)


def window(b):
    """(first, last) day: the first fixture day only feeds the ATR; the last day must be complete."""
    return str((b.index[0] + pd.Timedelta(days=1)).date()), str(((b.index[-1] + Q).normalize() - pd.Timedelta(days=1)).date())


def run(b, oi=None, funding=None, **cfg):
    oi = oi_series(b) if oi is None else oi
    funding = settlements(b) if funding is None else funding
    sim = orc.Simulator(b, funding, oi, cfg)
    return sim.run(*window(b))


def outcome(result):
    return [a["outcome"] for a in result["audit"]]


# ---------------------------------------------------------------- data layer
def raw_rows(times, oi, value=None):
    return pd.DataFrame({"create_time": [str(t.tz_localize(None)) for t in times], "symbol": "BTCUSDT",
                         "sum_open_interest": [str(x) for x in oi],
                         "sum_open_interest_value": [str(x) for x in (value if value is not None else oi)]})


def test_reversed_csv_rows_parse_identically():
    times = pd.date_range("2024-01-01", periods=6, freq="5min", tz="UTC")
    rows = raw_rows(times, [1, 2, 3, 4, 5, 6])
    pd.testing.assert_series_equal(om.parse_oi(rows), om.parse_oi(rows.iloc[::-1]))


def test_duplicates_conflicts_and_bad_values():
    times = pd.date_range("2024-01-01", periods=3, freq="5min", tz="UTC")
    rows = raw_rows(times, [1, 2, 3])
    assert len(om.parse_oi(pd.concat([rows, rows]))) == 3  # exact duplicates collapse
    conflict = pd.concat([rows, raw_rows(times[:1], [9])])
    with pytest.raises(om.OIDataError, match="conflicting"):
        om.parse_oi(conflict)
    for bad in ("nan", "inf", "0", "-1", ""):
        broken = rows.copy()
        broken.loc[1, "sum_open_interest"] = bad
        with pytest.raises(om.OIDataError, match="non-positive"):
            om.parse_oi(broken)
        series, dropped = om.parse_oi(broken, invalid="drop")
        assert list(dropped) == [times[1]] and times[1] not in series.index  # missing, never filled


def test_coverage_counts_missing_snapshots():
    times = pd.date_range("2024-01-01", periods=12, freq="5min", tz="UTC").delete(4)
    c = om.coverage(om.parse_oi(raw_rows(times, range(1, 12))), "2024-01-01", "2024-01-01 01:00")
    assert c["expected"] == 12 and c["missing"] == 1 and list(c["missing_times"]) == [pd.Timestamp("2024-01-01 00:20", tz="UTC")]


def test_oi_value_falling_with_price_is_not_contraction():
    b = scenario()
    t = SHOCK + H
    times = pd.date_range(b.index[0], b.index[-1] + Q, freq="5min")
    value = [1000.0 * (97.0 if x >= t else 100.0) for x in times]  # USDT value falls 3%, quantity flat
    oi = om.parse_oi(raw_rows(times, [1000.0] * len(times), value))
    result = run(b, oi)
    assert result["layers"]["price_shocks"] == 1 and result["layers"]["oi_not_contracting"] == 1
    assert result["trades"] == []


# ---------------------------------------------------------------- events
def test_atr_uses_only_the_14_bars_before_the_shock():
    b = scenario()
    h1, _ = orc.hourly_bars(b)
    ev = orc.detect(h1, oi_series(b), orc.DEFAULTS, T0, b.index[-1])
    assert len(ev) == 1 and ev.iloc[0]["atr"] == pytest.approx(1.0)
    assert ev.iloc[0]["c_prev"] == 100 and ev.iloc[0]["close_s"] == 97 and ev.iloc[0]["low_s"] == 96.9
    assert ev.iloc[0]["oi_change"] == pytest.approx(-0.02)


def test_event_threshold_edges():
    b = scenario()
    assert run(b, oi_series(b, -0.0099))["layers"]["events"] == 0
    assert run(b, oi_series(b, -0.01))["layers"]["events"] == 1
    shallow = scenario()
    put_hour(shallow, SHOCK, [(100, 100.2, 99, 99), (99, 99, 98.5, 98.5), (98.5, 98.5, 98.1, 98.2), (98.2, 98.3, 98.0, 98.01)])
    assert run(shallow)["layers"]["price_shocks"] == 0  # drop 1.99 < 2A


def test_incomplete_hour_is_not_a_bar():
    b = scenario().drop(SHOCK + 2 * Q)
    h1, incomplete = orc.hourly_bars(b)
    assert incomplete == 1 and SHOCK not in h1.index


def test_missing_oi_snapshot_is_reported_not_skipped_silently():
    b = scenario()
    oi = oi_series(b).drop(SHOCK)  # OI(t - 1h)
    result = run(b, oi)
    assert outcome(result) == ["OI_MISSING"] and result["missing_oi_event_times"] == [str(SHOCK + H)]
    assert run(b, oi, use_oi=False)["layers"]["signals"] == 1  # price-only control does not need it


# ---------------------------------------------------------------- confirmation and entry
def test_signal_fill_strictly_after_and_hand_computed_pnl():
    b = scenario()
    result = run(b)
    (tr,) = result["trades"]
    signal_at = SHOCK + 2 * H
    assert tr.fill_time == signal_at + Q > result["audit"][0]["signal_at"]
    assert tr.entry_open == 97.9 and tr.stop == pytest.approx(96.6) and tr.target == pytest.approx(100.0)
    e = 97.9 * 1.0003
    per_unit = (e - 96.6 * 0.9997) + e * 0.0005 + 96.6 * 0.9997 * 0.0005
    qty = math.floor(50.0 / per_unit / 0.001 + 1e-9) * 0.001
    assert tr.quantity == pytest.approx(qty)
    # no stop or target is hit, so the 24h time stop exits at the open 24h after the fill
    assert tr.exit_reason == "TIME_STOP" and tr.exit_time == tr.fill_time + 24 * H
    exit_px = 97.9 * 0.9997
    fees = qty * e * 0.0005 + qty * exit_px * 0.0005
    slip = qty * 97.9 * 0.0003 * 2
    assert tr.fees == pytest.approx(fees) and tr.slippage_cost == pytest.approx(slip)
    assert tr.net_pnl == pytest.approx(-fees - slip)
    assert result["final_cash"] == pytest.approx(10000 + tr.net_pnl)
    assert result["curve"].iloc[-1] == pytest.approx(result["final_cash"])


def test_second_confirmation_bar_and_expiry():
    b = scenario(reclaim_close=97.6)  # bar 1 closes up but below 97.75
    c2 = SHOCK + 2 * H
    put_hour(b, c2, [(97.6, 97.9, 97.5, 97.7), (97.7, 98, 97.6, 97.8), (97.8, 98, 97.7, 97.9), (97.9, 98.1, 97.8, 97.95)])
    (tr,) = run(b)["trades"]
    assert tr.fill_time == SHOCK + 3 * H + Q
    put_hour(b, c2, [(97.6, 97.7, 97.5, 97.6)] * 4)
    assert outcome(run(b)) == ["EXPIRED"]


def test_a_15m_low_below_the_event_low_cancels():
    b = scenario()
    b.loc[SHOCK + H + Q, "low"] = 96.8
    assert outcome(run(b)) == ["CANCELLED"]
    b = scenario()
    b.loc[SHOCK + 2 * H, "low"] = 96.85  # between the signal and the fill
    assert outcome(run(b)) == ["CANCELLED"]


def test_rejected_at_the_open_is_not_retried():
    b = scenario()
    b.loc[SHOCK + 2 * H + Q, "open"] = 97.7  # below the 97.75 reclaim level at the fill open
    result = run(b)
    assert outcome(result) == ["REJECT_BELOW_RECLAIM_AT_OPEN"] and result["trades"] == []


def test_rr_cost_lot_and_min_notional_gates():
    b = scenario()
    b.loc[SHOCK + 2 * H + Q:, ["open", "high", "low", "close"]] = (98.6, 98.9, 98.4, 98.6)
    assert outcome(run(b)) == ["REJECT_RR"]
    assert outcome(run(scenario(), taker_pct=0.05)) == ["REJECT_COST_GATE"]
    assert outcome(run(scenario(), initial_equity=20.0)) in (["REJECT_MIN_NOTIONAL"], ["REJECT_LOT"])


def test_delayed_entry_rechecks_at_the_later_open():
    b = scenario()
    (tr,) = run(b, entry_delay_bars=1)["trades"]
    assert tr.fill_time == SHOCK + 2 * H + 2 * Q
    b.loc[SHOCK + 2 * H + 2 * Q, "open"] = 97.7
    assert outcome(run(b, entry_delay_bars=1)) == ["REJECT_BELOW_RECLAIM_AT_OPEN"]


def test_oi_lag_never_uses_a_bar_closed_before_oi_was_available():
    b = scenario()
    assert run(b, oi_lag_minutes=60)["trades"][0].fill_time == SHOCK + 2 * H + Q  # available at close
    late = run(b, oi_lag_minutes=61)
    assert outcome(late) == ["EXPIRED"]  # bar 1 skipped, bar 2 is flat


def test_cooldown_and_open_position_block_new_events():
    b = scenario(hours=120)
    second = SHOCK + 6 * H  # the stop of the first trade is hit inside this shock: flat, but in cooldown
    put_hour(b, second, [(97.9, 98, 96, 96), (96, 96, 95, 95), (95, 95, 94.6, 94.8), (94.8, 94.9, 94.7, 94.8)])
    b.loc[second + H:, ["open", "high", "low", "close"]] = (97.9, 98.2, 97.7, 97.9)
    oi = oi_series(b)
    oi[second + H] = 970.0
    result = run(b, oi)
    assert result["layers"]["events"] == 2 and result["layers"]["skipped_cooldown"] == 1
    assert len(result["trades"]) == 1 and result["trades"][0].exit_reason == "STOP"


def test_an_open_position_blocks_a_new_event_even_after_cooldown():
    b = scenario(hours=120)
    fill = SHOCK + 2 * H + Q
    b.loc[fill + Q:, ["open", "high", "low", "close"]] = (99.0, 99.5, 98.5, 99.0)
    second = fill + 17 * H - Q  # hour open; the position (stop 96.6, target 100) is still open
    put_hour(b, second, [(99, 99.1, 98, 98), (98, 98, 97.5, 97.5), (97.5, 97.5, 96.8, 97), (97, 97.1, 96.7, 96.9)])
    b.loc[second + H:, ["open", "high", "low", "close"]] = (97.5, 97.8, 97.2, 97.5)
    oi = oi_series(b)
    oi[second + H] = 970.0
    result = run(b, oi, cooldown_hours=1)
    assert result["layers"]["events"] == 2 and result["layers"]["skipped_position_open"] == 1
    assert len(result["trades"]) == 1


# ---------------------------------------------------------------- exits
def test_stop_first_when_stop_and_target_share_a_bar():
    b = scenario()
    b.loc[SHOCK + 2 * H + 2 * Q, ["open", "high", "low", "close"]] = (97.9, 100.5, 96.0, 98)
    (tr,) = run(b)["trades"]
    assert tr.exit_reason == "STOP" and tr.exit_price == pytest.approx(96.6 * 0.9997)


def test_gap_through_stop_exits_at_the_worse_open():
    b = scenario()
    b.loc[SHOCK + 2 * H + 2 * Q, ["open", "high", "low", "close"]] = (95.0, 95.5, 94.0, 95)
    (tr,) = run(b)["trades"]
    assert tr.exit_reason == "STOP_GAP" and tr.exit_price == pytest.approx(95.0 * 0.9997)


def test_target_and_end_of_window():
    b = scenario()
    b.loc[SHOCK + 2 * H + 3 * Q, "high"] = 100.2
    (tr,) = run(b)["trades"]
    assert tr.exit_reason == "TARGET" and tr.exit_price == pytest.approx(100.0 * 0.9997)
    short = scenario(hours=50)
    result = run(short)
    (tr,) = result["trades"]
    assert tr.exit_reason == "END_OF_WINDOW" and tr.exit_time == result["end"] == tr.exit_bar + Q


def test_future_bars_do_not_change_a_finished_trade():
    b = scenario(hours=100)
    first = run(b)["trades"][0]
    changed = b.copy()
    changed.loc[first.exit_time + H:, ["high", "low"]] = (150, 50)
    again = run(changed)["trades"][0]
    assert (again.fill_time, again.exit_time, again.net_pnl) == (first.fill_time, first.exit_time, first.net_pnl)


# ---------------------------------------------------------------- funding accounts
def funding_at(b, *events):
    """Zero-rate settlements plus the given (time, rate) events."""
    f = settlements(b)
    for when, rate in events:
        f.loc[when, "funding_rate"] = rate
    return f.sort_index()


def test_no_positive_drops_received_funding_and_keeps_paid_funding():
    b = scenario()
    fill = SHOCK + 2 * H + Q
    pay, receive = fill + 3 * Q, fill + 7 * Q  # rates +0.001 (long pays), -0.002 (long receives)
    f = funding_at(b, (pay, 0.001), (receive, -0.002))
    actual = run(b, funding=f)["trades"][0]
    nopos = run(b, funding=f, funding_mode="no_positive")["trades"][0]
    paid, got = -actual.quantity * 97.9 * 0.001, actual.quantity * 97.9 * 0.002
    assert actual.funding == pytest.approx(paid + got)
    assert nopos.funding == pytest.approx(paid) and nopos.funding_skipped_positive == pytest.approx(got)
    assert nopos.net_pnl == pytest.approx(actual.net_pnl - got)


def test_paid_funding_shrinks_the_next_trade_size():
    b = scenario(hours=140)
    second = SHOCK + 50 * H
    put_hour(b, second, [(97.9, 98, 96, 96), (96, 96, 95, 95), (95, 95, 94.9, 95)] + [(95, 95.1, 94.9, 95)])
    put_hour(b, second + H, [(95, 95.3, 94.95, 95.2), (95.2, 95.5, 95.1, 95.4), (95.4, 95.7, 95.3, 95.6), (95.6, 95.9, 95.5, 95.8)])
    b.loc[second + 2 * H:, ["open", "high", "low", "close"]] = (95.8, 96.0, 95.6, 95.8)
    b.loc[second - 16 * H:second - Q, ["open", "high", "low", "close"]] = (97.9, 98.4, 97.4, 97.9)
    oi = oi_series(b)
    oi[second + H] = 970.0
    fill = SHOCK + 2 * H + Q
    big = funding_at(b, (fill + 4 * Q, 0.05))  # the long pays 5% of notional once
    base = run(b, oi, funding_mode="no_positive")["trades"]
    paid = run(b, oi, funding=big, funding_mode="no_positive")["trades"]
    assert len(base) == len(paid) == 2
    assert paid[1].equity_before < base[1].equity_before and paid[1].quantity < base[1].quantity


def test_daily_loss_breaker_blocks_the_next_entry():
    b = scenario(hours=140)
    gap = SHOCK + 2 * H + 2 * Q
    b.loc[gap, ["open", "high", "low", "close"]] = (80.0, 80.5, 79.0, 80)  # 0.5% risk sizing, -6.5% of equity
    b.loc[gap + Q:, ["open", "high", "low", "close"]] = (97.9, 98.2, 97.7, 97.9)
    second = SHOCK + 20 * H  # A = 0.5 here; a 1.3 drop with no wick, then a reclaim hour
    put_hour(b, second, [(97.9, 98, 97.5, 97.5), (97.5, 97.5, 97.0, 97.0), (97.0, 97.0, 96.7, 96.7), (96.7, 96.7, 96.6, 96.6)])
    put_hour(b, second + H, [(96.6, 96.8, 96.6, 96.7), (96.7, 96.9, 96.65, 96.8), (96.8, 96.95, 96.75, 96.9), (96.9, 97.0, 96.85, 96.95)])
    b.loc[second + 2 * H:, ["open", "high", "low", "close"]] = (96.95, 97.1, 96.8, 96.95)
    oi = oi_series(b)
    oi[second + H] = 970.0
    result = run(b, oi, cooldown_hours=1)
    (tr,) = result["trades"]
    assert tr.exit_reason == "STOP_GAP" and tr.net_pnl < -0.05 * 10000
    last = result["audit"][-1]
    assert last["outcome"] == "REJECT_BREAKER_LOCK" and result["rejects"] == {"BREAKER_LOCK": 1}
    assert last["fill_time"] < last["breaker_locked_until"] == tr.exit_time + 24 * H
    with pytest.raises(ValueError, match="lock_hours"):
        run(b, oi, lock_hours=1)  # the project breaker locks for exactly 24h


# ---------------------------------------------------------------- Codex review 2026-10-22 (F1-F4)
def load_cli():
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("reproduce_oi_reclaim", Path(__file__).resolve().parents[1] / "scripts" / "reproduce_oi_reclaim.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def repeated(blocks, hours=80):
    """`blocks` copies of the one-trade scenario back to back, each with its own OI contraction."""
    parts = []
    for k in range(blocks):
        part = scenario(hours)
        part.index = part.index + k * hours * H
        parts.append(part)
    b = pd.concat(parts)
    oi = pd.Series(1000.0, index=pd.date_range(b.index[0], b.index[-1] + Q, freq="5min"))
    for k in range(blocks):
        oi[SHOCK + H + k * hours * H] = 980.0
    return b, oi


def test_f1_three_losses_halve_the_risk_of_the_fourth_trade():
    b, oi = repeated(4)
    result = run(b, oi)
    trades = result["trades"]
    assert len(trades) == 4 and all(t.net_pnl < 0 and t.exit_reason == "TIME_STOP" for t in trades)
    assert [t.risk_multiplier for t in trades] == [1.0, 1.0, 1.0, 0.5]
    assert trades[3].risk_budget / trades[3].equity_before == pytest.approx(0.0025)
    assert trades[2].risk_budget / trades[2].equity_before == pytest.approx(0.005)


def test_f1_a_funding_payment_that_breaks_the_daily_loss_limit_closes_at_once():
    b = scenario()
    fill = SHOCK + 2 * H + Q
    pay = fill + Q
    result = run(b, funding=funding_at(b, (pay, 0.2)), funding_mode="no_positive")
    (tr,) = result["trades"]
    assert tr.funding < -0.05 * 10000
    assert tr.exit_reason == "CIRCUIT_BREAKER_LOCK" and tr.exit_time == pay and tr.exit_price == pytest.approx(97.9 * 0.9997)
    assert result["breaker"]["locks"] == 1
    # the forced close books its cashflow once and does not count as a strategy loss in the streak
    assert result["breaker"]["consecutive_losses_at_end"] == 0
    assert [e["kind"] for e in result["cashflows"]] == ["ENTRY", "FUNDING", "EXIT_CIRCUIT_BREAKER_LOCK"]


def test_f1_entry_passes_the_project_invariants():
    result = run(scenario(), risk_pct=0.03)  # above the 2% "normal" conviction tier ceiling
    assert outcome(result) == ["REJECT_INVARIANT"] and "RISK_TIER_EXCEEDED" in result["audit"][0]["invariant_reasons"][0]
    (tr,) = run(scenario())["trades"]
    assert 0 <= tr.liquidation_price < tr.stop  # 1x long: the estimate is 0, far below the stop


def test_f2_a_missing_15m_bar_fails_the_run_instead_of_missing_the_stop():
    b = scenario()
    fill = SHOCK + 2 * H + Q
    b.loc[fill + Q, ["open", "high", "low", "close"]] = (97.9, 98.2, 96.0, 97.9)
    assert run(b)["trades"][0].exit_reason == "STOP"
    with pytest.raises(orc.DataQualityError, match="15m bars missing"):
        run(b.drop(fill + Q))
    last_bar = pd.Timestamp(window(b)[1], tz="UTC") + pd.Timedelta(days=1) - Q
    with pytest.raises(orc.DataQualityError, match="15m bars missing"):
        run(b.drop(last_bar))  # the window's last bar is gone
    early = b.copy()
    early.loc[T0 + 15 * H, "close"] = np.nan
    with pytest.raises(orc.DataQualityError, match="non-finite"):
        run(early)


def test_f2_missing_or_bad_funding_fails_the_run_instead_of_paying_zero():
    b = scenario()
    with pytest.raises(orc.DataQualityError, match="no funding table"):
        orc.Simulator(b, None, oi_series(b)).run(*window(b))
    empty = pd.DataFrame({"funding_rate": pd.Series(dtype=float)}, index=pd.DatetimeIndex([], tz="UTC"))
    with pytest.raises(orc.DataQualityError, match="funding settlements missing"):
        run(b, funding=empty)
    gap = settlements(b).drop(SHOCK + 8 * H)
    with pytest.raises(orc.DataQualityError, match="funding settlements missing"):
        run(b, funding=gap)
    nan = settlements(b)
    nan.iloc[5, 0] = np.nan
    with pytest.raises(orc.DataQualityError, match="non-finite funding"):
        run(b, funding=nan)


def test_f2_cli_keeps_failed_data_apart_from_scored_results():
    cli = load_cli()
    b = scenario()
    cfg = {**orc.DEFAULTS}
    first, last = window(b)
    ok, result = cli.run_scenario(b, settlements(b), oi_series(b), cfg, first, last)
    assert ok["status"] == "OK" and ok["completed_trades"] == 1
    failed, result = cli.run_scenario(b.drop(SHOCK + 3 * H), settlements(b), oi_series(b), cfg, first, last)
    assert failed["status"] == "DATA_QUALITY_FAILED" and result is None and "completed_trades" not in failed
    no_oi, _ = cli.run_scenario(b, settlements(b), oi_series(b).drop(SHOCK), cfg, first, last)
    assert no_oi["status"] == "DATA_QUALITY_FAILED" and "total_return_pct" not in no_oi
    assert "total_return_pct" in no_oi["diagnostic_not_scored"]
    assert cli.preflight(b.drop(SHOCK + 3 * H), settlements(b), first, last).startswith("DATA_QUALITY_FAILED")


def test_f3_open_equity_includes_funding_when_it_is_paid():
    b = scenario()
    fill = SHOCK + 2 * H + Q
    pay = fill + Q
    base = run(b)
    paid = run(b, funding=funding_at(b, (pay, 0.001)))
    flow = paid["trades"][0].funding
    assert flow < 0
    difference = paid["curve"] - base["curve"]
    assert difference[pay] == 0  # the close before the payment
    assert difference[pay + Q] == pytest.approx(flow)  # the close of the bar it is paid in, position still open
    assert difference.iloc[-1] == pytest.approx(flow)


def test_f3_drawdown_is_measured_on_15m_closes():
    b = scenario()
    fill = SHOCK + 2 * H + Q
    dip = fill + 4 * Q  # closes at :30, mid-hour, below the hour's last close; no stop is touched
    b.loc[dip, ["open", "high", "low", "close"]] = (97.9, 97.9, 96.7, 96.7)
    result = run(b)
    cli = load_cli()
    s = cli.stats(result, orc.DEFAULTS)
    (tr,) = result["trades"]
    curve = result["curve"]
    expected = cli.drawdown_pct(curve, 10000.0)
    hourly = curve.resample("1h", label="right", closed="right").last()
    assert s["max_drawdown_pct_exact"] == pytest.approx(expected)
    assert expected > cli.drawdown_pct(hourly, 10000.0) + 0.1
    assert curve[dip + Q] == pytest.approx(10000 - tr.quantity * 97.9 * 0.0003 - tr.quantity * tr.entry_price * 0.0005
                                           + tr.quantity * (96.7 - 97.9))


def test_f3_an_intrabar_exit_is_stamped_at_the_bar_close():
    b = scenario()
    bar = SHOCK + 2 * H + 3 * Q
    b.loc[bar, "high"] = 100.2
    (tr,) = run(b)["trades"]
    assert tr.exit_reason == "TARGET" and tr.exit_bar == bar and tr.exit_time == bar + Q


@pytest.mark.parametrize("start", ["2023-12-30", "2024-01-30"])
def test_f4_end_of_window_settlement_is_in_the_reported_equity(start):
    b = scenario()
    b.index = b.index - T0 + pd.Timestamp(start, tz="UTC")
    oi = pd.Series(1000.0, index=pd.date_range(b.index[0], b.index[-1] + Q, freq="5min"))
    oi[b.index[0] + (SHOCK - T0) + H] = 980.0
    last = str((pd.Timestamp(start) + pd.Timedelta(days=1)).date())
    result = orc.Simulator(b, settlements(b), oi).run(last, last)  # one day; the trade is open at its end
    (tr,) = result["trades"]
    assert tr.exit_reason == "END_OF_WINDOW" and tr.exit_time == result["end"]
    s = load_cli().stats(result, orc.DEFAULTS)
    assert s["final_equity_usd"] == round(result["final_cash"], 2) == round(10000 + tr.net_pnl, 2)
    assert s["reconciliation"]["max_abs_diff"] < 1e-9
    assert s["total_return_pct"] == round(tr.net_pnl / 100, 2)
    month = pd.Timestamp(last).strftime("%Y-%m")
    assert list(s["yearly_return_pct"]) == [pd.Timestamp(last).year]  # no extra year at 1 January
    assert list(s["monthly"]["monthly_return_pct"]) == [month]  # no extra month at the 1st


def test_f4_cashflow_ledger_reconciles_with_trades_and_curve():
    b, oi = repeated(3)
    f = funding_at(b, (SHOCK + 2 * H + 2 * Q, 0.001), (SHOCK + 82 * H + 2 * Q, -0.002))
    for mode in ("actual", "no_positive"):
        result = run(b, oi, funding=f, funding_mode=mode)
        booked = sum(e["amount"] for e in result["cashflows"])
        assert booked == pytest.approx(sum(t.net_pnl for t in result["trades"]), abs=1e-9)
        assert result["curve"].iloc[-1] == pytest.approx(10000 + booked, abs=1e-9) == result["final_cash"]
