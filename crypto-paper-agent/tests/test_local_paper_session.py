from datetime import datetime, timedelta, timezone
import json
import time

import pytest

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
