"""Independent-review regressions: storage evidence is never a new account."""
import json
from datetime import timedelta

import pytest

from src.paper.live_session import LocalPaperSession, parse_klines
from src.execution.order_models import OrderRequest
from src.paper.public_stream import PublicKlineStream, parse_stream_event
from test_local_paper_session import FakeSource, BASE, stream_bar
from test_local_paper_session import rows
from test_local_paper_stream import event


@pytest.mark.parametrize('name,payload', [
    ('state.json', '{'), ('state.json', '{}'), ('state.json.tmp', '{"wallet":'),
    ('old.jsonl', ''), ('old.jsonl', '{"type":'), ('old.jsonl', '[]\n'),
    ('account.json', '{}'),
])
def test_orphan_or_invalid_storage_never_reports_fresh_money(tmp_path, name, payload):
    path = tmp_path / name
    path.write_text(payload, encoding='utf-8')
    session = LocalPaperSession(source=FakeSource(), journal_dir=tmp_path)
    result = session.start()
    assert result['status'] == 'RECOVERY_REQUIRED'
    assert result['account']['wallet_usd'] is None
    assert result['risk_gate']['admission_open'] is False
    assert session.broker is None
    assert path.read_text(encoding='utf-8') == payload


@pytest.mark.parametrize('damage', ['journal_missing', 'journal_partial', 'journal_revised', 'checkpoint_missing', 'checkpoint_partial'])
def test_checkpoint_and_journal_must_agree(tmp_path, damage):
    session = LocalPaperSession(source=FakeSource(), journal_dir=tmp_path)
    session.start()
    journal = next(tmp_path.glob('*.jsonl'))
    checkpoint = tmp_path / 'account.json'
    if damage == 'journal_missing':
        journal.unlink()
    elif damage == 'journal_partial':
        with journal.open('a', encoding='utf-8') as stream:
            stream.write('{"type":')
    elif damage == 'journal_revised':
        journal.write_bytes(journal.read_bytes().replace(b'10000', b'90000'))
    elif damage == 'checkpoint_missing':
        checkpoint.unlink(missing_ok=True)
    else:
        checkpoint.write_text('{', encoding='utf-8')
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    restarted = LocalPaperSession(source=FakeSource(), journal_dir=tmp_path)
    assert restarted.start()['status'] == 'RECOVERY_REQUIRED'
    assert restarted.state()['account']['wallet_usd'] is None
    assert restarted.broker is None
    restarted.stop()
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()} == before


def test_misaligned_closed_events_request_transport_reconnect(tmp_path):
    session = LocalPaperSession(source=FakeSource(), journal_dir=tmp_path)
    session.start()
    session.on_connection(True, None)
    session.on_stream_event(stream_bar('BTCUSDT'))
    session.on_stream_event(stream_bar('ETHUSDT'))
    state = session.on_stream_event(stream_bar('SOLUSDT', BASE + timedelta(minutes=15)))
    assert state['connection']['reconnect_required'] is True
    assert state['risk_gate']['admission_open'] is False
    assert session.broker.account_snapshots == []


@pytest.mark.parametrize('exposure', ['position', 'pending', 'funding'])
def test_long_downtime_preserves_all_exposure_read_only(tmp_path, exposure):
    source = FakeSource()
    session = LocalPaperSession(source=source, journal_dir=tmp_path)
    session.start()
    session.broker.submit_order(OrderRequest(symbol='BTCUSDT', direction='LONG',
        signal_price=100, stop_loss_price=90, signal_time=BASE))
    if exposure != 'pending':
        source.phase = 1
        source.now = int((BASE + timedelta(minutes=16)).timestamp() * 1000)
        session.poll()
        assert session.broker.positions['BTCUSDT'].quantity > 0
    if exposure == 'funding':
        # Pending settlement is not fabricated or backdated from a later REST window.
        with pytest.raises(ValueError, match='funding'):
            session._funding_metadata('BTCUSDT', BASE + timedelta(hours=4))
        session.status = 'QUARANTINED'
        session.error = 'funding provenance unavailable'
    session._journal({'type': 'PAPER_BATCH', 'state': session.state()})
    before = session.state()
    source.now += 90 * 24 * 60 * 60 * 1000
    def forbidden(*args):
        pytest.fail('restart must not use recent REST candles to resume old exposure')
    source.klines = forbidden
    restarted = LocalPaperSession(source=source, journal_dir=tmp_path)
    after = restarted.start()
    assert after['status'] == 'RECOVERY_REQUIRED'
    for field in ('account', 'open_positions', 'pending_orders', 'orders', 'funding_events'):
        assert after[field] == before[field]
    assert after['recovery']['reconciled'] is False
    assert restarted.broker is None
    assert restarted.stop()['status'] == 'RECOVERY_REQUIRED'


