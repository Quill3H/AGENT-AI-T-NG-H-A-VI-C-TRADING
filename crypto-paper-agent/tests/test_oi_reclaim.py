"""btc_oi_contraction_reclaim_v1 (src/strategies/oi_reclaim.py, src/data_layer/oi_metrics.py).

Synthetic 15m bars: 40 quiet hours around 100 (true range 1, so A = 1), then a shock hour that
closes 3 lower (>= 2A), then a reclaim hour. OI is a constant 1000 contracts except where a test
changes it."""
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


def full_days(b):
    """Real data covers whole UTC days: pad the fixture with flat bars at the last close."""
    day_end = b.index[-1].normalize() + pd.Timedelta(days=1)
    pad = pd.date_range(b.index[-1] + Q, day_end, freq="15min", inclusive="left")
    last = float(b["close"].iloc[-1])
    return pd.concat([b, pd.DataFrame({"open": last, "high": last, "low": last, "close": last}, index=pad)])


def schedule(b, rate=0.0):
    """Funding at 00/08/16 UTC over the fixture's days (zero unless a test sets it)."""
    idx = pd.date_range(b.index[0].normalize(), b.index[-1].normalize() + pd.Timedelta(days=1), freq="8h", inclusive="left")
    return pd.DataFrame({"funding_rate": rate}, index=idx)


def run(b, oi=None, funding=None, **cfg):
    oi = oi_series(b) if oi is None else oi
    b = full_days(b)
    funding = schedule(b) if funding is None else funding
    sim = orc.Simulator(b, funding, oi, cfg)
    return sim.run(str(b.index[0].date()), str((b.index[-1]).date()))


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
    late, oi = late_in_day()
    result = run(late, oi)
    (tr,) = result["trades"]
    assert tr.exit_reason == "END_OF_WINDOW" and tr.exit_time == late.index[-1] + Q == result["end"]


def test_future_bars_do_not_change_a_finished_trade():
    b = scenario(hours=100)
    first = run(b)["trades"][0]
    changed = b.copy()
    changed.loc[first.exit_time + H:, ["high", "low"]] = (150, 50)
    again = run(changed)["trades"][0]
    assert (again.fill_time, again.exit_time, again.net_pnl) == (first.fill_time, first.exit_time, first.net_pnl)


# ---------------------------------------------------------------- funding accounts
def funding_at(*events, days=8):
    """Zero-rate 8h schedule plus the given events (off-schedule times are allowed)."""
    base = pd.DataFrame({"funding_rate": 0.0}, index=pd.date_range(T0, T0 + pd.Timedelta(days=days), freq="8h", inclusive="left"))
    for when, rate in events:
        base.loc[when, "funding_rate"] = rate
    return base.sort_index()


def test_no_positive_drops_received_funding_and_keeps_paid_funding():
    b = scenario()
    fill = SHOCK + 2 * H + Q
    pay, receive = fill + 3 * Q, fill + 7 * Q  # rates +0.001 (long pays), -0.002 (long receives)
    f = funding_at((pay, 0.001), (receive, -0.002))
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
    big = funding_at((fill + 4 * Q, 0.05))  # the long pays 5% of notional once
    base = run(b, oi, funding_mode="no_positive")["trades"]
    paid = run(b, oi, funding=big, funding_mode="no_positive")["trades"]
    assert len(base) == len(paid) == 2
    assert paid[1].equity_before < base[1].equity_before and paid[1].quantity < base[1].quantity


def test_daily_loss_breaker_blocks_the_next_entry():
    b = scenario(hours=140)
    gap = SHOCK + 2 * H + 2 * Q
    b.loc[gap, ["open", "high", "low", "close"]] = (80.0, 80.5, 79.0, 80)  # about -6.6% of equity
    b.loc[gap + Q:, ["open", "high", "low", "close"]] = (97.9, 98.2, 97.7, 97.9)
    second = SHOCK + 20 * H  # A = 0.5 here; a 1.3 drop with no wick, then a reclaim hour
    put_hour(b, second, [(97.9, 98, 97.5, 97.5), (97.5, 97.5, 97.0, 97.0), (97.0, 97.0, 96.7, 96.7), (96.7, 96.7, 96.6, 96.6)])
    put_hour(b, second + H, [(96.6, 96.8, 96.6, 96.7), (96.7, 96.9, 96.65, 96.8), (96.8, 96.95, 96.75, 96.9), (96.9, 97.0, 96.85, 96.95)])
    b.loc[second + 2 * H:, ["open", "high", "low", "close"]] = (96.95, 97.1, 96.8, 96.95)
    oi = oi_series(b)
    oi[second + H] = 970.0
    result = run(b, oi, cooldown_hours=1)
    assert result["trades"][0].exit_reason == "STOP_GAP" and result["trades"][0].net_pnl < -0.05 * 10000
    assert outcome(result)[-1] == "REJECT_BREAKER_LOCK" and result["rejects"] == {"BREAKER_LOCK": 1}
    assert result["breaker"]["locks"] == 1
    with pytest.raises(ValueError, match="lock_hours"):
        run(b, oi, lock_hours=1)  # the project breaker locks for 24h; not a strategy knob


