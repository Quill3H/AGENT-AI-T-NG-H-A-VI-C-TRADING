"""One-owner, checksummed SQLite account store. Never repairs or resets evidence."""
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3

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
            if db.execute('SELECT count(*) FROM commits').fetchone()[0] != payload['generation']:
                raise ValueError('commit generation integrity mismatch')
            if digest(payload['config']) != payload['config_sha256']:
                raise ValueError('config integrity mismatch')
            for name, checksum in payload['machine'].get('legacy_fingerprints', {}).items():
                if Path(name).name != name or sha256((self.directory / name).read_bytes()).hexdigest() != checksum:
                    raise ValueError('legacy migration evidence changed')
            self.last = payload
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
            CREATE TABLE commits(batch_id TEXT PRIMARY KEY, intent_sha256 TEXT NOT NULL);
            PRAGMA user_version=3;
        ''')

    def commit(self, account_id, config, inputs, events, machine, batch_id, *, migration=False):
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
            used = db.execute('SELECT intent_sha256 FROM commits WHERE batch_id=?', (batch_id,)).fetchone()
            if used:
                if used[0] != intent:
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
            payload = {'version': VERSION, 'account_id': account_id, 'config': config,
                       'config_sha256': digest(config), 'machine': machine,
                       'generation': prior['generation'] + 1 if prior else 1,
                       **{table + '_root': roots[table][0] for table in roots},
                       **{table + '_count': roots[table][1] for table in roots}}
            db.execute('INSERT OR REPLACE INTO checkpoint VALUES(1,?,?)', (canonical(payload), digest(payload)))
            db.execute('INSERT INTO commits VALUES(?,?)', (batch_id, intent))
            db.commit()
            self.last = payload
            return json.loads(canonical(payload))
        except BaseException:
            db.rollback()
            raise

    def inputs(self, symbol, interval):
        if not self.path.exists():
            return []
        return [json.loads(row[0]) for row in self._connect().execute(
            'SELECT payload FROM inputs WHERE symbol=? AND interval=? ORDER BY open_time', (symbol, interval))]

    def input_at(self, symbol, interval, opened):
        row = self._connect().execute('SELECT payload FROM inputs WHERE symbol=? AND interval=? AND open_time=?',
                                     (symbol, interval, opened)).fetchone()
        return json.loads(row[0]) if row else None

    def events(self, after=0, limit=100):
        if type(after) is not int or after < 0 or type(limit) is not int or not 1 <= limit <= 500:
            raise ValueError('invalid event cursor/limit')
        rows = [] if not self.path.exists() else self._connect().execute(
            'SELECT seq,payload FROM events WHERE seq>? ORDER BY seq LIMIT ?', (after, limit + 1)).fetchall()
        return {'items': [dict(json.loads(raw), cursor=seq) for seq, raw in rows[:limit]],
                'next_cursor': rows[limit - 1][0] if len(rows) > limit else None}

    def close(self):
        if self.db is not None:
            try:
                if self.ownership is not None and self._writable and self.last is not None:
                    self.ownership.assert_owned()
                    self.db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
            finally:
                self.db.close()
                self.db = None
                self._writable = False
