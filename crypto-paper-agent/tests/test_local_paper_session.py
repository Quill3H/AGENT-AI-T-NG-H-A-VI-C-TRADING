from datetime import datetime, timedelta, timezone
import json
import time

import pandas as pd
import pytest

from src.execution.order_models import OrderRequest
from src.paper.live_session import BinancePublicSource, LocalPaperSession, parse_klines


UTC = timezone.utc
BASE = datetime(2026, 9, 27, 4, 0, tzinfo=UTC)


def rows(start, count, minutes, price=100.0):
    result = []
    for step in range(count):
        opened = start + timedelta(minutes=step * minutes)
        start_ms = int(opened.timestamp() * 1000)
        result.append([start_ms, str(price), str(price + 1), str(price - 1), str(price), "5", start_ms + minutes * 60_000 - 1])
    return result


def test_closed_bar_parser_excludes_provisional_bar_and_rejects_bad_geometry():
    bars = rows(BASE, 2, 1)
    closed, provisional = parse_klines(bars, "1m", int((BASE + timedelta(minutes=1, seconds=30)).timestamp() * 1000))
    assert [bar["open_time"] for bar in closed] == [BASE]
    assert provisional["open_time"] == BASE + timedelta(minutes=1)
    assert provisional["provisional"] is True
    bars[0][2] = "98"
    with pytest.raises(ValueError, match="OHLC"):
        parse_klines(bars, "1m", int((BASE + timedelta(minutes=2)).timestamp() * 1000))


def test_parser_rejects_duplicate_and_gapped_candles():
    now = int((BASE + timedelta(minutes=46)).timestamp() * 1000)
    with pytest.raises(ValueError, match="duplicate|sequence"):
        parse_klines(rows(BASE, 1, 15) * 2, "15m", now)
    with pytest.raises(ValueError, match="gap"):
        parse_klines(rows(BASE, 1, 15) + rows(BASE + timedelta(minutes=30), 1, 15), "15m", now)


class FakeSource:
    def __init__(self):
        self.now = int((BASE + timedelta(minutes=1)).timestamp() * 1000)
        self.phase = 0
        self.calls = []

    def server_time_ms(self):
        return self.now

    def klines(self, symbol, interval, limit):
        self.calls.append((symbol, interval))
        if interval == "4h":
            return rows(BASE - timedelta(hours=4 * 210), 210, 240)
        if interval == "1m":
            return rows(BASE - timedelta(minutes=2), 4, 1)
        count = 2 if self.phase == 0 else 3
        return rows(BASE - timedelta(minutes=30), count, 15)

    def funding(self, symbol, limit):
        return []


def test_session_starts_from_current_closed_baseline_and_processes_three_symbols(tmp_path):
    source = FakeSource()
    session = LocalPaperSession(source=source, journal_dir=tmp_path)
    first = session.start()
    assert first["mode"] == "PAPER_RESEARCH"
    assert first["completed_trades"] == 0
    assert first["last_processed_open_utc"] is None
    assert first["symbols"] == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    assert sorted(first["markets"]) == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    assert first["markets"]["ETHUSDT"]["last_closed_15m_price"] == 100.0
    journal = json.loads(next(tmp_path.glob("*.jsonl")).read_text(encoding="utf-8").splitlines()[0])
    assert len(journal["raw_warmup_4h"]["BTCUSDT"]) == 210
    assert len(journal["raw_baseline_15m"]["SOLUSDT"]) == 2
    assert len(journal["input_sha256"]) == 64
    assert session.start()["session_id"] == first["session_id"]
    source.phase = 1
    source.now = int((BASE + timedelta(minutes=16)).timestamp() * 1000)
    state = session.poll()
    assert state["last_processed_open_utc"] == BASE.isoformat()
    assert len(session.broker.account_snapshots) == 3
    assert state["completed_trades"] == 0
    assert state["account"]["equity_usd"] == 10000.0
    assert session.poll()["last_processed_open_utc"] == BASE.isoformat()
    assert len(session.broker.account_snapshots) == 3


