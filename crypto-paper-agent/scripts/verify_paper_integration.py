"""Bounded Windows/public-feed/browser observation. Requires built UI + Playwright.

Writes evidence to a NEW directory. Never touches the operator's paper account.
This is an author diagnostic, not a profitability or independent-review gate.
"""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import requests

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--seconds', type=int, default=25)
    args = parser.parse_args()
    if not 15 <= args.seconds <= 60:
        parser.error('observation must be 15..60 seconds')
    args.output_dir.mkdir(parents=True, exist_ok=False)
    output = args.output_dir.resolve()
    journal = output / 'journal'
    evidence = {'mode': 'PAPER_RESEARCH', 'verification': 'AUTHOR_SELF_REVIEWED',
                'public_stream': 'NOT_VERIFIED', 'console_errors': [], 'failed_requests': [],
                'page_errors': [], 'observations': [], 'phase': 'initial_run'}
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    url = f'http://127.0.0.1:{port}'

    def launch(log):
        process = subprocess.Popen([sys.executable, str(ROOT / 'scripts/run_local_paper_web.py'),
            '--port', str(port), '--journal-dir', str(journal)], cwd=output, stdout=log, stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                requests.get(url + '/api/health', timeout=1).raise_for_status()
                return process
            except requests.ConnectionError:
                if process.poll() is not None:
                    raise RuntimeError('backend process exited during startup')
                time.sleep(.1)
        process.terminate()
        process.wait(timeout=10)
        raise RuntimeError('backend did not listen within 15 seconds')

    def save(name, value):
        (output / name).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')

    from playwright.sync_api import sync_playwright
    with (output / 'server.log').open('wb') as log, sync_playwright() as playwright:
        process = launch(log)
        browser = playwright.chromium.launch(channel='msedge', headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 1000})
        page.on('pageerror', lambda exc: evidence['page_errors'].append(str(exc)))
        page.on('console', lambda msg: evidence['console_errors'].append({'phase': evidence['phase'], 'message': msg.text}) if msg.type == 'error' else None)
        page.on('requestfailed', lambda req: evidence['failed_requests'].append({'phase': evidence['phase'], 'url': req.url, 'failure': req.failure}))
        try:
            page.goto(url, wait_until='networkidle')
            page.get_by_role('button', name='Khởi động bot mô phỏng paper trading').click()
            deadline = time.monotonic() + args.seconds
            while time.monotonic() < deadline:
                state = requests.get(url + '/api/state', timeout=30).json()
                evidence['observations'].append({'status': state['status'], 'connection': state['connection'],
                    'orders': len(state['orders']), 'trades': state['completed_trades'], 'risk_gate': state['risk_gate']})
                page.wait_for_timeout(1000)
            save('public-state.json', state)
            chart_bounds = page.get_by_role('img', name='Biểu đồ nến BTCUSDT — Dữ liệu công khai Binance USD-M Futures').bounding_box()
            assert chart_bounds and chart_bounds['height'] > 150, f'chart not rendered: {chart_bounds}'
            evidence['chart_bounds'] = chart_bounds
            evidence['public_stream'] = 'EVENTS_OBSERVED' if state['connection']['last_event_received_at_utc'] else 'BLOCKED'
            evidence['public_orders'] = len(state['orders'])
            evidence['public_completed_trades'] = state['completed_trades']
            page.screenshot(path=str(output / 'public-browser.png'), full_page=True)
            stopped = requests.post(url + '/api/stop', timeout=15).json()
            assert stopped['status'] == 'STOPPED', stopped
            evidence['stop_idempotent'] = requests.post(url + '/api/stop', timeout=5).json()['status'] == 'STOPPED'
            save('stopped-state.json', stopped)
            evidence['phase'] = 'intentional_restart'
            process.terminate()
            process.wait(timeout=10)
            process = launch(log)
            restored = requests.post(url + '/api/start', timeout=5).json()
            assert restored['status'] == 'RECOVERY_REQUIRED'
            assert restored['session_id'] == stopped['session_id']
            assert restored['account'] == stopped['account']
            assert not restored['risk_gate']['admission_open']
            save('restart-state.json', restored)
            evidence['phase'] = 'after_restart'
            page.reload(wait_until='networkidle')
            locked = page.get_by_role('button', name='Khóa khởi động do cần đối soát journal')
            locked.wait_for()
            assert locked.is_disabled()
            page.screenshot(path=str(output / 'restart-browser.png'), full_page=True)
            evidence['restart_browser_locked'] = True
            evidence['status'] = 'AUTHOR_VERIFIED_API_BROWSER_RESTART'
        finally:
            browser.close()
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
            save('evidence.json', evidence)
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    main()
