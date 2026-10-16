"""Durable request-time intent must outlive the worker queue and long replay."""
from datetime import timedelta
from threading import Event, Thread
import time

import requests
import pytest

from src.execution.order_models import OrderRequest
from test_local_paper_session import BASE
from test_local_paper_server import await_operation
from test_paper_replay_recovery import RangeSource


def server_fixture(tmp_path, monkeypatch, clock):
    from src.paper import local_server
    class OfflineStream:
        def __init__(self, *args): pass
        def run(self): pass
        def close(self): pass
    monkeypatch.setattr(local_server, 'PublicKlineStream', OfflineStream)
    source = RangeSource()
    server = local_server.create_server(port=0, source=source, journal_dir=tmp_path, clock=clock)
    assert server.session.start()['status'] == 'SCANNING'
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, source, thread, f'http://127.0.0.1:{server.server_port}'


def test_pause_is_durable_before_waiting_for_busy_account_writer(tmp_path, monkeypatch):
    stamp = BASE + timedelta(minutes=31)
    server, _, thread, url = server_fixture(tmp_path, monkeypatch, lambda: stamp)
    try:
        with server.session.lock:
            reply = requests.post(url + '/api/pause', timeout=2)
            assert reply.status_code == 202
            operation = reply.json()['operation']
            receipts = [e for e in server.session.storage.events()['items'] if e['kind'] == 'OPERATOR_REQUEST']
            assert len(receipts) == 1, 'HTTP accepted a pause without a durable request receipt'
            assert receipts[0]['requested_at_utc'] == '2026-09-27T04:31:00+00:00'
            assert receipts[0]['request_id'] == operation['id']
            assert operation['durable'] is True
            assert operation['status'] in ('PENDING', 'RUNNING')
        assert await_operation(server)['status'] == 'APPLIED'
        assert server.session.runner.controls[-1]['effective_at_utc'] == '2026-09-27T04:31:00+00:00'
    finally:
        server.shutdown()
        thread.join(5)
        server.server_close()


def test_queued_stop_uses_request_time_for_next_outage_fill(tmp_path, monkeypatch):
    now = {'time': BASE + timedelta(minutes=31)}
    server, source, thread, url = server_fixture(tmp_path, monkeypatch, lambda: now['time'])
    session = server.session
    session.broker.submit_order(OrderRequest(symbol='BTCUSDT', direction='LONG',
        signal_price=100, stop_loss_price=90, signal_time=BASE, requested_quantity=1))
    session.checkpoint()
    entered, release = Event(), Event()
    original = source.klines_range
    def slow(*args):
        entered.set()
        assert release.wait(5)
        return original(*args)
    source.klines_range = slow
    source.now = int((BASE + timedelta(minutes=30, seconds=1)).timestamp() * 1000)
    replay = Thread(target=lambda: session.on_connection(True, None))
    replay.start()
    try:
        assert entered.wait(3)
        reply = requests.post(url + '/api/stop', timeout=2)
        assert reply.status_code == 202
        request_id = reply.json()['operation']['id']
        now['time'] = BASE + timedelta(minutes=61)
        release.set()
        replay.join(5)
        assert not replay.is_alive()
        assert await_operation(server)['status'] == 'APPLIED'
        source.klines_range = original
        source.now = int((BASE + timedelta(minutes=60, seconds=1)).timestamp() * 1000)
        session.poll()
        assert session.runner.controls[-1]['effective_at_utc'] == '2026-09-27T04:31:00+00:00'
        assert not session.broker.positions
        assert session.broker.trade_history[0].exit_time == BASE + timedelta(minutes=45)
        assert session.state()['status'] == 'STOPPED'
        events = session._all_events()
        assert len([e for e in events if e['kind'] == 'OPERATOR_INTENT' and e.get('request_id') == request_id]) == 1
    finally:
        release.set()
        replay.join(5)
        server.shutdown()
        thread.join(5)
        server.server_close()


def test_resume_after_terminal_stop_is_not_reported_as_applied(tmp_path, monkeypatch):
    server, source, thread, url = server_fixture(tmp_path, monkeypatch, lambda: BASE)
    try:
        assert requests.post(url + '/api/stop', timeout=2).status_code == 202
        assert await_operation(server)['status'] == 'APPLIED'
        assert server.session.state()['status'] == 'STOPPED'
        reply = requests.post(url + '/api/resume', timeout=2)
        if reply.status_code == 202:
            assert await_operation(server)['status'] == 'FAILED'
        else:
            assert reply.status_code in (409, 503)
        assert server.session.state()['operator_intent'] == 'STOPPED'
    finally:
        server.shutdown()
        thread.join(5)
        server.server_close()