def test_session_quarantines_gap_without_mutating_broker(tmp_path):
    source = FakeSource()
    session = LocalPaperSession(source=source, journal_dir=tmp_path)
    session.start()
    source.phase = 1
    source.now = int((BASE + timedelta(minutes=46)).timestamp() * 1000)
    source.klines = lambda symbol, interval, limit: (
        rows(BASE - timedelta(hours=4 * 210), 210, 240) if interval == "4h"
        else rows(BASE - timedelta(minutes=30), 2, 15) + rows(BASE + timedelta(minutes=15), 1, 15)
        if interval == "15m" else rows(BASE, 2, 1)
    )
    state = session.poll()
    assert state["status"] == "QUARANTINED"
    assert "gap" in state["error"].lower()
    assert session.broker.account_snapshots == []
    assert state["completed_trades"] == 0


def test_partial_symbol_batch_waits_then_recovers(tmp_path):
    source = FakeSource()
    session = LocalPaperSession(source=source, journal_dir=tmp_path)
    session.start()
    source.phase = 1
    source.now = int((BASE + timedelta(minutes=16)).timestamp() * 1000)
    original = source.klines
    source.klines = lambda symbol, interval, limit: (
        rows(BASE - timedelta(minutes=30), 2, 15)
        if symbol == "SOLUSDT" and interval == "15m" else original(symbol, interval, limit)
    )
    assert session.poll()["status"] == "WAITING_SYNC"
    assert session.broker.account_snapshots == []
    source.klines = original
    assert session.poll()["status"] == "SCANNING"
    assert len(session.broker.account_snapshots) == 3


def test_unavailable_four_hour_signal_fails_before_broker_mutation(tmp_path):
    source = FakeSource()
    session = LocalPaperSession(source=source, journal_dir=tmp_path)
    session.start()
    for symbol in session.last_open:
        session.last_open[symbol] = BASE + timedelta(hours=3, minutes=30)
    source.now = int((BASE + timedelta(hours=4, minutes=1)).timestamp() * 1000)
    original = source.klines
    source.klines = lambda symbol, interval, limit: (
        rows(BASE + timedelta(hours=3, minutes=45), 1, 15)
        if interval == "15m" else original(symbol, interval, limit)
    )
    state = session.poll()
    assert state["status"] == "QUARANTINED"
    assert "4h signal" in state["error"]
    assert session.broker.account_snapshots == []


def test_stale_closed_bar_quarantines_before_any_paper_fill(tmp_path):
    source = FakeSource()
    session = LocalPaperSession(source=source, journal_dir=tmp_path)
    session.start()
    source.now = int((BASE + timedelta(minutes=31)).timestamp() * 1000)
    state = session.poll()
    assert state["status"] == "QUARANTINED"
    assert "stale" in state["error"].lower()
    assert session.broker.account_snapshots == []


def test_stop_is_terminal_and_keeps_zero_trade_evidence(tmp_path):
    session = LocalPaperSession(source=FakeSource(), journal_dir=tmp_path)
    session.start()
    assert session.stop()["status"] == "STOPPED"
    assert session.poll()["completed_trades"] == 0
    assert session.broker.account_snapshots == []


def test_public_source_cannot_call_exchange_order_endpoint():
    source = BinancePublicSource()
    with pytest.raises(ValueError, match="not allowed"):
        source._get("/fapi/v1/order")


def test_public_source_rejects_server_clock_drift():
    source = BinancePublicSource()
    source._get = lambda path: {"serverTime": int(time.time() * 1000) - 180_000}
    with pytest.raises(ValueError, match="clock drift"):
        source.server_time_ms()


def test_start_failure_remains_visible_and_never_creates_a_trade(tmp_path):
    source = FakeSource()
    source.server_time_ms = lambda: (_ for _ in ()).throw(ValueError("market unavailable"))
    session = LocalPaperSession(source=source, journal_dir=tmp_path)
    with pytest.raises(ValueError, match="market unavailable"):
        session.start()
    assert session.state()["status"] == "QUARANTINED"
    assert session.state()["error"] == "market unavailable"
    assert session.state()["completed_trades"] == 0
    session.stop()
    assert not list(tmp_path.glob("*.jsonl"))


