from src.paper.local_server import host_allowed, origin_allowed, public_path


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
