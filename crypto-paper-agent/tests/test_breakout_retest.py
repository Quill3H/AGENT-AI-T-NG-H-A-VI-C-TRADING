from datetime import datetime, timedelta, timezone

import pandas as pd

from src.execution.order_models import OrderDirection
from src.strategies.breakout_retest import BreakoutRetestStrategy


def _history(values, volumes):
    start = datetime(2023, 1, 1, tzinfo=timezone.utc)
    idx = pd.date_range(start, periods=len(values), freq="4h", tz="UTC")
    return pd.DataFrame(
        {
            "open": values,
            "high": [v + 1 for v in values],
            "low": [v - 1 for v in values],
            "close": values,
            "volume": volumes,
        },
        index=idx,
    )


def _cfg():
    return {
        "strategy": {"timeframe_signal": "4h", "timeframe_execution": "15m"},
        "breakout": {
            "lookback_bars": 3,
            "volume_multiplier": 1.5,
            "retest_volume_max": 1.0,
            "rrr": 2.0,
        },
        "leverage": 2.0,
        "base_risk_percent": 0.02,
    }


def test_breakout_waits_for_retest_and_builds_rrr_two_order():
    strategy = BreakoutRetestStrategy(_cfg())
    base = [100.0, 100.5, 100.2, 100.4]
    history = _history(base + [103.0], [10, 10, 10, 10, 20])
    candle = {
        **history.iloc[-1].to_dict(),
        "close_time": history.index[-1].to_pydatetime(),
    }
    assert (
        strategy.on_candle_close(
            candle, history, type("B", (), {"positions": {}, "pending_orders": []})()
        )
        is None
    )
    assert strategy.setup.direction == OrderDirection.LONG
    retest = _history(base + [103.0, 102.0], [10, 10, 10, 10, 20, 5])
    candle = {
        **retest.iloc[-1].to_dict(),
        "close_time": retest.index[-1].to_pydatetime(),
    }
    req = strategy.on_candle_close(
        candle, retest, type("B", (), {"positions": {}, "pending_orders": []})()
    )
    assert req is not None
    assert req.direction == OrderDirection.LONG
    assert req.take_profit_price > req.signal_price
    assert req.metadata["rrr"] == 2.0


def test_long_breakout_fakeout_invalidation():
    strategy = BreakoutRetestStrategy(_cfg())
    history = _history([100, 100, 100, 100, 103], [10, 10, 10, 10, 20])
    candle = {
        **history.iloc[-1].to_dict(),
        "close_time": history.index[-1].to_pydatetime(),
    }
    strategy.on_candle_close(
        candle, history, type("B", (), {"positions": {}, "pending_orders": []})()
    )
    invalid = _history([100, 100, 100, 100, 103, 99], [10, 10, 10, 10, 20, 5])
    candle = {
        **invalid.iloc[-1].to_dict(),
        "close_time": invalid.index[-1].to_pydatetime(),
    }
    assert (
        strategy.on_candle_close(
            candle, invalid, type("B", (), {"positions": {}, "pending_orders": []})()
        )
        is None
    )
    assert strategy.setup.direction is None


import pytest
from dataclasses import asdict


def _call(strategy, frame, broker=None):
    broker = broker or type("B", (), {"positions": {}, "pending_orders": []})()
    return strategy.on_candle_close(
        {"close_time": frame.index[-1].to_pydatetime()}, frame, broker
    )


@pytest.mark.parametrize("short", [False, True])
def test_real_long_short_retest_and_duplicate_event(short):
    prices = [100, 100, 100, 100, 103, 101.8]
    if short:
        prices = [200 - p for p in prices]
    frame = _history(prices, [10, 10, 10, 10, 20, 5])
    s = BreakoutRetestStrategy(_cfg())
    assert _call(s, frame.iloc[:-1]) is None
    age = s.setup.age
    assert _call(s, frame.iloc[:-1]) is None
    assert s.setup.age == age
    req = _call(s, frame)
    assert req is not None
    assert req.direction == (OrderDirection.SHORT if short else OrderDirection.LONG)
    assert abs(req.take_profit_price - req.signal_price) == pytest.approx(
        2 * abs(req.signal_price - req.stop_loss_price)
    )
    assert _call(s, frame) is None
    assert s.candidate_count == 1


def test_setup_timeout_high_volume_retest_and_pending_conflict():
    cfg = _cfg()
    cfg["breakout"]["max_setup_age_bars"] = 1
    s = BreakoutRetestStrategy(cfg)
    f = _history([100, 100, 100, 100, 103, 101.8, 101.8], [10, 10, 10, 10, 20, 18, 5])
    assert _call(s, f.iloc[:5]) is None
    assert _call(s, f.iloc[:6]) is None
    assert _call(s, f) is None
    assert s.setup.direction is None
    s = BreakoutRetestStrategy(_cfg())
    _call(s, f.iloc[:5])
    f.iloc[-1, f.columns.get_loc("volume")] = 5
    assert (
        _call(s, f, type("B", (), {"positions": {}, "pending_orders": [object()]})())
        is None
    )