def test_late_funding_event_cannot_be_backdated(tmp_path):
    source = FakeSource()
    source.funding = lambda symbol, limit: [{"fundingTime": int(BASE.timestamp() * 1000) + 3,
                                             "fundingRate": "0.0001"}]
    session = LocalPaperSession(source=source, journal_dir=tmp_path)
    with pytest.raises(ValueError, match="late exact funding"):
        session._funding_metadata("BTCUSDT", BASE)


def test_exact_funding_event_observed_after_settlement_cannot_be_backdated(tmp_path):
    source = FakeSource()
    source.funding = lambda symbol, limit: [{"fundingTime": int(BASE.timestamp() * 1000),
                                             "fundingRate": "0.0001"}]
    session = LocalPaperSession(source=source, journal_dir=tmp_path)
    with pytest.raises(ValueError, match="observed after settlement"):
        session._funding_metadata(
            "BTCUSDT", BASE, observed_ms=int((BASE + timedelta(minutes=15)).timestamp() * 1000)
        )


def stream_bar(symbol, opened=BASE, closed=True, interval="15m"):
    return {"symbol": symbol, "interval": interval, "open_time": opened,
            "close_time": opened + timedelta(minutes=15 if interval == "15m" else 1),
            "event_time": opened + timedelta(minutes=15 if interval == "15m" else 1),
            "received_at": opened + timedelta(minutes=16),
            "available_at": opened + timedelta(minutes=16), "open": 100.0, "high": 101.0,
            "low": 99.0, "close": 100.0, "volume": 5.0, "closed": closed}


def test_only_complete_three_symbol_stream_batch_reaches_broker(tmp_path):
    source = FakeSource()
    session = LocalPaperSession(source=source, journal_dir=tmp_path)
    session.start()
    session.on_connection(True, None)
    assert session.state()["status"] == "WAITING_SYNC"
    assert session.state()["risk_gate"]["admission_open"] is False
    source.phase = 1
    source.now = int((BASE + timedelta(minutes=16)).timestamp() * 1000)
    for symbol in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
        session.on_stream_event(stream_bar(symbol, closed=False))
    assert session.broker.account_snapshots == []
    session.on_stream_event(stream_bar("BTCUSDT"))
    session.on_stream_event(stream_bar("ETHUSDT"))
    assert session.broker.account_snapshots == []
    assert session.on_stream_event(stream_bar("SOLUSDT"))["status"] == "SCANNING"
    assert len(session.broker.account_snapshots) == 3
    for symbol in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
        session.on_stream_event(stream_bar(symbol))
    assert len(session.broker.account_snapshots) == 3


def test_stream_disconnect_blocks_paper_admission_until_resync(tmp_path):
    source = FakeSource()
    session = LocalPaperSession(source=source, journal_dir=tmp_path)
    session.start()
    session.on_connection(True, None)
    session.on_connection(False, "network dropped")
    assert session.state()["status"] == "WAITING_CONNECTION"
    assert session.state()["connection"]["connected"] is False
    source.phase = 1
    source.now = int((BASE + timedelta(minutes=16)).timestamp() * 1000)
    for symbol in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
        session.on_stream_event(stream_bar(symbol))
    assert session.broker.account_snapshots == []
    session.on_connection(True, None)
    for symbol in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
        session.on_stream_event(stream_bar(symbol))
    assert len(session.broker.account_snapshots) == 3


def test_restart_never_resets_existing_paper_account(tmp_path):
    source = FakeSource()
    session = LocalPaperSession(source=source, journal_dir=tmp_path)
    session.start()
    source.phase = 1
    source.now = int((BASE + timedelta(minutes=16)).timestamp() * 1000)
    session.poll()
    old_state = session.state()
    journal_path = next(tmp_path.glob("*.jsonl"))
    original_bytes = journal_path.read_bytes()
    restarted = LocalPaperSession(source=source, journal_dir=tmp_path)
    state = restarted.start()
    assert state["status"] == "RECOVERY_REQUIRED"
    assert state["session_id"] == old_state["session_id"]
    assert state["account"] == old_state["account"]
    assert state["last_processed_open_utc"] == old_state["last_processed_open_utc"]
    assert state["connection"]["connected"] is False
    assert restarted.broker is None
    assert journal_path.read_bytes() == original_bytes


