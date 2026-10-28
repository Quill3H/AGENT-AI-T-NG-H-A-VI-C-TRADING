import importlib
import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest
import yaml


def lab():
    assert importlib.util.find_spec('scripts.backtest_lab'), 'shared backtest tool is missing'
    return importlib.import_module('scripts.backtest_lab')


@pytest.fixture
def setup_lab(tmp_path):
    data = tmp_path / 'data'
    data.mkdir()
    index = pd.date_range('2023-09-01', '2024-01-02', freq='4h', tz='UTC', inclusive='left')
    def bars(idx):
        return pd.DataFrame({'open': 100., 'high': 101., 'low': 99., 'close': 100.,
                             'volume': 10., 'taker_buy_base_volume': 5.}, index=idx)
    bars(index).to_parquet(data / 'BTCUSDT_perp_4h.parquet')
    bars(pd.date_range('2024-01-01', periods=96, freq='15min', tz='UTC')).to_parquet(data / 'BTCUSDT_perp_15m.parquet')
    pd.DataFrame({'funding_rate': 0.0001}, index=pd.date_range('2023-12-31', periods=6, freq='8h', tz='UTC')).to_parquet(data / 'BTCUSDT_perp_funding.parquet')
    batch = tmp_path / 'batch.yaml'
    job = dict(name='base', strategy='trend_following', symbol='BTCUSDT', start='2024-01-01', end='2024-01-01')
    batch.write_text(yaml.safe_dump({'jobs': [job]}))
    return data, batch, job


def execute(tmp_path, setup_lab, output='out'):
    data, batch, _ = setup_lab
    return lab().main(['--data-dir', str(data), '--batch', str(batch), '--cache-dir', str(tmp_path / 'cache'), '--output', str(tmp_path / output)])


def rows(tmp_path, name='out'):
    return json.loads((tmp_path / name / 'comparison.json').read_text())['runs']


def test_real_runner_parity_and_second_run_does_not_execute(tmp_path, setup_lab, monkeypatch):
    from scripts.run_vision_backtest import run
    expected = run(setup_lab[0], 'trend_following', '2024-01-01', '2024-01-01')
    assert execute(tmp_path, setup_lab) == 0
    first = rows(tmp_path)[0]
    assert first['summary'] == json.loads(json.dumps(expected, default=str))
    assert first['status'] == 'OK' and first['cached'] is False
    monkeypatch.setattr(lab(), 'run_job', lambda *a: pytest.fail('cache hit executed the broker'))
    assert execute(tmp_path, setup_lab, 'second') == 0
    assert rows(tmp_path, 'second')[0]['cached'] is True
    assert (tmp_path / 'second' / 'comparison.csv').is_file()
    assert 'RETROSPECTIVE' in (tmp_path / 'second' / 'comparison.md').read_text(encoding='utf-8')


