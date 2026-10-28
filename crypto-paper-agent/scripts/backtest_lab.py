#!/usr/bin/env python3
"""Offline batch backtests with content-addressed reuse and comparison reports."""
import argparse
import csv
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import re
import sys
import time
import tempfile
from datetime import date
from pathlib import Path

import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from scripts import run_vision_backtest, run_vision_carry  # noqa: E402
from src.data_layer.cache_manager import timeframe_to_timedelta  # noqa: E402
from src.data_layer.vision_dataset import load_funding  # noqa: E402
from src.strategies.registry import DIRECTIONAL_STRATEGIES  # noqa: E402

SCHEMA = 1
METRICS = ('total_return_pct', 'max_drawdown_pct', 'completed_trades', 'win_rate_pct', 'final_equity_usd')


def io_path(path):
    """Use Windows extended paths for deep workspace/cache filenames."""
    path = Path(path).resolve()
    value = str(path)
    if os.name == 'nt' and not value.startswith('\\\\?\\'):
        value = '\\\\?\\UNC\\' + value[2:] if value.startswith('\\\\') else '\\\\?\\' + value
    return Path(value)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, allow_nan=False).encode()).hexdigest()


def file_hash(path):
    with io_path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def code_identity():
    files = [p for folder in ('src', 'scripts', 'config') for p in (PROJECT_ROOT / folder).rglob('*')
             if p.is_file() and p.suffix in ('.py', '.yaml', '.yml', '.json')]
    files += list(PROJECT_ROOT.glob('requirements*.txt'))
    return {str(p.relative_to(PROJECT_ROOT)).replace('\\', '/'): file_hash(p) for p in sorted(files)}


def data_identity(data_dir):
    files = sorted(p for p in data_dir.iterdir() if p.is_file() and p.suffix in ('.parquet', '.json'))
    if not any(p.suffix == '.parquet' for p in files):
        raise ValueError('data directory contains no normalized Parquet files')
    return {p.name: file_hash(p) for p in files}


def runtime_identity():
    return {'python': platform.python_version(), 'platform': platform.platform(),
            'packages': sorted((d.metadata['Name'], d.version) for d in importlib.metadata.distributions())}


def load_jobs(batch):
    content = yaml.safe_load(batch.read_text(encoding='utf-8'))
    if not isinstance(content, dict) or set(content) != {'jobs'} or not isinstance(content['jobs'], list) or not content['jobs']:
        raise ValueError('batch must contain a nonempty jobs list')
    jobs, names = [], set()
    allowed = {'name', 'strategy', 'symbol', 'start', 'end', 'configs', 'cost_multiplier'}
    for raw in content['jobs']:
        if not isinstance(raw, dict) or set(raw) - allowed or not {'name', 'strategy', 'symbol', 'start', 'end'} <= set(raw):
            raise ValueError('each job needs name/strategy/symbol/start/end; unknown fields are rejected')
        job = dict(raw)
        name = job['name']
        if not isinstance(name, str) or not name.strip() or name in names or any(c in name for c in '\r\n'):
            raise ValueError('job names must be unique nonempty single-line strings')
        names.add(name)
        if job['strategy'] not in {*DIRECTIONAL_STRATEGIES, 'funding_arbitrage'}:
            raise ValueError(f"unsupported strategy: {job['strategy']}")
        if not isinstance(job['symbol'], str) or not re.fullmatch('[A-Z0-9]+USDT', job['symbol']):
            raise ValueError('symbol must be an uppercase USDT symbol, e.g. BTCUSDT')
        for key in ('start', 'end'):
            job[key] = date.fromisoformat(str(job[key])).isoformat()
        if job['start'] > job['end']:
            raise ValueError('start must be on or before end')
        cost = job.get('cost_multiplier', 1.0)
        if isinstance(cost, bool) or not isinstance(cost, (int, float)) or not math.isfinite(cost) or cost <= 0:
            raise ValueError('cost_multiplier must be finite and positive')
        job['cost_multiplier'] = float(cost)
        configs = job.get('configs', [])
        if not isinstance(configs, list) or not all(isinstance(p, str) for p in configs):
            raise ValueError('configs must be a list of YAML paths relative to the batch file')
        job['configs'] = [str((batch.parent / p).resolve()) for p in configs]
        for path in job['configs']:
            if not isinstance(yaml.safe_load(Path(path).read_text(encoding='utf-8')), dict):
                raise ValueError(f'config must be a mapping: {path}')
        jobs.append(job)
    return jobs


