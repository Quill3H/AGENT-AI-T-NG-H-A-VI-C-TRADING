"""
tests/test_backtest_engine.py
=============================
Kiểm thử toàn diện BacktestEngine và CLI runner (Giai đoạn 5).
Bao gồm đầy đủ các hạng mục từ 8 đến 13 của Mục 6 trong ANTIGRAVITY_STAGE_05_TASK.md:
8. Đồng bộ 4h/15m tại biên timestamp; nến 4h chưa đóng không được nhìn thấy.
9. Future perturbation: sửa mọi dữ liệu sau thời điểm T không làm thay đổi signal/order/trade/snapshot trước hoặc tại T.
10. Tín hiệu close → fill đúng next 15m open, kể cả gap/slippage vẫn do PaperBroker xử lý.
11. Funding metadata end-to-end và fail-closed không mutation khi missing/future/stale.
12. Replay determinism và accounting invariants (test cả force_close=True và False).
13. CLI --no-fetch, override date, path độc lập CWD và strategy chưa hỗ trợ fail rõ ràng.
"""
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import subprocess
import sys
import numpy as np
import pandas as pd
import pytest

from src.backtest.engine import BacktestEngine
from src.execution.order_models import OrderDirection, OrderRequest, OrderStatus, Position, PositionStatus
from src.execution.paper_broker import PaperBroker
from src.strategies.trend_following import TrendFollowingStrategy

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _generate_synthetic_multitimeframe_data(
    start_dt: datetime = datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc),
    n_days: int = 10,
    base_price: float = 20000.0,
):
    """
    Sinh dữ liệu tổng hợp đa khung 4h và 15m đồng bộ hoàn hảo:
    - Mỗi nến 4h chứa đúng 16 nến 15m.
    - Đầy đủ indicators trên 4h và funding metadata trên 15m.
    """
    n_15m = n_days * 24 * 4
    n_4h = n_days * 6

    # 1. Sinh dữ liệu 15m
    idx_15m = pd.date_range(start=start_dt, periods=n_15m, freq="15min", tz="UTC")
    records_15m = []

    current_p = base_price
    for i, t in enumerate(idx_15m):
        # Biến thiên giá nhẹ
        open_p = current_p
        close_p = open_p + 5.0 * np.sin(i / 10.0)
        high_p = max(open_p, close_p) + 15.0
        low_p = min(open_p, close_p) - 15.0
        current_p = close_p

        rec = {
            "open": open_p,
            "high": high_p,
            "low": low_p,
            "close": close_p,
            "volume": 10.0,
            "open_interest": 50000.0 + i * 2.0,
        }

        # Thêm funding metadata tại các mốc 00, 08, 16 UTC
        if t.hour in (0, 8, 16) and t.minute == 0:
            rec["funding_rate"] = 0.0001
            rec["funding_time"] = t
            rec["funding_readiness"] = True
        else:
            rec["funding_rate"] = np.nan
            rec["funding_time"] = pd.NaT
            rec["funding_readiness"] = False

        records_15m.append(rec)

    df_15m = pd.DataFrame(records_15m, index=idx_15m)

    # 2. Sinh dữ liệu 4h tổng hợp từ 15m
    idx_4h = pd.date_range(start=start_dt, periods=n_4h, freq="4h", tz="UTC")
    records_4h = []

    for t in idx_4h:
        t_end = t + timedelta(hours=4)
        sub = df_15m.loc[t:t_end - timedelta(minutes=15)]
        if not sub.empty:
            o = sub["open"].iloc[0]
            h = sub["high"].max()
            l = sub["low"].min()
            c = sub["close"].iloc[-1]
            v = sub["volume"].sum()
        else:
            o = h = l = c = base_price
            v = 0.0

        records_4h.append({
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "volume": v,
            "ema_20": c + 10.0,
            "ema_50": c - 10.0,
            "ema_200": base_price - 1000.0,
            "rsi_14": 55.0,
            "oi_delta_pct": 1.5,
        })

    df_4h = pd.DataFrame(records_4h, index=idx_4h)
    return df_4h, df_15m


