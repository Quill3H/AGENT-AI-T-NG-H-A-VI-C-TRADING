from src.paper.local_server import host_allowed, origin_allowed, public_path
import threading
import requests
import pytest
from test_local_paper_session import FakeSource


def test_local_api_rejects_cross_site_origins():
    assert origin_allowed("http://127.0.0.1:8765")
    assert origin_allowed("http://localhost:5173")
    assert origin_allowed("http://127.0.0.1:8766", server_port=8766)
    assert not origin_allowed("https://outside.example")
    assert not origin_allowed("http://127.0.0.1.evil.example:8765")


def test_loopback_host_header_rejects_dns_rebinding():
    assert host_allowed("127.0.0.1:8765")
    assert host_allowed("localhost:8765")
    assert not host_allowed("outside.example:8765")
    assert not host_allowed("localhost.evil.example:8765")
    assert not host_allowed("localhost:5173")


def test_static_server_does_not_escape_built_web_root(tmp_path):
    (tmp_path / "index.html").write_text("paper", encoding="utf-8")
    assert public_path(tmp_path, "/") == tmp_path / "index.html"
    assert public_path(tmp_path, "/../../config/default_config.yaml") is None
    assert public_path(tmp_path, "/api/unknown") is None


def test_malformed_origin_is_denied_without_crashing_handler():
    assert not origin_allowed('http://localhost:bad')
    assert not origin_allowed('http://[broken')
    assert not origin_allowed('http://user@localhost:8765')


@pytest.fixture
def api(tmp_path):
    from src.paper.local_server import create_server
    server = create_server(port=0, source=FakeSource(), journal_dir=tmp_path)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    yield f'http://127.0.0.1:{server.server_port}', server
    server.shutdown()
    server.server_close()
    worker.join(timeout=5)


def test_http_health_recovery_start_stop_and_errors(api, tmp_path):
    url, server = api
    health = requests.get(url + '/api/health', timeout=2)
    assert health.status_code == 200
    assert health.json()['api_time_utc']
    assert health.json()['risk_gate']['admission_open'] is False
    assert requests.post(url + '/api/start', data='bad', timeout=2).status_code == 400
    assert requests.post(url + '/api/start', headers={'Origin': 'http://localhost:bad'}, timeout=2).status_code == 403
    # Evidence created after construction must still block the first Start.
    (tmp_path / 'state.json').write_text('{', encoding='utf-8')
    for endpoint in ('start', 'start', 'stop', 'stop'):
        reply = requests.post(url + '/api/' + endpoint, timeout=3)
        assert reply.status_code == 200
        assert reply.json()['status'] == 'RECOVERY_REQUIRED'
        assert reply.json()['account']['wallet_usd'] is None
    assert requests.get(url + '/api/missing', timeout=2).status_code == 404


def test_second_server_cannot_bind_same_port(api, tmp_path):
    from src.paper.local_server import create_server
    _, first = api
    with pytest.raises(OSError):
        duplicate = create_server(port=first.server_port, source=FakeSource(), journal_dir=tmp_path)
        duplicate.server_close()


def test_api_source_failure_keeps_state_contract(api):
    url, server = api
    def unavailable():
        raise ValueError('public data unavailable')
    server.session.source.server_time_ms = unavailable
    response = requests.post(url + '/api/start', timeout=3)
    assert response.status_code == 503
    assert response.json()['status'] == 'QUARANTINED'
    assert response.json()['account']['equity_usd'] == 10000
    assert response.json()['risk_gate']['admission_open'] is False
    assert response.json()['api_time_utc']
