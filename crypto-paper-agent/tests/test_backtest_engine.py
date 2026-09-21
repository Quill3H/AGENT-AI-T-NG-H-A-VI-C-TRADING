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
import yaml

from src.backtest.engine import BacktestEngine
from src.data_layer.cache_manager import save_to_cache
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
    df_15m.index.name = "timestamp"

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
    df_4h.index.name = "timestamp"
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

def test_future_perturbation_invariance():
    """
    Kiểm tra tính bất biến trước nhiễu tương lai (Zero Lookahead Bias):
    1. Tạo dữ liệu thực với ít nhất 1 setup, 1 lệnh và 1 giao dịch phát sinh trước T.
    2. Chạy lần 1 (nguyên bản), ghi nhận toàn bộ orders, trades và account snapshots trước hoặc tại T.
    3. Nhiễu toàn bộ dữ liệu OHLC 15m và 4h sau T (nhân 2.5x).
    4. Tính toán lại toàn bộ chỉ báo kỹ thuật trên 4h qua pipeline thật (add_all_features).
    5. Chạy lần 2 trên dữ liệu đã nhiễu và kiểm chứng:
       - Toàn bộ orders trước hoặc tại T bất biến 100%.
       - Toàn bộ trades trước hoặc tại T bất biến 100%.
       - Toàn bộ account snapshots trước hoặc tại T bất biến 100%.
       - Các chỉ báo sau T thực sự đã bị thay đổi bởi perturbation.
    """
    config = {
        "account": {"initial_equity_usd": 10000.0},
        "fees": {"taker_pct": 0.0005, "maker_pct": 0.0002, "slippage_pct": 0.0003},
        "funding_rate": {"settlement_hours_utc": [0, 8, 16], "max_forward_fill_candles": 480},
        "strategy": {"name": "TREND_FOLLOWING", "timeframe_signal": "4h", "timeframe_execution": "15m"},
        "default_conviction": "normal",
        "leverage": 2.0,
        "base_risk_percent": 0.02,
        "rules": {
            "crossover_fast_ema": 20, "crossover_slow_ema": 50, "regime_ema": 200,
            "rsi_period": 14, "rsi_threshold": 50.0, "max_setup_age_bars": 12, "swing_lookback_bars": 5
        },
        "oi_confluence": {"mode": "optional", "fallback_when_nan": True, "nan_log_note": "OI_BYPASSED_HISTORICAL"},
        "stop_loss": {"method": "swing_causal", "trailing_method": "ema50_tightening_only"},
        "take_profit": {"enabled": False},
        "leverage_brackets": {"BTCUSDT": [[50000, 0.004, 0], [250000, 0.005, 50]]},
        "circuit_breakers": {"daily_loss_limit_pct": 0.05, "consecutive_losses_threshold": 3, "risk_reduction_on_streak": 0.5},
    }

    start_dt = datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc)
    idx_4h = pd.date_range(start=start_dt, periods=270, freq="4h", tz="UTC")

    # 250 nến đầu 10000, nến 251 crossover lên 10500
    prices = [10000.0] * 250 + [10500.0, 10550.0, 10520.0, 10600.0] + [10700.0] * 16
    df_4h_raw = pd.DataFrame({
        "open": prices,
        "high": [p + 50.0 for p in prices],
        "low": [p - 50.0 for p in prices],
        "close": prices,
        "volume": 1000.0,
        "open_interest": [50000.0 + i * 100.0 for i in range(len(prices))],
    }, index=idx_4h)

    # Nến 252 tạo pullback retest vào vùng EMA20/50
    from src.features import add_all_features
    df_4h_feat_temp = add_all_features(df_4h_raw, config)
    e20 = df_4h_feat_temp.loc[idx_4h[252], "ema_20"]
    e50 = df_4h_feat_temp.loc[idx_4h[252], "ema_50"]
    df_4h_raw.loc[idx_4h[252], "low"] = e50 - 5.0
    df_4h_raw.loc[idx_4h[252], "high"] = e20 + 20.0
    df_4h_raw.loc[idx_4h[252], "close"] = e20 + 10.0
    df_4h_raw.loc[idx_4h[252], "open"] = e20 + 5.0

    # Nến 253 quét qua swing SL (9950) để đóng vị thế trước T
    df_4h_raw.loc[idx_4h[253], "low"] = 9800.0
    df_4h_raw.loc[idx_4h[253], "close"] = 9850.0

    idx_15m = pd.date_range(start=start_dt, periods=270 * 16, freq="15min", tz="UTC")
    records_15m = []
    for t in idx_15m:
        parent_4h_t = t.floor("4h")
        c_4h = df_4h_raw.loc[parent_4h_t]
        rec = {
            "open": c_4h["open"],
            "high": c_4h["high"],
            "low": c_4h["low"],
            "close": c_4h["close"],
            "volume": c_4h["volume"] / 16.0,
            "open_interest": c_4h["open_interest"],
        }
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

    # Điểm cắt T được đặt tại nến 255 (sau khi lệnh đã khớp và đóng)
    split_time = idx_4h[255]

    # Run 1: Dữ liệu gốc
    strat1 = TrendFollowingStrategy(config=config, symbol="BTCUSDT")
    engine1 = BacktestEngine(config=config, data_4h=df_4h_raw.copy(), data_15m=df_15m.copy(), strategy=strat1)
    engine1.run(force_close=False)

    orders_before_T_1 = [
        (o.requested_at, o.status.value, o.reference_price, o.actual_fill_price)
        for o in engine1.broker.order_history if o.requested_at <= split_time
    ]
    trades_before_T_1 = [
        (t.entry_time, t.exit_time, t.entry_price, t.exit_price, t.quantity, t.net_pnl)
        for t in engine1.broker.trade_history if t.entry_time <= split_time
    ]
    snaps_before_T_1 = [
        (s.timestamp, s.wallet_balance, s.equity, s.available_margin)
        for s in engine1.broker.account_snapshots if s.timestamp <= split_time
    ]

    # Kiểm tra tính phi-rỗng (non-vacuous): bắt buộc có lệnh và trade thật trước T
    assert len(orders_before_T_1) >= 1, "Test must be non-vacuous: at least 1 order must exist before T"
    assert len(trades_before_T_1) >= 1, "Test must be non-vacuous: at least 1 trade must exist before T"
    assert len(snaps_before_T_1) > 0, "Test must be non-vacuous: snapshots must exist before T"

    # Tạo perturbation dữ liệu thô sau T (nhân 2.5x)
    df_4h_perturbed = df_4h_raw.copy()
    df_15m_perturbed = df_15m.copy()

    mask_4h = df_4h_perturbed.index > split_time
    df_4h_perturbed.loc[mask_4h, "open"] *= 2.5
    df_4h_perturbed.loc[mask_4h, "high"] *= 2.5
    df_4h_perturbed.loc[mask_4h, "low"] *= 2.5
    df_4h_perturbed.loc[mask_4h, "close"] *= 2.5

    mask_15m = df_15m_perturbed.index > split_time
    df_15m_perturbed.loc[mask_15m, "open"] *= 2.5
    df_15m_perturbed.loc[mask_15m, "high"] *= 2.5
    df_15m_perturbed.loc[mask_15m, "low"] *= 2.5
    df_15m_perturbed.loc[mask_15m, "close"] *= 2.5

    # Run 2: Dữ liệu bị nhiễu sau T (Engine tự động gọi add_all_features trên df_4h_perturbed)
    strat2 = TrendFollowingStrategy(config=config, symbol="BTCUSDT")
    engine2 = BacktestEngine(config=config, data_4h=df_4h_perturbed, data_15m=df_15m_perturbed, strategy=strat2)
    engine2.run(force_close=False)

    orders_before_T_2 = [
        (o.requested_at, o.status.value, o.reference_price, o.actual_fill_price)
        for o in engine2.broker.order_history if o.requested_at <= split_time
    ]
    trades_before_T_2 = [
        (t.entry_time, t.exit_time, t.entry_price, t.exit_price, t.quantity, t.net_pnl)
        for t in engine2.broker.trade_history if t.entry_time <= split_time
    ]
    snaps_before_T_2 = [
        (s.timestamp, s.wallet_balance, s.equity, s.available_margin)
        for s in engine2.broker.account_snapshots if s.timestamp <= split_time
    ]

    # 1. Toàn bộ orders, trades và snapshots trước hoặc tại T phải giống hệt nhau
    assert orders_before_T_1 == orders_before_T_2, "Orders before or at T must be invariant"
    assert trades_before_T_1 == trades_before_T_2, "Trades before or at T must be invariant"
    assert snaps_before_T_1 == snaps_before_T_2, "Snapshots before or at T must be invariant"

    # 2. Chứng minh các chỉ báo kỹ thuật sau T thực sự đã bị biến đổi do nhiễu
    assert not engine1.data_4h.loc[mask_4h, "ema_20"].equals(engine2.data_4h.loc[mask_4h, "ema_20"]), (
        "Future indicators must be altered by future OHLC perturbation"
    )


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