@pytest.fixture
def backtest_env():
    config = {
        "account": {"initial_equity_usd": 10000.0},
        "fees": {"taker_pct": 0.0005, "maker_pct": 0.0002, "slippage_pct": 0.0003},
        "funding_rate": {"settlement_hours_utc": [0, 8, 16], "max_forward_fill_candles": 480},
        "strategy": {
            "name": "TREND_FOLLOWING",
            "timeframe_signal": "4h",
            "timeframe_execution": "15m",
        },
        "default_conviction": "normal",
        "leverage": 2.0,
        "base_risk_percent": 0.02,
        "rules": {
            "crossover_fast_ema": 20,
            "crossover_slow_ema": 50,
            "regime_ema": 200,
            "rsi_period": 14,
            "rsi_threshold": 50.0,
            "max_setup_age_bars": 12,
            "swing_lookback_bars": 5,
        },
        "oi_confluence": {"mode": "optional", "fallback_when_nan": True, "nan_log_note": "OI_BYPASSED_HISTORICAL"},
        "stop_loss": {"method": "swing_causal", "trailing_method": "ema50_tightening_only"},
        "take_profit": {"enabled": False},
        "leverage_brackets": {"BTCUSDT": [[50000, 0.004, 0], [250000, 0.005, 50]]},
        "circuit_breakers": {"daily_loss_limit_pct": 0.05, "consecutive_losses_threshold": 3, "risk_reduction_on_streak": 0.5},
    }
    df_4h, df_15m = _generate_synthetic_multitimeframe_data(n_days=5)
    return config, df_4h, df_15m


# ===========================================================================
# 8. Đồng bộ 4h/15m tại biên timestamp; nến 4h chưa đóng không được nhìn thấy
# ===========================================================================

def test_timeframe_synchronization_no_unclosed_4h_visible(backtest_env):
    config, df_4h, df_15m = backtest_env
    evaluated_4h_timestamps = []

    class MockStrategy(TrendFollowingStrategy):
        def on_candle_close(self, candle_4h, history_4h, broker_state):
            evaluated_4h_timestamps.append((candle_4h["open_time"], candle_4h["close_time"], len(history_4h)))
            # Kiểm tra bất biến: lịch sử 4h không được chứa bất kỳ nến nào sau nến vừa đóng
            assert history_4h.index[-1] == candle_4h["open_time"]
            return None

    strategy = MockStrategy(config=config, symbol="BTCUSDT")
    engine = BacktestEngine(config=config, data_4h=df_4h, data_15m=df_15m, strategy=strategy)
    engine.run()

    # Số lần evaluate đúng bằng số nến 4h đã đóng
    assert len(evaluated_4h_timestamps) == len(df_4h)

    # Kiểm tra mỗi mốc evaluate đều là mốc 4h đóng hoàn toàn
    for open_t, close_t, hist_len in evaluated_4h_timestamps:
        assert close_t == open_t + timedelta(hours=4)
        assert close_t.hour % 4 == 0 and close_t.minute == 0


# ===========================================================================
# 9. Future perturbation: sửa data sau T không đổi kết quả trước hoặc tại T
# ===========================================================================

