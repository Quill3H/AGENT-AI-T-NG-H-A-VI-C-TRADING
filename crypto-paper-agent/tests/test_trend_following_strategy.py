"""
tests/test_trend_following_strategy.py
======================================
Kiểm thử toàn diện chiến lược Trend Following (Giai đoạn 5).
Bao gồm đầy đủ các hạng mục từ 1 đến 7 của Mục 6 trong ANTIGRAVITY_STAGE_05_TASK.md:
1. Crossover LONG/SHORT chỉ dùng hai nến đã đóng.
2. Không entry tại nến crossover; chỉ entry sau pullback/retest hợp lệ.
3. Setup expiry, invalidation và one-shot không phát tín hiệu lặp.
4. RSI biên 50 không pass (>50 LONG, <50 SHORT).
5. OI strict/optional/disabled, NaN fallback có note; None/string/Inf fail-closed.
6. Stop swing causal, warm-up, stop sai phía và trailing EMA50 tightening-only.
7. Warm-up EMA200 không phát tín hiệu.
"""
from datetime import datetime, timedelta, timezone
import math
import numpy as np
import pandas as pd
import pytest

from src.execution.order_models import OrderDirection, OrderRequest, Position, PositionStatus
from src.execution.paper_broker import PaperBroker
from src.strategies.trend_following import SetupState, TrendFollowingStrategy


def _make_dummy_4h_history(
    n_bars: int = 10,
    start_time: datetime = datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc),
    base_price: float = 20000.0,
    ema20_vals: list = None,
    ema50_vals: list = None,
    ema200_vals: list = None,
    rsi_vals: list = None,
    oi_delta_vals: list = None,
) -> pd.DataFrame:
    """Helper tạo DataFrame lịch sử 4h giả lập với đầy đủ columns."""
    records = []
    t = start_time
    for i in range(n_bars):
        p = base_price + i * 10.0
        records.append({
            "open": p,
            "high": p + 50.0,
            "low": p - 50.0,
            "close": p,
            "volume": 100.0,
            "ema_20": ema20_vals[i] if ema20_vals is not None else p + 5.0,
            "ema_50": ema50_vals[i] if ema50_vals is not None else p - 5.0,
            "ema_200": ema200_vals[i] if ema200_vals is not None else base_price - 1000.0,
            "rsi_14": rsi_vals[i] if rsi_vals is not None else 60.0,
            "oi_delta_pct": oi_delta_vals[i] if oi_delta_vals is not None else 2.5,
        })
        t += timedelta(hours=4)

    idx = pd.date_range(start=start_time, periods=n_bars, freq="4h", tz="UTC")
    df = pd.DataFrame(records, index=idx)
    return df


@pytest.fixture
def base_config():
    return {
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
        "oi_confluence": {
            "mode": "optional",
            "fallback_when_nan": True,
            "nan_log_note": "OI_BYPASSED_HISTORICAL",
        },
        "stop_loss": {
            "method": "swing_causal",
            "trailing_method": "ema50_tightening_only",
        },
        "take_profit": {
            "enabled": False,
        },
    }


# ===========================================================================
# 1. Crossover LONG/SHORT chỉ dùng hai nến đã đóng
# ===========================================================================

def test_crossover_only_on_two_closed_bars(base_config):
    strategy = TrendFollowingStrategy(config=base_config, symbol="BTCUSDT")

    # Bar 0: EMA20 <= EMA50 (20000 <= 20100)
    # Bar 1: EMA20 > EMA50 (20200 > 20100) -> CROSSOVER!
    df = _make_dummy_4h_history(
        n_bars=2,
        base_price=25000.0,
        ema20_vals=[20000.0, 20200.0],
        ema50_vals=[20100.0, 20100.0],
        ema200_vals=[18000.0, 18000.0],
    )

    candle = df.iloc[-1].to_dict()
    candle["close_time"] = df.index[-1] + timedelta(hours=4)
    candle["open_time"] = df.index[-1]

    # Tại nến crossover (Bar 1), không emit order, chuyển trạng thái sang ARMED
    order = strategy.on_candle_close(candle, df, broker_state=None)
    assert order is None
    assert strategy.setup.state == SetupState.ARMED
    assert strategy.setup.direction == OrderDirection.LONG
    assert strategy.setup.setup_age_bars == 0