# ---------------------------------------------------------------- Codex review 2026-10-22 (F1-F4)
def late_in_day():
    """Shock late on day 3, so a trade is still open when the window ends at 72h."""
    tail = scenario()
    tail.index = tail.index + 24 * H
    bars = pd.concat([quiet(24), tail]).iloc[:72 * 4]
    oi = pd.Series(1000.0, index=pd.date_range(T0, T0 + 72 * H, freq="5min"))
    oi[SHOCK + 25 * H] = 980.0
    return bars, oi


def losing_chain(blocks):
    """`blocks` copies of the base scenario, 80h apart, each ending in a 24h time stop (a loss)."""
    parts = []
    for k in range(blocks):
        block = scenario()
        block.index = block.index + k * 80 * H
        parts.append(block)
    bars = pd.concat(parts)
    oi = pd.Series(1000.0, index=pd.date_range(bars.index[0], bars.index[-1] + Q, freq="5min"))
    for k in range(blocks):
        oi[SHOCK + H + k * 80 * H] = 980.0
    return bars, oi


def test_f1_three_losses_halve_the_risk_of_the_next_trade():
    bars, oi = losing_chain(4)
    trades = run(bars, oi)["trades"]
    assert len(trades) == 4 and all(t.net_pnl < 0 for t in trades)
    assert [t.risk_multiplier for t in trades] == [1.0, 1.0, 1.0, 0.5]
    assert trades[3].risk_budget / trades[3].equity_before == pytest.approx(0.0025)
    assert trades[3].quantity < trades[2].quantity


def test_f1_funding_loss_trips_the_breaker_and_closes_at_that_open():
    b = scenario()
    fill = SHOCK + 2 * H + Q
    pay = fill + Q
    result = run(b, funding=funding_at((pay, 0.2)), funding_mode="no_positive")
    (tr,) = result["trades"]
    assert tr.funding < -0.05 * 10000
    assert tr.exit_reason == "CIRCUIT_BREAKER_LOCK" and tr.exit_time == pay
    assert result["breaker"]["locks"] == 1
    kinds = [(e["kind"], e["time"]) for e in result["ledger"]]
    assert kinds == [("ENTRY", fill), ("FUNDING", pay), ("EXIT", pay)]


def test_f1_forced_close_does_not_count_in_the_streak():
    bars, oi = losing_chain(4)
    fund = pd.DataFrame({"funding_rate": 0.0}, index=pd.date_range(T0, T0 + pd.Timedelta(days=15), freq="8h", inclusive="left"))
    fill2 = SHOCK + 2 * H + Q + 80 * H
    fund.loc[fill2 + Q, "funding_rate"] = 0.2  # second trade: emergency close, not a streak loss
    fund = fund.sort_index()
    trades = run(bars, oi, funding=fund, funding_mode="no_positive")["trades"]
    reasons = [t.exit_reason for t in trades]
    assert reasons[1] == "CIRCUIT_BREAKER_LOCK"
    # losses 1, 3, 4 (3 counted) -> only a trade after the fourth would be halved
    assert [t.risk_multiplier for t in trades] == [1.0] * len(trades)


def test_f2_missing_stop_candle_is_a_data_error_not_a_time_stop():
    b = scenario()
    fill = SHOCK + 2 * H + Q
    b.loc[fill + Q, ["open", "high", "low", "close"]] = (97.9, 98.2, 96.0, 97.9)
    assert run(b)["trades"][0].exit_reason == "STOP"
    with pytest.raises(orc.DataQualityError, match="missing_15m_bars"):
        run(b.drop(fill + Q))


def test_f2_missing_or_bad_funding_is_a_data_error_not_zero():
    b = scenario()
    empty = pd.DataFrame({"funding_rate": pd.Series(dtype=float)}, index=pd.DatetimeIndex([], tz="UTC"))
    with pytest.raises(orc.DataQualityError, match="missing_funding_events"):
        run(b, funding=empty)
    with pytest.raises(orc.DataQualityError, match="missing_funding_events"):
        run(b, funding=funding_at().drop(T0 + 2 * pd.Timedelta(days=1)))
    with pytest.raises(orc.DataQualityError, match="non_finite_funding"):
        run(b, funding=funding_at((T0 + 8 * H, float("nan"))))
    bad = scenario()
    bad.loc[T0 + 3 * Q, "close"] = float("inf")
    with pytest.raises(orc.DataQualityError, match="bad_ohlc"):
        run(bad)