def job_identity(job):
    if job['strategy'] == 'funding_arbitrage':
        config = run_vision_carry.load_config(job['configs'])
    else:
        config = run_vision_backtest.load_config(job['strategy'], job['configs'])
    external = {}
    signal = config.get('rules', {}).get('signal_path')
    if signal:
        path = Path(signal).resolve()
        external[str(path)] = file_hash(path)
    return {'strategy': job['strategy'], 'symbol': job['symbol'], 'start': job['start'], 'end': job['end'],
            'cost_multiplier': job['cost_multiplier'], 'config': config,
            'config_files': {p: file_hash(p) for p in job['configs']}, 'external_files': external}


def validate_data(job, data_dir):
    """Reject truncated windows; retain the existing runner's funding and fill rules."""
    config = job_identity(job)['config']
    start = pd.Timestamp(job['start'], tz='UTC')
    end = pd.Timestamp(job['end'], tz='UTC') + pd.Timedelta(days=1)
    symbol = job['symbol']
    if job['strategy'] == 'funding_arbitrage':
        required = [('perp', '1h', start), ('spot', '1h', start)]
    else:
        cfg = config.get('strategy', {})
        required = [('perp', cfg.get('timeframe_signal', '4h'), start - run_vision_backtest.WARMUP),
                    ('perp', cfg.get('timeframe_execution', '15m'), start)]
    for market, timeframe, first in required:
        frame = pd.read_parquet(data_dir / f'{symbol}_{market}_{timeframe}.parquet')
        index = frame.index
        step = pd.Timedelta(timeframe_to_timedelta(timeframe))
        if not isinstance(index, pd.DatetimeIndex) or str(index.tz) != 'UTC' or not index.is_monotonic_increasing or index.has_duplicates:
            raise ValueError('data index must be sorted, unique and UTC')
        expected = pd.date_range(first, end, freq=step, inclusive='left')
        # The existing carry loader explicitly forward-fills spot maintenance gaps.
        if market == 'spot':
            covered = len(index) and index[0] <= first and index[-1] >= expected[-1]
        else:
            covered = len(expected.difference(index)) == 0
        if not covered:
            raise ValueError(f'incomplete {symbol} {market} {timeframe} window (including required warmup)')
    funding = load_funding(data_dir, symbol)
    boundaries = pd.date_range(start, end, freq='8h', inclusive='left')
    if len(boundaries.difference(funding.index)) or not funding.loc[boundaries, 'funding_rate'].map(math.isfinite).all():
        raise ValueError('incomplete or nonfinite funding events')
    if job['strategy'] == 'funding_arbitrage':
        previous = start - pd.Timedelta(hours=8)
        if previous not in funding.index or not math.isfinite(funding.loc[previous, 'funding_rate']):
            raise ValueError('carry requires finite preceding funding at start minus 8 hours')


def run_job(job, data_dir):
    validate_data(job, data_dir)
    args = (data_dir, job['start'], job['end'], job['configs'], job['cost_multiplier'])
    if job['strategy'] == 'funding_arbitrage':
        return run_vision_carry.run(*args, symbol=job['symbol'])[1]
    return run_vision_backtest.run(data_dir, job['strategy'], *args[1:], symbol=job['symbol'])


def read_cache(path, identity):
    try:
        entry = json.loads(path.read_text(encoding='utf-8'))
        if entry['identity'] == identity and entry['summary_sha256'] == digest(entry['summary']):
            if isinstance(entry['summary'], dict) and all(k in entry['summary'] for k in METRICS):
                return entry['summary']
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str, allow_nan=False), encoding='utf-8')


