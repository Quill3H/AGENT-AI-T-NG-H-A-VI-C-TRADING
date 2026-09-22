from __future__ import annotations

import pytest

from src.backtest.engine import BacktestEngine
from src.research.synthetic import trend_config, trend_frames
from src.strategies.trend_following import TrendFollowingStrategy


@pytest.mark.parametrize("short", [False, True])
def test_trend_synthetic_workflow_completes_real_broker_lifecycle(short: bool) -> None:
    signal, execution = trend_frames(short=short)
    config = trend_config()
    engine = BacktestEngine(
        config,
        signal,
        execution,
        TrendFollowingStrategy(config),
    )

    metrics = engine.run(force_close=True)

    assert metrics["orders_filled_count"] == 1
    assert metrics["total_trades"] == 1
    assert metrics["accounting_invariants_verified"] is True
    trade = engine.broker.trade_history[0]
    assert trade.direction.value == ("SHORT" if short else "LONG")
    assert trade.initial_stop_loss_price is not None
    assert trade.initial_stop_loss_price > 0
    assert trade.entry_fee + trade.exit_fee > 0
