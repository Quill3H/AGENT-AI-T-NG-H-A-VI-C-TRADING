from copy import deepcopy
from dataclasses import asdict
import pandas as pd
import pytest
from src.strategies.smc_liquidity_sweep import SMCLiquiditySweepStrategy
from src.features.smc_features import compute_smc_features
from src.research.synthetic import smc_frames, smc_config
from src.backtest.engine import BacktestEngine
from src.execution.order_models import OrderDirection, OrderStatus, ExitReason
from src.report.generator import ReportGenerator


def signals(frame, cfg):
    s = SMCLiquiditySweepStrategy(cfg)
    orders = []
    for i in range(len(frame)):
        req = s.on_candle_close(
            {"close_time": frame.index[i] + pd.Timedelta(minutes=5)},
            frame.iloc[: i + 1],
            type("B", (), {"positions": {}, "pending_orders": []})(),
        )
        if req:
            orders.append(req)
    return s, orders


@pytest.mark.parametrize("short", [False, True])
def test_long_short_completed_5m_1m_trade_with_partial_accounting(tmp_path, short):
    frame, fast = smc_frames(short)
    cfg = smc_config()
    s = SMCLiquiditySweepStrategy(cfg)
    engine = BacktestEngine(cfg, frame, fast, s)
    metrics = engine.run()
    broker = engine.broker
    assert metrics["benchmark_comparison"]["expected_min"] == 50
    assert metrics["bars_by_timeframe"]["1m"] == len(fast)
    assert metrics["orders_filled_count"] == 1
    assert len(broker.trade_history) == 3  # two partial realizations and remainder
    filled = [o for o in broker.order_history if o.status == OrderStatus.FILLED][0]
    assert filled.direction == (OrderDirection.SHORT if short else OrderDirection.LONG)
    assert filled.processed_at >= frame.index[7] + pd.Timedelta(minutes=5)
    trades = broker.trade_history
    assert [t.quantity / filled.filled_quantity for t in trades] == pytest.approx(
        [0.4, 0.3, 0.3]
    )
    assert sum(t.entry_fee for t in trades) == pytest.approx(filled.fee_usd)
    assert trades[0].exit_reason == trades[1].exit_reason == ExitReason.TAKE_PROFIT
    assert trades[-1].exit_reason == ExitReason.STOP_LOSS
    assert broker.wallet_balance == pytest.approx(
        10000 + sum(t.net_pnl for t in trades)
    )
    broker.verify_accounting_invariants()
    artifacts = ReportGenerator(tmp_path).generate_all(
        "smc_short" if short else "smc_long", cfg, metrics, broker
    )
    assert len(artifacts) == 6
    assert artifacts["trades.sqlite"].is_file()


def test_fvg_before_retest_has_no_fill_and_limit_expires():
    f, fast = smc_frames()
    cfg = smc_config()
    engine = BacktestEngine(
        cfg, f.iloc[:8], fast.iloc[:40], SMCLiquiditySweepStrategy(cfg)
    )
    metrics = engine.run()
    assert metrics["submitted_orders_count"] == 1
    assert metrics["orders_filled_count"] == 0
    assert engine.broker.order_history[0].status == OrderStatus.CANCELLED


def test_swing_confirmation_and_order_block_body_not_backdated():
    f, _ = smc_frames()
    e = compute_smc_features(f, 1)
    assert not e.iloc[1].swing_low_confirmed
    assert e.iloc[2].swing_low_confirmed
    assert pd.isna(e.iloc[5].order_block_low)
    assert e.iloc[6].order_block_low == 100
    assert e.iloc[6].order_block_high == 102  # body, not wick [96,103]


def test_order_block_confluence_changes_admission():
    f, _ = smc_frames()
    cfg = smc_config()
    cfg["smc"]["ob_max_distance_atr"] = 0
    _, blocked = signals(f.iloc[:8], cfg)
    assert blocked == []
    cfg["entry"]["require_order_block_confluence"] = False
    _, allowed = signals(f.iloc[:8], cfg)
    assert len(allowed) == 1
    assert not allowed[0].metadata["order_block_confluence"]


def test_future_perturbation_preserves_features_signals_orders_trades():
    f, fast = smc_frames()
    changed = f.copy()
    changed.iloc[10:, :4] *= 1.1
    pd.testing.assert_frame_equal(
        compute_smc_features(f, 1).iloc[:10], compute_smc_features(changed, 1).iloc[:10]
    )
    cfg = smc_config()
    _, a = signals(f.iloc[:10], cfg)
    _, b = signals(changed.iloc[:10], cfg)
    assert len(a) == 1 and [asdict(x) for x in a] == [asdict(x) for x in b]
    changed_fast = fast.copy()
    changed_fast.loc[f.index[10] :, ["open", "high", "low", "close"]] *= 1.1
    runs = []
    for signal, execution in ((f, fast), (changed, changed_fast)):
        engine = BacktestEngine(cfg, signal, execution, SMCLiquiditySweepStrategy(cfg))
        engine.run()
        runs.append(
            (
                [
                    asdict(o)
                    for o in engine.broker.order_history
                    if o.processed_at < f.index[10]
                ],
                [
                    asdict(t)
                    for t in engine.broker.trade_history
                    if t.exit_time < f.index[10]
                ],
            )
        )
    assert runs[0] == runs[1]


def test_setup_timeout_and_invalidation():
    f, _ = smc_frames()
    cfg = smc_config()
    cfg["smc"]["max_setup_age_bars"] = 1
    s, orders = signals(f.iloc[:8], cfg)
    assert not orders
    f.iloc[6, f.columns.get_loc("close")] = 95
    f.iloc[6, f.columns.get_loc("low")] = 94
    s, orders = signals(f.iloc[:7], smc_config())
    assert not orders and s.setup.phase == "IDLE"