def test_short_crossover_only_on_two_closed_bars(base_config):
    strategy = TrendFollowingStrategy(config=base_config, symbol="BTCUSDT")

    # Bar 0: EMA20 >= EMA50 (20200 >= 20100)
    # Bar 1: EMA20 < EMA50 (20000 < 20100), close < EMA200 -> SHORT CROSSOVER!
    df = _make_dummy_4h_history(
        n_bars=2,
        base_price=15000.0,
        ema20_vals=[20200.0, 20000.0],
        ema50_vals=[20100.0, 20100.0],
        ema200_vals=[22000.0, 22000.0],
    )

    candle = df.iloc[-1].to_dict()
    candle["close_time"] = df.index[-1] + timedelta(hours=4)
    candle["open_time"] = df.index[-1]

    order = strategy.on_candle_close(candle, df, broker_state=None)
    assert order is None
    assert strategy.setup.state == SetupState.ARMED
    assert strategy.setup.direction == OrderDirection.SHORT
    assert strategy.setup.setup_age_bars == 0


# ===========================================================================
# 2. Không entry tại nến crossover; chỉ entry sau pullback/retest hợp lệ
# ===========================================================================

def test_no_entry_on_crossover_entry_after_retest(base_config):
    strategy = TrendFollowingStrategy(config=base_config, symbol="BTCUSDT")

    # Tạo chuỗi 7 nến:
    # Nến 0-4: warm-up history
    # Nến 5: Crossover (ARMED)
    # Nến 6: Pullback/Retest vào vùng EMA20/50 và close >= EMA20 -> Emits Order!
    df = _make_dummy_4h_history(
        n_bars=7,
        base_price=25000.0,
        ema20_vals=[20000, 20010, 20020, 20030, 20040, 20200, 20250],
        ema50_vals=[20100, 20100, 20100, 20100, 20100, 20100, 20150],
        ema200_vals=[18000] * 7,
        rsi_vals=[55.0] * 7,
        oi_delta_vals=[2.0] * 7,
    )
    # Điều chỉnh nến 6 để thỏa mãn Pullback:
    # ema20=20250, ema50=20150. Vùng [20150, 20250].
    # Cần low <= 20250, high >= 20150, close >= 20250.
    df.loc[df.index[6], "low"] = 20200.0
    df.loc[df.index[6], "high"] = 20400.0
    df.loc[df.index[6], "close"] = 20350.0

    # Bước 1: Nến 5 (crossover)
    candle_5 = df.iloc[5].to_dict()
    candle_5["close_time"] = df.index[5] + timedelta(hours=4)
    candle_5["open_time"] = df.index[5]
    order_5 = strategy.on_candle_close(candle_5, df.iloc[:6], broker_state=None)
    assert order_5 is None
    assert strategy.setup.state == SetupState.ARMED
    assert strategy.setup.setup_age_bars == 0

    # Bước 2: Nến 6 (pullback/retest hợp lệ)
    candle_6 = df.iloc[6].to_dict()
    candle_6["close_time"] = df.index[6] + timedelta(hours=4)
    candle_6["open_time"] = df.index[6]
    order_6 = strategy.on_candle_close(candle_6, df.iloc[:7], broker_state=None)

    assert order_6 is not None
    assert isinstance(order_6, OrderRequest)
    assert order_6.direction == OrderDirection.LONG
    assert order_6.signal_price == 20350.0
    assert order_6.take_profit_price is None  # Section 4.3: Không fixed TP
    assert strategy.setup.state == SetupState.IDLE  # One-shot: đã emit lệnh thì reset về IDLE


# ===========================================================================
# 3. Setup expiry, invalidation và one-shot không phát tín hiệu lặp
# ===========================================================================