def test_invalid_historical_volume_cannot_be_skipped_in_baseline():
    f = _history([100, 100, 100, 100, 103], [10, 10, float("nan"), 10, 20])
    s = BreakoutRetestStrategy(_cfg())
    assert _call(s, f) is None
    assert s.setup_count == 0


def test_future_perturbation_preserves_orders():
    f = _history(
        [100, 100, 100, 100, 103, 101.8, 110, 120], [10, 10, 10, 10, 20, 5, 20, 50]
    )
    changed = f.copy()
    changed.iloc[6:, :4] *= 2

    def orders(frame):
        s = BreakoutRetestStrategy(_cfg())
        result = []
        for i in range(1, 7):
            req = _call(s, frame.iloc[:i])
            if req:
                result.append(asdict(req))
        return result

    assert len(orders(f)) == 1
    assert orders(f) == orders(changed)


@pytest.mark.parametrize("short", [False, True])
def test_breakout_broker_logger_report_nonempty_and_fill_risk(tmp_path, short):
    from src.execution.paper_broker import PaperBroker
    from src.execution.order_models import OrderStatus, ExitReason
    from src.report.generator import ReportGenerator
    from src.report.metrics import calculate_backtest_metrics

    f = _history([100, 100, 100, 100, 104, 102], [10, 10, 10, 10, 20, 5]).astype(float)
    f.iloc[-1, f.columns.get_loc("low")] = 98
    if short:
        high = f.high.copy()
        low = f.low.copy()
        for col in ("open", "close"):
            f[col] = 200 - f[col]
        f["high"] = 200 - low
        f["low"] = 200 - high
    cfg = _cfg()
    cfg["fees"] = {"taker_pct": 0.0005, "slippage_pct": 0.0003}
    cfg["strategy"]["name"] = "BREAKOUT_RETEST"
    strategy = BreakoutRetestStrategy(cfg)
    _call(strategy, f.iloc[:-1])
    req = _call(strategy, f)
    assert req is not None
    broker = PaperBroker(cfg)
    broker.submit_order(req)
    t = req.signal_time
    p = req.signal_price

    def candle(ts, o, h, l, c):
        return {
            "symbol": "BTCUSDT",
            "open_time": ts,
            "close_time": ts + timedelta(minutes=1),
            "timeframe": "1m",
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "volume": 1.0,
        }

    broker.process_candle(candle(t, p, p + 0.1, p - 0.1, p))
    assert broker.order_history[-1].status == OrderStatus.FILLED
    pos = broker.positions["BTCUSDT"]
    assert pos.quantity * abs(pos.entry_price - pos.stop_loss_price) <= 200 + 1e-5
    assert (
        pos.take_profit_price == req.take_profit_price
    )  # broker contract preserves absolute TP, validates after fill
    target = req.take_profit_price
    broker.process_candle(
        candle(
            t + timedelta(minutes=1),
            p,
            max(p, target) + 0.1,
            min(p, target) - 0.1,
            target,
        )
    )
    broker.finalize(t + timedelta(minutes=2), force_close=True)
    assert len(broker.trade_history) == 1
    assert broker.trade_history[0].exit_reason == ExitReason.TAKE_PROFIT
    metrics = calculate_backtest_metrics(
        broker, cfg, t, t + timedelta(minutes=2), 2, 6, submitted_orders_count=1
    )
    artifacts = ReportGenerator(tmp_path).generate_all("breakout", cfg, metrics, broker)
    assert len(artifacts) == 6 and artifacts["trades.sqlite"].is_file()


@pytest.mark.parametrize("failure", ["risk", "margin", "conflict"])
def test_breakout_request_rejected_by_shared_gate(failure):
    from src.execution.paper_broker import PaperBroker
    from src.execution.order_models import OrderStatus

    f = _history([100, 100, 100, 100, 103, 101.8], [10, 10, 10, 10, 20, 5])
    strategy = BreakoutRetestStrategy(_cfg())
    _call(strategy, f.iloc[:-1])
    req = _call(strategy, f)
    assert req
    if failure == "risk":
        req.base_risk_percent = 0.1
    if failure == "margin":
        req.leverage = 1.0
    if failure == "conflict":
        req.requested_quantity = 1
    broker = PaperBroker(_cfg())
    broker.submit_order(req)
    t = req.signal_time
    p = req.signal_price
    broker.process_candle(
        {
            "symbol": "BTCUSDT",
            "open_time": t,
            "close_time": t + timedelta(minutes=1),
            "timeframe": "1m",
            "open": p,
            "high": p + 0.1,
            "low": p - 0.1,
            "close": p,
            "volume": 1.0,
        }
    )
    if failure == "conflict":
        assert broker.positions
        record = broker.submit_order(req)
        assert record.status == OrderStatus.REJECTED
    else:
        assert broker.order_history[-1].status == OrderStatus.REJECTED
        assert not broker.positions
