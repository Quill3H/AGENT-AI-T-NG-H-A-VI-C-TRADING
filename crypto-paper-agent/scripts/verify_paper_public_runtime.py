"""Actual Windows process/API/public-stream smoke on a separate temporary account."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

import requests

ROOT = Path(__file__).resolve().parents[1]


def listen(process, base, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f'Windows backend exited {process.returncode}')
        try:
            return requests.get(base + '/api/state', timeout=2).json()
        except requests.ConnectionError:
            time.sleep(.2)
    raise TimeoutError('Windows backend did not listen')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=int, default=45)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not 15 <= args.seconds <= 1800:
        parser.error('seconds must be 15..1800')
    evidence = {'mode': 'PAPER_RESEARCH', 'platform': sys.platform,
                'started_at_utc': datetime.now(timezone.utc).isoformat(), 'status': 'BLOCKED',
                'orders_kind': 'SIMULATED_ONLY', 'observations': [], 'restart_verified': False}
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    with tempfile.TemporaryDirectory(prefix='paper-public-qa-', ignore_cleanup_errors=True) as temporary:
        directory = Path(temporary)
        account = directory / 'account'
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        base = f'http://127.0.0.1:{port}'
        session_id = None
        for restart in range(2):
            failed = False
            with (directory / f'run-{restart}.log').open('wb') as log:
                process = subprocess.Popen([sys.executable, str(ROOT / 'scripts/run_local_paper_web.py'),
                    '--port', str(port), '--journal-dir', str(account), '--start'], cwd=directory,
                    stdout=log, stderr=log, creationflags=flags)
                try:
                    state = listen(process, base)
                    deadline = time.monotonic() + args.seconds + 60
                    observed_until = None
                    while time.monotonic() < deadline:
                        state = requests.get(base + '/api/state', timeout=3).json()
                        operation = state.get('operation') or {}
                        if operation.get('status') in ('APPLIED', 'FAILED') and observed_until is None:
                            observed_until = time.monotonic() + args.seconds
                        if observed_until is not None and time.monotonic() >= observed_until:
                            break
                        if state.get('status') == 'RECOVERY_REQUIRED' and operation.get('status') not in ('PENDING', 'RUNNING'):
                            raise RuntimeError(state.get('error'))
                        evidence['observations'].append({
                            'restart': restart, 'as_of_utc': state['api_time_utc'],
                            'status': state['status'], 'operation': operation,
                            'connection': state['connection'], 'prices': state['current_prices'],
                            'account': state['account'], 'orders': len(state['orders']),
                            'completed_positions': state['completed_trades'], 'error': state['error']})
                        time.sleep(1)
                    if not state['session_id'] or operation.get('status') != 'APPLIED':
                        raise RuntimeError(state.get('error') or 'public startup did not finish')
                    if restart == 0:
                        session_id = state['session_id']
                    elif state['session_id'] != session_id or state['trials']['total_capital_injected_usd'] != 10000:
                        raise RuntimeError('restart changed the account or allocated twice')
                    evidence['final_state'] = state
                    if restart:
                        evidence['restart_verified'] = True
                except Exception as exc:
                    evidence['error'] = f'{type(exc).__name__}: {exc}'
                    failed = True
                finally:
                    if os.name == 'nt' and process.poll() is None:
                        subprocess.run(['taskkill.exe', '/PID', str(process.pid), '/T', '/F'],
                                       capture_output=True, timeout=15, creationflags=flags)
                    elif process.poll() is None:
                        process.terminate()
                    process.wait(timeout=15)
            evidence[f'log_{restart}'] = (directory / f'run-{restart}.log').read_text(encoding='utf-8', errors='replace')[-8000:]
            if failed:
                break
        received = {s for item in evidence['observations'] for s, p in item['prices'].items() if p['valid']}
        evidence['fresh_public_symbols'] = sorted(received)
        evidence['public_websocket_verified'] = received == {'BTCUSDT', 'ETHUSDT', 'SOLUSDT'}
        if evidence['public_websocket_verified'] and evidence['restart_verified'] and not evidence.get('error'):
            evidence['status'] = 'AUTHOR_SELF_REVIEWED'
        evidence['completed_at_utc'] = datetime.now(timezone.utc).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps({k: v for k, v in evidence.items() if k not in ('observations', 'final_state') and not k.startswith('log_')}, indent=2))
    return 0 if evidence['status'] == 'AUTHOR_SELF_REVIEWED' else 2


if __name__ == '__main__':
    raise SystemExit(main())
