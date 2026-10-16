"""One-owner, checksummed SQLite account store. Never repairs or resets evidence."""
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sqlite3
from threading import RLock

from src.paper.account_lock import LOCK_FILENAME


VERSION = 3
IDENTITY_FILENAME = 'paper-account.identity.json'
EMPTY_ROOT = sha256(b'').hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return sha256(canonical(value).encode()).hexdigest()


def input_identity(value):
    return {k: v for k, v in value.items() if k != 'received_at_utc'}


def chained(root, value_hash):
    return sha256((root + value_hash).encode()).hexdigest()


class PaperStore:
    def __init__(self, directory, ownership=None):
        self.directory = Path(directory)
        self.path = self.directory / 'paper.sqlite3'
        self.ownership = ownership
        self.db = None
        self._writable = False
        self.last = None
        self.lock = RLock()
        self._commits = {}

    def _connect(self, create=False):
        if self.db is not None:
            if self.ownership is None or self._writable:
                return self.db
            # Read-only inspection precedes claiming ownership. A SQLite URI
            # opened mode=ro cannot become writable by assigning an owner.
            self.db.close()
            self.db = None
        if create:
            if self.ownership is None:
                raise RuntimeError('paper store requires lifetime owner')
            self.ownership.assert_owned()
            if self.ownership.directory != self.directory.resolve():
                raise RuntimeError('paper store owner directory mismatch')
            self.directory.mkdir(parents=True, exist_ok=True)
            mode = 'rwc'
        else:
            mode = 'rw' if self.ownership is not None else 'ro'
        self.db = sqlite3.connect(self.path.resolve().as_uri() + '?mode=' + mode,
                                  uri=True, timeout=2, isolation_level=None, check_same_thread=False)
        self._writable = mode != 'ro'
        self.db.execute('PRAGMA foreign_keys=ON')
        if self.ownership is not None:
            self.db.execute('PRAGMA synchronous=FULL')
        return self.db

    def inspect(self):
        with self.lock:
            return self._inspect()

    def _inspect(self):
        if not self.path.exists():
            evidence = [p for p in self.directory.iterdir()
                        if p.name not in ('logs', LOCK_FILENAME)] if self.directory.exists() else []
            if evidence:
                raise ValueError('legacy or orphan account evidence; verified migration required')
            self.last = None
            return None
        try:
            db = self._connect()
            if db.execute('PRAGMA quick_check').fetchone() != ('ok',):
                raise ValueError('SQLite integrity check failed')
            if db.execute('PRAGMA user_version').fetchone()[0] != VERSION:
                raise ValueError('paper store schema version mismatch')
            row = db.execute('SELECT payload, checksum FROM checkpoint WHERE id=1').fetchone()
            if row is None:
                raise ValueError('existing store has no committed account checkpoint')
            payload = json.loads(row[0])
            if digest(payload) != row[1]:
                raise ValueError('checkpoint integrity mismatch')
            self._verify_identity(payload['account_id'], payload['config_sha256'])
            allowed = {self.path.name, self.path.name + '-wal', self.path.name + '-shm',
                       'logs', LOCK_FILENAME, IDENTITY_FILENAME} | set(payload['machine'].get('legacy_fingerprints', {}))
            if any(p.name not in allowed for p in self.directory.iterdir()):
                raise ValueError('unknown/orphan account evidence beside compact store')
            roots = {}
            for table in ('inputs', 'events'):
                root, count = EMPTY_ROOT, 0
                columns = 'symbol,interval,open_time' if table == 'inputs' else 'event_key'
                for row in db.execute(f'SELECT seq,payload,checksum,{columns} FROM {table} ORDER BY seq'):
                    seq, raw, checksum, *keys = row
                    value = json.loads(raw)
                    expected_keys = [value[k] for k in ('symbol', 'interval', 'open_time')] if table == 'inputs' else [value['key']]
                    if seq != count + 1 or digest(value) != checksum or keys != expected_keys:
                        raise ValueError(f'{table} row integrity mismatch')
                    count += 1
                    root = chained(root, checksum)
                if payload[table + '_root'] != root or payload[table + '_count'] != count:
                    raise ValueError(f'{table} committed integrity mismatch')
                roots[table] = (root, count)
            root, count, commits = EMPTY_ROOT, 0, {}
            for row in db.execute('SELECT generation,batch_id,intent_sha256,previous_root,checksum FROM commits ORDER BY generation'):
                generation, batch_id, intent, previous, checksum = row
                metadata = dict(generation=generation, batch_id=batch_id, intent_sha256=intent, previous_root=previous)
                if (generation != count + 1 or type(batch_id) is not str or not batch_id
                        or type(intent) is not str or re.fullmatch('[0-9a-f]{64}', intent) is None
                        or previous != root or digest(metadata) != checksum):
                    raise ValueError('commit metadata integrity mismatch')
                root = chained(root, checksum)
                count += 1
                commits[batch_id] = tuple(row)
            if count != payload['generation'] or root != payload['commits_root']:
                raise ValueError('commit generation/root integrity mismatch')
            if digest(payload['config']) != payload['config_sha256']:
                raise ValueError('config integrity mismatch')
            for name, checksum in payload['machine'].get('legacy_fingerprints', {}).items():
                if Path(name).name != name or sha256((self.directory / name).read_bytes()).hexdigest() != checksum:
                    raise ValueError('legacy migration evidence changed')
            self.last = payload
            self._commits = commits
            self._control_records()
            return json.loads(canonical(payload))
        except (sqlite3.Error, OSError, ValueError, TypeError, KeyError) as exc:
            raise ValueError(f'paper store integrity/recovery required: {exc}') from exc

    def _verify_identity(self, account_id, config_sha256):
        expected = {'version': VERSION, 'account_id': account_id, 'config_sha256': config_sha256}
        try:
            identity = json.loads((self.directory / IDENTITY_FILENAME).read_text(encoding='ascii'))
            if identity != expected:
                raise ValueError('paper account identity mismatch')
        except (OSError, ValueError, TypeError) as exc:
            raise ValueError(f'paper account identity recovery required: {exc}') from exc

    def _initialize(self, account_id, config_sha256):
        # This immutable marker outlives a missing database. A crash before the
        # first SQLite commit leaves evidence to reconcile, never fresh capital.
        self.directory.mkdir(parents=True, exist_ok=True)
        identity = {'version': VERSION, 'account_id': account_id, 'config_sha256': config_sha256}
        with (self.directory / IDENTITY_FILENAME).open('x', encoding='ascii') as stream:
            stream.write(canonical(identity))
            stream.flush()
            os.fsync(stream.fileno())
        db = self._connect(create=True)
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript('''
            CREATE TABLE inputs(seq INTEGER PRIMARY KEY, symbol TEXT NOT NULL,
                interval TEXT NOT NULL, open_time TEXT NOT NULL, payload TEXT NOT NULL,
                checksum TEXT NOT NULL, UNIQUE(symbol,interval,open_time));
            CREATE TABLE events(seq INTEGER PRIMARY KEY, event_key TEXT NOT NULL UNIQUE,
                payload TEXT NOT NULL, checksum TEXT NOT NULL);
            CREATE TABLE checkpoint(id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL,
                checksum TEXT NOT NULL);
            CREATE TABLE commits(generation INTEGER PRIMARY KEY, batch_id TEXT NOT NULL UNIQUE,
                intent_sha256 TEXT NOT NULL, previous_root TEXT NOT NULL, checksum TEXT NOT NULL);
            PRAGMA user_version=3;
        ''')

    def commit(self, account_id, config, inputs, events, machine, batch_id, *, migration=False):
        with self.lock:
            return self._commit(account_id, config, inputs, events, machine, batch_id, migration=migration)

    def _commit(self, account_id, config, inputs, events, machine, batch_id, *, migration=False):
        if self.ownership is None:
            raise RuntimeError('paper store requires lifetime owner')
        self.ownership.assert_owned()
        if self.ownership.directory != self.directory.resolve():
            raise RuntimeError('paper store owner directory mismatch')
        if type(account_id) is not str or not account_id or type(batch_id) is not str or not batch_id:
            raise ValueError('missing account/batch identity')
        # Encode before touching disk. NaN and non-JSON objects cannot create a store.
        intent = digest([account_id, config, [input_identity(i) for i in inputs], events, machine])
        if not self.path.exists():
            if not migration:
                self.inspect()
            elif not machine.get('legacy_fingerprints'):
                raise ValueError('migration requires original evidence fingerprints')
            self._initialize(account_id, digest(config))
        self._verify_identity(account_id, digest(config))
        db = self._connect()
        try:
            db.execute('BEGIN IMMEDIATE')
            prior_row = db.execute('SELECT payload,checksum FROM checkpoint WHERE id=1').fetchone()
            prior = json.loads(prior_row[0]) if prior_row else None
            if prior is None and self.last is not None:
                raise ValueError('checkpoint removed during operation')
            if prior is not None:
                if (digest(prior) != prior_row[1] or self.last is None or prior != self.last
                        or account_id != prior['account_id'] or config != prior['config']):
                    raise ValueError('account checkpoint/config conflict')
            if prior is not None:
                count = db.execute('SELECT count(*) FROM commits').fetchone()[0]
                head = db.execute('SELECT generation,batch_id,intent_sha256,previous_root,checksum FROM commits ORDER BY generation DESC LIMIT 1').fetchone()
                if (count != prior['generation'] or count != len(self._commits) or head is None
                        or tuple(head) != self._commits.get(head[1])
                        or head[0] != prior['generation'] or chained(head[3], head[4]) != prior['commits_root']):
                    raise ValueError('commit metadata integrity mismatch')
            used = db.execute('SELECT generation,batch_id,intent_sha256,previous_root,checksum FROM commits WHERE batch_id=?', (batch_id,)).fetchone()
            known = self._commits.get(batch_id)
            if known is not None and used != known or used is not None and known != used:
                raise ValueError('commit retry metadata integrity mismatch')
            if used:
                if used[2] != intent:
                    raise ValueError('batch identity conflict')
                db.rollback()
                return json.loads(canonical(prior))
            roots = {table: [prior[table + '_root'], prior[table + '_count']] if prior
                     else [EMPTY_ROOT, 0] for table in ('inputs', 'events')}
            for item in inputs:
                if type(item) is not dict or item.get('provisional') is True:
                    raise ValueError('only canonical closed input records may be stored')
                key = (item['symbol'], item['interval'], item['open_time'])
                checksum = digest(item)
                previous = db.execute('SELECT payload FROM inputs WHERE symbol=? AND interval=? AND open_time=?', key).fetchone()
                if previous:
                    if input_identity(json.loads(previous[0])) != input_identity(item):
                        raise ValueError('canonical input revision conflict')
                    continue
                roots['inputs'][1] += 1
                db.execute('INSERT INTO inputs VALUES(?,?,?,?,?,?)',
                           (roots['inputs'][1], *key, canonical(item), checksum))
                roots['inputs'][0] = chained(roots['inputs'][0], checksum)
            for event in events:
                key = event['key']
                if type(key) is not str or not key or type(event.get('kind')) is not str:
                    raise ValueError('event identity/kind missing')
                checksum = digest(event)
                previous = db.execute('SELECT checksum FROM events WHERE event_key=?', (key,)).fetchone()
                if previous:
                    if previous[0] != checksum:
                        raise ValueError('event identity conflict')
                    continue
                roots['events'][1] += 1
                db.execute('INSERT INTO events VALUES(?,?,?,?)', (roots['events'][1], key, canonical(event), checksum))
                roots['events'][0] = chained(roots['events'][0], checksum)
            generation = prior['generation'] + 1 if prior else 1
            commit_meta = {'generation': generation, 'batch_id': batch_id, 'intent_sha256': intent,
                           'previous_root': prior['commits_root'] if prior else EMPTY_ROOT}
            checksum = digest(commit_meta)
            payload = {'version': VERSION, 'account_id': account_id, 'config': config,
                       'config_sha256': digest(config), 'machine': machine,
                       'generation': generation, 'commits_root': chained(commit_meta['previous_root'], checksum),
                       **{table + '_root': roots[table][0] for table in roots},
                       **{table + '_count': roots[table][1] for table in roots}}
            db.execute('INSERT OR REPLACE INTO checkpoint VALUES(1,?,?)', (canonical(payload), digest(payload)))
            metadata_row = (generation, batch_id, intent, commit_meta['previous_root'], checksum)
            db.execute('INSERT INTO commits VALUES(?,?,?,?,?)', metadata_row)
            db.commit()
            self.last = payload
            self._commits[batch_id] = metadata_row
            return json.loads(canonical(payload))
        except BaseException:
            db.rollback()
            raise

    def inputs(self, symbol, interval):
        with self.lock:
            if not self.path.exists():
                return []
            return [json.loads(row[0]) for row in self._connect().execute(
                'SELECT payload FROM inputs WHERE symbol=? AND interval=? ORDER BY open_time', (symbol, interval))]

    def input_at(self, symbol, interval, opened):
        with self.lock:
            row = self._connect().execute('SELECT payload FROM inputs WHERE symbol=? AND interval=? AND open_time=?',
                                         (symbol, interval, opened)).fetchone()
            return json.loads(row[0]) if row else None

    def events(self, after=0, limit=100):
        with self.lock:
            if type(after) is not int or after < 0 or type(limit) is not int or not 1 <= limit <= 500:
                raise ValueError('invalid event cursor/limit')
            rows = [] if not self.path.exists() else self._connect().execute(
                'SELECT seq,payload FROM events WHERE seq>? ORDER BY seq LIMIT ?', (after, limit + 1)).fetchall()
            return {'items': [dict(json.loads(raw), cursor=seq) for seq, raw in rows[:limit]],
                    'next_cursor': rows[limit - 1][0] if len(rows) > limit else None}

    def record_control(self, request_id, name, requested_at):
        """Commit a receipt without waiting on the longer financial writer lock."""
        from src.paper.trials import utc
        stamp = utc(requested_at).isoformat()
        if type(request_id) is not str or not request_id or name not in ('pause', 'resume', 'stop'):
            raise ValueError('invalid durable paper control')
        event = {'key': 'operator-request:' + request_id, 'kind': 'OPERATOR_REQUEST',
                 'request_id': request_id, 'name': name, 'requested_at_utc': stamp}
        with self.lock:
            if self.last is None or not self.path.exists():
                raise ValueError('verified account required before accepting durable controls')
            previous = self._connect().execute('SELECT payload FROM events WHERE event_key=?', (event['key'],)).fetchone()
            if previous is not None:
                if json.loads(previous[0]) != event:
                    raise ValueError('operator request identity conflict')
                return dict(event)
            saved = self.last
            self.commit(saved['account_id'], saved['config'], [], [event], saved['machine'], event['key'])
            return dict(event)

    def _control_records(self):
        from src.paper.trials import utc
        receipts, applied = {}, {}
        if not self.path.exists():
            return receipts, applied
        for raw, checksum, key in self._connect().execute(
                "SELECT payload,checksum,event_key FROM events WHERE event_key LIKE 'operator-request:%' OR event_key LIKE 'operator-applied:%' ORDER BY seq"):
            value = json.loads(raw)
            if digest(value) != checksum or value['key'] != key:
                raise ValueError('operator receipt integrity mismatch')
            request_id = value['request_id']
            if key == 'operator-request:' + request_id:
                if value['kind'] != 'OPERATOR_REQUEST' or value['name'] not in ('pause', 'resume', 'stop'):
                    raise ValueError('invalid operator receipt')
                utc(value['requested_at_utc'])
                receipts[request_id] = value
            elif key == 'operator-applied:' + request_id:
                request = receipts.get(request_id)
                if (request is None or value['kind'] not in ('OPERATOR_INTENT', 'OPERATOR_REJECTED')
                        or value['name'] != request['name']
                        or value['effective_at_utc'] != request['requested_at_utc']):
                    raise ValueError('operator application disagrees with durable receipt')
                if value['kind'] == 'OPERATOR_REJECTED' and not value.get('reason'):
                    raise ValueError('operator rejection reason missing')
                applied[request_id] = value
            else:
                raise ValueError('operator receipt identity mismatch')
        return receipts, applied

    def pending_controls(self):
        with self.lock:
            receipts, applied = self._control_records()
            return [r for key, r in receipts.items() if key not in applied]

    def control_application(self, request_id):
        with self.lock:
            row = self._connect().execute('SELECT payload,checksum FROM events WHERE event_key=?',
                                         ('operator-applied:' + request_id,)).fetchone() if self.path.exists() else None
            if row is None:
                return None
            value = json.loads(row[0])
            if digest(value) != row[1] or value.get('request_id') != request_id:
                raise ValueError('operator application integrity mismatch')
            return value

    def close(self):
        with self.lock:
            self._close()

    def _close(self):
        if self.db is not None:
            try:
                if self.ownership is not None and self._writable and self.last is not None:
                    self.ownership.assert_owned()
                    self.db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
            finally:
                self.db.close()
                self.db = None
                self._writable = False
