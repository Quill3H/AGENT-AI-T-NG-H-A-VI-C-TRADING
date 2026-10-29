from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from src.execution.order_models import OrderRequest, OrderStatus
from src.execution.paper_broker import PaperBroker

TIME = datetime(2026, 9, 1, 13, 51, tzinfo=timezone.utc)
SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT']


def broker():
    return PaperBroker({'execution': {'max_concurrent_positions': 4},
                        'fees': {'slippage_pct': 0., 'taker_pct': 0.},
                        'leverage_brackets': {s: [[1000000, .01, 0]] for s in SYMBOLS}},
                       funding_hours=set())


def order(symbol, when=TIME, quantity=1.):
    return OrderRequest(symbol, 'LONG', 100., 95., when,
                        take_profit_price=105., requested_quantity=quantity)


def candle(symbol, when=TIME, **prices):
    return dict(symbol=symbol, open_time=when, timeframe='1m',
                **({'open': 100., 'high': 101., 'low': 99., 'close': 100.} | prices))


def test_four_slots_include_pending_orders():
    b = broker()
    records = [b.submit_order(order(s)) for s in SYMBOLS]
    assert [r.status for r in records] == [OrderStatus.PENDING] * 4 + [OrderStatus.REJECTED]
    assert 'CAPACITY' in records[-1].rejection_reasons[0]


def test_batch_entries_precede_other_symbols_intrabar_outcomes():
    b = broker()
    assert hasattr(b, 'process_batch'), 'causal multi-symbol broker batch is missing'
    for s in SYMBOLS[:2]:
        b.submit_order(order(s))
    b.process_batch([candle(SYMBOLS[0], high=106.), candle(SYMBOLS[1])])
    fills = [r for r in b.order_history if r.status == OrderStatus.FILLED]
    assert len(fills) == 2
    assert b.positions[SYMBOLS[1]].metadata['entry_equity'] == 10000.
    assert b.trade_history[0].exit_time == TIME + timedelta(minutes=1)


def test_batch_sizes_from_all_known_opening_marks():
    b = broker()
    b.submit_order(OrderRequest(SYMBOLS[0], 'LONG', 100., 95., TIME, requested_quantity=10.))
    b.process_candle(candle(SYMBOLS[0], high=102., close=102.))
    b.submit_order(order(SYMBOLS[1], TIME + timedelta(minutes=1)))
    b.process_batch([candle(SYMBOLS[0], TIME + timedelta(minutes=1), open=103., high=104., low=102., close=104.),
                     candle(SYMBOLS[1], TIME + timedelta(minutes=1))])
    assert b.positions[SYMBOLS[1]].metadata['entry_equity'] == 10030.


def test_batch_peak_capacity_and_reentry_after_exit():
    b = broker()
    assert hasattr(b, 'process_batch'), 'causal multi-symbol broker batch is missing'
    for s in SYMBOLS[:4]:
        b.submit_order(order(s))
    events = b.process_batch([candle(s) for s in SYMBOLS])
    assert len(b.positions) == 4
    assert len(events) == 5
    b.request_close(SYMBOLS[0], TIME + timedelta(minutes=1))
    b.process_batch([candle(s, TIME + timedelta(minutes=1)) for s in SYMBOLS])
    assert b.submit_order(order(SYMBOLS[0], TIME + timedelta(minutes=2))).status == OrderStatus.PENDING
    b.process_batch([candle(s, TIME + timedelta(minutes=2)) for s in SYMBOLS])
    assert len(b.positions) == 4
    assert len(b.trade_history) == 1


def test_invalid_batch_is_rejected_before_mutation():
    b = broker()
    assert hasattr(b, 'process_batch'), 'causal multi-symbol broker batch is missing'
    for candles in ([candle(SYMBOLS[0]), candle(SYMBOLS[0])],
                    [candle(SYMBOLS[0]), candle(SYMBOLS[1], high=90.)],
                    [candle(SYMBOLS[0]), candle(SYMBOLS[1], TIME + timedelta(minutes=1))]):
        with pytest.raises(ValueError):
            b.process_batch(candles)
        assert not b.account_snapshots
        assert b.current_time is None


def test_single_symbol_batch_matches_existing_candle_api():
    a, b = broker(), broker()
    assert hasattr(b, 'process_batch'), 'causal multi-symbol broker batch is missing'
    for engine in (a, b):
        engine.submit_order(order(SYMBOLS[0]))
    for bar in [candle(SYMBOLS[0]), candle(SYMBOLS[0], TIME + timedelta(minutes=1), high=106.)]:
        a.process_candle(deepcopy(bar))
        b.process_batch([deepcopy(bar)])
    assert a.wallet_balance == b.wallet_balance
    assert a.trade_history == b.trade_history


