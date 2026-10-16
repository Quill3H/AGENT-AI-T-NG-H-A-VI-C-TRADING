"""Loopback-only static web and local paper-session API."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
import socket
from pathlib import Path
from threading import Event, Lock, Thread
from urllib.parse import parse_qs, unquote, urlparse
import webbrowser

from src.paper.live_session import PROJECT_ROOT
from src.paper.replay_session import DEFAULT_ACCOUNT_DIR, PaperReplaySession
from src.paper.commands import PaperCommands
from src.paper.public_stream import PublicKlineStream
from src.paper.account_lock import AccountOwnershipLock


def host_allowed(host, server_port=8765):
    return host in (f"127.0.0.1:{server_port}", f"localhost:{server_port}")


def origin_allowed(origin, server_port=8765):
    if origin is None:
        return True
    try:
        parsed = urlparse(origin)
        return (parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "localhost")
                and parsed.port in (server_port, 5173) and parsed.username is None
                and parsed.password is None and not parsed.path and not parsed.query and not parsed.fragment)
    except (TypeError, ValueError):
        return False


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


class ExclusiveHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = False

    def server_bind(self):
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def create_server(port=8765, source=None, journal_dir=None, clock=None, auto_start=False):
    root = PROJECT_ROOT / "web-preview/dist"
    stopped = Event()
    closing = Event()
    worker = None
    stream = None
    worker_lock = Lock()
    ownership = AccountOwnershipLock(journal_dir or DEFAULT_ACCOUNT_DIR)
    ownership.acquire()

    def start_market_worker_if_needed(state):
        nonlocal worker, stream
        if closing.is_set():
            return
        if state["status"] not in ("SCANNING", "WAITING_SYNC", "WAITING_CONNECTION", "STOPPING"):
            return
        if worker is not None and worker.is_alive():
            return
        stopped.clear()
        stream = PublicKlineStream(session.on_stream_event, session.on_connection, stopped)
        worker = Thread(target=stream.run, name="binance-public-kline", daemon=True)
        worker.start()

    def apply_command(command):
        if closing.is_set():
            raise RuntimeError('backend is shutting down')
        name = command['name']
        if name in ('pause', 'resume', 'stop'):
            result = session.apply_control_request(command)
        else:
            result = session.reconcile_resume() if name == 'restore' else getattr(session, name)()
        if result['status'] == 'RECOVERY_REQUIRED' or result.get('error') and name in ('start', 'restore'):
            raise RuntimeError(result.get('error') or 'paper account recovery required')
        with worker_lock:
            if result['status'] == 'STOPPED':
                stopped.set()
                if stream is not None:
                    stream.close()
            else:
                start_market_worker_if_needed(result)

    def api_state():
        result = session.state()
        result['operation'] = commands.state()
        return result

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
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                self.close_connection = True

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
                self._json(200, api_state())
                return
            if urlparse(self.path).path == "/api/health":
                state = api_state()
                self._json(200, {"api_version": 3, "mode": "PAPER_RESEARCH", "status": state["status"], "server_pid": os.getpid(),
                                 "operation": state['operation'], "backend_busy": state['backend_busy'],
                                 "operator_intent": state['operator_intent'], "execution_mode": state['execution_mode'],
                                 "connection": state["connection"], "session_id": state["session_id"],
                                 "api_time_utc": state["api_time_utc"], "recovery": state["recovery"],
                                 "risk_gate": state["risk_gate"], "error": state["error"],
                                 "source_time_utc": state["source_time_utc"]})
                return
            if urlparse(self.path).path == '/api/history':
                params = parse_qs(urlparse(self.path).query)
                try:
                    cursor, limit = int(params.get('cursor', ['0'])[0]), int(params.get('limit', ['100'])[0])
                    if session.state()['backend_busy']:
                        self._json(503, {'error': 'account writer busy; retry history after reconciliation'})
                    else:
                        self._json(200, session.history(cursor, limit))
                except (ValueError, TypeError) as exc:
                    self._json(400, {'error': str(exc)})
                except BlockingIOError as exc:
                    self._json(503, {'error': str(exc)})
                return
            if urlparse(self.path).path == "/api/chart":
                parsed = urlparse(self.path)
                params = parse_qs(parsed.query)
                symbol = params.get("symbol", ["BTCUSDT"])[0].upper()
                interval = params.get("interval", ["1m"])[0]
                try:
                    limit = int(params.get("limit", ["90"])[0])
                except (ValueError, TypeError):
                    limit = 90
                try:
                    chart_payload = session.chart_data(symbol=symbol, interval=interval, limit=limit)
                    self._json(200, chart_payload)
                except ValueError as exc:
                    self._json(400, {"error": str(exc)})
                except Exception as exc:
                    self._json(503, {"error": str(exc)})
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
            if self.path not in ("/api/start", "/api/stop", '/api/pause', '/api/resume'):
                self._json(404, {"error": "not found"})
                return
            if self.headers.get("Content-Length", "0") != "0" or self.headers.get("Transfer-Encoding"):
                raw_length = self.headers.get('Content-Length', '0')
                if not self.headers.get('Transfer-Encoding') and raw_length.isdecimal() and 0 < int(raw_length) <= 4096:
                    self.connection.settimeout(1)
                    try:
                        self.rfile.read(int(raw_length))
                    except (OSError, TimeoutError):
                        pass
                self._json(400, {"error": "request body not accepted"})
                return
            nonlocal worker, stream
            try:
                if closing.is_set():
                    raise RuntimeError("backend is shutting down")
                command = commands.submit(self.path.removeprefix('/api/'))
                result = api_state()
                result['operation'] = command
                self._json(202, result)
            except Exception as exc:
                result = api_state()
                result["error"] = result.get("error") or str(exc)
                self._json(503, result)

    class PaperServer(ExclusiveHTTPServer):
        def server_close(self):
            closing.set()
            try:
                if hasattr(self, 'session'):
                    self.session.request_shutdown()
                if hasattr(self, 'commands'):
                    self.commands.close()
                with worker_lock:
                    stopped.set()
                    if hasattr(self, 'session'):
                        self.session.on_connection(False, "backend is shutting down")
                    if stream is not None:
                        stream.close()
                    if worker is not None:
                        worker.join(timeout=15)
                        if worker.is_alive():
                            raise RuntimeError("market worker has not stopped; paper account ownership retained")
                    if hasattr(self, 'session'):
                        self.session.shutdown()
                    ownership.release()
            finally:
                super().server_close()

    try:
        server = PaperServer(("127.0.0.1", port), Handler)
    except Exception:
        ownership.release()
        raise
    port = server.server_port
    try:
        session = PaperReplaySession(source=source, journal_dir=journal_dir, auto_resume=False, ownership=ownership, clock=clock)
        server.session = session
        commands = PaperCommands(apply_command, accept=session.accept_control_request,
                                 application=session.storage.control_application, clock=session.clock)
        server.commands = commands
        if session._saved is not None or (session.journal_dir / 'account.json').exists():
            commands.submit('restore')
        elif auto_start and session.status == 'IDLE':
            commands.submit('start')
    except Exception:
        server.server_close()
        raise
    return server


def serve(port=8765, source=None, journal_dir=None, open_browser=False, auto_start=False):
    server = create_server(port=port, source=source, journal_dir=journal_dir, auto_start=auto_start)
    print(f"PAPER/RESEARCH local web: http://127.0.0.1:{port}/", flush=True)
    if open_browser:
        webbrowser.open(f"http://127.0.0.1:{port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