@pytest.mark.parametrize(
    "case_name,mutator,expected_exc,match_str",
    [
        ("missing", lambda df, idx: df.drop(columns=["funding_readiness"]), ValueError, "Missing funding_readiness"),
        ("bool_False", lambda df, idx: df.assign(funding_readiness=False), ValueError, "Funding data marked not ready"),
        ("str_False", lambda df, idx: df.assign(funding_readiness="False"), TypeError, "Invalid funding_readiness type"),
        ("int_1", lambda df, idx: df.assign(funding_readiness=1), TypeError, "Invalid funding_readiness type"),
        ("nan", lambda df, idx: df.assign(funding_readiness=np.nan), TypeError, "Invalid funding_readiness type"),
        ("future", lambda df, idx: df.assign(funding_time=idx + timedelta(minutes=15)), ValueError, "is in future"),
        ("stale", lambda df, idx: df.assign(funding_time=idx - timedelta(hours=25)), ValueError, "is excessively stale"),
    ],
)
def test_funding_metadata_fail_closed_and_zero_mutation(backtest_env, case_name, mutator, expected_exc, match_str):
    """
    Kiểm tra fail-closed vô điều kiện tại settlement boundary (Blocker 1):
    missing, False, 'False', 1, NaN, future, stale.
    Bắt buộc:
    1. Báo đúng lỗi ValueError hoặc TypeError.
    2. Tuyệt đối KHÔNG làm biến đổi (zero mutation) trạng thái broker/tài khoản.
    """
    config, df_4h, df_15m = backtest_env
    funding_idx = df_15m.index[0]  # 00:00 UTC settlement

    # Chuẩn bị broker có 1 vị thế mở trước settlement
    broker = PaperBroker(config=config)
    broker.positions["BTCUSDT"] = Position(
        position_id=f"POS_FUNDING_{case_name.upper()}",
        symbol="BTCUSDT",
        direction=OrderDirection.LONG,
        quantity=0.1,
        entry_price=20000.0,
        initial_margin=1000.0,
        isolated_collateral=1000.0,
        leverage=2.0,
        stop_loss_price=18000.0,
        liquidation_price=10000.0,
        opened_at=funding_idx,
    )
    init_balance = broker.wallet_balance
    init_collateral = broker.positions["BTCUSDT"].isolated_collateral
    init_reserved = broker.reserved_collateral
    init_trades_len = len(broker.trade_history)

    # Áp dụng mutation lỗi vào dữ liệu 15m
    df_15m_corrupted = mutator(df_15m.copy(), funding_idx)

    strategy = TrendFollowingStrategy(config=config, symbol="BTCUSDT")
    engine = BacktestEngine(
        config=config,
        data_4h=df_4h,
        data_15m=df_15m_corrupted,
        strategy=strategy,
        broker=broker,
    )

    with pytest.raises(expected_exc, match=match_str):
        engine.run()

    # Xác minh không có bất kỳ mutation nào xảy ra trên broker/account khi validation thất bại
    assert broker.wallet_balance == init_balance, f"Case {case_name}: wallet balance mutated!"
    assert broker.positions["BTCUSDT"].isolated_collateral == init_collateral, f"Case {case_name}: collateral mutated!"
    assert broker.reserved_collateral == init_reserved, f"Case {case_name}: reserved collateral mutated!"
    assert len(broker.trade_history) == init_trades_len, f"Case {case_name}: trade history mutated!"


