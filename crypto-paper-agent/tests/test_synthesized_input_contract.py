"""Offline regressions for explicit input identity and synchronized replay."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.data_layer.universe_loader import UniverseDataLoader
from src.execution.order_models import OrderDirection
from src.execution.order_models import OrderRequest
from src.strategies.synthesized import SynthesizedStrategy
from scripts.run_synthesized_backtest import load_strategy_config, run_universe_backtest

START = pd.Timestamp('2025-01-01', tz='UTC')
END = START + pd.Timedelta(days=1)


@pytest.mark.parametrize('value', [None, True, '0.0001', float('nan'), float('inf')])
def test_enabled_filter_rejects_unknown_funding(value):
    assert not SynthesizedStrategy({})._apply_funding_filter(OrderDirection.LONG, {'funding_rate': value})


def test_historical_missing_cache_fails_without_writing_synthetic(tmp_path):
    loader = UniverseDataLoader(raw_data_dir=tmp_path)
    with pytest.raises(ValueError, match='historical'):
        loader.load_universe(START, END, symbols=['BTCUSDT'])
    assert not list(tmp_path.rglob('*.parquet'))


def test_unproven_legacy_cache_is_not_upgraded(tmp_path):
    loader = UniverseDataLoader(raw_data_dir=tmp_path)
    data = loader.generate_synthetic_universe(START, END, ['BTCUSDT'])
    for tf, frame in data['BTCUSDT'].items():
        path = loader.get_cache_path('BTCUSDT', tf)
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(path)
    before = {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    with pytest.raises(ValueError, match='provenance'):
        loader.load_universe(START, END, symbols=['BTCUSDT'])
    assert before == {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}


def test_synthetic_cache_identity_is_separate_seeded_and_labelled(tmp_path):
    historical = UniverseDataLoader(raw_data_dir=tmp_path)
    loader = UniverseDataLoader(raw_data_dir=tmp_path, mode='synthetic', seed=7)
    data = loader.load_universe(START, END, symbols=['BTCUSDT'])
    assert loader.get_cache_path('BTCUSDT', '15m') != historical.get_cache_path('BTCUSDT', '15m')
    assert loader.provenance['mode'] == 'synthetic'
    assert loader.provenance['historical_verified'] is False
    assert loader.provenance['seed'] == 7
    assert len(loader.provenance['datasets']) == 2
    assert all(len(d['sha256']) == 64 for d in loader.provenance['datasets'])
    assert data['BTCUSDT']['15m']['funding_source'].eq('synthetic_constant').all()
    assert data['BTCUSDT']['15m']['funding_time'].nunique() == 4
    other = UniverseDataLoader(raw_data_dir=tmp_path, mode='synthetic', seed=8)
    assert not data['BTCUSDT']['15m']['close'].equals(other.load_universe(START, END, symbols=['BTCUSDT'])['BTCUSDT']['15m']['close'])


def test_default_risk_protections_survive_strategy_composition():
    cfg = load_strategy_config()
    assert cfg['risk']['max_notional_pct_of_equity'] == 2.0
    assert cfg['risk']['max_data_gap_minutes'] == 60
    assert cfg['synthesized']['macro_regime']['adx_threshold'] == 20
    assert cfg['leverage'] == 2.5


def test_runner_historical_preflight_preserves_existing_output(tmp_path):
    sentinel = tmp_path / 'trades.sqlite'
    sentinel.write_bytes(b'original evidence')
    with pytest.raises(ValueError):
        run_universe_backtest(start_date='2025-01-01', end_date='2025-01-02', symbols=['BTCUSDT'], output_dir=str(tmp_path))
    assert sentinel.read_bytes() == b'original evidence'


def test_cli_exposes_explicit_mode():
    script = Path(__file__).resolve().parents[1] / 'scripts/run_synthesized_backtest.py'
    result = subprocess.run([sys.executable, str(script), '--help'], capture_output=True, text=True)
    assert result.returncode == 0
    assert '--mode' in result.stdout


def test_enabled_filter_rejects_explicitly_unready_data():
    assert not SynthesizedStrategy({})._apply_funding_filter(OrderDirection.LONG,
        {'funding_rate': 0.0001, 'funding_readiness': False})


def _funded_frame():
    idx = pd.date_range(START, END, freq='15min', name='timestamp').as_unit('ms')
    event = idx.floor('8h')
    return pd.DataFrame({'open': 100., 'high': 101., 'low': 99., 'close': 100., 'volume': 10.,
        'funding_rate': .0001, 'funding_readiness': True, 'funding_time': event, 'funding_interval_hours': 8,
        'funding_source_time': event, 'funding_available_time': event}, index=idx)


def _write_historical(loader, frame, timeframe='15m', symbol='BTCUSDT'):
    # Fixture bytes are fabricated, solely to exercise manifest validation. This
    # is not an assertion of real Binance history or authentic economic evidence.
    return loader.save_to_cache(frame, symbol, timeframe, provenance={
        'source': 'binance_usdm', 'source_uri': 'https://data.binance.vision/test-fixture',
        'market': 'perpetual', 'funding_source': 'binance_usdm'})


def test_historical_hash_rejects_corrupt_cache(tmp_path):
    loader = UniverseDataLoader(raw_data_dir=tmp_path)
    path = _write_historical(loader, _funded_frame())
    path.write_bytes(path.read_bytes() + b'changed')
    with pytest.raises(ValueError, match='identity/hash'):
        loader.load_symbol('BTCUSDT', '15m', START, END)


def test_historical_parser_receives_the_verified_bytes(tmp_path, monkeypatch):
    import src.data_layer.universe_loader as module
    loader = UniverseDataLoader(raw_data_dir=tmp_path)
    original = _funded_frame()
    path = _write_historical(loader, original)
    read_table = module.pq.read_table

    def racing_writer(source, *args, **kwargs):
        # Mutating the path after verification must not change the replay input.
        path.write_bytes(b'concurrent replacement')
        return read_table(source, *args, **kwargs)

    monkeypatch.setattr(module.pq, 'read_table', racing_writer)
    actual = loader.load_symbol('BTCUSDT', '15m', START, END)
    pd.testing.assert_frame_equal(actual, original, check_freq=False)


def test_settlement_rejects_rate_unavailable_until_later_in_candle():
    frame = _funded_frame()
    frame['funding_available_time'] = frame['funding_time'] + pd.Timedelta(minutes=14)
    with pytest.raises(ValueError, match='settlement availability'):
        UniverseDataLoader.validate_funding(frame)


def test_source_manifest_covers_reporting_and_acceptance_code():
    from scripts.run_synthesized_backtest import source_identity
    identity = source_identity()
    for source in ('src/research/acceptance.py', 'src/report/generator.py',
                   'src/report/html_dashboard.py', 'src/execution/paper_broker.py'):
        assert source in identity
        assert len(identity[source]) == 64


def test_runner_rejects_source_changes_before_publishing(tmp_path, monkeypatch):
    import scripts.run_synthesized_backtest as module
    identities = iter(({'source': 'before'}, {'source': 'after'}))
    monkeypatch.setattr(module, 'source_identity', lambda: next(identities))
    output = tmp_path / 'changed-code'
    with pytest.raises(ValueError, match='source changed'):
        module.run_universe_backtest(start_date='2025-01-01', end_date='2025-01-02',
            symbols=['BTCUSDT'], mode='synthetic', output_dir=str(output))
    assert not (output / 'summary.json').exists()


@pytest.mark.parametrize('fault', ['missing', 'nan', 'bool', 'event_gap', 'duplicate', 'future_available', 'future_source'])
def test_historical_rejects_unknown_or_conflicting_funding(tmp_path, fault):
    loader = UniverseDataLoader(raw_data_dir=tmp_path)
    frame = _funded_frame()
    if fault == 'missing':
        frame = frame.drop(columns='funding_rate')
    elif fault == 'nan':
        frame.loc[frame.index[4], 'funding_rate'] = np.nan
    elif fault == 'bool':
        frame['funding_rate'] = True
    elif fault == 'event_gap':
        frame.loc[frame.index[32], 'funding_time'] = START
    elif fault == 'duplicate':
        frame.loc[frame.index[4], 'funding_rate'] = .0002
    elif fault == 'future_available':
        frame.loc[frame.index[4], 'funding_available_time'] = END
    elif fault == 'future_source':
        frame.loc[frame.index[4], 'funding_source_time'] = END
    _write_historical(loader, frame)
    with pytest.raises(ValueError, match='funding'):
        loader.load_symbol('BTCUSDT', '15m', START, END)


def test_historical_preserves_source_jitter_and_actual_event_identity(tmp_path):
    loader = UniverseDataLoader(raw_data_dir=tmp_path)
    frame = _funded_frame()
    frame['funding_source_time'] += pd.Timedelta(milliseconds=47)
    frame['funding_available_time'] = frame['funding_source_time']
    _write_historical(loader, frame)
    loaded = loader.load_symbol('BTCUSDT', '15m', START, END)
    pd.testing.assert_frame_equal(loaded, frame, check_freq=False)


def test_historical_conflicting_canonical_and_legacy_cache_rejected(tmp_path):
    loader = UniverseDataLoader(raw_data_dir=tmp_path)
    path = _write_historical(loader, _funded_frame())
    legacy = loader.get_legacy_cache_path('BTCUSDT', '15m')
    legacy.parent.mkdir(parents=True)
    changed = _funded_frame()
    changed['volume'] *= 2
    changed.to_parquet(legacy)
    manifest = json.loads(path.with_suffix(path.suffix + '.source.json').read_text())
    import hashlib
    manifest['sha256'] = hashlib.sha256(legacy.read_bytes()).hexdigest()
    legacy.with_suffix(legacy.suffix + '.source.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='conflict'):
        loader.load_symbol('BTCUSDT', '15m', START, END)


@pytest.mark.parametrize('interval', [1, 2, 4])
def test_historical_preserves_declared_funding_intervals(tmp_path, interval):
    loader = UniverseDataLoader(raw_data_dir=tmp_path)
    frame = _funded_frame()
    event = frame.index.floor(f'{interval}h')
    frame['funding_time'] = event
    frame['funding_source_time'] = event
    frame['funding_available_time'] = event
    frame['funding_interval_hours'] = interval
    _write_historical(loader, frame)
    loaded = loader.load_symbol('BTCUSDT', '15m', START, END)
    assert loaded['funding_time'].nunique() == 24 // interval + 1
    assert loaded['funding_interval_hours'].eq(interval).all()


def test_runner_peer_future_close_cannot_change_earlier_opening_fill(tmp_path, monkeypatch):
    import scripts.run_synthesized_backtest as runner
    from src.execution.paper_broker import PaperBroker
    monkeypatch.setattr(runner.ReportGenerator, 'generate_all', lambda *a, **k: {})
    future_close = [100.]

    def universe(self, start, end, symbols):
        self.provenance = {'mode': 'synthetic', 'historical_verified': False, 'source': 'synthetic_fixture', 'datasets': []}
        data = {}
        for sym in symbols:
            frame = _funded_frame().loc[start:end].copy()
            if sym == 'BTCUSDT':
                frame.loc[frame.index[1], ['close', 'high']] = [future_close[0], max(101., future_close[0])]
            macro = frame.resample('4h').agg({'open':'first', 'high':'max', 'low':'min', 'close':'last', 'volume':'sum'})
            data[sym] = {'15m': frame, '4h': macro}
        return data

    def signal(self, candle_15m, **kwargs):
        if candle_15m['open_time'] == START:
            return OrderRequest(symbol=self.symbol, direction=OrderDirection.LONG,
                signal_time=candle_15m['close_time'], signal_price=100., stop_loss_price=95.,
                leverage=2.5, base_risk_percent=.004, partial_exits=[])
        return None
    monkeypatch.setattr(runner.UniverseDataLoader, 'load_universe', universe)
    monkeypatch.setattr(runner.SynthesizedStrategy, 'on_candle_close', signal)
    def quantity(name):
        result = runner.run_universe_backtest(start_date='2025-01-01', end_date='2025-01-01 04:00',
            symbols=['BTCUSDT', 'ETHUSDT'], output_dir=str(tmp_path / name), mode='synthetic')
        return next(t.quantity for t in result['broker'].trade_history if t.symbol == 'ETHUSDT')
    original_batch = PaperBroker.process_batch
    monkeypatch.setattr(PaperBroker, 'process_batch', lambda self, cs: [original_batch(self, [c])[0] for c in cs])
    with pytest.raises(ValueError, match='overlap'):
        quantity('forbidden-serial')  # Repaired broker rejects the old runner schedule.
    monkeypatch.setattr(PaperBroker, 'process_batch', original_batch)
    future_close[0] = 100.
    synchronized_before = quantity('synchronized-before')
    future_close[0] = 110.
    assert synchronized_before == quantity('synchronized-after')


def test_runner_rejects_different_configured_timeframe(tmp_path):
    path = tmp_path / 'wrong-timeframe.yaml'
    path.write_text('strategy:\n  timeframe_execution: 1h\n', encoding='utf-8')
    with pytest.raises(ValueError, match='timeframe'):
        run_universe_backtest(start_date='2025-01-01', end_date='2025-01-02', symbols=['BTCUSDT'],
            mode='synthetic', config_path=str(path), output_dir=str(tmp_path / 'output'))


def test_synthetic_runner_artifacts_keep_identity_and_exact_window(tmp_path):
    result = run_universe_backtest(start_date='2025-01-01', end_date='2025-01-02',
        symbols=['BTCUSDT'], output_dir=str(tmp_path / 'reports'), mode='synthetic', seed=23)
    summary = json.loads(Path(result['artifacts']['summary.json']).read_text(encoding='utf-8'))
    assert result['broker'].current_time == END
    assert result['metrics']['bars_15m_count'] == 96
    assert result['metrics']['bars_4h_count'] == 6
    assert result['provenance']['seed'] == 23
    assert result['config']['data']['start_date'] == '2025-01-01'
    assert result['config']['data']['end_date'] == '2025-01-02'
    assert result['config']['data']['timeframes'] == ['15m', '4h']
    assert summary['data_provenance'] == result['provenance']
    assert summary['economic_evaluation']['verdict'] != 'ELIGIBLE_FOR_REVIEW'
    assert summary['source_hashes'] == result['config']['source_hashes']


def test_runner_refuses_to_overwrite_partial_existing_evidence(tmp_path):
    output = tmp_path / 'old'
    output.mkdir()
    original = output / 'summary.json'
    original.write_bytes(b'preserved original')
    with pytest.raises(ValueError, match='Output'):
        run_universe_backtest(start_date='2025-01-01', end_date='2025-01-02',
            symbols=['BTCUSDT'], output_dir=str(output), mode='synthetic')
    assert original.read_bytes() == b'preserved original'


def test_runner_misaligned_peer_rejected_before_output_or_broker_mutation(tmp_path, monkeypatch):
    import scripts.run_synthesized_backtest as runner
    def bad_universe(self, start, end, symbols):
        frame = _funded_frame().loc[start:end]
        shifted = frame.copy()
        shifted.index = shifted.index + pd.Timedelta(minutes=1)
        macro = frame.resample('4h').agg({'open':'first', 'high':'max', 'low':'min', 'close':'last', 'volume':'sum'})
        return {'BTCUSDT': {'15m': frame, '4h': macro}, 'ETHUSDT': {'15m': shifted, '4h': macro}}
    monkeypatch.setattr(runner.UniverseDataLoader, 'load_universe', bad_universe)
    def forbidden_broker(*a, **k):
        pytest.fail('invalid input constructed a broker')
    monkeypatch.setattr(runner, 'PaperBroker', forbidden_broker)
    output = tmp_path / 'invalid'
    with pytest.raises(ValueError, match='Misaligned'):
        runner.run_universe_backtest(start_date='2025-01-01', end_date='2025-01-02',
            symbols=['BTCUSDT', 'ETHUSDT'], output_dir=str(output), mode='synthetic')
    assert not output.exists()
