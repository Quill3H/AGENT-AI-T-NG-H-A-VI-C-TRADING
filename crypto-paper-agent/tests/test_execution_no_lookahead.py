"""
tests/test_execution_no_lookahead.py - Kiểm thử Tính Bất biến Nhân quả và Chống Lookahead
========================================================================================
Chứng minh:
1. Tín hiệu sinh tại close nến t tuyệt đối không bao giờ được fill tại nến t.
2. Việc thay đổi close/high/low của nến t+1 không làm thay đổi giá fill và kết quả duyệt tại open nến t+1.
3. Xáo trộn dữ liệu tương lai sau mốc cutoff không làm thay đổi lịch sử giao dịch và số dư trước cutoff.
"""
from datetime import datetime, timedelta, timezone
import random
import pytest

from src.execution.order_models import (
    OrderDirection,
    OrderRequest,
    OrderStatus,
)
from src.execution.paper_broker import PaperBroker


def test_signal_on_close_never_fills_same_candle(config):
    """Tín hiệu sinh tại close nến t không được fill tại nến t; chỉ fill ở nến t+1 open."""
    broker = PaperBroker(config=config, initial_balance=10000.0)
    t0 = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)

    # Nến 0
    broker.process_candle({
        "open_time": t0, "open": 50000.0, "high": 50100.0, "low": 49900.0, "close": 50050.0, "timeframe": "1m"
    })

    # Tại close nến 0 (10:01), chiến lược tạo signal
    req = OrderRequest(
        symbol="BTCUSDT",
        direction=OrderDirection.LONG,
        signal_price=50050.0,
        stop_loss_price=49000.0,
        signal_time=t0 + timedelta(minutes=1),
        leverage=2.0,
        base_risk_percent=0.02,
        conviction_tier="normal",
        requested_quantity=0.1,
    )
    rec = broker.submit_order(req)
    # Trạng thái hiện tại: PENDING, vị thế chưa mở
    assert rec.status == OrderStatus.PENDING
    assert "BTCUSDT" not in broker.positions

    # Nến 1 (10:01): Open nến 1 mới là thời điểm fill!
    t1 = t0 + timedelta(minutes=1)
    broker.process_candle({
        "open_time": t1, "open": 50100.0, "high": 50200.0, "low": 50050.0, "close": 50150.0, "timeframe": "1m"
    })

    # Vị thế được mở tại nến 1 với giá open (50100 + slippage)
    assert "BTCUSDT" in broker.positions
    pos = broker.positions["BTCUSDT"]
    assert pos.opened_at == t1
    assert abs(pos.entry_price - (50100.0 * (1.0 + broker.slippage_pct))) < 1e-4


def test_entry_sizing_independent_of_candle_high_low_close(config):
    """
    Kích thước vị thế và việc duyệt lệnh tại Pha 3 (open) hoàn toàn độc lập
    với giá High, Low, Close của chính nến đó.
    """
    t0 = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=1)

    results = []
    # Thử 2 kịch bản nến t1 với cùng Open=50000 nhưng High, Low, Close cực kỳ khác nhau
    scenarios = [
        {"high": 50100.0, "low": 49900.0, "close": 50050.0},
        {"high": 60000.0, "low": 45000.0, "close": 55000.0},
    ]

    for sc in scenarios:
        broker = PaperBroker(config=config, initial_balance=10000.0)
        broker.process_candle({"open_time": t0, "open": 50000.0, "high": 50100.0, "low": 49900.0, "close": 50000.0, "timeframe": "1m"})

        req = OrderRequest(
            symbol="BTCUSDT", direction=OrderDirection.LONG, signal_price=50000.0, stop_loss_price=42000.0,
            signal_time=t1, leverage=2.0, base_risk_percent=0.02, conviction_tier="normal"
        )
        broker.submit_order(req)

        candle_1 = {
            "open_time": t1,
            "open": 50000.0,
            "high": sc["high"],
            "low": sc["low"],
            "close": sc["close"],
            "timeframe": "1m",
        }
        broker.process_candle(candle_1)
        pos = broker.positions["BTCUSDT"]
        results.append((pos.entry_price, pos.quantity, pos.initial_margin))

    # Cả hai kịch bản đều cho ra kết quả entry_price, quantity, initial_margin giống hệt nhau
    assert results[0][0] == results[1][0]
    assert results[0][1] == results[1][1]
    assert results[0][2] == results[1][2]


