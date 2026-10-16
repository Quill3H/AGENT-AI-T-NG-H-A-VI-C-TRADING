from threading import Event, Thread
import time

import requests

from test_paper_replay_recovery import RangeSource
from test_local_paper_server import await_operation


def test_api_returns_pending_start_and_health_while_source_stalls(tmp_path, monkeypatch):
    from src.paper import local_server
    class OfflineStream:
        def __init__(self, *args):
            pass
        def run(self):
            pass
        def close(self):
            pass
    monkeypatch.setattr(local_server, 'PublicKlineStream', OfflineStream)
    source = RangeSource()
    entered, release = Event(), Event()
    original = source.server_time_ms
    def slow():
        entered.set()
        assert release.wait(5)
        return original()
    source.server_time_ms = slow
    server = local_server.create_server(port=0, source=source, journal_dir=tmp_path)
    serving = Thread(target=server.serve_forever, daemon=True)
    serving.start()
    url = f'http://127.0.0.1:{server.server_port}'
    try:
        started = time.monotonic()
        reply = requests.post(url + '/api/start', timeout=1)
        assert reply.status_code == 202
        assert time.monotonic() - started < 1
        assert entered.wait(1)
        health = requests.get(url + '/api/health', timeout=1).json()
        assert health['api_version'] == 3
        assert not health['risk_gate']['admission_open']
        duplicate = requests.post(url + '/api/start', timeout=1).json()
        assert duplicate['operation']['id'] == reply.json()['operation']['id']
        release.set()
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            state = requests.get(url + '/api/state', timeout=1).json()
            if state['operation']['status'] == 'APPLIED':
                break
            time.sleep(.01)
        assert state['session_id']
        assert state['trials']['total_capital_injected_usd'] == 10000
        response = requests.post(url + '/api/pause', timeout=1)
        assert response.status_code in (200, 202)
        assert await_operation(server)['status'] == 'APPLIED'
        assert requests.get(url + '/api/history?limit=bad', timeout=1).status_code == 400
        events = requests.get(url + '/api/history?limit=100', timeout=1).json()
        assert len([e for e in events['items'] if e['kind'] == 'ACCOUNT_START']) == 1
    finally:
        release.set()
        server.shutdown()
        serving.join(5)
        server.server_close()
