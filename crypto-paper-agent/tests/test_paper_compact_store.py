"""Compact state must be atomic, immutable and independently verifiable."""
import json
import sqlite3
import subprocess
import sys

import pytest

from src.paper.account_lock import AccountOwnershipLock


def make_store(tmp_path):
    from src.paper.compact_store import PaperStore
    owner = AccountOwnershipLock(tmp_path)
    owner.acquire()
    return PaperStore(tmp_path, owner), owner


def sample(close=100):
    return dict(symbol='BTCUSDT', interval='15m', open_time='2026-10-01T00:00:00+00:00',
                close_time='2026-10-01T00:15:00+00:00', open=100, high=101,
                low=99, close=close, volume=2, source='Binance USD-M REST',
                exchange_close_ms=1790813699999, received_at_utc='2026-10-01T00:15:01+00:00')


def test_atomic_commit_and_input_deduplication(tmp_path):
    store, owner = make_store(tmp_path)
    try:
        assert store.inspect() is None
        first = store.commit('account-1', {'version': 1}, [sample()],
                             [{'key': 'event-1', 'kind': 'START', 'value': 10000}], {'cash': 10000}, 'batch-1')
        assert store.inspect()['machine'] == {'cash': 10000}
        later_receipt = sample()
        later_receipt['received_at_utc'] = '2026-10-01T01:00:00+00:00'
        store.commit('account-1', {'version': 1}, [later_receipt], [], {'cash': 10000}, 'batch-2')
        assert len(store.inputs('BTCUSDT', '15m')) == 1
        with pytest.raises(ValueError, match='conflict'):
            store.commit('account-1', {'version': 1}, [sample(100.5)], [], {'cash': 9000}, 'batch-3')
        assert store.inspect()['machine'] == first['machine']
        assert store.events()['items'][0]['value'] == 10000
    finally:
        store.close()
        owner.release()


def test_event_identity_conflict_aborts_whole_batch(tmp_path):
    store, owner = make_store(tmp_path)
    try:
        store.commit('a', {}, [], [{'key': '1', 'kind': 'X', 'value': 1}], {'cash': 10000}, '1')
        before = store.inspect()
        with pytest.raises(ValueError, match='conflict'):
            store.commit('a', {}, [sample()], [{'key': '1', 'kind': 'X', 'value': 2}], {'cash': 500}, '2')
        assert store.inspect() == before
        assert store.inputs('BTCUSDT', '15m') == []
    finally:
        store.close()
        owner.release()


def test_corrupt_or_missing_committed_rows_are_never_new_account(tmp_path):
    store, owner = make_store(tmp_path)
    try:
        store.commit('a', {}, [sample()], [], {'cash': 9999}, '1')
        store.close()
        with sqlite3.connect(tmp_path / 'paper.sqlite3') as db:
            db.execute('DELETE FROM inputs')
        from src.paper.compact_store import PaperStore
        broken = PaperStore(tmp_path, owner)
        with pytest.raises(ValueError, match='integrity'):
            broken.inspect()
        broken.close()
    finally:
        owner.release()


def test_orphan_evidence_cannot_create_initial_capital(tmp_path):
    from src.paper.compact_store import PaperStore
    (tmp_path / 'account.json').write_text('{', encoding='utf-8')
    store = PaperStore(tmp_path)
    with pytest.raises(ValueError, match='legacy|evidence'):
        store.inspect()
    assert (tmp_path / 'account.json').read_text() == '{'
    assert not (tmp_path / 'paper.sqlite3').exists()


def test_writes_without_lifetime_owner_fail(tmp_path):
    from src.paper.compact_store import PaperStore
    store = PaperStore(tmp_path)
    with pytest.raises(RuntimeError, match='owner'):
        store.commit('a', {}, [], [], {}, '1')
    assert not (tmp_path / 'paper.sqlite3').exists()


def test_torn_database_fails_closed_and_is_preserved(tmp_path):
    from src.paper.compact_store import PaperStore
    path = tmp_path / 'paper.sqlite3'
    path.write_bytes(b'SQLite format 3\x00torn')
    store = PaperStore(tmp_path)
    with pytest.raises(ValueError):
        store.inspect()
    assert path.read_bytes() == b'SQLite format 3\x00torn'


def test_missing_database_retains_account_identity_and_never_becomes_new(tmp_path):
    store, owner = make_store(tmp_path)
    try:
        store.commit('existing-account', {}, [sample()], [], {'cash': 7300}, '1')
        store.close()
        (tmp_path / 'paper.sqlite3').unlink()
        from src.paper.compact_store import PaperStore
        missing = PaperStore(tmp_path, owner)
        with pytest.raises(ValueError, match='evidence|identity|recovery'):
            missing.inspect()
        with pytest.raises(ValueError, match='evidence|identity|recovery'):
            missing.commit('replacement', {}, [], [], {'cash': 10000}, 'new')
        assert not (tmp_path / 'paper.sqlite3').exists()
    finally:
        owner.release()


