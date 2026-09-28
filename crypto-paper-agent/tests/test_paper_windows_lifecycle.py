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
                process.terminate()
                process.wait(timeout=10)
        assert (journal / 'state.json').read_bytes() == evidence
        assert sorted(p.name for p in journal.iterdir()) == ['state.json']
