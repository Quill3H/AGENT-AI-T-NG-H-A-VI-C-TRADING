"""Deterministic integration checks for the local paper futures contract."""

from datetime import timedelta
import json
import threading

import pandas as pd
import pytest
import requests

from src.paper.live_session import LocalPaperSession
from src.paper.local_server import create_server
from src.strategies.trend_following import SetupState
from src.execution.order_models import OrderDirection
from test_local_paper_session import BASE, FakeSource, rows, stream_bar


def _features():
    opened = BASE - timedelta(hours=4)
    return pd.DataFrame([{
        "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0,
        "volume": 5.0,
    }], index=pd.DatetimeIndex([opened]))


class _SignalStrategy:
    def update_trailing_stop(self, candle, broker):
        return None

    def on_candle_close(self, candle, features, broker):
        from src.execution.order_models import OrderRequest
        return OrderRequest(
            symbol="BTCUSDT", direction="LONG", signal_price=100.0,
            stop_loss_price=90.0, signal_time=candle["close_time"], leverage=1.0,
        )


class _NoSignalStrategy:
    def update_trailing_stop(self, candle, broker):
        return None

    def on_candle_close(self, candle, features, broker):
        return None


def _start_server(source, journal_dir):
    server = create_server(port=0, source=source, journal_dir=journal_dir)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    return server, worker


def test_chart_api_is_read_only_closed_only_bounded_and_strict(tmp_path):
    source = FakeSource()
    server, worker = _start_server(source, tmp_path)
    try:
        url = f"http://127.0.0.1:{server.server_port}/api/chart"
        before = requests.get(f"http://127.0.0.1:{server.server_port}/api/state", timeout=2).json()
        response = requests.get(url, params={"symbol": "BTCUSDT", "interval": "1m"}, timeout=2)
        assert response.status_code == 200
        payload = response.json()
        assert set(payload) == {"symbol", "interval", "source_time_utc", "candles"}
        assert payload["symbol"] == "BTCUSDT"
        assert payload["interval"] == "1m"
        assert payload["candles"]
        assert len(payload["candles"]) <= 200
        assert all(set(candle) == {"time_utc", "open", "high", "low", "close"}
                   for candle in payload["candles"])
        assert all(candle["time_utc"] < payload["source_time_utc"]
                   for candle in payload["candles"])
        calls_after_first = len(source.calls)
        cached = requests.get(url, params={"symbol": "BTCUSDT", "interval": "1m"}, timeout=2)
        assert cached.status_code == 200
        assert len(source.calls) == calls_after_first
        assert not list(tmp_path.glob("*.jsonl"))
        after = requests.get(f"http://127.0.0.1:{server.server_port}/api/state", timeout=2).json()
        for key in ("status", "account", "orders", "pending_orders", "open_positions", "trades"):
            assert after[key] == before[key]

        assert requests.get(url + "?symbol=BTCUSDT&interval=1m&extra=x", timeout=2).status_code == 400
        assert requests.get(url + "?symbol=XRPUSDT&interval=1m", timeout=2).status_code == 400
        assert requests.get(url + "?symbol=BTCUSDT&interval=2h", timeout=2).status_code == 400
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)


def test_chart_source_failure_is_explicit_and_does_not_quarantine_session(tmp_path):
    source = FakeSource()
    server, worker = _start_server(source, tmp_path)
    try:
        def unavailable(*args, **kwargs):
            raise RuntimeError("Binance public chart unavailable")

        source.server_time_ms = unavailable
        response = requests.get(
            f"http://127.0.0.1:{server.server_port}/api/chart",
            params={"symbol": "ETHUSDT", "interval": "15m"}, timeout=2,
        )
        assert response.status_code == 502
        assert "public chart source unavailable" in response.json()["error"]
        state = requests.get(f"http://127.0.0.1:{server.server_port}/api/state", timeout=2).json()
        assert state["status"] == "IDLE"
        assert state["account"]["wallet_usd"] == 10000.0
        assert not list(tmp_path.glob("*.jsonl"))
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)


def test_trend_decision_is_pending_then_fills_at_next_15m_open(tmp_path):
    source = FakeSource()
    session = LocalPaperSession(source=source, journal_dir=tmp_path)
    session.start()
    session.strategies["BTCUSDT"] = _SignalStrategy()
    session._on_signal_close(BASE, {"BTCUSDT": _features()})
    assert session.state()["strategy_decisions"]["BTCUSDT"]["state"] == "SIGNAL_PENDING"
    assert len(session.broker.pending_orders) == 1

    source.phase = 1
    source.now = int((BASE + timedelta(minutes=16)).timestamp() * 1000)
    state = session.poll()
    assert state["strategy_decisions"]["BTCUSDT"]["state"] == "POSITION_OPEN"
    assert state["orders"][0]["status"] == "FILLED"
    assert state["open_positions"][0]["symbol"] == "BTCUSDT"
    assert state["orders"][0]["requested_at_utc"] == BASE.isoformat()