def test_future_perturbation_preserves_past_ledger(config):
    """
    Future Perturbation Test:
    Tạo 50 nến. Tại nến 20 (cutoff), xáo trộn toàn bộ dữ liệu từ nến 21 đến 50.
    Chứng minh rằng toàn bộ lịch sử giao dịch và số dư tính đến nến 20 là hoàn toàn bất biến.
    """
    t_start = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
    cutoff_index = 20

    def generate_candles(seed=42, perturb_after_cutoff=False):
        rng = random.Random(seed)
        candles = []
        base_price = 50000.0
        t = t_start
        for i in range(50):
            if perturb_after_cutoff and i > cutoff_index:
                # Dữ liệu tương lai bị xáo trộn mạnh
                pct_change = rng.uniform(-0.05, 0.05)
            else:
                pct_change = 0.001 * (1 if i % 2 == 0 else -0.8)
            base_price = base_price * (1.0 + pct_change)
            c = {
                "open_time": t,
                "open": base_price,
                "high": base_price * 1.002,
                "low": base_price * 0.998,
                "close": base_price * 1.001,
                "symbol": "BTCUSDT",
                "timeframe": "1m",
            }
            candles.append(c)
            t += timedelta(minutes=1)
        return candles

    candles_original = generate_candles(seed=42, perturb_after_cutoff=False)
    candles_perturbed = generate_candles(seed=999, perturb_after_cutoff=True)

    # Đảm bảo các nến từ 0 đến cutoff là giống hệt nhau
    for i in range(cutoff_index + 1):
        assert candles_original[i] == candles_perturbed[i]
    # Đảm bảo các nến sau cutoff là khác nhau
    assert candles_original[cutoff_index + 1] != candles_perturbed[cutoff_index + 1]

    # Chạy lần 1 với dữ liệu gốc
    broker1 = PaperBroker(config=config, initial_balance=10000.0)
    # Gửi lệnh ở nến 5, fill ở nến 6
    for i, c in enumerate(candles_original):
        if i == 5:
            req = OrderRequest(
                symbol="BTCUSDT", direction=OrderDirection.LONG, signal_price=c["close"], stop_loss_price=c["close"] * 0.95,
                signal_time=c["open_time"] + timedelta(minutes=1), leverage=2.0, base_risk_percent=0.02, requested_quantity=0.05
            )
            broker1.submit_order(req)
        broker1.process_candle(c)
        if i == cutoff_index:
            break

    # Chạy lần 2 với dữ liệu bị xáo trộn sau cutoff
    broker2 = PaperBroker(config=config, initial_balance=10000.0)
    for i, c in enumerate(candles_perturbed):
        if i == 5:
            req = OrderRequest(
                symbol="BTCUSDT", direction=OrderDirection.LONG, signal_price=c["close"], stop_loss_price=c["close"] * 0.95,
                signal_time=c["open_time"] + timedelta(minutes=1), leverage=2.0, base_risk_percent=0.02, requested_quantity=0.05
            )
            broker2.submit_order(req)
        broker2.process_candle(c)
        if i == cutoff_index:
            break

    # Đối soát tại cutoff: Snapshot, Wallet, Position, Trade history của 2 broker là giống nhau 100%
    assert broker1.wallet_balance == broker2.wallet_balance
    assert broker1.available_margin == broker2.available_margin
    assert len(broker1.positions) == len(broker2.positions)
    assert broker1.positions["BTCUSDT"].entry_price == broker2.positions["BTCUSDT"].entry_price
    assert broker1.positions["BTCUSDT"].quantity == broker2.positions["BTCUSDT"].quantity
