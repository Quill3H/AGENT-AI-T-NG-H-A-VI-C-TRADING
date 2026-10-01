"""Run the actual Windows entrypoint and launcher; no exchange operations."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import pytest
import requests

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(os.name != 'nt', reason='Windows operation evidence')


def kill_owned_process(process):
    if process.poll() is None:
        subprocess.run(['taskkill.exe', '/PID', str(process.pid), '/T', '/F'],
                       capture_output=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
    process.wait(timeout=15)


def test_windows_launcher_refuses_occupied_port_without_initializing_account(tmp_path):
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        listener.listen()
        port = listener.getsockname()[1]
        result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
            '-File', str(ROOT / 'scripts/windows/run-paper-server.ps1'), '-Port', str(port),
            '-JournalDir', str(tmp_path), '-PythonPath', sys.executable],
            capture_output=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode == 2, result.stderr.decode(errors='replace')
    assert list(tmp_path.iterdir()) == []


def test_windows_server_restart_preserves_corrupt_evidence_and_no_new_account(tmp_path):
    journal = tmp_path / 'paper'
    journal.mkdir()
    (journal / 'state.json').write_text('{"unfinished":', encoding='utf-8')
    evidence = (journal / 'state.json').read_bytes()
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    for restart in range(2):
        with (tmp_path / f'server-{restart}.log').open('wb') as log:
            process = subprocess.Popen([sys.executable, str(ROOT / 'scripts/run_local_paper_web.py'),
                '--port', str(port), '--journal-dir', str(journal)], cwd=tmp_path,
                stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline:
                    try:
                        response = requests.get(f'http://127.0.0.1:{port}/api/health', timeout=1)
                        break
                    except requests.ConnectionError:
                        assert process.poll() is None, 'server exited during startup'
                        time.sleep(.1)
                else:
                    pytest.fail('Windows backend failed to listen')
                assert response.json()['status'] == 'RECOVERY_REQUIRED'
                for action in ('start', 'start', 'stop', 'stop'):
                    state = requests.post(f'http://127.0.0.1:{port}/api/{action}', timeout=2).json()
                    assert state['status'] == 'RECOVERY_REQUIRED'
                    assert state['account']['equity_usd'] is None
                    assert not state['risk_gate']['admission_open']
            finally:
                kill_owned_process(process)
        assert (journal / 'state.json').read_bytes() == evidence
        assert sorted(p.name for p in journal.iterdir()) == ['.paper-owner.lock', 'state.json']
        assert (journal / '.paper-owner.lock').stat().st_size == 0


def test_windows_process_restart_open_pending_offline_and_repeated_funding(tmp_path):
    from datetime import timedelta
    from src.execution.order_models import OrderRequest
    from src.paper.replay_session import PaperReplaySession
    from test_local_paper_session import BASE
    from test_paper_replay_recovery import RangeSource
    source = RangeSource()
    journal = tmp_path / 'account'
    session = PaperReplaySession(source=source, journal_dir=journal)
    session.start()
    session.broker.submit_order(OrderRequest(symbol='BTCUSDT', direction='SHORT', signal_time=BASE,
        signal_price=100, stop_loss_price=150, requested_quantity=1))
    session.checkpoint()
    source.now = int((BASE + timedelta(minutes=16)).timestamp() * 1000)
    session.on_connection(True, None)
    session.broker.submit_order(OrderRequest(symbol='ETHUSDT', direction='LONG',
        signal_time=BASE + timedelta(minutes=15), signal_price=100, stop_loss_price=50, requested_quantity=1))
    session.checkpoint()
    account_id, initial_wallet = session.session_id, session.broker.wallet_balance
    session.shutdown()
    target = int((BASE + timedelta(hours=12, minutes=16)).timestamp() * 1000)
    code = '''
import sys
from datetime import datetime, timezone
sys.path.insert(0, sys.argv[1])
sys.path.insert(0, sys.argv[1] + '/tests')
from src.paper import local_server
from test_paper_replay_recovery import RangeSource
class OfflineSocket:
    def __init__(self, *args): pass
    def run(self): pass
    def close(self): pass
local_server.PublicKlineStream = OfflineSocket
source = RangeSource()
source.now, source.offline = int(sys.argv[4]), sys.argv[5] == 'offline'
server = local_server.create_server(port=int(sys.argv[3]), journal_dir=sys.argv[2], source=source,
    clock=lambda: datetime.fromtimestamp(source.now / 1000, timezone.utc))
server.serve_forever()
'''
    reference = None
    for restart in range(4):
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        with (tmp_path / f'restore-{restart}.log').open('wb') as log:
            process = subprocess.Popen([sys.executable, '-c', code, str(ROOT), str(journal),
                str(port), str(target), 'offline' if restart == 0 else 'online'], cwd=tmp_path,
                stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                deadline = time.monotonic() + 45
                while time.monotonic() < deadline:
                    assert process.poll() is None, 'backend exited unexpectedly'
                    try:
                        state = requests.get(f'http://127.0.0.1:{port}/api/state', timeout=2).json()
                        if state['operation'] and state['operation']['status'] in ('APPLIED', 'FAILED'):
                            break
                    except requests.ConnectionError:
                        pass
                    time.sleep(.1)
                else:
                    pytest.fail('Windows fixture recovery did not finish')
                assert state['session_id'] == account_id
                assert state['trials']['total_capital_injected_usd'] == 10000
                assert not state['risk_gate']['admission_open']
                if restart == 0:
                    assert state['status'] == 'WAITING_CONNECTION'
                    assert len(state['open_positions']) == len(state['pending_orders']) == 1
                    assert state['account']['wallet_usd'] == initial_wallet
                    assert state['funding_events'] == []
                else:
                    assert state['operation']['status'] == 'APPLIED', state['error']
                    assert len(state['open_positions']) == 2
                    assert state['pending_orders'] == []
                    assert len(state['funding_events']) == 4
                    assert len(state['orders']) == 2
                    financial = {key: state[key] for key in ('account', 'orders', 'open_positions', 'funding_events')}
                    if reference is None: reference = financial
                    else: assert financial == reference
            finally:
                kill_owned_process(process)
