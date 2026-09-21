from datetime import datetime, timedelta, timezone

import pandas as pd

from src.execution.order_models import OrderDirection
from src.strategies.breakout_retest import BreakoutRetestStrategy


def _history(values, volumes):
    start = datetime(2023, 1, 1, tzinfo=timezone.utc)
    idx = pd.date_range(start, periods=len(values), freq="4h", tz="UTC")
    return pd.DataFrame(
        {"open": values, "high": [v + 1 for v in values], "low": [v - 1 for v in values], "close": values, "volume": volumes},
        index=idx,
    )


def _cfg():
    return {"strategy": {"timeframe_signal": "4h", "timeframe_execution": "15m"}, "breakout": {"lookback_bars": 3, "volume_multiplier": 1.5, "retest_volume_max": 1.0, "rrr": 2.0}, "leverage": 2.0, "base_risk_percent": 0.02}


def test_breakout_waits_for_retest_and_builds_rrr_two_order():
    strategy = BreakoutRetestStrategy(_cfg())
    base = [100.0, 100.5, 100.2, 100.4]
    history = _history(base + [103.0], [10, 10, 10, 10, 20])
    candle = {**history.iloc[-1].to_dict(), "close_time": history.index[-1].to_pydatetime()}
    assert strategy.on_candle_close(candle, history, type("B", (), {"positions": {}, "pending_orders": []})()) is None
    assert strategy.setup.direction == OrderDirection.LONG
    retest = _history(base + [103.0, 102.0], [10, 10, 10, 10, 20, 5])
    candle = {**retest.iloc[-1].to_dict(), "close_time": retest.index[-1].to_pydatetime()}
    req = strategy.on_candle_close(candle, retest, type("B", (), {"positions": {}, "pending_orders": []})())
    assert req is not None
    assert req.direction == OrderDirection.LONG
    assert req.take_profit_price > req.signal_price
    assert req.metadata["rrr"] == 2.0


def test_long_breakout_fakeout_invalidation():
    strategy = BreakoutRetestStrategy(_cfg())
    history = _history([100, 100, 100, 100, 103], [10, 10, 10, 10, 20])
    candle = {**history.iloc[-1].to_dict(), "close_time": history.index[-1].to_pydatetime()}
    strategy.on_candle_close(candle, history, type("B", (), {"positions": {}, "pending_orders": []})())
    invalid = _history([100, 100, 100, 100, 103, 99], [10, 10, 10, 10, 20, 5])
    candle = {**invalid.iloc[-1].to_dict(), "close_time": invalid.index[-1].to_pydatetime()}
    assert strategy.on_candle_close(candle, invalid, type("B", (), {"positions": {}, "pending_orders": []})()) is None
    assert strategy.setup.direction is None

import pytest
from dataclasses import asdict


def _call(strategy, frame, broker=None):
    broker = broker or type('B', (), {'positions': {}, 'pending_orders': []})()
    return strategy.on_candle_close({'close_time': frame.index[-1].to_pydatetime()}, frame, broker)


@pytest.mark.parametrize('short', [False, True])
def test_real_long_short_retest_and_duplicate_event(short):
    prices = [100, 100, 100, 100, 103, 101.8]
    if short: prices = [200-p for p in prices]
    frame = _history(prices, [10,10,10,10,20,5])
    s = BreakoutRetestStrategy(_cfg())
    assert _call(s, frame.iloc[:-1]) is None
    age = s.setup.age
    assert _call(s, frame.iloc[:-1]) is None
    assert s.setup.age == age
    req = _call(s, frame)
    assert req is not None
    assert req.direction == (OrderDirection.SHORT if short else OrderDirection.LONG)
    assert abs(req.take_profit_price-req.signal_price) == pytest.approx(2*abs(req.signal_price-req.stop_loss_price))
    assert _call(s, frame) is None
    assert s.candidate_count == 1


def test_setup_timeout_high_volume_retest_and_pending_conflict():
    cfg = _cfg(); cfg['breakout']['max_setup_age_bars'] = 1
    s = BreakoutRetestStrategy(cfg)
    f = _history([100,100,100,100,103,101.8,101.8], [10,10,10,10,20,18,5])
    assert _call(s, f.iloc[:5]) is None
    assert _call(s, f.iloc[:6]) is None
    assert _call(s, f) is None
    assert s.setup.direction is None
    s = BreakoutRetestStrategy(_cfg())
    _call(s, f.iloc[:5])
    f.iloc[-1, f.columns.get_loc('volume')] = 5
    assert _call(s, f, type('B', (), {'positions': {}, 'pending_orders': [object()]})()) is None


def test_invalid_historical_volume_cannot_be_skipped_in_baseline():
    f = _history([100,100,100,100,103], [10,10,float('nan'),10,20])
    s = BreakoutRetestStrategy(_cfg())
    assert _call(s, f) is None
    assert s.setup_count == 0


def test_future_perturbation_preserves_orders():
    f = _history([100,100,100,100,103,101.8,110,120], [10,10,10,10,20,5,20,50])
    changed = f.copy(); changed.iloc[6:, :4] *= 2
    def orders(frame):
        s = BreakoutRetestStrategy(_cfg()); result=[]
        for i in range(1, 7):
            req = _call(s, frame.iloc[:i])
            if req: result.append(asdict(req))
        return result
    assert len(orders(f)) == 1
    assert orders(f) == orders(changed)