def test_pending_mutation_cannot_present_previous_balance_as_current(tmp_path):
    session = LocalPaperSession(source=FakeSource(), journal_dir=tmp_path)
    session.start()
    session._journal({'type': 'PAPER_INPUT', 'received_at_utc': BASE.isoformat()})
    restarted = LocalPaperSession(source=FakeSource(), journal_dir=tmp_path)
    assert restarted.state()['status'] == 'RECOVERY_REQUIRED'
    assert restarted.state()['account']['equity_usd'] is None


def test_disk_failure_at_start_is_recovery_not_retryable_new_account(tmp_path, monkeypatch):
    import src.paper.durable_journal as journal
    def disk_full(*args):
        raise OSError('disk full')
    monkeypatch.setattr(journal.os, 'replace', disk_full)
    session = LocalPaperSession(source=FakeSource(), journal_dir=tmp_path)
    with pytest.raises(OSError, match='disk full'):
        session.start()
    assert session.state()['status'] == 'RECOVERY_REQUIRED'
    assert session.state()['account']['wallet_usd'] is None
    assert session.start()['status'] == 'RECOVERY_REQUIRED'


def test_transport_closes_socket_when_session_requests_reconnect(monkeypatch):
    import websocket
    from threading import Event
    raw = event(closed=True)
    monkeypatch.setattr('src.paper.public_stream.time.time', lambda: (raw['data']['E'] + 100) / 1000)
    stopped = Event()
    sockets = []
    connections = []
    class Socket:
        def __init__(self, url, **callbacks):
            self.callbacks, self.closed = callbacks, False
            sockets.append(self)
        def close(self):
            self.closed = True
        def run_forever(self, **kwargs):
            self.callbacks['on_open'](self)
            self.callbacks['on_message'](self, json.dumps(raw))
            stopped.set()
    monkeypatch.setattr(websocket, 'WebSocketApp', Socket)
    stream = PublicKlineStream(lambda e: {'status': 'WAITING_CONNECTION',
        'connection': {'reconnect_required': True}}, lambda ok, reason: connections.append(ok), stopped)
    stream.run()
    assert sockets[0].closed
    assert connections[-1] is False


@pytest.mark.parametrize('field', ['o', 'h', 'l', 'c', 'v'])
def test_boolean_price_is_rejected(field):
    raw = event()
    raw['data']['k'][field] = True
    with pytest.raises(ValueError):
        parse_stream_event(raw, raw['data']['E'] + 100)


def test_stream_and_rest_price_disagreement_blocks_before_fill(tmp_path):
    source = FakeSource()
    session = LocalPaperSession(source=source, journal_dir=tmp_path)
    session.start()
    session.on_connection(True, None)
    source.phase = 1
    source.now = int((BASE + timedelta(minutes=16)).timestamp() * 1000)
    for symbol in ('BTCUSDT', 'ETHUSDT', 'SOLUSDT'):
        bar = stream_bar(symbol)
        bar['close'] = 100.5
        state = session.on_stream_event(bar)
    assert state['status'] == 'QUARANTINED'
    assert session.broker.account_snapshots == []


def test_reconnect_discards_old_partial_batch_then_processes_once(tmp_path):
    source = FakeSource()
    session = LocalPaperSession(source=source, journal_dir=tmp_path)
    session.start()
    session.on_connection(True, None)
    session.on_stream_event(stream_bar('BTCUSDT'))
    session.on_connection(False, 'network lost')
    session.on_connection(True, None)
    source.phase = 1
    source.now = int((BASE + timedelta(minutes=16)).timestamp() * 1000)
    for symbol in ('ETHUSDT', 'SOLUSDT'):
        session.on_stream_event(stream_bar(symbol))
    assert session.broker.account_snapshots == []
    session.on_stream_event(stream_bar('BTCUSDT'))
    assert len(session.broker.account_snapshots) == 3
    session.on_stream_event(stream_bar('BTCUSDT'))
    assert len(session.broker.account_snapshots) == 3


@pytest.mark.parametrize('column', [3, 5])
def test_rest_boolean_values_fail_before_becoming_valid_prices(column):
    raw = rows(BASE, 1, 15)
    raw[0][column] = True
    with pytest.raises(ValueError):
        parse_klines(raw, '15m', int((BASE + timedelta(minutes=16)).timestamp() * 1000))


def test_rest_future_provisional_open_is_rejected():
    with pytest.raises(ValueError):
        parse_klines(rows(BASE + timedelta(minutes=15), 1, 15), '15m', int(BASE.timestamp()*1000))


def test_provisional_display_updates_cannot_mutate_durable_snapshot(tmp_path):
    session = LocalPaperSession(source=FakeSource(), journal_dir=tmp_path)
    session.start()
    session.on_connection(True, None)
    session.on_stream_event(stream_bar('BTCUSDT', closed=False))
    session.on_stream_event(stream_bar('BTCUSDT'))
    restarted = LocalPaperSession(source=FakeSource(), journal_dir=tmp_path)
    assert restarted.state()['status'] == 'RECOVERY_REQUIRED'
    assert restarted.state()['account']['wallet_usd'] == 10000.0
    assert restarted.state()['recovery']['view'] == 'LAST_DURABLE_SNAPSHOT'
