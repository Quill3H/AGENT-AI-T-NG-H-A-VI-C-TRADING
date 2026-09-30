"""Account writer ownership, tested with real Windows sockets and processes."""
from pathlib import Path
import subprocess
import sys

import pytest

from src.paper.live_session import LocalPaperSession
from src.paper.local_server import create_server
from test_local_paper_session import FakeSource


@pytest.mark.parametrize("alias", ["plain", "dot", "parent", "case"])
def test_servers_on_different_ports_cannot_own_the_same_account(tmp_path, alias):
    if alias == "case" and sys.platform != "win32":
        pytest.skip("case-insensitive path alias is a Windows contract")
    paths = {"plain": tmp_path, "dot": tmp_path / ".", "parent": tmp_path / "child" / "..", "case": Path(str(tmp_path).upper())}
    first = create_server(port=0, source=FakeSource(), journal_dir=tmp_path)
    second = None
    try:
        before = {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.suffix in (".json", ".jsonl")}
        with pytest.raises(RuntimeError, match="account.*in use"):
            second = create_server(port=0, source=FakeSource(), journal_dir=paths[alias])
        assert {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.suffix in (".json", ".jsonl")} == before
        assert first.session.state()["status"] == "IDLE"
    finally:
        if second is not None:
            second.server_close()
        first.server_close()


def test_direct_session_cannot_start_under_server_owner(tmp_path):
    first = create_server(port=0, source=FakeSource(), journal_dir=tmp_path)
    other = LocalPaperSession(source=FakeSource(), journal_dir=tmp_path)
    try:
        with pytest.raises(RuntimeError, match="account.*in use"):
            other.start()
        assert not (tmp_path / "account.json").exists()
    finally:
        other.shutdown()
        first.server_close()


def test_read_only_inspection_does_not_grant_write_rights(tmp_path):
    first = LocalPaperSession(source=FakeSource(), journal_dir=tmp_path)
    try:
        assert first.start()["status"] == "SCANNING"
        view = LocalPaperSession(source=FakeSource(), journal_dir=tmp_path)
        before = (tmp_path / "account.json").read_bytes()
        assert view.state()["status"] == "RECOVERY_REQUIRED"
        assert view.state()["session_id"] == first.session_id
        with pytest.raises(RuntimeError, match="account.*in use"):
            view.reconcile_resume()
        assert (tmp_path / "account.json").read_bytes() == before
    finally:
        first.shutdown()


def test_shutdown_releases_owner_but_cannot_reactivate_old_session(tmp_path):
    first = LocalPaperSession(source=FakeSource(), journal_dir=tmp_path)
    assert first.start()["status"] == "SCANNING"
    first.shutdown()
    before = (tmp_path / "account.json").read_bytes()
    first.shutdown()
    with pytest.raises(RuntimeError, match="shut down|ownership"):
        first.checkpoint()
    assert (tmp_path / "account.json").read_bytes() == before
    second = create_server(port=0, source=FakeSource(), journal_dir=tmp_path)
    try:
        assert second.session.state()["session_id"] == first.session_id
        assert second.session.state()["status"] == "WAITING_CONNECTION"
    finally:
        second.server_close()


def test_different_accounts_remain_independent(tmp_path):
    first = create_server(port=0, source=FakeSource(), journal_dir=tmp_path / "a")
    second = create_server(port=0, source=FakeSource(), journal_dir=tmp_path / "b")
    try:
        assert first.session.state()["status"] == second.session.state()["status"] == "IDLE"
    finally:
        first.server_close()
        second.server_close()


def test_late_transport_callback_cannot_reopen_shutdown_admission(tmp_path):
    from datetime import timedelta
    from test_local_paper_session import BASE, stream_bar
    source = FakeSource()
    session = LocalPaperSession(source=source, journal_dir=tmp_path)
    session.start()
    session.shutdown()
    before = (tmp_path / "account.json").read_bytes()
    session.on_connection(True, None)
    source.phase = 1
    source.now = int((BASE + timedelta(minutes=16)).timestamp() * 1000)
    for symbol in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
        session.on_stream_event(stream_bar(symbol))
    assert session.state()["connection"]["connected"] is False
    assert session.state()["risk_gate"]["admission_open"] is False
    assert session.broker.account_snapshots == []
    assert session.poll()["connection"]["connected"] is False
    assert (tmp_path / "account.json").read_bytes() == before


def test_process_death_releases_account_without_deleting_evidence(tmp_path):
    code = """
import sys
sys.path.insert(0, 'tests')
from src.paper.local_server import create_server
from test_local_paper_session import FakeSource
server = create_server(port=0, source=FakeSource(), journal_dir=sys.argv[1])
print('OWNER_READY', flush=True)
sys.stdin.readline()
server.server_close()
"""
    process = subprocess.Popen([sys.executable, "-u", "-c", code, str(tmp_path)],
                               cwd=Path(__file__).resolve().parents[1], stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    duplicate = None
    try:
        assert process.stdout.readline().strip() == "OWNER_READY"
        with pytest.raises(RuntimeError, match="account.*in use"):
            duplicate = create_server(port=0, source=FakeSource(), journal_dir=tmp_path)
    finally:
        if duplicate is not None:
            duplicate.server_close()
        process.terminate()
        process.communicate(timeout=15)
    successor = create_server(port=0, source=FakeSource(), journal_dir=tmp_path)
    try:
        assert successor.session.state()["status"] == "IDLE"
        assert not (tmp_path / "account.json").exists()
    finally:
        successor.server_close()


def test_unknown_operational_file_remains_recovery_evidence(tmp_path):
    (tmp_path / "unexpected.lock").write_text("not our marker", encoding="ascii")
    server = create_server(port=0, source=FakeSource(), journal_dir=tmp_path)
    try:
        assert server.session.state()["status"] == "RECOVERY_REQUIRED"
        assert server.session.state()["account"]["wallet_usd"] is None
    finally:
        server.server_close()


def test_start_during_server_teardown_cannot_allocate_account(tmp_path, monkeypatch):
    from threading import Event, Thread
    import requests
    from src.paper import local_server
    # Substitute only the external socket transport; real HTTP/session/storage run.
    class OfflineTransport:
        def __init__(self, *args):
            pass
        def run(self):
            pass
        def close(self):
            pass
    monkeypatch.setattr(local_server, "PublicKlineStream", OfflineTransport)
    server = create_server(port=0, source=FakeSource(), journal_dir=tmp_path)
    serving = Thread(target=server.serve_forever, daemon=True)
    serving.start()
    entered, release = Event(), Event()
    original_shutdown = server.session.shutdown
    def delayed_shutdown():
        entered.set()
        if not release.wait(5):
            raise RuntimeError("test teardown synchronization timed out")
        return original_shutdown()
    monkeypatch.setattr(server.session, "shutdown", delayed_shutdown)
    closing = Thread(target=server.server_close, daemon=True)
    closing.start()
    try:
        assert entered.wait(2)
        response = requests.post(f"http://127.0.0.1:{server.server_port}/api/start", timeout=2)
        assert response.status_code == 503
        assert not (tmp_path / "account.json").exists()
    finally:
        server.shutdown()
        serving.join(timeout=5)
        release.set()
        closing.join(timeout=5)