@pytest.mark.parametrize('value', [0, -1, True, 4.5, '4'])
def test_invalid_capacity_is_not_silently_ignored(value):
    with pytest.raises((ValueError, TypeError)):
        PaperBroker({'execution': {'max_concurrent_positions': value}})


def portfolio_module():
    import importlib.util
    assert importlib.util.find_spec('scripts.run_crypto_orb_portfolio'), 'portfolio runner is missing'
    from scripts import run_crypto_orb_portfolio
    return run_crypto_orb_portfolio


def pattern_data():
    import pandas as pd
    index = pd.date_range('2026-09-01 13:30', periods=50, freq='min', tz='UTC')
    frame = pd.DataFrame({'open': 100., 'high': 100.1, 'low': 99.9, 'close': 100., 'volume': 10.}, index=index)
    frame.iloc[21:24, :4] = [[100.5, 100.7, 100.4, 100.6],
                              [100.6, 101.4, 100.6, 101.4], [101.4, 101.6, 101.2, 101.5]]
    return frame


def test_signal_is_closed_bar_causal_and_has_quantitative_filter():
    m = portfolio_module()
    frame = pattern_data()
    cfg = m.load_settings({})
    signal_time = frame.index[23]
    assert signal_time in m.find_signals(frame, cfg, .01).index
    mutated = frame.copy()
    mutated.iloc[24:, :4] *= 2
    import pandas as pd
    pd.testing.assert_frame_equal(m.find_signals(frame, cfg, .01).loc[:signal_time],
                                  m.find_signals(mutated, cfg, .01).loc[:signal_time])
    frame.iloc[22, frame.columns.get_loc('open')] = 101.3
    assert signal_time not in m.find_signals(frame, cfg, .01).index


def test_first_signal_does_not_require_two_future_bars():
    import pandas as pd
    m = portfolio_module()
    frame = pattern_data()
    frame.iloc[19:22, :4] = frame.iloc[21:24, :4].to_numpy()
    cfg = m.load_settings({})
    time = frame.index[21]
    complete = m.find_signals(frame, cfg)
    assert time in complete.index
    pd.testing.assert_frame_equal(m.find_signals(frame.loc[:time], cfg), complete.loc[:time])


def test_sample_targets_count_completed_trades_and_include_empty_week():
    import pandas as pd
    m = portfolio_module()
    trades = [{'exit_time': pd.Timestamp('2026-09-21 15:00', tz='UTC')}] * 60
    report = m.sample_report(trades, '2026-09-01', '2026-09-30', 60, 240)
    full = {r['start']: r for r in report['weeks'] if r['full_window']}
    assert full['2026-09-21']['completed_trades'] == 60
    assert full['2026-09-21']['status'] == 'PASS'
    assert full['2026-09-14']['status'] == 'FAIL'
    assert report['months'][0]['status'] == 'FAIL'
    assert report['months'][0]['completed_trades'] == 60


@pytest.mark.parametrize('override', [dict(max_concurrent_positions=5), dict(symbols=['MNQ']),
                                      dict(symbols=['BTCUSDT', 'BTCUSDT']), dict(risk_per_trade=0),
                                      dict(unknown=True), dict(weekly_target=True)])
def test_portfolio_settings_fail_closed(override):
    with pytest.raises(ValueError):
        portfolio_module().load_settings(override)


def test_minute_data_gap_and_nan_are_rejected():
    m = portfolio_module()
    frame = pattern_data()
    m.validate_bars(frame, frame.index, 'test')
    with pytest.raises(ValueError):
        m.validate_bars(frame.drop(frame.index[4]), frame.index, 'test')
    frame.iloc[3, 0] = float('nan')
    with pytest.raises(ValueError):
        m.validate_bars(frame, frame.index, 'test')


def test_portfolio_gross_notional_limit_applies_at_actual_fill():
    b = broker()
    b.config['risk'] = {'max_gross_notional_pct_of_equity': .5}
    for symbol in SYMBOLS[:2]:
        b.submit_order(order(symbol, quantity=40.))
    b.process_batch([candle(s) for s in SYMBOLS[:2]])
    assert len(b.positions) == 1
    assert 'GROSS_NOTIONAL' in b.order_history[-1].rejection_reasons[0]