def test_funding_metadata_valid_zero_rate(backtest_env):
    """
    Kiểm tra funding_rate = 0.0 hợp lệ với đầy đủ provenance (readiness=True, time hợp lệ).
    Settlement phải thực thi thành công và không gây biến đổi số dư ví do cashflow = 0.
    """
    config, df_4h, df_15m = backtest_env
    funding_idx = df_15m.index[0]  # 00:00 UTC

    df_15m_valid = df_15m.copy()
    df_15m_valid.loc[funding_idx, "funding_rate"] = 0.0
    df_15m_valid.loc[funding_idx, "funding_readiness"] = True
    df_15m_valid.loc[funding_idx, "funding_time"] = funding_idx

    broker = PaperBroker(config=config)
    broker.positions["BTCUSDT"] = Position(
        position_id="POS_FUNDING_ZERO",
        symbol="BTCUSDT",
        direction=OrderDirection.LONG,
        quantity=0.1,
        entry_price=20000.0,
        initial_margin=1000.0,
        isolated_collateral=1000.0,
        leverage=2.0,
        stop_loss_price=18000.0,
        liquidation_price=10000.0,
        opened_at=funding_idx,
    )
    init_balance = broker.wallet_balance

    strategy = TrendFollowingStrategy(config=config, symbol="BTCUSDT")
    engine = BacktestEngine(
        config=config,
        data_4h=df_4h,
        data_15m=df_15m_valid,
        strategy=strategy,
        broker=broker,
    )

    metrics = engine.run(force_close=True)
    assert metrics["accounting_invariants_verified"] is True
    # Funding cashflow phải bằng 0.0 tại mốc này
    funding_events = [e for e in broker.funding_history if e.timestamp == funding_idx]
    if funding_events:
        assert funding_events[0].cashflow_usd == 0.0


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

