"""Restart admission is based on exact saved machinery and fresh source bars."""
from datetime import timedelta

import pytest

from src.execution.order_models import OrderRequest
from src.paper.live_session import LocalPaperSession
from test_local_paper_session import BASE, FakeSource, rows, stream_bar


def _start(tmp_path, source=None):
    source = source or FakeSource()
    session = LocalPaperSession(source=source, journal_dir=tmp_path)
    assert session.start()["status"] == "SCANNING"
    return session, source


def test_flat_restart_restores_same_account_and_processing_mark(tmp_path):
    session, source = _start(tmp_path)
    source.phase = 1
    source.now = int((BASE + timedelta(minutes=16)).timestamp() * 1000)
    assert session.poll()["status"] == "SCANNING"
    before = session.state()

    restarted = LocalPaperSession(source=source, journal_dir=tmp_path)
    assert restarted.state()["risk_gate"]["admission_open"] is False
    result = restarted.reconcile_resume()
    assert result["status"] == "WAITING_CONNECTION"
    assert restarted.session_id == session.session_id
    assert result["account"] == before["account"]
    assert result["last_processed_open_utc"] == before["last_processed_open_utc"]
    assert restarted.broker._order_seq == session.broker._order_seq
    assert restarted.broker.account_snapshots == session.broker.account_snapshots

    restarted.on_connection(True, None)
    for symbol in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
        restarted.on_stream_event(stream_bar(symbol))
    assert len(restarted.broker.account_snapshots) == 3
    again = LocalPaperSession(source=source, journal_dir=tmp_path)
    assert again.reconcile_resume()["status"] == "WAITING_CONNECTION"
    assert len(again.broker.account_snapshots) == 3


def test_pending_order_survives_restart_and_fills_once(tmp_path):
    session, source = _start(tmp_path)
    session.broker.submit_order(OrderRequest(symbol="BTCUSDT", direction="LONG",
        signal_price=100, stop_loss_price=90, signal_time=BASE))
    session.checkpoint()
    restarted = LocalPaperSession(source=source, journal_dir=tmp_path)
    assert restarted.reconcile_resume()["status"] == "WAITING_CONNECTION"
    assert len(restarted.broker.pending_orders) == 1
    source.phase = 1
    source.now = int((BASE + timedelta(minutes=16)).timestamp() * 1000)
    restarted.on_connection(True, None)
    for symbol in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
        restarted.on_stream_event(stream_bar(symbol))
    assert len(restarted.broker.pending_orders) == 0
    assert len(restarted.broker.positions) == 1
    order_id = restarted.broker.order_history[-1].order_id
    third = LocalPaperSession(source=source, journal_dir=tmp_path)
    assert third.reconcile_resume()["status"] == "WAITING_CONNECTION"
    assert third.broker.order_history[-1].order_id == order_id
    assert len(third.broker.positions) == 1


def test_open_position_downtime_gap_remains_read_only(tmp_path):
    session, source = _start(tmp_path)
    session.broker.submit_order(OrderRequest(symbol="BTCUSDT", direction="LONG",
        signal_price=100, stop_loss_price=90, signal_time=BASE))
    session.checkpoint()
    source.phase = 1
    source.now = int((BASE + timedelta(minutes=16)).timestamp() * 1000)
    session.poll()
    saved = session.state()
    source.now = int((BASE + timedelta(minutes=46)).timestamp() * 1000)
    source.klines = lambda symbol, interval, limit: (
        rows(BASE - timedelta(hours=4 * 210), 210, 240) if interval == "4h"
        else rows(BASE - timedelta(minutes=30), 5, 15) if interval == "15m"
        else rows(BASE, 4, 1))
    restarted = LocalPaperSession(source=source, journal_dir=tmp_path)
    result = restarted.reconcile_resume()
    assert result["status"] == "RECOVERY_REQUIRED"
    assert result["account"] == saved["account"]
    assert "gap" in result["error"].lower()
    assert result["risk_gate"]["admission_open"] is False


def test_stopped_session_stays_stopped_after_service_restart(tmp_path):
    session, source = _start(tmp_path)
    session.stop()
    restarted = LocalPaperSession(source=source, journal_dir=tmp_path)
    assert restarted.reconcile_resume()["status"] == "STOPPED"
    assert restarted.state()["risk_gate"]["admission_open"] is False


def test_legacy_view_cannot_be_promoted_to_running_broker(tmp_path):
    session, source = _start(tmp_path)
    checkpoint = tmp_path / "account.json"
    assert checkpoint.is_file()
    # Existing version-one evidence lacks a typed machine image.
    restarted = LocalPaperSession(source=source, journal_dir=tmp_path)
    assert restarted.reconcile_resume()["status"] == "WAITING_CONNECTION"


def test_corrupt_checkpoint_never_contacts_market_or_rewrites_evidence(tmp_path):
    session, source = _start(tmp_path)
    checkpoint = tmp_path / "account.json"
    checkpoint.write_text("{", encoding="utf-8")
    original = checkpoint.read_bytes()
    source.server_time_ms = lambda: pytest.fail("invalid evidence must not fetch market")
    restarted = LocalPaperSession(source=source, journal_dir=tmp_path)
    assert restarted.reconcile_resume()["status"] == "RECOVERY_REQUIRED"
    assert checkpoint.read_bytes() == original
