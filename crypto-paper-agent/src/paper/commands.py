"""One serialized control worker. Never owns financial accounting itself."""
from collections import deque
from copy import deepcopy
from datetime import datetime, timezone
from threading import Condition, Event, Thread


class PaperCommands:
    def __init__(self, apply):
        self.apply = apply
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
            self.latest = {'id': f'control-{self.sequence}', 'name': name, 'status': 'PENDING', 'error': None,
                           'requested_at_utc': datetime.now(timezone.utc).isoformat(), 'completed_at_utc': None}
            self.queue.append(self.latest)
            self.condition.notify()
            return deepcopy(self.latest)

    def state(self):
        with self.condition:
            return deepcopy(self.latest)

    def _run(self):
        while True:
            with self.condition:
                self.condition.wait_for(lambda: self.closed or self.queue)
                if self.closed:
                    return
                command = self.queue.popleft()
                command['status'] = 'RUNNING'
            try:
                self.apply(command['name'])
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