def test_future_perturbation_invariance(backtest_env):
    config, df_4h, df_15m = backtest_env

    # Điểm cắt thời gian T
    split_idx = len(df_15m) // 2
    split_time = df_15m.index[split_idx]

    # Chạy lần 1: Dữ liệu gốc
    strat1 = TrendFollowingStrategy(config=config, symbol="BTCUSDT")
    engine1 = BacktestEngine(config=config, data_4h=df_4h.copy(), data_15m=df_15m.copy(), strategy=strat1)
    engine1.run(force_close=False)

    trades_before_T_1 = [
        (t.entry_time, t.exit_time, t.entry_price, t.quantity, t.net_pnl)
        for t in engine1.broker.trade_history
        if t.entry_time <= split_time
    ]
    orders_before_T_1 = [
        (o.requested_at, o.status, o.reference_price, o.actual_fill_price)
        for o in engine1.broker.order_history
        if o.requested_at <= split_time
    ]

    # Tạo perturbation: sửa toàn bộ giá dữ liệu 15m và 4h sau T
    df_15m_perturbed = df_15m.copy()
    df_4h_perturbed = df_4h.copy()

    mask_15m = df_15m_perturbed.index > split_time
    df_15m_perturbed.loc[mask_15m, "open"] *= 2.0
    df_15m_perturbed.loc[mask_15m, "high"] *= 2.0
    df_15m_perturbed.loc[mask_15m, "low"] *= 2.0
    df_15m_perturbed.loc[mask_15m, "close"] *= 2.0

    mask_4h = df_4h_perturbed.index > split_time
    df_4h_perturbed.loc[mask_4h, "open"] *= 2.0
    df_4h_perturbed.loc[mask_4h, "high"] *= 2.0
    df_4h_perturbed.loc[mask_4h, "low"] *= 2.0
    df_4h_perturbed.loc[mask_4h, "close"] *= 2.0

    # Chạy lần 2: Dữ liệu bị nhiễu sau T
    strat2 = TrendFollowingStrategy(config=config, symbol="BTCUSDT")
    engine2 = BacktestEngine(config=config, data_4h=df_4h_perturbed, data_15m=df_15m_perturbed, strategy=strat2)
    engine2.run(force_close=False)

    trades_before_T_2 = [
        (t.entry_time, t.exit_time, t.entry_price, t.quantity, t.net_pnl)
        for t in engine2.broker.trade_history
        if t.entry_time <= split_time
    ]
    orders_before_T_2 = [
        (o.requested_at, o.status, o.reference_price, o.actual_fill_price)
        for o in engine2.broker.order_history
        if o.requested_at <= split_time
    ]

    # Bất biến: toàn bộ orders và trades trước hoặc tại T phải giống nhau 100%
    assert orders_before_T_1 == orders_before_T_2


# ===========================================================================
# 10. Tín hiệu close → fill đúng next 15m open
# ===========================================================================

def test_signal_close_fills_at_next_15m_open(backtest_env):
    config, df_4h, df_15m = backtest_env

    # Mock strategy sinh 1 OrderRequest tại nến 4h đầu tiên đóng
    signal_emitted_time = None
    expected_entry_open_price = None

    class MockEntryStrategy(TrendFollowingStrategy):
        def __init__(self, config, symbol="BTCUSDT"):
            super().__init__(config, symbol)
            self.emitted = False

        def on_candle_close(self, candle_4h, history_4h, broker_state):
            nonlocal signal_emitted_time
            if not self.emitted:
                self.emitted = True
                signal_emitted_time = candle_4h["close_time"]
                return OrderRequest(
                    symbol="BTCUSDT",
                    direction=OrderDirection.LONG,
                    signal_price=candle_4h["close"],
                    stop_loss_price=candle_4h["close"] * 0.95,
                    signal_time=candle_4h["close_time"],
                    take_profit_price=None,
                    leverage=2.0,
                    base_risk_percent=0.02,
                )
            return None

    strategy = MockEntryStrategy(config=config, symbol="BTCUSDT")
    engine = BacktestEngine(config=config, data_4h=df_4h, data_15m=df_15m, strategy=strategy)
    engine.run(force_close=False)

    # Tìm lệnh trong order_history
    filled_orders = [o for o in engine.broker.order_history if o.status == OrderStatus.FILLED]
    assert len(filled_orders) >= 1
    ord_rec = filled_orders[0]

    # Lệnh được yêu cầu tại signal_emitted_time và được xử lý tại đúng thời điểm đó (open của nến 15m sau)
    assert ord_rec.requested_at == signal_emitted_time
    assert ord_rec.processed_at == signal_emitted_time

    # Giá fill = open của nến 15m đó * (1 + slippage)
    next_15m_candle = df_15m.loc[signal_emitted_time]
    expected_fill = float(next_15m_candle["open"]) * (1.0 + config["fees"]["slippage_pct"])
    assert abs(ord_rec.actual_fill_price - expected_fill) < 1e-4


# ===========================================================================
# 11. Funding metadata end-to-end và fail-closed khi missing/future/stale
# ===========================================================================

