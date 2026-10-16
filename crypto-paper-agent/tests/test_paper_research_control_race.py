"""Control/account serialization. Numeric scores below are test fixtures, not research evidence."""
from datetime import timedelta
from threading import Event, Thread

from src.execution.order_models import OrderRequest
from test_local_paper_session import BASE
from test_paper_replay_recovery import create
from test_paper_research_cycle import fold


def failed_session(tmp_path, monkeypatch):
    from src.paper import research_cycle
    from test_paper_causal_runner import batch
    session, source = create(tmp_path)
    session.broker.submit_order(OrderRequest(symbol='BTCUSDT', direction='LONG', leverage=3,
        signal_price=100, stop_loss_price=99.75, signal_time=BASE, requested_quantity=240))
    candidate = session.runner.fork()
    first = batch(BASE)
    first['BTCUSDT'].update(low=99.99, high=100.05)
    candidate.advance(first)
    candidate.advance(batch(BASE + timedelta(minutes=15), 60))
    session._persist(candidate, candidate.all_inputs(), [], 'fixture-gap-loss')
    assert session.broker.equity < 5000
    assert not session.broker.positions and not session.broker.pending_orders
    inputs = {s: {'4h': session.runner.signal_history[s], '15m': []} for s in session.runner.strategies}
    monkeypatch.setattr(session, '_research_inputs', lambda cutoff: inputs)
    monkeypatch.setattr(research_cycle, '_partition', lambda *args, **kwargs: fold())
    return session, source


def test_control_accepted_during_research_prevents_replacement_allocation(tmp_path, monkeypatch):
    from src.paper import replay_session
    session, _ = failed_session(tmp_path, monkeypatch)
    entered, release = Event(), Event()
    original = replay_session.evaluate_research
    def slow(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return original(*args, **kwargs)
    monkeypatch.setattr(replay_session, 'evaluate_research', slow)
    research = Thread(target=session.run_research)
    research.start()
    try:
        assert entered.wait(3)
        command = {'id': 'pause-during-research', 'name': 'pause',
                   'requested_at_utc': '2026-09-27T04:30:00+00:00'}
        assert session.accept_control_request(command)['durable'] is True
        release.set()
        research.join(5)
        assert not research.is_alive()
        assert session.status != 'RECOVERY_REQUIRED', session.error
        assert session.runner.intent == 'PAUSED'
        assert session.research['last_verdict']['eligible'] is True
        assert session.runner.trials.total_capital_injected == 10000
        assert not any(e['kind'] == 'PAPER_CAPITAL_ALLOCATION' for e in session._all_events())
    finally:
        release.set()
        research.join(5)
        session.shutdown()


def test_resume_reuses_persisted_eligible_verdict_at_new_boundary_once(tmp_path, monkeypatch):
    from src.paper import replay_session
    session, source = failed_session(tmp_path, monkeypatch)
    original = replay_session.evaluate_research
    def paused_evaluation(*args, **kwargs):
        verdict = original(*args, **kwargs)
        session.accept_control_request({'id': 'pause-after-eligible', 'name': 'pause',
                                        'requested_at_utc': '2026-09-27T04:30:00+00:00'})
        return verdict
    monkeypatch.setattr(replay_session, 'evaluate_research', paused_evaluation)
    state = session.run_research()
    assert state['research']['last_verdict']['eligible'] is True
    assert session.runner.intent == 'PAUSED'
    verdict = dict(session.research['last_verdict'])
    session.shutdown()
    def forbidden(*args, **kwargs):
        raise AssertionError('consumed holdout must never be reevaluated or reranked')
    monkeypatch.setattr(replay_session, 'evaluate_research', forbidden)
    source.now = int((BASE + timedelta(minutes=45, seconds=1)).timestamp() * 1000)
    resumed = replay_session.PaperReplaySession(source=source, journal_dir=tmp_path, auto_resume=True,
                                               clock=lambda: BASE + timedelta(minutes=45))
    try:
        assert resumed.runner.intent == 'PAUSED', resumed.error
        assert resumed.resume()['status'] != 'RECOVERY_REQUIRED', resumed.error
        resumed.run_research()
        assert resumed.runner.trials.total_capital_injected == 20000, resumed.error
        assert resumed.runner.trials.current['started_at_utc'] == '2026-09-27T04:45:00+00:00'
        assert resumed.research['last_verdict'] == verdict
        resumed.run_research()
        assert resumed.runner.trials.total_capital_injected == 20000
        events = resumed._all_events()
        assert len([e for e in events if e['kind'] == 'RESEARCH_VERDICT']) == 1
        assert len([e for e in events if e['kind'] == 'PAPER_CAPITAL_ALLOCATION']) == 1
        promotion = [e for e in events if e['kind'] == 'RESEARCH_PROMOTION']
        assert len(promotion) == 1
        assert promotion[0]['verdict_identity'] == verdict['identity']
        assert promotion[0]['simulated_at_utc'] == '2026-09-27T04:45:00+00:00'
    finally:
        resumed.shutdown()
    again = replay_session.PaperReplaySession(source=source, journal_dir=tmp_path, auto_resume=True,
                                             clock=lambda: BASE + timedelta(minutes=45))
    try:
        assert again.status == 'WAITING_CONNECTION', again.error
        assert again.runner.trials.total_capital_injected == 20000
        assert again.research['last_verdict'] == verdict
    finally:
        again.shutdown()


def test_promotion_and_durable_acceptance_share_one_linearization_boundary(tmp_path, monkeypatch):
    from src.paper.causal_runner import CausalRunner
    session, _ = failed_session(tmp_path, monkeypatch)
    entered, release, accepted = Event(), Event(), Event()
    original = CausalRunner.promote
    errors = []
    command = {'id': 'stop-at-promotion-boundary', 'name': 'stop',
               'requested_at_utc': '2026-09-27T04:30:00+00:00'}
    def stalled(self, *args):
        entered.set()
        assert release.wait(5)
        return original(self, *args)
    monkeypatch.setattr(CausalRunner, 'promote', stalled)
    def accept():
        try:
            session.accept_control_request(command)
            accepted.set()
        except Exception as exc:
            errors.append(exc)
    research = Thread(target=session.run_research)
    control = Thread(target=accept)
    research.start()
    try:
        assert entered.wait(3)
        control.start()
        assert not accepted.wait(.2), 'durable receipt was accepted inside an uncommitted promotion'
        release.set()
        research.join(5)
        control.join(5)
        assert not errors
        assert accepted.is_set()
        assert session.status != 'RECOVERY_REQUIRED', session.error
        assert session.runner.trials.total_capital_injected == 20000
        session.apply_control_request(command)
        assert session.runner.intent == 'STOPPED'
        events = session._all_events()
        capital = next(e for e in events if e['kind'] == 'PAPER_CAPITAL_ALLOCATION')
        receipt = next(e for e in events if e['kind'] == 'OPERATOR_REQUEST')
        assert capital['cursor'] < receipt['cursor']
    finally:
        release.set()
        research.join(5)
        if control.ident is not None:
            control.join(5)
        session.shutdown()
