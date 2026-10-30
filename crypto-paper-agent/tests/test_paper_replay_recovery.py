"""Complete public-range replay with real broker/storage; fixtures are not live evidence."""
from datetime import timedelta
from pathlib import Path

import pytest
import requests

from src.execution.order_models import OrderRequest
from src.paper.public_stream import SYMBOLS
from test_local_paper_session import BASE, FakeSource, rows


class RangeSource(FakeSource):
    def __init__(self):
        super().__init__()
        self.range_calls = []
        self.offline = False
        self.bad = None

    def klines(self, symbol, interval, limit):
        result = super().klines(symbol, interval, limit)
        if interval == '4h':
            for bar in result:
                bar[5] = '80'
        return result

    def server_time_ms(self):
        if self.offline:
            raise requests.ConnectionError('fixture network disconnected')
        return self.now

    def klines_range(self, symbol, interval, start_ms, end_ms, limit):
        if self.offline:
            raise requests.ConnectionError('fixture network disconnected')
        self.range_calls.append((symbol, interval, start_ms, end_ms, limit))
        minutes = 15 if interval == '15m' else 240
        count = min(limit, (end_ms + 1 - start_ms) // (minutes * 60000))
        from src.paper.live_session import _utc
        result = rows(_utc(start_ms), count, minutes)
        if interval == '4h':
            for bar in result:
                bar[5] = '80'  # 16 execution candles, each with volume 5.
        if self.bad == symbol and result:
            result[0][5] = 'NaN'
        return result


def create(tmp_path, source=None):
    from src.paper.replay_session import PaperReplaySession
    source = source or RangeSource()
    session = PaperReplaySession(source=source, journal_dir=tmp_path)
    assert session.start()['status'] == 'SCANNING'
    return session, source


def test_missing_compact_database_is_recovery_required_not_new_capital(tmp_path):
    from src.paper.replay_session import PaperReplaySession
    session, source = create(tmp_path)
    session.shutdown()
    (tmp_path / 'paper.sqlite3').unlink()
    restarted = PaperReplaySession(source=source, journal_dir=tmp_path)
    try:
        for _ in range(2):
            state = restarted.start()
            assert state['status'] == 'RECOVERY_REQUIRED'
            assert state['account']['equity_usd'] is None
            assert state['trials'] is None
            assert not state['risk_gate']['admission_open']
            assert not (tmp_path / 'paper.sqlite3').exists()
    finally:
        restarted.shutdown()


def test_owner_authorized_separate_profile_preserves_all_legacy_bytes(tmp_path, monkeypatch):
    from src.paper import replay_session
    legacy = tmp_path / 'paper_sessions'
    legacy.mkdir()
    (legacy / 'persistent_state.json').write_bytes(b'{"legacy":"incomplete evidence"}')
    (legacy / 'old.jsonl').write_bytes(b'{"kind":"old_result","equity":7300}\n')
    before = {p.name: p.read_bytes() for p in legacy.iterdir()}
    separate = tmp_path / 'paper_accounts' / 'windows-paper-v3'
    monkeypatch.setattr(replay_session, 'DEFAULT_ACCOUNT_DIR', separate)
    session = replay_session.PaperReplaySession(source=RangeSource())
    try:
        state = session.start()
        assert state['status'] == 'SCANNING', state['error']
        assert state['account_profile'] == 'windows-paper-v3'
        assert state['account']['equity_usd'] == 10000
        assert state['trials']['total_capital_injected_usd'] == 10000
        assert {p.name: p.read_bytes() for p in legacy.iterdir()} == before
        assert (separate / 'paper.sqlite3').exists()
        assert len([e for e in session.history()['items'] if e['kind'] == 'ACCOUNT_START']) == 1
    finally:
        session.shutdown()


def test_outage_longer_than_rest_page_replays_all_pending_and_funding_once(tmp_path):
    from src.paper.replay_session import PaperReplaySession
    session, source = create(tmp_path)
    session.broker.submit_order(OrderRequest(symbol='BTCUSDT', direction='SHORT',
        signal_price=100, stop_loss_price=150, signal_time=BASE, requested_quantity=1))
    session.checkpoint()
    original_id = session.session_id
    session.shutdown()
    source.now = int((BASE + timedelta(minutes=15 * 513, seconds=1)).timestamp() * 1000)
    restarted = PaperReplaySession(source=source, journal_dir=tmp_path, auto_resume=True)
    try:
        state = restarted.state()
        assert state['status'] == 'WAITING_CONNECTION', state['error']
        assert state['execution_mode'] == 'REPLAY'
        assert state['risk_gate']['admission_open'] is False
        assert restarted.session_id == original_id
        assert state['last_processed_open_utc'] == (BASE + timedelta(minutes=15 * 512)).isoformat()
        assert len([r for r in source.range_calls if r[0] == 'BTCUSDT' and r[1] == '15m']) == 2
        assert len(restarted.broker.order_history) == 1
        assert len(restarted.broker.funding_history) == 16
        assert restarted.broker.wallet_balance != 10000
        wallet, funding = restarted.broker.wallet_balance, list(restarted.broker.funding_history)
    finally:
        restarted.shutdown()
    again = PaperReplaySession(source=source, journal_dir=tmp_path, auto_resume=True)
    try:
        assert again.broker.wallet_balance == wallet
        assert again.broker.funding_history == funding
        assert len(again.broker.order_history) == 1
        assert again.state()['funding_model']['kind'] == 'FIXED_SIMULATED'
    finally:
        again.shutdown()


def test_network_restart_retains_full_machine_and_can_reconnect(tmp_path):
    from src.paper.replay_session import PaperReplaySession
    session, source = create(tmp_path)
    session.broker.submit_order(OrderRequest(symbol='BTCUSDT', direction='LONG',
        signal_price=100, stop_loss_price=90, signal_time=BASE, requested_quantity=1))
    session.checkpoint()
    session.shutdown()
    source.offline = True
    resumed = PaperReplaySession(source=source, journal_dir=tmp_path, auto_resume=True)
    try:
        assert resumed.state()['status'] == 'WAITING_CONNECTION'
        assert len(resumed.broker.pending_orders) == 1
        assert resumed.state()['current_prices']['BTCUSDT']['price'] is None
        source.offline = False
        source.now = int((BASE + timedelta(minutes=16)).timestamp() * 1000)
        resumed.on_connection(True, None)
        assert len(resumed.broker.positions) == 1
        assert resumed.broker.order_history[0].filled_quantity == 1
    finally:
        resumed.shutdown()


def test_malformed_symbol_blocks_before_any_batch_commit(tmp_path):
    from src.paper.replay_session import PaperReplaySession
    session, source = create(tmp_path)
    initial = session.runner.capture()
    source.bad = 'SOLUSDT'
    source.now = int((BASE + timedelta(minutes=31)).timestamp() * 1000)
    session.on_connection(True, None)
    state = session.state()
    assert not state['risk_gate']['admission_open']
    assert state['status'] in ('RECOVERY_REQUIRED', 'WAITING_CONNECTION')
    assert session.runner.capture() == initial
    session.shutdown()


def test_corrupt_database_never_fetches_market_or_allocates_capital(tmp_path):
    from src.paper.replay_session import PaperReplaySession
    path = tmp_path / 'paper.sqlite3'
    path.write_bytes(b'torn database')
    source = RangeSource()
    source.server_time_ms = lambda: pytest.fail('invalid account must not fetch source')
    session = PaperReplaySession(source=source, journal_dir=tmp_path, auto_resume=True)
    assert session.state()['status'] == 'RECOVERY_REQUIRED'
    assert session.state()['account']['wallet_usd'] is None
    assert session.broker is None
    assert path.read_bytes() == b'torn database'
    session.shutdown()


def test_pause_and_terminal_stop_intent_survive_restarts(tmp_path):
    from src.paper.replay_session import PaperReplaySession
    session, source = create(tmp_path)
    assert session.pause()['operator_intent'] == 'PAUSED'
    session.shutdown()
    resumed = PaperReplaySession(source=source, journal_dir=tmp_path, auto_resume=True)
    assert resumed.state()['operator_intent'] == 'PAUSED'
    assert not resumed.state()['risk_gate']['admission_open']
    # Stop takes effect now, never retroactively at the old source baseline.
    assert resumed.stop()['status'] == 'STOPPING'
    resumed.shutdown()
    stopped = PaperReplaySession(source=source, journal_dir=tmp_path, auto_resume=True)
    assert stopped.state()['operator_intent'] == 'STOPPING'
    assert stopped.start()['operator_intent'] == 'STOPPING'
    stopped.shutdown()


def test_storage_failure_on_pause_blocks_without_committing_intent(tmp_path, monkeypatch):
    session, source = create(tmp_path)
    before = session.runner.capture()
    def disk_error(*args, **kwargs):
        raise OSError('fixture disk full')
    monkeypatch.setattr(session.storage, 'commit', disk_error)
    state = session.pause()
    assert state['status'] == 'RECOVERY_REQUIRED'
    assert 'disk full' in state['error']
    assert not state['risk_gate']['admission_open']
    assert session.runner.capture() == before
    session.shutdown()


def test_fresh_account_failed_transport_can_retry_without_second_allocation(tmp_path):
    from src.paper.replay_session import PaperReplaySession
    source = RangeSource()
    source.offline = True
    session = PaperReplaySession(source=source, journal_dir=tmp_path)
    try:
        assert session.start()['status'] == 'WAITING_CONNECTION'
        assert not session.storage.path.exists()
        source.offline = False
        assert session.start()['status'] == 'SCANNING'
        assert session.broker.wallet_balance == 10000
        session.start()
        assert len([e for e in session._all_events() if e['kind'] == 'ACCOUNT_START']) == 1
    finally:
        session.shutdown()


def test_future_perturbation_in_downloaded_pages_leaves_past_execution_identical(tmp_path):
    from src.paper.recovery_state import pack
    from src.paper.replay_session import PaperReplaySession
    from copy import deepcopy
    cutoff = BASE + timedelta(hours=4)
    histories = []
    for version in (100, 120):
        source = RangeSource()
        original = source.klines_range
        def perturbed(symbol, interval, start_ms, end_ms, limit):
            result = original(symbol, interval, start_ms, end_ms, limit)
            for r in result:
                if r[0] >= int(cutoff.timestamp() * 1000):
                    r[1:5] = [str(version), str(version + 1), str(version - 1), str(version)]
            return result
        source.klines_range = perturbed
        session, _ = create(tmp_path / str(version), source)
        session.broker.submit_order(OrderRequest(symbol='BTCUSDT', direction='LONG',
            signal_price=100, stop_loss_price=90, signal_time=BASE, requested_quantity=1))
        session.checkpoint()
        original_persist = session._persist
        checkpoints = []
        def capture(candidate, inputs, extra_events, batch_id, **kwargs):
            original_persist(candidate, inputs, extra_events, batch_id, **kwargs)
            if candidate.last_open['BTCUSDT'] + timedelta(minutes=15) <= cutoff:
                checkpoints.append((deepcopy(candidate.capture()), pack(candidate.broker.order_history),
                                    pack(candidate.broker.trade_history), pack(candidate.signal_history)))
        session._persist = capture
        source.now = int((BASE + timedelta(hours=8, seconds=1)).timestamp() * 1000)
        try:
            session.on_connection(True, None)
            assert session.status != 'RECOVERY_REQUIRED', session.error
            assert len(checkpoints) == 16
            assert session.broker.order_history[0].filled_quantity == 1
            histories.append(checkpoints)
        finally:
            session.shutdown()
    assert histories[0] == histories[1]


def test_research_cache_older_than_feature_seed_does_not_reseed_on_restart(tmp_path):
    from src.paper.causal_runner import stored_bar, validate_bar
    from src.paper.replay_session import PaperReplaySession
    from src.paper.live_session import parse_klines
    session, source = create(tmp_path)
    before = session.runner.capture()
    oldest = session.runner.signal_history['BTCUSDT'][0]['open_time'] - timedelta(hours=4)
    raw, _ = parse_klines(rows(oldest, 1, 240), '4h', source.now)
    input_bar = stored_bar(validate_bar(raw[0], 'BTCUSDT', '4h'))
    session._persist(session.runner.fork(), [input_bar], [], 'older-research-cache')
    session.shutdown()
    restored = PaperReplaySession(source=source, journal_dir=tmp_path, auto_resume=True)
    try:
        assert restored.status == 'WAITING_CONNECTION', restored.error
        assert restored.runner.capture() == before
    finally:
        restored.shutdown()


def test_failed_account_missing_research_data_never_resets_capital(tmp_path, monkeypatch):
    from src.paper.replay_session import PaperReplaySession
    from test_paper_causal_runner import batch
    session, source = create(tmp_path)
    session.broker.submit_order(OrderRequest(symbol='BTCUSDT', direction='LONG', leverage=3,
        signal_price=100, stop_loss_price=99.75, signal_time=BASE, requested_quantity=190))
    candidate = session.runner.fork()
    first = batch(BASE)
    first['BTCUSDT'].update(low=99.99, high=100.05)
    candidate.advance(first)
    candidate.advance(batch(BASE + timedelta(minutes=15), 60))
    session._persist(candidate, candidate.all_inputs(), [], 'fixture-real-gap-loss')
    equity = session.broker.equity
    assert equity < 5000
    def missing(cutoff):
        raise ValueError('missing historical research coverage')
    monkeypatch.setattr(session, '_research_inputs', missing)
    try:
        result = session.run_research()
        assert result['research']['status'] == 'DATA_BLOCKED'
        assert result['trials']['total_capital_injected_usd'] == 10000
        assert result['account']['wallet_usd'] == equity
        assert not result['risk_gate']['admission_open']
        session.run_research()
        assert len([e for e in session._all_events() if e['kind'] == 'RESEARCH_VERDICT']) == 1
    finally:
        session.shutdown()
    source.now = int((BASE + timedelta(minutes=31)).timestamp() * 1000)
    resumed = PaperReplaySession(source=source, journal_dir=tmp_path, auto_resume=True)
    try:
        assert resumed.broker.equity == equity
        assert resumed.runner.trials.total_capital_injected == 10000
        assert resumed.state()['research']['status'] == 'DATA_BLOCKED'
    finally:
        resumed.shutdown()


def test_state_remains_responsive_and_gate_closed_during_stalled_history(tmp_path):
    from threading import Event, Thread
    import time
    session, source = create(tmp_path)
    entered, release = Event(), Event()
    original = source.server_time_ms
    def slow():
        entered.set()
        assert release.wait(5)
        return original()
    source.server_time_ms = slow
    worker = Thread(target=lambda: session.on_connection(True, None))
    worker.start()
    try:
        assert entered.wait(2)
        before = time.monotonic()
        state = session.state()
        assert time.monotonic() - before < 1
        assert state['backend_busy'] is True
        assert not state['risk_gate']['admission_open']
        assert not state['connection']['connected']
        before = time.monotonic()
        with pytest.raises(BlockingIOError, match='busy'):
            session.history()
        assert time.monotonic() - before < 1
    finally:
        release.set()
        worker.join(5)
        session.shutdown()


def stream_event(symbol, opened, closed=True):
    stamp = opened + timedelta(minutes=15) if closed else opened + timedelta(seconds=1)
    return dict(symbol=symbol, interval='15m', open_time=opened,
                close_time=opened + timedelta(minutes=15), event_time=stamp,
                received_at=stamp, available_at=stamp, closed=closed,
                open=100.0, high=101.0, low=99.0, close=100.0, volume=5.0)


def test_partial_batch_duplicate_ignores_later_receipt_not_canonical_revision(tmp_path):
    session, source = create(tmp_path)
    try:
        session.on_connection(True, None)
        value = stream_event('BTCUSDT', BASE)
        session.clock = lambda: value['received_at']
        session.on_stream_event(value)
        duplicate = dict(value, received_at=value['received_at'] + timedelta(seconds=1),
                         available_at=value['received_at'] + timedelta(seconds=1))
        session.clock = lambda: duplicate['received_at']
        state = session.on_stream_event(duplicate)
        assert state['status'] == 'WAITING_SYNC'
        assert state['connection']['connected'] is True
        assert list(session.stream_closed) == ['BTCUSDT']
        assert session.last_open['BTCUSDT'] == BASE - timedelta(minutes=15)
    finally:
        session.shutdown()


def test_shutdown_request_cancels_replay_at_committed_boundary(tmp_path):
    from threading import Event, Thread
    session, source = create(tmp_path)
    entered, release = Event(), Event()
    original = source.klines_range
    def slow(*args, **kwargs):
        entered.set()
        assert release.wait(3)
        return original(*args, **kwargs)
    source.klines_range = slow
    source.now = int((BASE + timedelta(minutes=31)).timestamp() * 1000)
    before = session.runner.capture()
    worker = Thread(target=lambda: session.on_connection(True, None))
    worker.start()
    try:
        assert entered.wait(2)
        session.request_shutdown()
        release.set()
        worker.join(3)
        assert not worker.is_alive()
        assert session.runner.capture() == before
        assert session.status != 'RECOVERY_REQUIRED'
        session.ownership.assert_owned()
    finally:
        release.set()
        worker.join(5)
        session.shutdown()


@pytest.mark.parametrize('case', ['future', 'stale', 'revision', 'partial_conflict'])
def test_stream_decision_seam_does_not_trust_caller_provenance(tmp_path, case):
    session, source = create(tmp_path)
    session.on_connection(True, None)
    before = session.runner.capture()
    value = stream_event('BTCUSDT', BASE)
    session.clock = lambda: value['received_at']
    if case == 'future':
        value['event_time'] = value['received_at'] + timedelta(seconds=1)
    elif case == 'stale':
        value['received_at'] += timedelta(seconds=31)
        value['available_at'] = value['received_at']
    elif case == 'revision':
        value = stream_event('BTCUSDT', BASE - timedelta(minutes=15))
        value['high'] = 500.0
    else:
        session.on_stream_event(value)
        assert 'BTCUSDT' in session.stream_closed
        value = stream_event('BTCUSDT', BASE + timedelta(minutes=15))
    state = session.on_stream_event(value)
    try:
        assert state['status'] in ('RECOVERY_REQUIRED', 'WAITING_CONNECTION')
        assert not state['risk_gate']['admission_open']
        assert session.runner.capture() == before
    finally:
        session.shutdown()


def test_exact_legacy_v2_migration_preserves_original_files_and_pending_order(tmp_path):
    from src.paper.live_session import LocalPaperSession
    from src.paper.replay_session import PaperReplaySession
    source = RangeSource()
    legacy = LocalPaperSession(source=source, journal_dir=tmp_path)
    legacy.start()
    legacy.broker.submit_order(OrderRequest(symbol='BTCUSDT', direction='LONG',
        signal_price=100, stop_loss_price=90, signal_time=BASE, requested_quantity=1))
    legacy.checkpoint()
    legacy.shutdown()
    originals = {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.suffix in ('.json', '.jsonl')}
    migrated = PaperReplaySession(source=source, journal_dir=tmp_path, auto_resume=True)
    try:
        assert migrated.state()['status'] == 'WAITING_CONNECTION', migrated.state()['error']
        assert len(migrated.broker.pending_orders) == 1
        assert migrated.broker.wallet_balance == 10000
        assert migrated.state()['funding_model']['effective_at_utc'] == BASE.isoformat()
        assert all((tmp_path / name).read_bytes() == value for name, value in originals.items())
        assert len([e for e in migrated._all_events() if e['kind'] == 'LEGACY_MIGRATION']) == 1
    finally:
        migrated.shutdown()


def test_legacy_gap_with_unproven_funding_is_not_erased_by_fixed_switch(tmp_path):
    from src.paper.live_session import LocalPaperSession
    from src.paper.replay_session import PaperReplaySession
    source = RangeSource()
    legacy = LocalPaperSession(source=source, journal_dir=tmp_path)
    legacy.start()
    legacy.broker.submit_order(OrderRequest(symbol='BTCUSDT', direction='LONG',
        signal_price=100, stop_loss_price=90, signal_time=BASE, requested_quantity=1))
    legacy.checkpoint()
    legacy.shutdown()
    original = (tmp_path / 'account.json').read_bytes()
    source.now = int((BASE + timedelta(hours=24)).timestamp() * 1000)
    migrated = PaperReplaySession(source=source, journal_dir=tmp_path, auto_resume=True)
    assert migrated.state()['status'] == 'RECOVERY_REQUIRED'
    assert migrated.state()['risk_gate']['admission_open'] is False
    assert not (tmp_path / 'paper.sqlite3').exists()
    assert (tmp_path / 'account.json').read_bytes() == original
    migrated.shutdown()