def test_real_replay_allows_multiple_entries_per_day_but_never_five():
    m = portfolio_module()
    frame = pattern_data()
    frame.iloc[24, :4] = [101.5] * 4
    frame.iloc[36:40, :4] = frame.iloc[21:25, :4].to_numpy()
    cfg = m.load_settings({'symbols': SYMBOLS, 'start': '2026-09-01', 'end': '2026-09-01'})
    import pandas as pd
    funding = {s: pd.DataFrame(columns=['funding_rate', 'funding_source_time']) for s in SYMBOLS}
    result = m.replay({s: frame.copy() for s in SYMBOLS}, funding,
                      {s: {'observed_grid_increment': .01} for s in SYMBOLS}, cfg)
    assert result['summary']['completed_trades'] == 8
    assert result['summary']['peak_positions'] == 4
    assert result['summary']['rejection_counts']['EXECUTION_REJECT_PORTFOLIO_CAPACITY'] == 2
    assert abs(cfg['initial_equity'] + sum(t['net_pnl'] for t in result['trades'])
               - result['summary']['final_equity']) < 1e-8


def test_future_archive_grid_cannot_change_earlier_replay_stop():
    import pandas as pd
    m = portfolio_module()
    cfg = m.load_settings({'symbols': SYMBOLS[:1], 'start': '2026-09-01', 'end': '2026-09-01'})
    frame = pattern_data()
    frame.iloc[24, :4] = [101.5] * 4
    later = frame.copy()
    later.iloc[30:, :4] += .03
    funding = {SYMBOLS[0]: pd.DataFrame(columns=['funding_rate', 'funding_source_time'])}
    def run(bars, whole_archive_grid):
        return m.replay({SYMBOLS[0]: bars}, funding,
                        {SYMBOLS[0]: {'observed_grid_increment': whole_archive_grid}}, cfg)
    a, b = run(frame, .1), run(later, .01)
    assert a['trades'][0]['initial_stop_loss_price'] == b['trades'][0]['initial_stop_loss_price']
    assert a['trades'][0]['initial_stop_loss_price'] == pytest.approx(100.3)


def test_portfolio_cli_publishes_and_reuses_verified_cache(tmp_path, monkeypatch):
    import json
    import pandas as pd
    import yaml
    from scripts import backtest_lab
    m = portfolio_module()
    data = tmp_path / 'data'
    data.mkdir()
    cfg = m.load_settings({'symbols': SYMBOLS[:1], 'start': '2026-09-01', 'end': '2026-09-01'})
    config = tmp_path / 'job.yaml'
    config.write_text(yaml.safe_dump(cfg), encoding='utf-8')
    for prefix in ('klines_BTCUSDT-1m', 'klines_BTCUSDT-15m', 'fundingRate_BTCUSDT-fundingRate'):
        for suffix in ('.zip', '.zip.CHECKSUM'):
            (data / (prefix + '-2026-09' + suffix)).write_bytes(b'fixture')
    def load(*args):
        return ({SYMBOLS[0]: pattern_data()},
                {SYMBOLS[0]: pd.DataFrame(columns=['funding_rate', 'funding_source_time'])},
                {SYMBOLS[0]: {'status': 'PASS', 'observed_grid_increment': .01}})
    monkeypatch.setattr(m, 'load_archive', load)
    args = ['--data-dir', str(data), '--portfolio-config', str(config), '--cache-dir', str(tmp_path / 'cache')]
    assert backtest_lab.main(args + ['--output', str(tmp_path / 'first')]) == 0
    first = json.loads((tmp_path / 'first/result.json').read_text())
    assert not first['cached']
    assert (tmp_path / 'first/trades.csv').is_file()
    monkeypatch.setattr(m, 'replay', lambda *a: pytest.fail('cache hit must not replay'))
    assert backtest_lab.main(args + ['--output', str(tmp_path / 'second')]) == 0
    second = json.loads((tmp_path / 'second/result.json').read_text())
    assert second['cached'] and second['summary'] == first['summary']
    assert backtest_lab.main(args + ['--output', str(tmp_path / 'first')]) == 2


def test_zip_checksum_corruption_fails_closed(tmp_path):
    from zipfile import ZipFile
    import hashlib
    m = portfolio_module()
    path = tmp_path / 'bars.zip'
    with ZipFile(path, 'w') as archive:
        archive.writestr('bars.csv', 'open,close\n100,101\n')
    sidecar = path.with_suffix('.zip.CHECKSUM')
    sidecar.write_text(hashlib.sha256(path.read_bytes()).hexdigest() + ' bars.zip')
    assert m.read_zip(path).iloc[0]['close'] == 101
    path.write_bytes(path.read_bytes() + b'corruption')
    with pytest.raises(ValueError, match='checksum'):
        m.read_zip(path)
