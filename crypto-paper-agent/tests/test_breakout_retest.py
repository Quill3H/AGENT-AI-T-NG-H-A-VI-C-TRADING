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


def test_breakout_fakeout_invalidation_and_short_symmetry():
    strategy = BreakoutRetestStrategy(_cfg())
    history = _history([100, 100, 100, 100, 103], [10, 10, 10, 10, 20])
    candle = {**history.iloc[-1].to_dict(), "close_time": history.index[-1].to_pydatetime()}
    strategy.on_candle_close(candle, history, type("B", (), {"positions": {}, "pending_orders": []})())
    invalid = _history([100, 100, 100, 100, 103, 99], [10, 10, 10, 10, 20, 5])
    candle = {**invalid.iloc[-1].to_dict(), "close_time": invalid.index[-1].to_pydatetime()}
    assert strategy.on_candle_close(candle, invalid, type("B", (), {"positions": {}, "pending_orders": []})()) is None
    assert strategy.setup.direction is None
