"""Migration and replay labels must retain terminal intent and factual provenance."""
from datetime import timedelta

from test_local_paper_session import BASE
from test_paper_replay_recovery import RangeSource, create, stream_event


def test_legacy_stopped_migration_can_restart_without_new_capital(tmp_path):
    from src.paper.live_session import LocalPaperSession
    from src.paper.replay_session import PaperReplaySession
    source = RangeSource()
    legacy = LocalPaperSession(source=source, journal_dir=tmp_path)
    legacy.start()
    assert legacy.stop()['status'] == 'STOPPED'
    legacy.shutdown()
    originals = {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.suffix in ('.json', '.jsonl')}
    migrated = PaperReplaySession(source=source, journal_dir=tmp_path, auto_resume=True)
    assert migrated.state()['status'] == 'STOPPED', migrated.state()['error']
    migrated.shutdown()
    restarted = PaperReplaySession(source=source, journal_dir=tmp_path, auto_resume=True)
    try:
        state = restarted.state()
        assert state['status'] == 'STOPPED', state['error']
        assert state['operator_intent'] == 'STOPPED'
        assert state['trials']['total_capital_injected_usd'] == 10000
        assert all((tmp_path / name).read_bytes() == value for name, value in originals.items())
    finally:
        restarted.shutdown()


def test_missing_closed_events_are_labeled_replay_not_realtime(tmp_path):
    session, source = create(tmp_path)
    try:
        session.on_connection(True, None)
        source.now = int((BASE + timedelta(minutes=45, seconds=1)).timestamp() * 1000)
        session.clock = lambda: BASE + timedelta(minutes=45, seconds=2)
        for symbol in ('BTCUSDT', 'ETHUSDT', 'SOLUSDT'):
            event = stream_event(symbol, BASE + timedelta(minutes=30))
            session.on_stream_event(event)
        assert session.state()['status'] == 'SCANNING', session.state()['error']
        batches = [e for e in session._all_events() if e['kind'] == 'PAPER_BATCH']
        assert [e['execution_mode'] for e in batches] == ['REPLAY', 'REPLAY', 'REALTIME']
        assert [e['simulated_at_utc'] for e in batches] == [
            '2026-09-27T04:15:00+00:00', '2026-09-27T04:30:00+00:00', '2026-09-27T04:45:00+00:00']
    finally:
        session.shutdown()
