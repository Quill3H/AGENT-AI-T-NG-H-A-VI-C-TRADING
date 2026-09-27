from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.execution.paper_broker import PaperBroker
from src.paper.live_session import LocalPaperSession, SYMBOLS
from src.paper.persistence import (
    evaluate_recovery_safety,
    load_persistent_state,
    save_persistent_state,
)

UTC = timezone.utc
BASE = datetime(2026, 9, 27, 4, 0, tzinfo=UTC)


def test_persistent_state_roundtrip(tmp_path: Path):
    broker = PaperBroker(initial_balance=10000.0)
    broker.wallet_balance = 9850.25
    broker.circuit_breaker.consecutive_losses = 2
    broker.circuit_breaker.is_locked = True

    saved = save_persistent_state(
        journal_dir=tmp_path,
        session_id="test-session-01",
        broker=broker,
        last_processed=BASE,
        last_open={"BTCUSDT": BASE},
        last_4h={"BTCUSDT": BASE},
    )
    assert saved.is_file()

    loaded = load_persistent_state(tmp_path)
    assert loaded is not None
    assert loaded["session_id"] == "test-session-01"
    assert loaded["account"]["wallet_balance"] == 9850.25
    assert loaded["account"]["circuit_breaker"]["consecutive_losses"] == 2
    assert loaded["account"]["circuit_breaker"]["is_locked"] is True


def test_session_retains_balance_across_restart_without_resetting_to_10000(tmp_path: Path):
    class FakeSource:
        def __init__(self):
            self.now = int((BASE + timedelta(minutes=1)).timestamp() * 1000)

        def server_time_ms(self):
            return self.now

        def klines(self, symbol, interval, limit):
            def rows(start, count, minutes, price=100.0):
                res = []
                for s in range(count):
                    t = start + timedelta(minutes=s * minutes)
                    ms = int(t.timestamp() * 1000)
                    res.append([ms, str(price), str(price + 1), str(price - 1), str(price), "1", ms + minutes * 60_000 - 1])
                return res

            if interval == "4h":
                return rows(BASE - timedelta(hours=4 * 210), 210, 240)
            if interval == "1m":
                return rows(BASE - timedelta(minutes=2), 4, 1)
            return rows(BASE - timedelta(minutes=30), 2, 15)

        def funding(self, symbol, limit):
            return []

    # 1. First session runs and updates wallet
    session1 = LocalPaperSession(source=FakeSource(), journal_dir=tmp_path)
    session1.start()
    session1.broker.wallet_balance = 9750.0  # Simulated trade loss
    session1.stop()

    # Verify persistent state saved
    loaded = load_persistent_state(tmp_path)
    assert loaded["account"]["wallet_balance"] == 9750.0

    # 2. Second session starts after restart — MUST NOT reset to 10,000!
    session2 = LocalPaperSession(source=FakeSource(), journal_dir=tmp_path)
    state2 = session2.start()

    assert state2["account"]["wallet_usd"] == 9750.0
    assert state2["account"]["wallet_usd"] != 10000.0


def test_recovery_quarantines_when_open_position_stop_loss_breached_during_downtime():
    class FakeSourceBreached:
        def server_time_ms(self):
            return int((BASE + timedelta(hours=1)).timestamp() * 1000)

        def klines(self, symbol, interval, limit):
            # Low price dipped to 90.0, breaching 95.0 stop loss
            ms = int(BASE.timestamp() * 1000)
            return [[ms, "98.0", "99.0", "90.0", "92.0", "10", ms + 900000 - 1]]

    saved_state = {
        "saved_at_utc": BASE.isoformat(),
        "account": {"initial_balance": 10000.0, "wallet_balance": 10000.0},
        "positions": [
            {
                "symbol": "BTCUSDT",
                "direction": "LONG",
                "entry_price": 100.0,
                "stop_loss_price": 95.0,
                "liquidation_price": 82.0,
                "quantity": 0.1,
                "leverage": 2,
            }
        ],
    }

    is_safe, reason = evaluate_recovery_safety(
        saved_state,
        int((BASE + timedelta(hours=1)).timestamp() * 1000),
        FakeSourceBreached(),
    )
    assert is_safe is False
    assert "chạm stop-loss/thanh lý" in reason
