"""Cross-branch regressions for paper recovery and transport."""

from threading import Event

from src.paper.live_session import LocalPaperSession
from src.paper.local_server import create_server
from src.paper.public_stream import STREAM_URL
from test_local_paper_session import FakeSource


def test_corrupt_legacy_account_never_resets_balance_or_rewrites_evidence(tmp_path):
    legacy = tmp_path / "persistent_state.json"
    legacy.write_bytes(b"{broken")
    source = FakeSource()
    source.server_time_ms = lambda: (_ for _ in ()).throw(AssertionError("market fetch on corrupt evidence"))
    session = LocalPaperSession(source=source, journal_dir=tmp_path, auto_resume=True)
    assert session.state()["status"] == "RECOVERY_REQUIRED"
    assert session.state()["risk_gate"]["admission_open"] is False
    assert session.start()["status"] == "RECOVERY_REQUIRED"
    assert legacy.read_bytes() == b"{broken"
    assert not (tmp_path / "state.json").exists()


def test_restarted_server_starts_transport_without_browser_request(tmp_path, monkeypatch):
    started = Event()

    class ObservedStream:
        def __init__(self, on_event, on_connection, stopped):
            self.stopped = stopped

        def run(self):
            started.set()
            self.stopped.wait(2)

        def close(self):
            pass

    monkeypatch.setattr("src.paper.local_server.PublicKlineStream", ObservedStream)
    first = create_server(port=0, source=FakeSource(), journal_dir=tmp_path)
    assert first.session.start()["status"] == "SCANNING"
    first.server_close()
    second = create_server(port=0, source=FakeSource(), journal_dir=tmp_path)
    try:
        assert second.session.state()["status"] == "WAITING_CONNECTION"
        assert started.wait(1)
        assert second.session.stop()["status"] == "STOPPED"
    finally:
        second.server_close()
    started.clear()
    third = create_server(port=0, source=FakeSource(), journal_dir=tmp_path)
    try:
        assert third.session.status == "STOPPED"
        assert not started.wait(.1)
    finally:
        third.server_close()


def test_closed_chart_contract_keeps_three_symbols(tmp_path):
    session = LocalPaperSession(source=FakeSource(), journal_dir=tmp_path)
    assert session.start()["status"] == "SCANNING"
    state = session.state()
    assert set(state["charts"]) == {"BTCUSDT", "ETHUSDT", "SOLUSDT"}
    assert state["chart"] == state["charts"]["BTCUSDT"]


def test_binance_public_kline_stream_uses_market_route():
    assert STREAM_URL.startswith("wss://fstream.binance.com/market/stream?streams=")
