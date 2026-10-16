"""Real serialized controls; HTTP must not wait for history downloads."""
from threading import Event
import time

import pytest


def test_command_worker_deduplicates_running_command_and_serializes_stop():
    from src.paper.commands import PaperCommands
    entered, release = Event(), Event()
    applied = []
    def action(name):
        if name == 'start':
            entered.set()
            assert release.wait(5)
        applied.append(name)
    worker = PaperCommands(action)
    try:
        first = worker.submit('start')
        assert entered.wait(2)
        assert worker.submit('start')['id'] == first['id']
        stop = worker.submit('stop')
        assert stop['status'] == 'PENDING'
        assert applied == []
        release.set()
        deadline = time.monotonic() + 3
        while worker.state()['status'] in ('PENDING', 'RUNNING') and time.monotonic() < deadline:
            time.sleep(.01)
        assert applied == ['start', 'stop']
        assert worker.state()['status'] == 'APPLIED'
    finally:
        release.set()
        worker.close()
    with pytest.raises(RuntimeError):
        worker.submit('start')


def test_failed_command_is_reported_without_killing_the_control_worker():
    from src.paper.commands import PaperCommands
    def fail(name):
        raise OSError('fixture storage failure')
    worker = PaperCommands(fail)
    try:
        worker.submit('start')
        deadline = time.monotonic() + 3
        while worker.state()['status'] in ('PENDING', 'RUNNING') and time.monotonic() < deadline:
            time.sleep(.01)
        assert worker.state()['status'] == 'FAILED'
        assert 'storage failure' in worker.state()['error']
    finally:
        worker.close()
