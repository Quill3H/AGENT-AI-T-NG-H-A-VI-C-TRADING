"""
tests/test_execution_accounting.py - Kiểm tra Hạch toán Kế toán & Bài toán Oracle
=================================================================================
Kiểm tra các bất biến kế toán (wallet, equity, available margin, reserved margin)
và bài toán Oracle bắt buộc theo tài liệu nhiệm vụ Giai đoạn 4.
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


def test_mandatory_oracle_long_trade():
    """
    BÀI TOÁN ORACLE LONG BẮT BUỘC THEO MỤC 8 ANTIGRAVITY_STAGE_04_TASK.md:
    - Vốn ban đầu: 10,000 USD
    - Leverage: 2x
    - Entry actual: 100
    - SL: 98, TP: 104
    - Base risk: 0.002, tier: low, quantity: 10
    - Slippage: 0, Taker fee: 0.0005 (0.05%)
    - Chuỗi 300 nến 1 phút
    - 1 kỳ settlement funding lúc 08:00 UTC, rate +0.0001, settlement mark 100
    - TP khớp sau settlement
    """
    config = {
        "account": {"initial_equity_usd": 10000.0},
        "risk": {
            "max_leverage": 5.0,
            "min_liquidation_buffer_pct": 0.30,
            "conviction_tiers": {"low": 0.01, "normal": 0.02, "high": 0.05, "ultra_high": 0.10},
        },
        "fees": {
            "taker_pct": 0.0005,
            "maker_pct": 0.0002,
            "slippage_pct": 0.0,  # 0 slippage cho fixture oracle
        },
        "circuit_breakers": {
            "daily_loss_limit_pct": 0.05,
            "consecutive_losses_threshold": 3,
            "risk_reduction_on_streak": 0.5,
            "recovery_mode": "after_3_wins",
            "consecutive_wins_to_recover": 3,
        },
        "news_filter": {"enabled": False},
    }

    broker = PaperBroker(config=config, initial_balance=10000.0)
    assert broker.slippage_pct == 0.0
    assert broker.taker_fee_pct == 0.0005

    t_start = datetime(2026, 9, 1, 7, 30, tzinfo=timezone.utc)

    # Nến 0: 07:30 - Sinh tín hiệu mua tại close nến này
    candle_0 = {
        "open_time": t_start,
        "open": 100.0,
        "high": 100.5,
        "low": 99.5,
        "close": 100.0,
        "symbol": "BTCUSDT",
        "timeframe": "1m",
    }
    broker.process_candle(candle_0)

    # Gửi lệnh tại close nến 0 (chuẩn bị cho open nến 1 lúc 07:31)
    req = OrderRequest(
        symbol="BTCUSDT",
        direction=OrderDirection.LONG,
        signal_price=100.0,
        stop_loss_price=98.0,
        take_profit_price=104.0,
        signal_time=t_start + timedelta(minutes=1),
        leverage=2.0,
        base_risk_percent=0.002,
        conviction_tier="low",
        requested_quantity=10.0,
    )
    rec = broker.submit_order(req)
    assert rec.status == OrderStatus.PENDING

    # Nến 1: 07:31 - Khớp lệnh tại open = 100
    t_entry = t_start + timedelta(minutes=1)
    candle_1 = {
        "open_time": t_entry,
        "open": 100.0,
        "high": 100.2,
        "low": 99.8,
        "close": 100.0,
        "symbol": "BTCUSDT",
        "timeframe": "1m",
    }
    res_1 = broker.process_candle(candle_1)

    # Đối soát tại Nến 1 (Ngay sau khi vào lệnh):
    # Notional = 10 * 100 = 1,000 USD
    # Initial reserved margin = 1000 / 2 = 500 USD
    # Entry fee = 1000 * 0.0005 = 0.50 USD
    assert "BTCUSDT" in broker.positions
    pos = broker.positions["BTCUSDT"]
    assert pos.quantity == 10.0
    assert pos.entry_price == 100.0
    assert pos.initial_margin == 500.0
    assert pos.isolated_collateral == 500.0
    assert pos.entry_fee == 0.50
    assert abs(broker.wallet_balance - 9999.50) < 1e-4
    assert abs(broker.available_margin - 9499.50) < 1e-4

    # Chạy các nến từ 07:32 đến 07:59 (giá đi ngang quanh 100, không chạm SL hay TP)
    curr_time = t_entry
    for i in range(2, 30):
        curr_time += timedelta(minutes=1)
        c = {
            "open_time": curr_time,
            "open": 100.0,
            "high": 100.3,
            "low": 99.7,
            "close": 100.0,
            "symbol": "BTCUSDT",
            "timeframe": "1m",
        }
        broker.process_candle(c)

    # Nến lúc 08:00: Mốc settlement funding (hours={0, 8, 16})
    # Funding rate = +0.0001, settlement mark = 100.0
    curr_time += timedelta(minutes=1)
    assert curr_time.hour == 8 and curr_time.minute == 0
    candle_funding = {
        "open_time": curr_time,
        "open": 100.0,
        "high": 100.2,
        "low": 99.8,
        "close": 100.0,
        "symbol": "BTCUSDT",
        "timeframe": "1m",
        "funding_rate": 0.0001,
    }
    broker.process_candle(candle_funding)

    # Đối soát sự kiện Funding lúc 08:00:
    # Funding cashflow = -1 * 10 * 100 * 0.0001 = -0.10 USD
    # Wallet balance = 9999.50 - 0.10 = 9999.40 USD
    # Isolated collateral = 500.0 - 0.10 = 499.90 USD
    assert len(broker.funding_history) == 1
    f_evt = broker.funding_history[0]
    assert abs(f_evt.cashflow_usd - (-0.10)) < 1e-4
    assert abs(pos.isolated_collateral - 499.90) < 1e-4
    assert abs(broker.wallet_balance - 9999.40) < 1e-4
    assert abs(broker.available_margin - 9499.50) < 1e-4  # 9999.40 - 499.90 = 9499.50

    # Chạy tiếp các nến từ 08:01 đến 08:30 (giá đi ngang quanh 100-102)
    for _ in range(30):
        curr_time += timedelta(minutes=1)
        c = {
            "open_time": curr_time,
            "open": 100.0,
            "high": 101.0,
            "low": 99.8,
            "close": 100.5,
            "symbol": "BTCUSDT",
            "timeframe": "1m",
        }
        broker.process_candle(c)

    # Nến chạm Take Profit tại 104.0
    curr_time += timedelta(minutes=1)
    candle_tp = {
        "open_time": curr_time,
        "open": 101.0,
        "high": 104.5,  # Chạm TP 104.0
        "low": 100.5,
        "close": 103.0,
        "symbol": "BTCUSDT",
        "timeframe": "1m",
    }
    broker.process_candle(candle_tp)

    # Đối soát kết quả đóng vị thế tại TP:
    # Vị thế đã đóng hoàn tất
    assert "BTCUSDT" not in broker.positions
    assert len(broker.trade_history) == 1
    trade = broker.trade_history[0]

    assert trade.exit_reason == ExitReason.TAKE_PROFIT
    assert trade.exit_price == 104.0
    # Gross price PnL = 10 * (104.0 - 100.0) = 40.00 USD
    assert abs(trade.gross_price_pnl - 40.00) < 1e-4
    # Exit fee = 10 * 104.0 * 0.0005 = 0.52 USD
    assert abs(trade.exit_fee - 0.52) < 1e-4
    # Entry fee = 0.50 USD
    assert abs(trade.entry_fee - 0.50) < 1e-4
    # Funding cashflow = -0.10 USD
    assert abs(trade.funding_cashflow - (-0.10)) < 1e-4
    # Net trade PnL = 40.00 - 0.50 - 0.52 + (-0.10) = 38.88 USD
    assert abs(trade.net_pnl - 38.88) < 1e-4

    # Final wallet / equity sau khi flat = 10000 + 38.88 = 10038.88 USD
    assert abs(broker.wallet_balance - 10038.88) < 1e-4
    assert abs(broker.equity - 10038.88) < 1e-4
    # Reserved margin cuối = 0; Available margin cuối = 10038.88 USD
    assert broker.reserved_collateral == 0.0
    assert abs(broker.available_margin - 10038.88) < 1e-4


def test_short_trade_with_negative_funding():
    """
    Kiểm tra giao dịch SHORT với funding rate âm (Rate < 0: SHORT phải trả phí funding).
    """
    config = {
        "account": {"initial_equity_usd": 10000.0},
        "risk": {
            "max_leverage": 5.0,
            "min_liquidation_buffer_pct": 0.30,
            "conviction_tiers": {"normal": 0.02},
        },
        "fees": {
            "taker_pct": 0.0005,
            "maker_pct": 0.0002,
            "slippage_pct": 0.0,
        },
        "circuit_breakers": {
            "daily_loss_limit_pct": 0.05,
            "consecutive_losses_threshold": 3,
            "risk_reduction_on_streak": 0.5,
            "recovery_mode": "after_3_wins",
            "consecutive_wins_to_recover": 3,
        },
        "news_filter": {"enabled": False},
    }

    broker = PaperBroker(config=config, initial_balance=10000.0)
    t0 = datetime(2026, 9, 1, 7, 58, tzinfo=timezone.utc)

    # Nến 0
    broker.process_candle({
        "open_time": t0, "open": 200.0, "high": 201.0, "low": 199.0, "close": 200.0, "timeframe": "1m"
    })

    # Lệnh SHORT: entry 200, SL 205, TP 190, qty 5
    req = OrderRequest(
        symbol="BTCUSDT",
        direction=OrderDirection.SHORT,
        signal_price=200.0,
        stop_loss_price=205.0,
        take_profit_price=190.0,
        signal_time=t0 + timedelta(minutes=1),
        leverage=2.0,
        base_risk_percent=0.02,
        conviction_tier="normal",
        requested_quantity=5.0,
    )
    broker.submit_order(req)

    # Nến 1: 07:59 - Mở SHORT tại 200.0
    t1 = t0 + timedelta(minutes=1)
    broker.process_candle({
        "open_time": t1, "open": 200.0, "high": 200.5, "low": 199.5, "close": 200.0, "timeframe": "1m"
    })

    # Entry notional = 5 * 200 = 1,000 USD, entry fee = 0.50 USD
    # Wallet = 9,999.50 USD
    assert abs(broker.wallet_balance - 9999.50) < 1e-4

    # Nến 2: 08:00 - Settlement funding với rate âm: -0.0002
    # SHORT direction_sign = -1 -> cashflow = -(-1) * 5 * 200 * (-0.0002) = -0.20 USD (SHORT phải trả phí)
    t2 = t1 + timedelta(minutes=1)
    broker.process_candle({
        "open_time": t2, "open": 200.0, "high": 200.5, "low": 199.5, "close": 200.0,
        "timeframe": "1m", "funding_rate": -0.0002
    })
    assert len(broker.funding_history) == 1
    assert abs(broker.funding_history[0].cashflow_usd - (-0.20)) < 1e-4
    assert abs(broker.wallet_balance - 9999.30) < 1e-4

    # Nến 3: Chạm TP SHORT tại 190.0
    t3 = t2 + timedelta(minutes=1)
    broker.process_candle({
        "open_time": t3, "open": 199.0, "high": 199.5, "low": 189.5, "close": 191.0, "timeframe": "1m"
    })

    trade = broker.trade_history[0]
    assert trade.exit_reason == ExitReason.TAKE_PROFIT
    assert trade.exit_price == 190.0
    # Gross PnL = 5 * (200.0 - 190.0) = +50.00 USD
    assert abs(trade.gross_price_pnl - 50.00) < 1e-4
    # Exit fee = 5 * 190 * 0.0005 = 0.475 USD
    assert abs(trade.exit_fee - 0.475) < 1e-4
    # Net trade PnL = 50.00 - 0.50 - 0.475 + (-0.20) = 48.825 USD
    assert abs(trade.net_pnl - 48.825) < 1e-4
    # Final wallet = 10000 + 48.825 = 10048.825 USD
    assert abs(broker.wallet_balance - 10048.825) < 1e-4


def test_accounting_invariants_verification():
    """Kiểm tra hàm verify_accounting_invariants phát hiện sai lệch kế toán."""
    config = {
        "account": {"initial_equity_usd": 10000.0},
        "risk": {"max_leverage": 5.0, "min_liquidation_buffer_pct": 0.30},
        "fees": {"taker_pct": 0.0005, "slippage_pct": 0.0},
        "news_filter": {"enabled": False},
    }
    broker = PaperBroker(config=config, initial_balance=10000.0)
    broker.verify_accounting_invariants()  # Không văng exception

    # Làm sai lệch wallet_balance
    broker.wallet_balance += 10.0
    with pytest.raises(AssertionError, match="Accounting invariant violated"):
        broker.verify_accounting_invariants()
