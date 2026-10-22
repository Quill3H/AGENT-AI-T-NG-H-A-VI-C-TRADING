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


def run(b, oi=None, funding=None, **cfg):
    oi = oi_series(b) if oi is None else oi
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
    short = scenario(hours=50)
    (tr,) = run(short)["trades"]
    assert tr.exit_reason == "END_OF_WINDOW" and tr.exit_time == short.index[-1] + Q


def test_future_bars_do_not_change_a_finished_trade():
    b = scenario(hours=100)
    first = run(b)["trades"][0]
    changed = b.copy()
    changed.loc[first.exit_time + H:, ["high", "low"]] = (150, 50)
    again = run(changed)["trades"][0]
    assert (again.fill_time, again.exit_time, again.net_pnl) == (first.fill_time, first.exit_time, first.net_pnl)


# ---------------------------------------------------------------- funding accounts
def funding_at(*events):
    return pd.DataFrame({"funding_rate": [r for _, r in events]}, index=pd.DatetimeIndex([t for t, _ in events]))


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
    b.loc[gap, ["open", "high", "low", "close"]] = (90.0, 90.5, 89.0, 90)  # about -8% of equity at 1x
    b.loc[gap + Q:, ["open", "high", "low", "close"]] = (97.9, 98.2, 97.7, 97.9)
    second = SHOCK + 20 * H  # A = 0.5 here; a 1.3 drop with no wick, then a reclaim hour
    put_hour(b, second, [(97.9, 98, 97.5, 97.5), (97.5, 97.5, 97.0, 97.0), (97.0, 97.0, 96.7, 96.7), (96.7, 96.7, 96.6, 96.6)])
    put_hour(b, second + H, [(96.6, 96.8, 96.6, 96.7), (96.7, 96.9, 96.65, 96.8), (96.8, 96.95, 96.75, 96.9), (96.9, 97.0, 96.85, 96.95)])
    b.loc[second + 2 * H:, ["open", "high", "low", "close"]] = (96.95, 97.1, 96.8, 96.95)
    oi = oi_series(b)
    oi[second + H] = 970.0
    result = run(b, oi, risk_pct=0.2, cooldown_hours=1)
    assert result["trades"][0].exit_reason == "STOP_GAP"
    assert outcome(result)[-1] == "REJECT_BREAKER_LOCK" and result["rejects"] == {"BREAKER_LOCK": 1}
    assert len(run(b, oi, risk_pct=0.2, cooldown_hours=1, lock_hours=1)["trades"]) == 2  # same event trades once the lock is over