def test_queued_resume_cannot_roll_back_an_already_requested_terminal_stop(tmp_path, monkeypatch):
    server, _, thread, url = server_fixture(tmp_path, monkeypatch, lambda: BASE)
    try:
        with server.session.lock:
            assert requests.post(url + '/api/stop', timeout=2).status_code == 202
            response = requests.post(url + '/api/resume', timeout=2)
            assert response.status_code == 202
            request_id = response.json()['operation']['id']
        assert await_operation(server)['status'] == 'FAILED'
        assert server.session.state()['status'] == 'STOPPED'
        assert server.session.state()['operator_intent'] == 'STOPPED'
        completion = server.session.storage.control_application(request_id)
        assert completion['kind'] == 'OPERATOR_REJECTED'
        assert not server.session.storage.pending_controls()
        assert len([e for e in server.session._all_events() if e['kind'] == 'OPERATOR_INTENT']) == 1
    finally:
        server.shutdown()
        thread.join(5)
        server.server_close()


def test_accepted_request_survives_crash_before_worker_application(tmp_path):
    from src.paper.replay_session import PaperReplaySession
    from test_paper_replay_recovery import create
    session, source = create(tmp_path)
    session.broker.submit_order(OrderRequest(symbol='BTCUSDT', direction='LONG',
        signal_price=100, stop_loss_price=90, signal_time=BASE, requested_quantity=1))
    session.checkpoint()
    stamp = BASE + timedelta(minutes=1)
    command = {'id': 'crash-before-application', 'name': 'pause', 'requested_at_utc': stamp.isoformat()}
    assert session.accept_control_request(command)['durable'] is True
    assert session.runner.intent == 'RUNNING'
    session.shutdown()
    source.now = int((BASE + timedelta(minutes=31)).timestamp() * 1000)
    states = []
    for _ in range(3):
        recovered = PaperReplaySession(source=source, journal_dir=tmp_path, auto_resume=True)
        try:
            assert recovered.status == 'WAITING_CONNECTION', recovered.error
            assert recovered.runner.intent == 'PAUSED'
            assert recovered.runner.controls[-1]['effective_at_utc'] == '2026-09-27T04:01:00+00:00'
            assert len(recovered.broker.positions) == 1  # Opening at 04:00 preceded the pause request.
            assert len(recovered.broker.order_history) == 1
            assert recovered.storage.pending_controls() == []
            assert len([e for e in recovered._all_events() if e['kind'] == 'OPERATOR_INTENT']) == 1
            states.append((recovered.broker.wallet_balance, len(recovered.broker.funding_history),
                           recovered.runner.trials.total_capital_injected))
        finally:
            recovered.shutdown()
    assert states[0] == states[1] == states[2]
    assert states[0][2] == 10000


def test_backward_control_timestamp_fails_closed_without_rewriting_it(tmp_path):
    from test_paper_replay_recovery import create
    session, _ = create(tmp_path)
    original = session.runner.capture()
    command = {'id': 'clock-went-backward', 'name': 'pause',
               'requested_at_utc': (BASE - timedelta(seconds=1)).isoformat()}
    try:
        session.accept_control_request(command)
        with pytest.raises(ValueError, match='backdate'):
            session.apply_control_request(command)
        assert session.state()['status'] == 'RECOVERY_REQUIRED'
        assert session.runner.capture() == original
        assert session.storage.pending_controls()[0]['requested_at_utc'] == '2026-09-27T03:59:59+00:00'
        assert not session.state()['risk_gate']['admission_open']
    finally:
        session.shutdown()


def test_unapplied_terminal_stop_restores_without_requiring_network(tmp_path):
    from src.paper.replay_session import PaperReplaySession
    from test_paper_replay_recovery import create
    session, source = create(tmp_path)
    session.accept_control_request({'id': 'stop-before-crash', 'name': 'stop',
                                    'requested_at_utc': BASE.isoformat()})
    session.shutdown()
    source.offline = True
    recovered = PaperReplaySession(source=source, journal_dir=tmp_path, auto_resume=True)
    try:
        assert recovered.status == 'STOPPED', recovered.error
        assert recovered.runner.intent == 'STOPPED'
        assert not recovered.storage.pending_controls()
        assert recovered.runner.trials.total_capital_injected == 10000
    finally:
        recovered.shutdown()