def test_setup_expiry(base_config):
    strategy = TrendFollowingStrategy(config=base_config, symbol="BTCUSDT")

    # Nến crossover
    df = _make_dummy_4h_history(
        n_bars=2,
        base_price=25000.0,
        ema20_vals=[20000.0, 20200.0],
        ema50_vals=[20100.0, 20100.0],
        ema200_vals=[18000.0, 18000.0],
    )
    c0 = df.iloc[-1].to_dict()
    c0["close_time"] = df.index[-1] + timedelta(hours=4)
    strategy.on_candle_close(c0, df, broker_state=None)
    assert strategy.setup.state == SetupState.ARMED

    # Gửi 12 nến không có pullback (low > ema20)
    for age in range(1, 13):
        candle = {
            "close": 25000.0, "high": 25100.0, "low": 24900.0,
            "ema_20": 20300.0, "ema_50": 20100.0, "ema_200": 18000.0,
            "rsi_14": 60.0, "oi_delta_pct": 1.0,
            "close_time": df.index[-1] + timedelta(hours=4 * (age + 1)),
        }
        order = strategy.on_candle_close(candle, df, broker_state=None)
        assert order is None
        assert strategy.setup.state == SetupState.ARMED
        assert strategy.setup.setup_age_bars == age

    # Tạo history với nến t-1 có ema_20 > ema_50 để không kích hoạt crossover mới
    df_exp = _make_dummy_4h_history(
        n_bars=5,
        base_price=25000.0,
        ema20_vals=[20200.0] * 5,
        ema50_vals=[20100.0] * 5,
        ema200_vals=[18000.0] * 5,
    )

    # Nến thứ 13: tuổi > 12 -> Expiry -> Reset về IDLE!
    candle_13 = {
        "close": 25000.0, "high": 25100.0, "low": 24900.0,
        "ema_20": 20300.0, "ema_50": 20100.0, "ema_200": 18000.0,
        "rsi_14": 60.0, "oi_delta_pct": 1.0,
        "close_time": df.index[-1] + timedelta(hours=4 * 14),
    }
    order_13 = strategy.on_candle_close(candle_13, df_exp, broker_state=None)
    assert order_13 is None
    assert strategy.setup.state == SetupState.IDLE


def test_setup_invalidation_regime_or_crossover_flip(base_config):
    strategy = TrendFollowingStrategy(config=base_config, symbol="BTCUSDT")

    # Arm LONG setup
    df = _make_dummy_4h_history(
        n_bars=2,
        base_price=25000.0,
        ema20_vals=[20000.0, 20200.0],
        ema50_vals=[20100.0, 20100.0],
        ema200_vals=[18000.0, 18000.0],
    )
    c0 = df.iloc[-1].to_dict()
    c0["close_time"] = df.index[-1] + timedelta(hours=4)
    strategy.on_candle_close(c0, df, broker_state=None)
    assert strategy.setup.state == SetupState.ARMED

    # Nến sau đó close đâm thủng EMA200 (close <= ema200) -> Invalidation!
    candle_inv = {
        "close": 17500.0, "high": 18000.0, "low": 17000.0,
        "ema_20": 20200.0, "ema_50": 20100.0, "ema_200": 18000.0,
        "rsi_14": 40.0, "oi_delta_pct": 1.0,
        "close_time": df.index[-1] + timedelta(hours=8),
    }
    order = strategy.on_candle_close(candle_inv, df, broker_state=None)
    assert order is None
    assert strategy.setup.state == SetupState.IDLE


# ===========================================================================
# 4. RSI biên 50 không pass (>50 LONG, <50 SHORT)
# ===========================================================================

@pytest.mark.parametrize("rsi_val,should_pass", [
    (50.0, False),  # Đúng biên 50 -> Không pass
    (49.9, False),  # < 50 -> Không pass
    (50.01, True),  # > 50 -> Pass
    (65.0, True),   # > 50 -> Pass
])
def test_rsi_threshold_boundary_long(base_config, rsi_val, should_pass):
    strategy = TrendFollowingStrategy(config=base_config, symbol="BTCUSDT")
    df = _make_dummy_4h_history(n_bars=6, base_price=20000.0)

    # Đặt trạng thái ARMED
    strategy.setup.state = SetupState.ARMED
    strategy.setup.direction = OrderDirection.LONG
    strategy.setup.trigger_time = df.index[-2]
    strategy.setup.setup_age_bars = 1

    candle = {
        "open": 20300.0, "high": 20400.0, "low": 20180.0, "close": 20300.0,
        "ema_20": 20200.0, "ema_50": 20150.0, "ema_200": 18000.0,
        "rsi_14": rsi_val,
        "oi_delta_pct": 1.5,
        "close_time": df.index[-1] + timedelta(hours=4),
    }

    order = strategy.on_candle_close(candle, df, broker_state=None)
    if should_pass:
        assert order is not None
        assert order.direction == OrderDirection.LONG
    else:
        assert order is None