def test_f3_open_equity_includes_funding_when_paid():
    b = scenario()
    fill = SHOCK + 2 * H + Q
    pay = fill + Q
    base = run(b)
    paid = run(b, funding=funding_at((pay, 0.001)))
    flow = paid["trades"][0].funding
    assert flow < 0
    diff = paid["curve"] - base["curve"]
    assert diff[pay] == 0 and diff[pay + Q] == pytest.approx(flow)  # known from the close of the bar it was paid in
    assert paid["final_cash"] - base["final_cash"] == pytest.approx(flow)


def test_f3_curve_is_rebuilt_from_the_ledger_and_marks_the_open_position():
    b = scenario()
    result = run(b)
    (tr,) = result["trades"]
    curve = result["curve"]
    fill = tr.fill_time
    entry_cost = -(tr.quantity * tr.entry_open * 0.0003 + tr.quantity * tr.entry_price * 0.0005)
    assert curve[fill] == 10000
    assert curve[fill + Q] == pytest.approx(10000 + entry_cost + tr.quantity * (97.9 - 97.9))
    assert curve.iloc[-1] == pytest.approx(result["final_cash"])
    assert result["final_cash"] == pytest.approx(10000 + sum(e["amount"] for e in result["ledger"]))


def test_f3_intrabar_exit_is_stamped_when_the_bar_closes():
    b = scenario()
    hit = SHOCK + 2 * H + 3 * Q
    b.loc[hit, "high"] = 100.2
    (tr,) = run(b)["trades"]
    assert tr.exit_reason == "TARGET" and tr.intrabar_estimated
    assert tr.exit_bar_open == hit and tr.exit_time == hit + Q
    gap = scenario()
    gap.loc[SHOCK + 2 * H + 2 * Q, ["open", "high", "low", "close"]] = (95.0, 95.5, 94.0, 95)
    (tr,) = run(gap)["trades"]
    assert tr.exit_time == SHOCK + 2 * H + 2 * Q and not tr.intrabar_estimated  # known at the open


def _cli():
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parent.parent / "scripts" / "reproduce_oi_reclaim.py"
    spec = importlib.util.spec_from_file_location("reproduce_oi_reclaim", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_f4_report_keeps_the_end_of_window_settlement():
    cli = _cli()
    bars, oi = late_in_day()
    bars = full_days(bars)
    cfg = dict(orc.DEFAULTS)
    s, result = cli.evaluate(bars, schedule(bars), oi, cfg, str(bars.index[0].date()), str(bars.index[-1].date()))
    assert result["trades"][0].exit_reason == "END_OF_WINDOW"
    assert s["status"] == "OK" and s["final_equity_usd"] == round(result["final_cash"], 2)
    assert s["final_equity_exact_usd"] - 10000 == pytest.approx(sum(t.net_pnl for t in result["trades"]))
    assert s["total_return_pct"] == round((result["final_cash"] / 10000 - 1) * 100, 2)


def test_f4_year_end_window_has_no_extra_year():
    cli = _cli()
    start = pd.Timestamp("2023-12-29", tz="UTC")
    bars = pd.DataFrame({"open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0},
                        index=pd.date_range(start, pd.Timestamp("2024-01-01", tz="UTC"), freq="15min", inclusive="left"))
    s, _ = cli.evaluate(bars, schedule(bars), pd.Series(1000.0, index=pd.date_range(start, pd.Timestamp("2024-01-01", tz="UTC"), freq="5min")),
                        dict(orc.DEFAULTS), "2023-12-29", "2023-12-31")
    assert list(s["yearly_return_pct"]) == [2023] and list(s["monthly"]["monthly_return_pct"]) == ["2023-12"]


def test_cli_reports_data_failures_without_scoring_them():
    cli = _cli()
    b = full_days(scenario())
    s, result = cli.evaluate(b.drop(SHOCK + 3 * H), schedule(b), oi_series(b), dict(orc.DEFAULTS),
                             str(b.index[0].date()), str(b.index[-1].date()))
    assert result is None and s["status"] == "DATA_QUALITY_FAILED" and not s["scored"]
    assert "total_return_pct" not in s and s["data_quality"]["missing_15m_bars"]["count"] == 1
    s, _ = cli.evaluate(b, schedule(b), oi_series(b).drop(SHOCK), dict(orc.DEFAULTS),
                        str(b.index[0].date()), str(b.index[-1].date()))
    assert s["status"] == "DATA_QUALITY_FAILED" and "total_return_pct" not in s and "diagnostic" in s
