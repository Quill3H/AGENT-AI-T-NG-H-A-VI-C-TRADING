"""
tests/test_paper_broker.py - Kiểm thử Logic Khớp lệnh và Vận hành Paper Broker
=============================================================================
Kiểm tra vòng đời vị thế, thứ tự ưu tiên intrabar (Liquidation > SL > TP),
gap exits, chính sách 1 vị thế/symbol, và tích hợp Circuit Breaker.
"""
from datetime import datetime, timedelta, timezone
import pytest

from src.execution.order_models import (
    ExitReason,
    OrderDirection,
    OrderRequest,
    OrderStatus,
)
from src.execution.paper_broker import PaperBroker


@pytest.fixture
def default_broker(config):
    return PaperBroker(config=config, initial_balance=10000.0)


def test_single_position_per_symbol_limit(default_broker):
    """Từ chối mở vị thế mới khi symbol đó đã có vị thế đang hoạt động."""
    t0 = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
    default_broker.process_candle({
        "open_time": t0, "open": 50000.0, "high": 50100.0, "low": 49900.0, "close": 50000.0, "timeframe": "1m"
    })

    # Mở vị thế thứ nhất
    req1 = OrderRequest(
        symbol="BTCUSDT",
        direction=OrderDirection.LONG,
        signal_price=50000.0,
        stop_loss_price=49000.0,
        signal_time=t0 + timedelta(minutes=1),
        leverage=2.0,
        base_risk_percent=0.02,
        conviction_tier="normal",
        requested_quantity=0.1,
    )
    rec1 = default_broker.submit_order(req1)
    assert rec1.status == OrderStatus.PENDING

    # Khớp lệnh 1 tại nến 1
    t1 = t0 + timedelta(minutes=1)
    default_broker.process_candle({
        "open_time": t1, "open": 50000.0, "high": 50100.0, "low": 49900.0, "close": 50000.0, "timeframe": "1m"
    })
    assert "BTCUSDT" in default_broker.positions

    # Gửi tiếp lệnh thứ 2 cùng symbol BTCUSDT -> Bị từ chối ngay lập tức
    req2 = OrderRequest(
        symbol="BTCUSDT",
        direction=OrderDirection.SHORT,
        signal_price=50000.0,
        stop_loss_price=51000.0,
        signal_time=t1 + timedelta(minutes=1),
        leverage=2.0,
        base_risk_percent=0.02,
        conviction_tier="normal",
        requested_quantity=0.1,
    )
    rec2 = default_broker.submit_order(req2)
    assert rec2.status == OrderStatus.REJECTED
    assert any("POSITION_EXISTS" in r for r in rec2.rejection_reasons)


def test_intrabar_priority_sl_over_tp(default_broker):
    """
    Khi cả SL và TP đều có thể chạm trong cùng 1 nến [low, high]:
    Quy tắc bảo thủ của đặc tả: SL được ưu tiên xử lý trước TP.
    """
    t0 = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
    default_broker.process_candle({
        "open_time": t0, "open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0, "timeframe": "1m"
    })

    # LONG: entry 100, SL 95, TP 105
    req = OrderRequest(
        symbol="BTCUSDT",
        direction=OrderDirection.LONG,
        signal_price=100.0,
        stop_loss_price=95.0,
        take_profit_price=105.0,
        signal_time=t0 + timedelta(minutes=1),
        leverage=2.0,
        base_risk_percent=0.02,
        conviction_tier="normal",
        requested_quantity=1.0,
    )
    default_broker.submit_order(req)

    # Nến 1: Vào vị thế tại 100.0
    t1 = t0 + timedelta(minutes=1)
    default_broker.process_candle({
        "open_time": t1, "open": 100.0, "high": 100.2, "low": 99.8, "close": 100.0, "timeframe": "1m"
    })

    # Nến 2: Nến biến động cực lớn quét cả 2 đầu: Low 94 <= SL(95) và High 106 >= TP(105)
    t2 = t1 + timedelta(minutes=1)
    default_broker.process_candle({
        "open_time": t2, "open": 100.0, "high": 106.0, "low": 94.0, "close": 100.0, "timeframe": "1m"
    })

    # Phải thoát bằng STOP_LOSS, không phải TAKE_PROFIT
    assert len(default_broker.trade_history) == 1
    trade = default_broker.trade_history[0]
    assert trade.exit_reason == ExitReason.STOP_LOSS
    assert trade.exit_price <= 95.0  # SL kèm slippage bán