def test_data_edit_even_with_same_size_and_mtime_invalidates(tmp_path, setup_lab):
    import os
    data, _, _ = setup_lab
    extra = data / 'manifest.json'
    extra.write_text('{"v":1}')
    assert execute(tmp_path, setup_lab) == 0
    stamp = extra.stat()
    extra.write_text('{"v":2}')
    os.utime(extra, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    assert execute(tmp_path, setup_lab, 'second') == 0
    assert rows(tmp_path)[0]['run_id'] != rows(tmp_path, 'second')[0]['run_id']
    assert rows(tmp_path, 'second')[0]['cached'] is False


def test_config_cost_and_code_identity_invalidate(tmp_path, setup_lab, monkeypatch):
    assert execute(tmp_path, setup_lab) == 0
    _, batch, job = setup_lab
    job['cost_multiplier'] = 2
    batch.write_text(yaml.safe_dump({'jobs': [job]}))
    assert execute(tmp_path, setup_lab, 'cost') == 0
    assert rows(tmp_path)[0]['run_id'] != rows(tmp_path, 'cost')[0]['run_id']
    config = tmp_path / 'override.yaml'
    config.write_text('rules:\n  test_marker: 1\n')
    job['configs'] = ['override.yaml']
    batch.write_text(yaml.safe_dump({'jobs': [job]}))
    assert execute(tmp_path, setup_lab, 'config1') == 0
    config.write_text('rules:\n  test_marker: 2\n')
    assert execute(tmp_path, setup_lab, 'config2') == 0
    assert rows(tmp_path, 'config1')[0]['run_id'] != rows(tmp_path, 'config2')[0]['run_id']
    original = lab().code_identity
    monkeypatch.setattr(lab(), 'code_identity', lambda: {**original(), 'test_dirty_code': 'changed'})
    assert execute(tmp_path, setup_lab, 'code') == 0
    assert rows(tmp_path, 'config2')[0]['run_id'] != rows(tmp_path, 'code')[0]['run_id']


def test_corrupt_cache_is_rerun(tmp_path, setup_lab):
    assert execute(tmp_path, setup_lab) == 0
    entry = next(lab().io_path(tmp_path / 'cache').glob('*.json'))
    payload = json.loads(entry.read_text())
    payload['summary']['total_return_pct'] = 99999
    entry.write_text(json.dumps(payload))
    assert execute(tmp_path, setup_lab, 'second') == 0
    assert rows(tmp_path, 'second')[0]['cached'] is False
    assert rows(tmp_path, 'second')[0]['summary']['total_return_pct'] != 99999


def test_failed_job_is_recorded_not_cached_and_other_jobs_continue(tmp_path, setup_lab, monkeypatch):
    _, batch, job = setup_lab
    batch.write_text(yaml.safe_dump({'jobs': [{**job, 'name': 'bad'}, {**job, 'name': 'good', 'cost_multiplier': 2}]}))
    original = lab().run_job
    def fail_one(job, data):
        if job['name'] == 'bad':
            raise ValueError('deliberate failure')
        return original(job, data)
    monkeypatch.setattr(lab(), 'run_job', fail_one)
    assert execute(tmp_path, setup_lab) == 1
    result = rows(tmp_path)
    assert [r['status'] for r in result] == ['ERROR', 'OK']
    assert 'deliberate failure' in result[0]['error']
    assert len(list((tmp_path / 'cache').glob('*.json'))) == 1


@pytest.mark.parametrize('change', ['strategy', 'cost', 'dates', 'unknown', 'duplicate', 'empty'])
def test_invalid_batch_rejected_before_output(tmp_path, setup_lab, change):
    _, batch, job = setup_lab
    if change == 'strategy': job['strategy'] = '../unknown'
    if change == 'cost': job['cost_multiplier'] = -1
    if change == 'dates': job['end'] = '2023-12-01'
    if change == 'unknown': job['typo_param'] = 5
    jobs = [job, job] if change == 'duplicate' else ([] if change == 'empty' else [job])
    batch.write_text(yaml.safe_dump({'jobs': jobs}))
    assert execute(tmp_path, setup_lab) == 2
    assert not (tmp_path / 'out').exists()


def test_output_never_overwrites_and_must_stay_outside_data(tmp_path, setup_lab):
    output = tmp_path / 'out'
    output.mkdir()
    (output / 'keep').write_text('original')
    assert execute(tmp_path, setup_lab) == 2
    assert (output / 'keep').read_text() == 'original'
    assert lab().main(['--data-dir', str(setup_lab[0]), '--batch', str(setup_lab[1]), '--cache-dir', str(tmp_path / 'cache'), '--output', str(setup_lab[0] / 'out')]) == 2


def test_missing_or_partial_data_is_error_not_zero_profit(tmp_path, setup_lab):
    path = setup_lab[0] / 'BTCUSDT_perp_15m.parquet'
    pd.read_parquet(path).iloc[:-1].to_parquet(path)
    assert execute(tmp_path, setup_lab) == 1
    assert rows(tmp_path)[0]['status'] == 'ERROR'
    assert not list((tmp_path / 'cache').glob('*.json'))


def test_mutation_during_execution_publishes_no_cache_or_report(tmp_path, setup_lab, monkeypatch):
    original = lab().run_job
    def mutate(job, data):
        summary = original(job, data)
        (Path(data) / 'manifest.json').write_text('{"changed":true}')
        return summary
    monkeypatch.setattr(lab(), 'run_job', mutate)
    assert execute(tmp_path, setup_lab) == 2
    assert not (tmp_path / 'out').exists()
    assert not list((tmp_path / 'cache').glob('*.json'))


def prepare_carry(setup_lab):
    data, batch, job = setup_lab
    bars = pd.read_parquet(data / 'BTCUSDT_perp_15m.parquet').iloc[::4]
    for market in ('perp', 'spot'):
        bars.to_parquet(data / f'BTCUSDT_{market}_1h.parquet')
    job['strategy'] = 'funding_arbitrage'
    batch.write_text(yaml.safe_dump({'jobs': [job]}))


def test_carry_requires_preceding_funding_not_shortened_window(tmp_path, setup_lab):
    prepare_carry(setup_lab)
    path = setup_lab[0] / 'BTCUSDT_perp_funding.parquet'
    frame = pd.read_parquet(path)
    frame.loc[frame.index >= pd.Timestamp('2024-01-01', tz='UTC')].to_parquet(path)
    assert execute(tmp_path, setup_lab) == 1
    assert rows(tmp_path)[0]['status'] == 'ERROR'
    assert 'preceding funding' in rows(tmp_path)[0]['error']


def test_carry_adapter_matches_original_and_caches(tmp_path, setup_lab):
    prepare_carry(setup_lab)
    from scripts.run_vision_carry import run
    expected = run(setup_lab[0], '2024-01-01', '2024-01-01')[1]
    assert execute(tmp_path, setup_lab) == 0
    assert rows(tmp_path)[0]['summary'] == json.loads(json.dumps(expected, default=str))
    assert execute(tmp_path, setup_lab, 'second') == 0
    assert rows(tmp_path, 'second')[0]['cached'] is True


def test_windows_long_cache_and_output_paths(tmp_path, setup_lab):
    # Windows's legacy limit is 260 characters; deep workspace paths are normal here.
    long_base = tmp_path / ('a' * 60) / ('b' * 60)
    output, cache = long_base / 'out', long_base / 'cache'
    args = ['--data-dir', str(setup_lab[0]), '--batch', str(setup_lab[1]), '--cache-dir', str(cache), '--output', str(output)]
    assert lab().main(args) == 0
    args[-1] = str(long_base / 'second')
    assert lab().main(args) == 0


def test_external_signal_changes_invalidate_and_real_trades_match(tmp_path, setup_lab):
    data, batch, job = setup_lab
    signals = tmp_path / 'signals.parquet'
    idx = pd.read_parquet(data / 'BTCUSDT_perp_4h.parquet').index
    pd.DataFrame({'BTCUSDT': 1.}, index=idx).to_parquet(signals)
    config = tmp_path / 'signal.yaml'
    config.write_text(yaml.safe_dump({'strategy': {'timeframe_signal': '4h'}, 'rules': {'signal_path': str(signals)}, 'base_risk_percent': 0.01, 'leverage': 2}))
    job.update(strategy='signal_series', configs=['signal.yaml'])
    batch.write_text(yaml.safe_dump({'jobs': [job]}))
    from scripts.run_vision_backtest import run
    expected = run(data, 'signal_series', '2024-01-01', '2024-01-01', [str(config)])
    assert expected['completed_trades'] > 0
    assert execute(tmp_path, setup_lab) == 0
    assert rows(tmp_path)[0]['summary'] == json.loads(json.dumps(expected, default=str))
    pd.DataFrame({'BTCUSDT': -1.}, index=idx).to_parquet(signals)
    assert execute(tmp_path, setup_lab, 'second') == 0
    assert rows(tmp_path)[0]['run_id'] != rows(tmp_path, 'second')[0]['run_id']


def test_prefixed_windows_paths_cannot_bypass_protected_directories(tmp_path, setup_lab, monkeypatch):
    import os
    if os.name != 'nt':
        pytest.skip('Windows path aliases')
    tool = lab()
    monkeypatch.setattr(tool, 'PROJECT_ROOT', tmp_path / 'project')
    data, batch, _ = setup_lab
    protected_cache = tool.io_path(tool.PROJECT_ROOT / 'config' / 'lab-must-not-be-created')
    assert tool.main(['--data-dir', str(data), '--batch', str(batch), '--cache-dir', str(protected_cache), '--output', str(tmp_path / 'out')]) == 2
    assert not protected_cache.exists()
    assert tool.main(['--data-dir', str(tool.io_path(data)), '--batch', str(batch), '--cache-dir', str(tmp_path / 'cache'), '--output', str(data / 'out')]) == 2
    assert not (data / 'out').exists()