def test_real_trend_rulebook_uses_closed_4h_then_next_15m_open(tmp_path, monkeypatch):
    source = FakeSource()
    session = LocalPaperSession(source=source, journal_dir=tmp_path)
    session.start()
    strategy = session.strategies["BTCUSDT"]
    strategy.setup.state = SetupState.ARMED
    strategy.setup.direction = OrderDirection.LONG
    strategy.setup.trigger_time = BASE - timedelta(hours=4)
    strategy.setup.setup_age_bars = 0

    original = source.klines
    def timed_klines(symbol, interval, limit):
        if interval == "15m":
            start = BASE + timedelta(hours=3, minutes=30) + (timed_klines.step * timedelta(minutes=15))
            return rows(start, 2, 15)
        if interval == "4h":
            return rows(BASE - timedelta(hours=4 * 209), 210, 240)
        return original(symbol, interval, limit)

    timed_klines.step = 0
    source.klines = timed_klines
    for symbol in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
        session.last_open[symbol] = BASE + timedelta(hours=3, minutes=30)
        session.last_4h[symbol] = BASE - timedelta(hours=4)

    def features(frame, config):
        frame = frame.copy()
        frame["ema_20"] = 99.0
        frame["ema_50"] = 98.0
        frame["ema_200"] = 80.0
        frame["rsi_14"] = 60.0
        frame["oi_delta_pct"] = 1.0
        return frame

    monkeypatch.setattr("src.paper.live_session.add_all_features", features)
    source.now = int((BASE + timedelta(hours=4, minutes=1)).timestamp() * 1000)
    state = session.poll()
    assert state["status"] == "SCANNING"
    assert state["strategy_decisions"]["BTCUSDT"]["state"] == "SIGNAL_PENDING"
    assert state["strategy_decisions"]["BTCUSDT"]["time_utc"] == (BASE + timedelta(hours=4)).isoformat()
    assert state["orders"][0]["status"] == "PENDING"
    assert state["open_positions"] == []
    assert len(session.broker.account_snapshots) == 3

    timed_klines.step = 1
    source.now = int((BASE + timedelta(hours=4, minutes=16)).timestamp() * 1000)
    state = session.poll()
    assert state["orders"][0]["status"] == "FILLED"
    assert state["orders"][0]["processed_at_utc"] == (BASE + timedelta(hours=4)).isoformat()
    assert state["strategy_decisions"]["BTCUSDT"]["state"] == "POSITION_OPEN"
    assert len(session.broker.account_snapshots) == 6


def test_no_signal_and_locked_risk_are_backend_decisions(tmp_path):
    source = FakeSource()
    session = LocalPaperSession(source=source, journal_dir=tmp_path)
    session.start()
    session.strategies["BTCUSDT"] = _NoSignalStrategy()
    session._on_signal_close(BASE, {"BTCUSDT": _features()})
    assert session.state()["strategy_decisions"]["BTCUSDT"]["state"] == "NO_SIGNAL"

    session.strategies["BTCUSDT"] = _SignalStrategy()
    session._on_signal_close(BASE, {"BTCUSDT": _features()})
    session.broker.circuit_breaker.is_locked = True
    source.phase = 1
    source.now = int((BASE + timedelta(minutes=16)).timestamp() * 1000)
    state = session.poll()
    decision = state["strategy_decisions"]["BTCUSDT"]
    assert decision["state"] == "ORDER_REJECTED"
    assert "CIRCUIT_BREAKER" in " ".join(state["orders"][-1]["rejection_reasons"])
    assert not state["open_positions"]


def test_decision_snapshot_is_journaled_and_restored_without_duplicate_processing(tmp_path):
    source = FakeSource()
    session = LocalPaperSession(source=source, journal_dir=tmp_path)
    session.start()
    session.strategies["BTCUSDT"] = _NoSignalStrategy()
    session._on_signal_close(BASE, {"BTCUSDT": _features()})
    session.checkpoint()
    records = [json.loads(line) for line in next(tmp_path.glob("*.jsonl")).read_text(encoding="utf-8").splitlines()]
    assert records[-1]["type"] == "PAPER_CHECKPOINT"
    assert records[-1]["state"]["strategy_decisions"]["BTCUSDT"]["state"] == "NO_SIGNAL"

    restarted = LocalPaperSession(source=source, journal_dir=tmp_path)
    assert restarted.state()["status"] == "RECOVERY_REQUIRED"
    assert restarted.state()["strategy_decisions"]["BTCUSDT"]["state"] == "NO_SIGNAL"
    assert restarted.state()["account"]["wallet_usd"] == 10000.0