def write_reports(output, rows, identity):
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'comparison.json', {'label': 'RETROSPECTIVE_RESEARCH', 'identity': identity, 'runs': rows})
    columns = ['name', 'strategy', 'symbol', 'start', 'end', 'cost_multiplier', 'status', 'cached', 'elapsed_seconds', *METRICS, 'run_id', 'error']
    with (output / 'comparison.csv').open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, row.get('summary', {}).get(k, '')) for k in columns})
    lines = ['# So sánh backtest', '', 'RETROSPECTIVE_RESEARCH — nghiên cứu trên dữ liệu quá khứ, không phải xác nhận hiệu quả tương lai.', '',
             '| Phương án | Trạng thái | Dùng lại | Lãi/lỗ % | Sụt giảm % | Số lệnh |', '|---|---|---|---:|---:|---:|']
    for row in rows:
        summary = row.get('summary', {})
        name = row['name'].replace('|', '\\|')
        lines.append(f"| {name} | {row['status']} | {'Có' if row['cached'] else 'Không'} | {summary.get('total_return_pct', '')} | {summary.get('max_drawdown_pct', '')} | {summary.get('completed_trades', '')} |")
    errors = [f"- {r['name']}: {r['error']}" for r in rows if r['status'] == 'ERROR']
    (output / 'comparison.md').write_text('\n'.join(lines + [''] + errors) + '\n', encoding='utf-8')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--list-strategies', action='store_true')
    parser.add_argument('--data-dir', type=Path)
    parser.add_argument('--batch', type=Path)
    parser.add_argument('--cache-dir', type=Path, default=PROJECT_ROOT / 'artifacts' / 'backtest-lab-cache')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    if args.list_strategies:
        print('\n'.join(sorted({*DIRECTIONAL_STRATEGIES, 'funding_arbitrage'})))
        return 0
    try:
        if not all((args.data_dir, args.batch, args.output)):
            raise ValueError('--data-dir, --batch and --output are required')
        data, batch, output, cache = map(io_path, (args.data_dir, args.batch, args.output, args.cache_dir))
        if output.exists():
            raise ValueError('output already exists; choose a new directory')
        protected = [data, *(io_path(PROJECT_ROOT / p) for p in ('src', 'scripts', 'config'))]
        for target in (output, cache):
            if any(target == p or target.is_relative_to(p) or p.is_relative_to(target) for p in protected):
                raise ValueError('output/cache must be outside input data and source/config directories')
        if output == cache or output.is_relative_to(cache) or cache.is_relative_to(output):
            raise ValueError('output and cache directories must be separate')
        jobs = load_jobs(batch)
        def snapshot():
            return {'schema': SCHEMA, 'code': code_identity(), 'data': data_identity(data),
                    'runtime': runtime_identity(), 'jobs': [job_identity(j) for j in jobs], 'batch_sha256': file_hash(batch)}
        before = snapshot()
        # Normalize YAML date values and tuples so identity equals its JSON round-trip.
        before = json.loads(json.dumps(before, default=str))
        common = {k: before[k] for k in ('schema', 'code', 'data', 'runtime')}
        rows, pending = [], {}
        for job, settings in zip(jobs, before['jobs']):
            identity = {**common, 'job': settings}
            run_id = digest(identity)
            started = time.perf_counter()
            summary = pending.get(run_id, {}).get('summary') or read_cache(cache / f'{run_id}.json', identity)
            row = {k: job[k] for k in ('name', 'strategy', 'symbol', 'start', 'end', 'cost_multiplier')}
            row.update(run_id=run_id, cached=summary is not None)
            try:
                if summary is None:
                    summary = json.loads(json.dumps(run_job(job, data), default=str, allow_nan=False))
                    if not isinstance(summary, dict) or not all(k in summary for k in METRICS):
                        raise ValueError('runner did not return a complete summary')
                    pending[run_id] = {'identity': identity, 'summary': summary, 'summary_sha256': digest(summary)}
                row.update(status='OK', summary=summary)
            except Exception as error:
                row.update(status='ERROR', error=f'{type(error).__name__}: {error}')
            row['elapsed_seconds'] = round(time.perf_counter() - started, 6)
            rows.append(row)
            print(f"{job['name']}: {row['status']} ({'cache' if row['cached'] else 'executed'})", flush=True)
        if digest(snapshot()) != digest(before):
            raise ValueError('inputs changed during execution; no cache or report published')
        cache.mkdir(parents=True, exist_ok=True)
        for run_id, entry in pending.items():
            # Atomic replace prevents interrupted cache writes becoming valid hits.
            with tempfile.NamedTemporaryFile(dir=cache, suffix='.tmp', delete=False) as stream:
                temporary = Path(stream.name)
            try:
                write_json(temporary, entry)
                temporary.replace(cache / f'{run_id}.json')
            finally:
                temporary.unlink(missing_ok=True)
        write_reports(output, rows, before)
        print(f'Reports: {output}', flush=True)
        return 1 if any(r['status'] == 'ERROR' for r in rows) else 0
    except (OSError, ValueError, TypeError, KeyError, yaml.YAMLError) as error:
        print(f'Backtest Lab: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
