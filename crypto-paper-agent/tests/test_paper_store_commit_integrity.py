"""A renamed batch or changed intent hash cannot undermine exactly-once replay."""
import sqlite3

import pytest

from test_paper_compact_store import make_store, sample


@pytest.mark.parametrize('statement', [
    "UPDATE commits SET batch_id='renamed' WHERE batch_id='batch-1'",
    "UPDATE commits SET intent_sha256='altered' WHERE batch_id='batch-1'",
])
def test_commit_identity_tampering_blocks_inspection(tmp_path, statement):
    store, owner = make_store(tmp_path)
    try:
        store.commit('a', {}, [sample()], [], {'cash': 9999}, 'batch-1')
        store.close()
        with sqlite3.connect(tmp_path / 'paper.sqlite3') as db:
            db.execute(statement)
        with pytest.raises(ValueError, match='integrity|commit'):
            store.inspect()
    finally:
        store.close()
        owner.release()


def test_identical_retry_is_safe_after_restart_and_receipt_timestamp_change(tmp_path):
    store, owner = make_store(tmp_path)
    try:
        original = store.commit('a', {}, [sample()], [{'key': 'fill', 'kind': 'FILL'}],
                                {'cash': 9999}, 'batch-1')
        store.close()
        assert store.inspect() == original
        same = sample()
        same['received_at_utc'] = '2026-10-01T01:00:00+00:00'
        again = store.commit('a', {}, [same], [{'key': 'fill', 'kind': 'FILL'}],
                             {'cash': 9999}, 'batch-1')
        assert again == original
        assert len(store.events()['items']) == 1
        assert len(store.inputs('BTCUSDT', '15m')) == 1
        assert store.db.execute('SELECT count(*) FROM commits').fetchone()[0] == 1
    finally:
        store.close()
        owner.release()


def test_renamed_batch_cannot_be_reexecuted_with_new_machine(tmp_path):
    store, owner = make_store(tmp_path)
    try:
        store.commit('a', {}, [sample()], [], {'cash': 9999}, 'batch-1')
        store.db.execute("UPDATE commits SET batch_id='renamed'")
        with pytest.raises(ValueError, match='integrity|commit'):
            store.commit('a', {}, [], [], {'cash': 10000}, 'batch-1')
    finally:
        store.close()
        owner.release()
