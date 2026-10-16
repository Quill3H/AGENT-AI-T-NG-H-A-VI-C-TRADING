"""One serialized control worker. Never owns financial accounting itself."""
from collections import deque
from copy import deepcopy
from datetime import datetime, timezone
from threading import Condition, Event, Thread
from uuid import uuid4


class PaperCommands:
    def __init__(self, apply, accept=None, application=None, clock=None):
        self.apply = apply
        self.accept = accept
        self.application = application
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.condition = Condition()
        self.queue = deque()
        self.closed = False
        self.sequence = 0
        self.latest = None
        self.worker = Thread(target=self._run, name='paper-controls', daemon=True)
        self.worker.start()

    def submit(self, name):
        if name not in ('start', 'restore', 'pause', 'resume', 'stop'):
            raise ValueError('unknown paper command')
        with self.condition:
            if self.closed:
                raise RuntimeError('backend is shutting down')
            if self.latest and self.latest['name'] == name and self.latest['status'] in ('PENDING', 'RUNNING'):
                return deepcopy(self.latest)
            if len(self.queue) >= 16:
                raise RuntimeError('paper control queue is full')
            self.sequence += 1
            command = {'id': 'control-' + uuid4().hex, 'name': name, 'status': 'PENDING', 'error': None,
                       'requested_at_utc': self.clock().isoformat(), 'completed_at_utc': None,
                       'durable': False}
            if self.accept is not None:
                command = self.accept(command)
            self.latest = command
            self.queue.append(self.latest)
            self.condition.notify()
            return deepcopy(self.latest)

    def state(self):
        with self.condition:
            command = deepcopy(self.latest)
        if command and command.get('durable') and command['status'] in ('PENDING', 'RUNNING') and self.application:
            applied = self.application(command['id'])
            if applied is not None:
                command.update(intent_persisted=True, effective_at_utc=applied['effective_at_utc'],
                               intent_persisted_at_utc=applied['processed_at_utc'])
        return command

    def _run(self):
        while True:
            with self.condition:
                self.condition.wait_for(lambda: self.closed or self.queue)
                if self.closed:
                    return
                command = self.queue.popleft()
                command['status'] = 'RUNNING'
            try:
                self.apply(deepcopy(command) if self.accept is not None else command['name'])
                error = None
            except Exception as exc:
                error = str(exc)
            with self.condition:
                command.update(status='FAILED' if error else 'APPLIED', error=error,
                               completed_at_utc=datetime.now(timezone.utc).isoformat())
                self.condition.notify_all()

    def close(self):
        with self.condition:
            self.closed = True
            for command in self.queue:
                command.update(status='CANCELLED', error='backend shutdown before application')
            self.queue.clear()
            self.condition.notify_all()
        self.worker.join(timeout=20)
        if self.worker.is_alive():
            raise RuntimeError('control worker has not stopped; account ownership retained')