@pytest.mark.parametrize('damage', ['missing', 'torn', 'wrong_account'])
def test_independent_identity_damage_blocks_restore_and_write(tmp_path, damage):
    from src.paper.compact_store import IDENTITY_FILENAME
    store, owner = make_store(tmp_path)
    try:
        store.commit('a', {}, [], [], {'cash': 7300}, '1')
        marker = tmp_path / IDENTITY_FILENAME
        if damage == 'missing':
            marker.unlink()
        elif damage == 'torn':
            marker.write_text('{"version":', encoding='ascii')
        else:
            identity = json.loads(marker.read_text())
            identity['account_id'] = 'wrong-account'
            marker.write_text(json.dumps(identity), encoding='ascii')
        before = store.db.execute('SELECT payload FROM checkpoint').fetchone()[0]
        with pytest.raises(ValueError, match='identity'):
            store.inspect()
        with pytest.raises(ValueError, match='identity'):
            store.commit('a', {}, [], [], {'cash': 10000}, '2')
        assert store.db.execute('SELECT payload FROM checkpoint').fetchone()[0] == before
    finally:
        store.close()
        owner.release()


def test_crash_after_identity_before_database_cannot_allocate_again(tmp_path, monkeypatch):
    from src.paper.compact_store import IDENTITY_FILENAME, PaperStore
    store, owner = make_store(tmp_path)
    def interrupted(*args, **kwargs):
        raise OSError('fixture interruption before SQLite create')
    monkeypatch.setattr(store, '_connect', interrupted)
    try:
        with pytest.raises(OSError, match='interruption'):
            store.commit('a', {}, [], [], {'cash': 10000}, '1')
        assert (tmp_path / IDENTITY_FILENAME).exists()
        assert not (tmp_path / 'paper.sqlite3').exists()
        with pytest.raises(ValueError, match='evidence'):
            PaperStore(tmp_path, owner).inspect()
    finally:
        owner.release()


def test_process_death_inside_sql_transaction_keeps_last_commit(tmp_path):
    store, owner = make_store(tmp_path)
    before = store.commit('a', {}, [sample()], [], {'cash': 9876.5}, '1')
    store.close()
    owner.release()
    code = """
import sqlite3, sys, time
db=sqlite3.connect(sys.argv[1], isolation_level=None)
db.execute('BEGIN IMMEDIATE')
db.execute("INSERT INTO events VALUES(1,'uncommitted','{}','invalid')")
print('UNCOMMITTED', flush=True)
time.sleep(30)
"""
    child = subprocess.Popen([sys.executable, '-u', '-c', code, str(tmp_path / 'paper.sqlite3')],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == 'UNCOMMITTED'
        child.kill()
        child.communicate(timeout=10)
    finally:
        if child.poll() is None:
            child.kill()
            child.communicate(timeout=10)
    reopened, owner = make_store(tmp_path)
    try:
        assert reopened.inspect() == before
        assert reopened.events()['items'] == []
    finally:
        reopened.close()
        owner.release()


def test_readonly_inspection_then_claim_can_commit_without_reset(tmp_path):
    store, owner = make_store(tmp_path)
    store.commit('a', {}, [], [], {'cash': 7654}, '1')
    store.close()
    owner.release()
    from src.paper.compact_store import PaperStore
    reader = PaperStore(tmp_path)
    assert reader.inspect()['machine']['cash'] == 7654
    owner = AccountOwnershipLock(tmp_path)
    owner.acquire()
    reader.ownership = owner
    try:
        reader.commit('a', {}, [], [], {'cash': 7654}, '2')
        assert reader.inspect()['machine']['cash'] == 7654
    finally:
        reader.close()
        owner.release()


def test_unknown_file_is_not_silently_ignored_in_existing_account(tmp_path):
    store, owner = make_store(tmp_path)
    try:
        store.commit('a', {}, [], [], {'cash': 9999}, '1')
        (tmp_path / 'uncommitted-account.json.tmp').write_text('unknown evidence')
        with pytest.raises(ValueError, match='evidence'):
            store.inspect()
    finally:
        store.close()
        owner.release()


@pytest.mark.parametrize('statement', [
    "UPDATE inputs SET symbol='ETHUSDT'",
    "UPDATE events SET event_key='different-key'",
    "UPDATE inputs SET payload=replace(payload,'00:15:01','00:15:09')",
])
def test_index_identity_tampering_cannot_hide_verified_evidence(tmp_path, statement):
    store, owner = make_store(tmp_path)
    try:
        store.commit('a', {}, [sample()], [{'key': 'x', 'kind': 'Y'}], {'cash': 10000}, '1')
        store.close()
        with sqlite3.connect(tmp_path / 'paper.sqlite3') as db:
            db.execute(statement)
        with pytest.raises(ValueError, match='integrity'):
            store.inspect()
    finally:
        store.close()
        owner.release()