def test_gap_exit_at_open_exits_at_open_price(default_broker):
    """
    Nếu nến tiếp theo mở cửa nhảy gap qua Stop-Loss:
    Giá thoát lệnh thực tế là giá OPEN (kèm slippage), không được khớp giá SL cũ.
    """
    t0 = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
    default_broker.process_candle({
        "open_time": t0, "open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0, "timeframe": "1m"
    })

    req = OrderRequest(
        symbol="BTCUSDT",
        direction=OrderDirection.LONG,
        signal_price=100.0,
        stop_loss_price=95.0,
        take_profit_price=110.0,
        signal_time=t0 + timedelta(minutes=1),
        leverage=2.0,
        base_risk_percent=0.02,
        conviction_tier="normal",
        requested_quantity=1.0,
    )
    default_broker.submit_order(req)

    # Nến 1: Vào vị thế tại 100.0
    t1 = t0 + timedelta(minutes=1)
    default_broker.process_candle({
        "open_time": t1, "open": 100.0, "high": 100.2, "low": 99.8, "close": 100.0, "timeframe": "1m"
    })

    # Nến 2: Nhảy gap down ngay tại open = 90.0 (thấp hơn SL 95.0)
    t2 = t1 + timedelta(minutes=1)
    res = default_broker.process_candle({
        "open_time": t2, "open": 90.0, "high": 91.0, "low": 89.0, "close": 90.5, "timeframe": "1m"
    })

    # Thoát lệnh ngay tại Pha 1 (Gap exit)
    assert len(default_broker.trade_history) == 1
    trade = default_broker.trade_history[0]
    assert trade.exit_reason == ExitReason.STOP_LOSS
    # Giá thoát lệnh khoảng 90 * (1 - 0.0003) = 89.973, không phải 95!
    assert abs(trade.exit_price - (90.0 * (1.0 - default_broker.slippage_pct))) < 1e-4


def test_update_stop_loss_tightening_only(default_broker):
    """Kiểm tra chỉ cho phép thắt chặt Stop Loss, không cho phép nới rộng rủi ro."""
    t0 = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
    default_broker.process_candle({
        "open_time": t0, "open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0, "timeframe": "1m"
    })

    req = OrderRequest(
        symbol="BTCUSDT",
        direction=OrderDirection.LONG,
        signal_price=100.0,
        stop_loss_price=95.0,
        signal_time=t0 + timedelta(minutes=1),
        leverage=2.0,
        base_risk_percent=0.02,
        conviction_tier="normal",
        requested_quantity=1.0,
    )
    default_broker.submit_order(req)

    t1 = t0 + timedelta(minutes=1)
    default_broker.process_candle({
        "open_time": t1, "open": 100.0, "high": 100.2, "low": 99.8, "close": 100.0, "timeframe": "1m"
    })

    # Nâng SL từ 95 lên 97: Hợp lệ
    assert default_broker.update_stop_loss("BTCUSDT", 97.0) is True
    assert default_broker.positions["BTCUSDT"].stop_loss_price == 97.0

    # Hạ SL từ 97 xuống 94: BỊ TỪ CHỐI (không cho nới rộng SL)
    assert default_broker.update_stop_loss("BTCUSDT", 94.0) is False
    assert default_broker.positions["BTCUSDT"].stop_loss_price == 97.0