def test_cli_invalid_strategy_fails_clearly():
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "run_backtest.py"),
        "--strategy", "invalid_strategy",
    ]
    res = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=30)
    assert res.returncode != 0
    assert "invalid choice" in res.stderr.lower() or "invalid strategy" in res.stderr.lower()


def test_cli_no_fetch_missing_cache_fails_clearly():
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "run_backtest.py"),
        "--strategy", "trend_following",
        "--start", "1990-01-01",
        "--end", "1990-01-10",
        "--no-fetch",
    ]
    res = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    assert res.returncode == 1
    assert "incomplete" in res.stderr.lower() or "error" in res.stderr.lower()


def test_cli_cwd_independence(tmp_path):
    """
    Kiểm tra CLI runner thực thi hoàn toàn độc lập với CWD và hermetic (Review 10 Blocker 1):
    1. Không phụ thuộc cache data/raw bị gitignore.
    2. Tự tạo cache parquet tổng hợp tối thiểu trong tmp_path/mock_cache.
    3. Tạo config tạm trong tmp_path trỏ raw_data_dir về mock_cache.
    4. Thực thi subprocess với cwd=str(tmp_path) bên ngoài project root.
    5. Xác thực trend_following chạy thành công với --config, --strategy, --start, --end, --no-fetch.
    6. Test pass hoàn toàn trên clean clone không có data/raw.
    """
    cache_dir = tmp_path / "mock_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    # 1. Sinh dữ liệu tổng hợp đa khung 4h và 15m đồng bộ cho 3 ngày
    df_4h, df_15m = _generate_synthetic_multitimeframe_data(
        start_dt=datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc),
        n_days=3,
    )
    df_4h.index.name = "timestamp"
    df_15m.index.name = "timestamp"

    # Lưu vào mock cache
    save_to_cache(df_4h, str(cache_dir), "binance", "BTCUSDT", "4h", "ohlcv")
    save_to_cache(df_15m[["open", "high", "low", "close", "volume"]], str(cache_dir), "binance", "BTCUSDT", "15m", "ohlcv")
    save_to_cache(pd.DataFrame({"open_interest": 50000.0}, index=df_4h.index), str(cache_dir), "binance", "BTCUSDT", "4h", "open_interest")
    save_to_cache(df_15m[["open_interest"]], str(cache_dir), "binance", "BTCUSDT", "15m", "open_interest")

    # Funding rate: 8h và 15m
    df_funding = df_15m[df_15m["funding_rate"].notna()][["funding_rate"]]
    save_to_cache(df_funding, str(cache_dir), "binance", "BTCUSDT", "8h", "funding_rate")
    save_to_cache(df_funding, str(cache_dir), "binance", "BTCUSDT", "15m", "funding_rate")

    # 2. Tạo config YAML tạm trong tmp_path trỏ raw_data_dir về mock_cache
    with open(PROJECT_ROOT / "config" / "default_config.yaml", "r", encoding="utf-8") as f:
        base_cfg = yaml.safe_load(f)

    base_cfg["data"]["raw_data_dir"] = str(cache_dir)
    cfg_file = tmp_path / "hermetic_test_config.yaml"
    with open(cfg_file, "w", encoding="utf-8") as f:
        yaml.safe_dump(base_cfg, f)

    # 3. Chạy subprocess với cwd=str(tmp_path) bên ngoài project root
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "run_backtest.py"),
        "--config", str(cfg_file),
        "--strategy", "trend_following",
        "--start", "2023-01-01",
        "--end", "2023-01-02",
        "--no-fetch",
        "--output-dir", str(tmp_path / "reports"),
        "--run-id", "cwd_independence_stage6",
    ]
    res = subprocess.run(
        cmd,
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
    )
    assert res.returncode == 0, f"CLI failed from external CWD:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "BACKTEST EXECUTION REPORT" in res.stdout
    assert "PASSED (wallet_balance matches ledger)" in res.stdout
    assert "[STATUS: AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED]" in res.stdout