def test_contiguous_gap_without_exposure_is_journaled_but_never_filled(tmp_path):
    source = FakeSource()
    session = LocalPaperSession(source=source, journal_dir=tmp_path)
    session.start()
    source.now = int((BASE + timedelta(minutes=31)).timestamp() * 1000)
    original = source.klines
    source.klines = lambda symbol, interval, limit: (
        rows(BASE - timedelta(minutes=30), 4, 15) if interval == "15m"
        else original(symbol, interval, limit))
    state = session.poll()
    assert state["status"] == "WAITING_SYNC"
    assert state["completed_trades"] == 0
    assert state["last_processed_open_utc"] is None
    assert session.broker.account_snapshots == []
    records = [json.loads(line) for line in next(tmp_path.glob("*.jsonl")).read_text(encoding="utf-8").splitlines()]
    assert [record["type"] for record in records] == ["SESSION_START", "PAPER_GAP_SKIPPED"]


def test_gap_with_pending_order_requires_recovery_before_mutation(tmp_path):
    source = FakeSource()
    session = LocalPaperSession(source=source, journal_dir=tmp_path)
    session.start()
    session.broker.pending_closes["BTCUSDT"] = BASE
    source.now = int((BASE + timedelta(minutes=31)).timestamp() * 1000)
    original = source.klines
    source.klines = lambda symbol, interval, limit: (
        rows(BASE - timedelta(minutes=30), 4, 15) if interval == "15m"
        else original(symbol, interval, limit))
    state = session.poll()
    assert state["status"] == "QUARANTINED"
    assert "exposure" in state["error"]
    assert session.broker.account_snapshots == []


def test_halted_broker_never_advertises_open_admission(tmp_path):
    session = LocalPaperSession(source=FakeSource(), journal_dir=tmp_path)
    session.start()
    session.on_connection(True, None)
    session.status = "SCANNING"
    session.broker.is_halted = True
    assert session.state()["risk_gate"]["admission_open"] is False
    assert "halted" in session.state()["risk_gate"]["reason"]


def test_synthetic_strategy_request_fills_then_stops_with_reconciled_cash(tmp_path):
    source = FakeSource()
    session = LocalPaperSession(source=source, journal_dir=tmp_path)
    session.start()

    class SyntheticSignal:
        def update_trailing_stop(self, candle, broker):
            return None

        def on_candle_close(self, candle, features, broker):
            return OrderRequest(symbol="BTCUSDT", direction="LONG", signal_price=100,
                                stop_loss_price=90, signal_time=BASE, leverage=1)

    session.strategies["BTCUSDT"] = SyntheticSignal()
    features = pd.DataFrame([{"open": 100, "high": 101, "low": 99, "close": 100, "volume": 5}],
                            index=pd.DatetimeIndex([BASE - timedelta(hours=4)]))
    session._on_signal_close(BASE, {"BTCUSDT": features})
    assert len(session.broker.pending_orders) == 1
    session.on_connection(True, None)
    source.phase = 1
    source.now = int((BASE + timedelta(minutes=16)).timestamp() * 1000)
    for symbol in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
        session.on_stream_event(stream_bar(symbol))
    assert "BTCUSDT" in session.broker.positions
    assert session.state()["orders"][0]["status"] == "FILLED"

    original = source.klines
    def stop_bar(symbol, interval, limit):
        if interval != "15m":
            return original(symbol, interval, limit)
        data = rows(BASE - timedelta(minutes=30), 4, 15)
        data[-1][3] = "89"
        return data

    source.klines = stop_bar
    source.now = int((BASE + timedelta(minutes=31)).timestamp() * 1000)
    for symbol in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
        session.on_stream_event(stream_bar(symbol, opened=BASE + timedelta(minutes=15)))
    state = session.state()
    assert state["completed_trades"] == 1
    assert state["trades"][0]["exit_reason"] == "STOP_LOSS"
    assert state["open_positions"] == []
    assert state["account"]["equity_usd"] == pytest.approx(state["account"]["wallet_usd"])
    session.broker.verify_accounting_invariants()
