"""Crash-detecting paper journal. Saved views are evidence, never broker restore."""
from hashlib import sha256
import json
import os
from pathlib import Path
import re


def encode(value):
    return json.dumps(value, sort_keys=True, default=str, allow_nan=False).encode('utf-8')


def decode(data):
    def reject(value):
        raise ValueError(f'non-finite JSON value: {value}')
    return json.loads(data, parse_constant=reject)


class DurableJournal:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.marker = self.directory / 'account.json'
        self.session_id = None
        self.digest = None
        self.snapshot = None
        self.machine = None

    def inspect(self):
        """Return (existing, snapshot, reason); never modify recovery evidence."""
        try:
            entries = list(self.directory.iterdir()) if self.directory.exists() else []
            evidence = [p for p in entries if p.name != 'logs']
            if not evidence:
                return False, None, None
            checkpoint = decode(self.marker.read_bytes())
            if not isinstance(checkpoint, dict) or checkpoint.get('version') not in (1, 2):
                raise ValueError('invalid account checkpoint')
            session_id = checkpoint.get('session_id')
            if not isinstance(session_id, str) or not re.fullmatch(r'[A-Za-z0-9-]+', session_id):
                raise ValueError('invalid account identity')
            self.session_id = session_id
            if {p.name for p in evidence} != {'account.json', f'{session_id}.jsonl'}:
                raise ValueError('missing, orphaned or unfinished account evidence')
            raw = (self.directory / f'{session_id}.jsonl').read_bytes()
            if not raw or not raw.endswith(b'\n'):
                raise ValueError('empty or incomplete journal')
            if sha256(raw).hexdigest() != checkpoint.get('journal_sha256'):
                raise ValueError('journal/checkpoint checksum mismatch')
            snapshot = None
            pending = False
            for index, line in enumerate(raw.splitlines()):
                record = decode(line)
                if not isinstance(record, dict) or not isinstance(record.get('type'), str):
                    raise ValueError('invalid journal record')
                if index == 0 and (record['type'] != 'SESSION_START' or record.get('session_id') != session_id):
                    raise ValueError('journal account identity mismatch')
                if record['type'] in ('PAPER_INPUT', 'STOP_INTENT'):
                    pending = True
                if 'state' in record:
                    snapshot = record['state']
                    if record['type'] in ('PAPER_BATCH', 'SESSION_STOP'):
                        pending = False
            if pending:
                raise ValueError('uncommitted paper mutation; last account state is uncertain')
            if not isinstance(snapshot, dict) or snapshot != checkpoint.get('state'):
                raise ValueError('checkpoint view does not match journal')
            machine = checkpoint.get('machine')
            if machine is not None and not isinstance(machine, dict):
                raise ValueError('invalid machine checkpoint')
            if snapshot.get('session_id') != session_id or not isinstance(snapshot.get('account'), dict):
                raise ValueError('invalid saved account view')
            for name in ('orders', 'pending_orders', 'open_positions', 'trades', 'funding_events'):
                if not isinstance(snapshot.get(name), list):
                    raise ValueError(f'missing saved {name}')
            self.machine = machine
            self.digest = checkpoint.get('journal_sha256')
            self.snapshot = snapshot
            return True, snapshot, 'Saved account is read-only until exact broker/risk/funding recovery is verified.'
        except (OSError, ValueError, TypeError, KeyError) as exc:
            return True, None, f'Account evidence is incomplete or inconsistent: {exc}'

    def append(self, session_id, record, machine=None):
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f'{session_id}.jsonl'
        if self.digest is None:
            # Exclusive creation leaves durable evidence even if the first write dies.
            if any(p.name != 'logs' for p in self.directory.iterdir()):
                raise ValueError('existing account evidence cannot be overwritten')
            with self.marker.open('xb') as stream:
                stream.write(encode({'version': 1, 'session_id': session_id, 'initializing': True}))
                stream.flush()
                os.fsync(stream.fileno())
            self.session_id = session_id
            raw = b''
        else:
            raw = path.read_bytes()
            checkpoint = decode(self.marker.read_bytes())
            if sha256(raw).hexdigest() != self.digest or checkpoint.get('journal_sha256') != self.digest:
                raise ValueError('account evidence changed during session')
        payload = encode(record) + b'\n'
        with path.open('ab') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        digest = sha256(raw + payload).hexdigest()
        snapshot = decode(encode(record['state'])) if 'state' in record else self.snapshot
        if machine is None:
            machine = self.machine
        checkpoint = {'version': 2 if machine is not None else 1, 'session_id': session_id,
                      'journal_sha256': digest, 'state': snapshot, 'machine': machine}
        temporary = self.directory / 'account.json.tmp'
        with temporary.open('xb') as stream:
            stream.write(encode(checkpoint))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.marker)
        self.digest, self.snapshot, self.machine = digest, snapshot, machine
