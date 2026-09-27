"""Loopback-only static web and local paper-session API."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
from threading import Event, Lock, Thread
from urllib.parse import unquote, urlparse
import webbrowser

from src.paper.live_session import LocalPaperSession, PROJECT_ROOT
from src.paper.public_stream import PublicKlineStream


def host_allowed(host, server_port=8765):
    return host in (f"127.0.0.1:{server_port}", f"localhost:{server_port}")


def origin_allowed(origin, server_port=8765):
    if origin is None:
        return True
    parsed = urlparse(origin)
    return parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "localhost") and parsed.port in (server_port, 5173)


def public_path(root, requested):
    route = unquote(urlparse(requested).path)
    if route.startswith("/api/"):
        return None
    root = Path(root).resolve()
    relative = route.lstrip("/") or "index.html"
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root) or not candidate.is_file():
        return None
    return candidate


def serve(port=8765, source=None, journal_dir=None, open_browser=False):
    root = PROJECT_ROOT / "web-preview/dist"
    session = LocalPaperSession(source=source, journal_dir=journal_dir)
    stopped = Event()
    worker = None
    stream = None
    worker_lock = Lock()

    class Handler(BaseHTTPRequestHandler):
        def _local_host(self):
            if host_allowed(self.headers.get("Host"), server_port=port):
                return True
            self._json(403, {"error": "non-loopback host rejected"})
            return False

        def _json(self, code, payload):
            body = json.dumps(payload, allow_nan=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            origin = self.headers.get("Origin")
            if origin and origin_allowed(origin, server_port=port):
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self):
            if not self._local_host():
                return
            origin = self.headers.get("Origin")
            if not origin or not origin_allowed(origin, server_port=port):
                self._json(403, {"error": "cross-site origin rejected"})
                return
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self):
            if not self._local_host():
                return
            if urlparse(self.path).path == "/api/state":
                self._json(200, session.state())
                return
            if urlparse(self.path).path == "/api/health":
                state = session.state()
                self._json(200, {"mode": "PAPER_RESEARCH", "status": state["status"],
                                 "connection": state["connection"], "session_id": state["session_id"]})
                return
            target = public_path(root, self.path)
            if target is None:
                self._json(404, {"error": "not found"})
                return
            body = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if not self._local_host():
                return
            if not origin_allowed(self.headers.get("Origin"), server_port=port):
                self._json(403, {"error": "cross-site origin rejected"})
                return
            if self.path not in ("/api/start", "/api/stop"):
                self._json(404, {"error": "not found"})
                return
            if self.headers.get("Content-Length", "0") != "0":
                self._json(400, {"error": "request body not accepted"})
                return
            nonlocal worker, stream
            try:
                if self.path == "/api/start":
                    with worker_lock:
                        result = session.start()
                        if result["status"] == "SCANNING" and (worker is None or not worker.is_alive()):
                            stopped.clear()
                            stream = PublicKlineStream(session.on_stream_event, session.on_connection, stopped)
                            worker = Thread(target=stream.run, name="binance-public-kline", daemon=True)
                            worker.start()
                else:
                    with worker_lock:
                        stopped.set()
                        if stream is not None:
                            stream.close()
                        result = session.stop()
                self._json(200, result)
            except Exception as exc:
                self._json(503, {"error": str(exc), "status": "UNAVAILABLE", "mode": "PAPER_RESEARCH"})

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"PAPER/RESEARCH local web: http://127.0.0.1:{port}/", flush=True)
    if open_browser:
        webbrowser.open(f"http://127.0.0.1:{port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stopped.set()
        if stream is not None:
            stream.close()
        session.stop()
        server.server_close()