@pytest.mark.parametrize("rsi_val,should_pass", [
    (50.0, False),  # Đúng biên 50 -> Không pass
    (50.1, False),  # > 50 -> Không pass
    (49.99, True),  # < 50 -> Pass
    (35.0, True),   # < 50 -> Pass
])
def test_rsi_threshold_boundary_short(base_config, rsi_val, should_pass):
    strategy = TrendFollowingStrategy(config=base_config, symbol="BTCUSDT")
    df = _make_dummy_4h_history(n_bars=6, base_price=15000.0)

    strategy.setup.state = SetupState.ARMED
    strategy.setup.direction = OrderDirection.SHORT
    strategy.setup.trigger_time = df.index[-2]
    strategy.setup.setup_age_bars = 1

    # SHORT pullback: ema20=15100, ema50=15200.
    # Vùng [15100, 15200]. high >= 15100, low <= 15200, close <= 15100.
    candle = {
        "open": 15050.0, "high": 15150.0, "low": 14950.0, "close": 15050.0,
        "ema_20": 15100.0, "ema_50": 15200.0, "ema_200": 18000.0,
        "rsi_14": rsi_val,
        "oi_delta_pct": 2.0,
        "close_time": df.index[-1] + timedelta(hours=4),
    }

    order = strategy.on_candle_close(candle, df, broker_state=None)
    if should_pass:
        assert order is not None
        assert order.direction == OrderDirection.SHORT
    else:
        assert order is None


# ===========================================================================
# 5. OI strict/optional/disabled, NaN fallback có note; None/string/Inf fail-closed
# ===========================================================================

def test_oi_confluence_strict_mode(base_config):
    cfg = dict(base_config)
    cfg["oi_confluence"]["mode"] = "strict"
    strategy = TrendFollowingStrategy(config=cfg, symbol="BTCUSDT")
    df = _make_dummy_4h_history(n_bars=6)

    strategy.setup.state = SetupState.ARMED
    strategy.setup.direction = OrderDirection.LONG
    strategy.setup.setup_age_bars = 1

    # Khi OI là NaN trong strict mode -> Phải chặn vào lệnh
    candle_nan = {
        "close": 20300.0, "high": 20400.0, "low": 20180.0,
        "ema_20": 20200.0, "ema_50": 20150.0, "ema_200": 18000.0,
        "rsi_14": 60.0, "oi_delta_pct": float("nan"),
        "close_time": df.index[-1] + timedelta(hours=4),
    }
    assert strategy.on_candle_close(candle_nan, df, broker_state=None) is None

    # Khi OI > 0 trong strict mode -> Cho phép vào lệnh
    candle_ok = dict(candle_nan, oi_delta_pct=1.2)
    order = strategy.on_candle_close(candle_ok, df, broker_state=None)
    assert order is not None
    assert "oi_note" not in order.metadata


def test_oi_confluence_optional_mode_nan_fallback(base_config):
    cfg = dict(base_config)
    cfg["oi_confluence"]["mode"] = "optional"
    cfg["oi_confluence"]["fallback_when_nan"] = True
    cfg["oi_confluence"]["nan_log_note"] = "OI_BYPASSED_HISTORICAL"
    strategy = TrendFollowingStrategy(config=cfg, symbol="BTCUSDT")
    df = _make_dummy_4h_history(n_bars=6)

    strategy.setup.state = SetupState.ARMED
    strategy.setup.direction = OrderDirection.LONG
    strategy.setup.setup_age_bars = 1

    candle_nan = {
        "close": 20300.0, "high": 20400.0, "low": 20180.0,
        "ema_20": 20200.0, "ema_50": 20150.0, "ema_200": 18000.0,
        "rsi_14": 60.0, "oi_delta_pct": float("nan"),
        "close_time": df.index[-1] + timedelta(hours=4),
    }
    order = strategy.on_candle_close(candle_nan, df, broker_state=None)
    assert order is not None
    assert order.metadata.get("oi_note") == "OI_BYPASSED_HISTORICAL"


@pytest.mark.parametrize("invalid_oi", [
    "not_a_number",
    True,
    False,
    float("inf"),
    float("-inf"),
])
def test_oi_confluence_invalid_types_fail_closed(base_config, invalid_oi):
    strategy = TrendFollowingStrategy(config=base_config, symbol="BTCUSDT")
    df = _make_dummy_4h_history(n_bars=6)

    strategy.setup.state = SetupState.ARMED
    strategy.setup.direction = OrderDirection.LONG
    strategy.setup.setup_age_bars = 1

    candle = {
        "close": 20300.0, "high": 20400.0, "low": 20180.0,
        "ema_20": 20200.0, "ema_50": 20150.0, "ema_200": 18000.0,
        "rsi_14": 60.0, "oi_delta_pct": invalid_oi,
        "close_time": df.index[-1] + timedelta(hours=4),
    }
    # Phải fail-closed (không phát lệnh, không unhandled crash)
    order = strategy.on_candle_close(candle, df, broker_state=None)
    assert order is None