def test_circuit_breaker_streak_risk_reduction_and_recovery(config):
    """
    Kiểm tra tích hợp Circuit Breaker:
    - 3 lệnh thua liên tiếp -> giảm risk_multiplier xuống 0.5.
    - Đúng 3 lệnh thắng liên tiếp sau đó -> phục hồi về 1.0 (after_3_wins).
    """
    broker = PaperBroker(config=config, initial_balance=10000.0)
    t = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)

    for i in range(3):
        # Nến tạo signal
        broker.process_candle({"open_time": t, "open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0, "timeframe": "1m"})
        t += timedelta(minutes=1)
        req = OrderRequest(
            symbol="BTCUSDT", direction=OrderDirection.LONG, signal_price=100.0, stop_loss_price=99.0,
            signal_time=t, leverage=2.0, base_risk_percent=0.02, requested_quantity=1.0,
        )
        broker.submit_order(req)
        # Nến vào lệnh
        broker.process_candle({"open_time": t, "open": 100.0, "high": 100.2, "low": 99.8, "close": 100.0, "timeframe": "1m"})
        t += timedelta(minutes=1)
        # Nến dính SL (thua)
        broker.process_candle({"open_time": t, "open": 100.0, "high": 100.1, "low": 98.5, "close": 98.8, "timeframe": "1m"})
        t += timedelta(minutes=1)

    # Sau 3 lệnh thua liên tiếp -> risk multiplier phải giảm xuống 0.5
    assert broker.circuit_breaker.consecutive_losses == 3
    assert broker.circuit_breaker.risk_multiplier == 0.5

    # Bây giờ cho 3 lệnh thắng liên tiếp
    for i in range(3):
        broker.process_candle({"open_time": t, "open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0, "timeframe": "1m"})
        t += timedelta(minutes=1)
        req = OrderRequest(
            symbol="BTCUSDT", direction=OrderDirection.LONG, signal_price=100.0, stop_loss_price=95.0, take_profit_price=105.0,
            signal_time=t, leverage=2.0, base_risk_percent=0.02, requested_quantity=1.0,
        )
        broker.submit_order(req)
        # Nến vào lệnh
        broker.process_candle({"open_time": t, "open": 100.0, "high": 100.2, "low": 99.8, "close": 100.0, "timeframe": "1m"})
        t += timedelta(minutes=1)
        # Nến dính TP (thắng)
        broker.process_candle({"open_time": t, "open": 100.0, "high": 106.0, "low": 99.5, "close": 104.0, "timeframe": "1m"})
        t += timedelta(minutes=1)

    # Sau đúng 3 lệnh thắng liên tiếp -> risk multiplier phục hồi về 1.0!
    assert broker.circuit_breaker.consecutive_losses == 0
    assert broker.circuit_breaker.risk_multiplier == 1.0


def test_intrabar_priority_liquidation_over_sl(config):
    """
    Quy tắc bảo thủ tối cao: Liquidation > Stop Loss > Take Profit.
    Nếu nến quét sâu qua cả giá Liquidation và giá Stop Loss, sự kiện thanh lý
    bắt buộc phải được ghi nhận (LIQUIDATION).
    """
    broker = PaperBroker(config=config, initial_balance=10000.0)
    t = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
    broker.process_candle({"open_time": t, "open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0, "timeframe": "1m"})
    t += timedelta(minutes=1)

    # Đặt SL tại 82.0, leverage 2.0 -> P_liq khoảng 50.4 (Buffer = (82 - 50.4)/100 = 31.6% >= 30%)
    req = OrderRequest(
        symbol="BTCUSDT", direction=OrderDirection.LONG, signal_price=100.0, stop_loss_price=82.0,
        signal_time=t, leverage=2.0, base_risk_percent=0.02, requested_quantity=1.0,
    )
    broker.submit_order(req)
    # Nến vào lệnh
    broker.process_candle({"open_time": t, "open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0, "timeframe": "1m"})
    t += timedelta(minutes=1)

    liq_price = broker.positions["BTCUSDT"].liquidation_price

    # Nến sập mạnh quét thủng cả SL (80) lẫn Liquidation price (khoảng 75)
    broker.process_candle({"open_time": t, "open": 98.0, "high": 99.0, "low": 50.0, "close": 60.0, "timeframe": "1m"})

    assert len(broker.trade_history) == 1
    trade = broker.trade_history[0]
    assert trade.exit_reason == ExitReason.LIQUIDATION
    assert trade.exit_price <= liq_price


def test_replay_determinism_identical_results(config):
    """
    Kiểm tra tính tất định tuyệt đối:
    Hai lần chạy độc lập với cùng dữ liệu nến và lệnh phải cho ra
    kết quả chính xác từng bit về order_history, trade_history, wallet, equity.
    """
    def run_simulation():
        b = PaperBroker(config=config, initial_balance=10000.0)
        t = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
        for i in range(15):
            c = {
                "open_time": t,
                "open": 50000.0 + i * 10,
                "high": 50100.0 + i * 10,
                "low": 49900.0 + i * 10,
                "close": 50050.0 + i * 10,
                "symbol": "BTCUSDT",
                "timeframe": "1m",
            }
            if i == 2:
                req = OrderRequest(
                    symbol="BTCUSDT", direction=OrderDirection.LONG, signal_price=c["close"],
                    stop_loss_price=48000.0, take_profit_price=50500.0,
                    signal_time=c["open_time"] + timedelta(minutes=1), leverage=2.0,
                    base_risk_percent=0.02, requested_quantity=0.05
                )
                b.submit_order(req)
            b.process_candle(c)
            t += timedelta(minutes=1)
        return b

    b1 = run_simulation()
    b2 = run_simulation()

    assert b1.wallet_balance == b2.wallet_balance
    assert b1.equity == b2.equity
    assert b1.available_margin == b2.available_margin
    assert len(b1.trade_history) == len(b2.trade_history)
    for t1, t2 in zip(b1.trade_history, b2.trade_history):
        assert t1.trade_id == t2.trade_id
        assert t1.net_pnl == t2.net_pnl
        assert t1.exit_reason == t2.exit_reason
    assert len(b1.order_history) == len(b2.order_history)
    for o1, o2 in zip(b1.order_history, b2.order_history):
        assert o1.order_id == o2.order_id
        assert o1.status == o2.status


def test_finalize_replaces_last_snapshot_with_post_close_equity(default_broker):
    """Force-close costs must be present in the final equity curve exactly once."""
    t0 = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
    default_broker.process_candle({
        "open_time": t0, "open": 100.0, "high": 100.2, "low": 99.8,
        "close": 100.0, "timeframe": "1m",
    })
    default_broker.submit_order(OrderRequest(
        symbol="BTCUSDT",
        direction=OrderDirection.LONG,
        signal_price=100.0,
        stop_loss_price=95.0,
        signal_time=t0 + timedelta(minutes=1),
        leverage=2.0,
        base_risk_percent=0.02,
        requested_quantity=1.0,
    ))
    default_broker.process_candle({
        "open_time": t0 + timedelta(minutes=1), "open": 100.0,
        "high": 100.2, "low": 99.8, "close": 100.0, "timeframe": "1m",
    })

    snapshot_count = len(default_broker.account_snapshots)
    finalize_time = default_broker.current_time
    default_broker.finalize(timestamp=finalize_time, force_close=True)

    assert len(default_broker.trade_history) == 1
    assert len(default_broker.account_snapshots) == snapshot_count
    assert default_broker.account_snapshots[-1].timestamp == finalize_time
    assert default_broker.account_snapshots[-1].equity == pytest.approx(default_broker.equity)
    assert default_broker.account_snapshots[-1].open_positions_count == 0

    default_broker.finalize(timestamp=finalize_time, force_close=True)
    assert len(default_broker.trade_history) == 1
    assert len(default_broker.account_snapshots) == snapshot_count