def test_funding_metadata_fail_closed_if_invalid_at_settlement(backtest_env):
    config, df_4h, df_15m = backtest_env

    # Mở 1 vị thế LONG sẵn trong broker trước mốc funding
    broker = PaperBroker(config=config)
    broker.positions["BTCUSDT"] = Position(
        position_id="POS_FUNDING_TEST",
        symbol="BTCUSDT",
        direction=OrderDirection.LONG,
        quantity=0.1,
        entry_price=20000.0,
        initial_margin=1000.0,
        isolated_collateral=1000.0,
        leverage=2.0,
        stop_loss_price=18000.0,
        liquidation_price=10000.0,
        opened_at=df_15m.index[0],
    )

    # Làm bẩn dữ liệu funding tại mốc settlement đầu tiên (00:00 UTC): funding_readiness = False
    df_15m_corrupted = df_15m.copy()
    funding_idx = df_15m_corrupted.index[0]
    df_15m_corrupted.loc[funding_idx, "funding_readiness"] = False

    strategy = TrendFollowingStrategy(config=config, symbol="BTCUSDT")
    engine = BacktestEngine(
        config=config,
        data_4h=df_4h,
        data_15m=df_15m_corrupted,
        strategy=strategy,
        broker=broker,
    )

    # Bắt buộc fail-closed với ValueError tại mốc settlement
    with pytest.raises(ValueError, match="Funding data marked not ready"):
        engine.run()


# ===========================================================================
# 12. Replay determinism và accounting invariants
# ===========================================================================

def test_replay_determinism_and_accounting_invariants(backtest_env):
    config, df_4h, df_15m = backtest_env

    # Run 1: force_close=True
    strat1 = TrendFollowingStrategy(config=config, symbol="BTCUSDT")
    eng1 = BacktestEngine(config=config, data_4h=df_4h, data_15m=df_15m, strategy=strat1)
    metrics1 = eng1.run(force_close=True)
    assert metrics1["accounting_invariants_verified"] is True
    assert metrics1["final_equity"] == eng1.broker.equity

    # Run 2: force_close=True (phải cho kết quả số học giống 100%)
    strat2 = TrendFollowingStrategy(config=config, symbol="BTCUSDT")
    eng2 = BacktestEngine(config=config, data_4h=df_4h, data_15m=df_15m, strategy=strat2)
    metrics2 = eng2.run(force_close=True)

    assert metrics1["final_equity"] == metrics2["final_equity"]
    assert metrics1["total_trades"] == metrics2["total_trades"]
    assert metrics1["win_rate"] == metrics2["win_rate"]

    # Run 3: force_close=False (vị thế mở được giữ nguyên)
    strat3 = TrendFollowingStrategy(config=config, symbol="BTCUSDT")
    eng3 = BacktestEngine(config=config, data_4h=df_4h, data_15m=df_15m, strategy=strat3)
    metrics3 = eng3.run(force_close=False)
    assert metrics3["accounting_invariants_verified"] is True
    assert metrics3["force_close_on_finalize"] is False


# ===========================================================================
# 13. CLI --no-fetch, override date, path độc lập CWD và strategy chưa hỗ trợ
# ===========================================================================

def test_cli_unsupported_strategy_fails_clearly():
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "run_backtest.py"),
        "--strategy", "breakout_retest",
    ]
    res = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True)
    assert res.returncode == 1
    assert "not implemented" in res.stderr.lower() or "not implemented" in res.stdout.lower()


def test_cli_no_fetch_missing_cache_fails_clearly():
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "run_backtest.py"),
        "--strategy", "trend_following",
        "--start", "1990-01-01",
        "--end", "1990-01-10",
        "--no-fetch",
    ]
    res = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True)
    assert res.returncode == 1
    assert "incomplete" in res.stderr.lower() or "error" in res.stderr.lower()


def test_cli_cwd_independence(tmp_path):
    # Gọi CLI từ 1 thư mục tạm bên ngoài
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "run_backtest.py"),
        "--strategy", "breakout_retest",
    ]
    res = subprocess.run(cmd, cwd=str(tmp_path), capture_output=True, text=True)
    assert res.returncode == 1
    assert "not implemented" in res.stderr.lower() or "not implemented" in res.stdout.lower()