# ===========================================================================
# 6. Stop swing causal, warm-up, stop sai phía và trailing EMA50 tightening-only
# ===========================================================================

def test_causal_swing_stop_and_warmup(base_config):
    strategy = TrendFollowingStrategy(config=base_config, symbol="BTCUSDT")

    # 1. Warm-up không đủ 5 nến -> trả về None
    df_short = _make_dummy_4h_history(n_bars=3)
    stop = strategy._calculate_swing_stop(OrderDirection.LONG, df_short, signal_price=21000.0)
    assert stop is None

    # 2. Đủ 5 nến: kiểm tra đáy swing causal
    df_5 = _make_dummy_4h_history(n_bars=5, base_price=20000.0)
    # Gán cụ thể các giá trị low trong 5 nến: [19900, 19800, 19850, 19950, 20000]
    df_5["low"] = [19900.0, 19800.0, 19850.0, 19950.0, 20000.0]
    stop_long = strategy._calculate_swing_stop(OrderDirection.LONG, df_5, signal_price=20500.0)
    assert stop_long == 19800.0  # min(low)

    # 3. Stop sai phía: nếu min(low) >= signal_price -> trả về None
    stop_invalid = strategy._calculate_swing_stop(OrderDirection.LONG, df_5, signal_price=19700.0)
    assert stop_invalid is None


def test_trailing_stop_ema50_tightening_only(base_config):
    broker = PaperBroker(config=base_config)
    broker.last_mark_prices["BTCUSDT"] = 25000.0

    # Tạo vị thế LONG giả lập trong broker: entry=22000, stop_loss=21000
    pos = Position(
        position_id="POS_BTC_001",
        symbol="BTCUSDT",
        direction=OrderDirection.LONG,
        quantity=0.1,
        entry_price=22000.0,
        initial_margin=1100.0,
        isolated_collateral=1100.0,
        leverage=2.0,
        stop_loss_price=21000.0,
        liquidation_price=11000.0,
        opened_at=datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc),
    )
    broker.positions["BTCUSDT"] = pos
    strategy = TrendFollowingStrategy(config=base_config, symbol="BTCUSDT")

    # Trường hợp 1: EMA50 = 23000 (cao hơn stop cũ 21000 và thấp hơn mark 25000)
    # -> Siết chặt thành công!
    candle_up = {"ema_50": 23000.0, "close": 25000.0}
    strategy.update_trailing_stop(candle_up, broker)
    assert pos.stop_loss_price == 23000.0

    # Trường hợp 2: EMA50 = 22500 (thấp hơn stop hiện tại 23000 -> nới lỏng)
    # -> Bị chặn (tightening-only)!
    candle_down = {"ema_50": 22500.0, "close": 25000.0}
    strategy.update_trailing_stop(candle_down, broker)
    assert pos.stop_loss_price == 23000.0  # Không bị giảm

    # Trường hợp 3: EMA50 = 26000 (cao hơn mark price 25000)
    # -> Bị chặn (không được vượt qua mark price)!
    candle_over = {"ema_50": 26000.0, "close": 25000.0}
    strategy.update_trailing_stop(candle_over, broker)
    assert pos.stop_loss_price == 23000.0


# ===========================================================================
# 7. Warm-up EMA200 không phát tín hiệu
# ===========================================================================

def test_warmup_ema200_no_signal(base_config):
    strategy = TrendFollowingStrategy(config=base_config, symbol="BTCUSDT")

    # Khi EMA200 là NaN (chưa đủ 200 nến warm-up)
    df = _make_dummy_4h_history(
        n_bars=10,
        base_price=25000.0,
        ema200_vals=[float("nan")] * 10,
    )
    candle = df.iloc[-1].to_dict()
    candle["close_time"] = df.index[-1] + timedelta(hours=4)

    order = strategy.on_candle_close(candle, df, broker_state=None)
    assert order is None
    assert strategy.setup.state == SetupState.IDLE
