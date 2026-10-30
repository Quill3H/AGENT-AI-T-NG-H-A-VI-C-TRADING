"""Compact Windows PAPER account, exact recovery and full chronological replay."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from threading import Event, RLock
from uuid import uuid4

import requests

from src.execution.funding_model import FixedFundingModel
from src.paper.live_session import LocalPaperSession, PROJECT_ROOT, _config, _utc, parse_klines
from src.paper.history_source import BinanceHistorySource, fetch_closed_range, PaperInterrupted, check_interruption
from src.paper.causal_runner import CausalRunner, stored_bar, validate_bar
from src.paper.compact_store import PaperStore, digest
from src.paper.durable_journal import DurableJournal
from src.paper.public_stream import SYMBOLS, INTERVAL_MS
from src.paper.recovery_state import restore_session
from src.paper.recipes import recipe_snapshot
from src.paper.research_cycle import evaluate_research, promotion_verdict, research_windows, promotion_block_reason
from src.paper.trials import utc


UTC = timezone.utc
DEFAULT_ACCOUNT_DIR = PROJECT_ROOT / 'data/paper_accounts/windows-paper-v3'


def fixed_model_config(effective):
    return {'kind': 'FIXED_SIMULATED', 'version': 'fixed-001', 'rate': 0.0001,
            'effective_at_utc': effective.isoformat(), 'settlement_hours_utc': [0, 8, 16],
            'price_proxy': 'CANDLE_OPEN', 'symbols': list(SYMBOLS)}


class PaperReplaySession(LocalPaperSession):
    """Reuse validated display/ownership helpers; new accounts never use v2 writes."""
    def __init__(self, source=None, journal_dir=None, auto_resume=False, ownership=None, clock=None):
        self.source = source or BinanceHistorySource()
        self.journal_dir = Path(journal_dir or DEFAULT_ACCOUNT_DIR)
        self.ownership, self._closed = ownership, False
        if ownership is not None:
            ownership.assert_owned()
            if ownership.directory != self.journal_dir.resolve():
                raise ValueError('account ownership path mismatch')
        self.lock = RLock()
        self.cancel_event = Event()
        self.clock = clock or (lambda: datetime.now(UTC))
        self.config = _config()
        self.config_hash = digest(self.config)
        self.session_id, self.status, self.error = None, 'IDLE', None
        self.broker, self.runner = None, None
        self.strategies, self.last_open, self.last_4h = {}, {}, {}
        self.last_processed = None
        self.chart, self.charts, self.markets = [], {s: [] for s in SYMBOLS}, {}
        self.server_ms, self.received_at = None, None
        self.stream_connected, self.reconnect_required = False, False
        self.stream_error, self.stream_last_event_at = 'public stream not connected', None
        self.stream_closed = {}
        self.recovery_snapshot, self.recovery_machine = None, None
        self.replay = {'target_close_utc': None, 'processed_batches': 0, 'remaining_batches': 0}
        self.legacy_fingerprints = {}
        self._event_keys = set()
        self.catalog = []
        self.research = {'status': 'NOT_REQUIRED', 'used_holdouts': [],
                         'next_attempt_after_utc': None, 'last_verdict': None}
        self._chart_cache = {}
        self.strategy_decisions = {symbol: {"state": "SCANNING", "symbol": symbol, "time_utc": None,
            "order_id": None, "trade_id": None, "reason": None} for symbol in SYMBOLS}
        self._batch_decisions = {}
        self.storage = PaperStore(self.journal_dir, ownership)
        self._saved = None
        try:
            self._saved = self.storage.inspect()
            if self._saved is not None:
                self.session_id = self._saved['account_id']
                self.status = 'RECOVERY_REQUIRED'
                self.error = 'compact account awaits exact restore'
        except ValueError as exc:
            self.status, self.error = 'RECOVERY_REQUIRED', str(exc)
        if auto_resume:
            self._claim_account()
            self.storage.ownership = self.ownership
            self.reconcile_resume()
        self._published = self._state_unlocked()

    def _adopt(self, runner):
        self.runner, self.broker = runner, runner.broker
        self.config, self.config_hash = deepcopy(runner.config), digest(runner.config)
        self.strategies, self.last_open, self.last_4h = runner.strategies, runner.last_open, runner.last_4h
        if not self.catalog:
            available = utc(runner.trials.trials[0]['recipe']['available_at_utc'])
            self.catalog = [recipe_snapshot(name, runner.config, available)
                            for name in ('trend_following', 'breakout_retest')]
        if runner.broker.current_time is not None:
            self.last_processed = runner.last_open['BTCUSDT']
        self.markets = {s: {'last_closed_15m_price': runner.broker.last_mark_prices.get(s),
                            'as_of_utc': (runner.last_open[s] + timedelta(minutes=15)).isoformat()}
                        for s in SYMBOLS}

    def _all_events(self):
        result, cursor = [], 0
        while True:
            page = self.storage.events(cursor, 500)
            result.extend(page['items'])
            if page['next_cursor'] is None:
                return result
            cursor = page['next_cursor']

    def _persist(self, candidate, inputs, extra_events, batch_id, migration=False):
        candidate.broker.verify_accounting_invariants()
        previous = self._saved['machine']['runner'] if self._saved else None
        since = previous['ledger_counts'] if previous and previous['trial_id'] == candidate.trial_id else None
        ledger = [e for e in candidate.ledger_events(since) if e['key'] not in self._event_keys]
        catalog = self.catalog or [recipe_snapshot(name, candidate.config,
                                   utc(candidate.trials.trials[0]['recipe']['available_at_utc']))
                                   for name in ('trend_following', 'breakout_retest')]
        machine = {'runner': candidate.capture(), 'legacy_fingerprints': self.legacy_fingerprints,
                   'catalog': deepcopy(catalog), 'research': deepcopy(self.research)}
        saved = self.storage.commit(self.session_id, candidate.config, inputs,
                                    ledger + candidate.trial_events + extra_events, machine, batch_id, migration=migration)
        self._event_keys.update(e['key'] for e in ledger + candidate.trial_events + extra_events)
        self._saved = saved
        candidate.execution_inputs = []  # Canonical execution bars now live in SQLite only.
        candidate.trial_events.clear()
        self._adopt(candidate)

    def checkpoint(self):
        with self.lock:
            self._claim_account()
            self.storage.ownership = self.ownership
            if self.runner is None or self.status == 'RECOVERY_REQUIRED':
                raise ValueError('no reconciled runner to checkpoint')
            self._persist(self.runner, [], [], 'checkpoint-' + str(self.storage.last['generation'] + 1))
            return self.state()

    def start(self):
        with self.lock:
            self._claim_account()
            self.storage.ownership = self.ownership
            if self.status == 'RECOVERY_REQUIRED':
                return self.reconcile_resume()
            if self.status == 'WAITING_CONNECTION' and self.runner is None:
                try:
                    if self.storage.inspect() is None:
                        self.status = 'IDLE'
                except ValueError as exc:
                    self.status, self.error = 'RECOVERY_REQUIRED', str(exc)
                    return self.state()
            if self.status != 'IDLE':
                return self.state()
            try:
                existing = self.storage.inspect()
            except ValueError as exc:
                self.status, self.error = 'RECOVERY_REQUIRED', str(exc)
                return self.state()
            try:
                check_interruption(self.cancel_event)
                if existing is not None:
                    self.status = 'RECOVERY_REQUIRED'
                    return self.reconcile_resume()
                server = self.source.server_time_ms()
                warmup, baseline = {}, {}
                for symbol in SYMBOLS:
                    check_interruption(self.cancel_event)
                    warmup[symbol], _ = parse_klines(self.source.klines(symbol, '4h', 250), '4h', server)
                    execution, _ = parse_klines(self.source.klines(symbol, '15m', 4), '15m', server)
                    if not execution or server - int(execution[-1]['close_time'].timestamp() * 1000) > INTERVAL_MS['15m']:
                        raise ValueError('stale initial public baseline')
                    baseline[symbol] = execution[-1]
                boundary = baseline['BTCUSDT']['close_time']
                config = deepcopy(self.config)
                config['paper_funding_model'] = fixed_model_config(boundary)
                candidate = CausalRunner(config, 'trend_following', boundary)
                candidate.initialize(warmup, baseline)
                self.session_id = datetime.now(UTC).strftime('%Y%m%dT%H%M%S') + '-' + uuid4().hex[:8]
                receipt = datetime.now(UTC).isoformat()
                inputs = [dict(i, received_at_utc=receipt) for i in candidate.all_inputs()]
                event = {'key': 'account-start', 'kind': 'ACCOUNT_START', 'capital_usd': 10000,
                         'recipe_identity': candidate.recipe['identity'], 'funding_model': config['paper_funding_model'],
                         'simulated_at_utc': boundary.isoformat(), 'processed_at_utc': receipt}
                self._persist(candidate, inputs, [event], 'account-start')
                self.server_ms, self.received_at, self.status = server, receipt, 'SCANNING'
                self.error = None
                self.markets = {s: {'last_closed_15m_price': baseline[s]['close'],
                                    'as_of_utc': baseline[s]['close_time'].isoformat()} for s in SYMBOLS}
                return self.state()
            except PaperInterrupted:
                self.stream_connected, self.reconnect_required = False, False
                return self.state()
            except Exception as exc:
                self.status = 'RECOVERY_REQUIRED' if self.storage.path.exists() else 'WAITING_CONNECTION'
                self.error = f'paper start blocked: {exc}'
                return self.state()

    def reconcile_resume(self):
        with self.lock:
            if self._closed:
                raise RuntimeError('paper session has been shut down')
            self._claim_account()
            self.storage.ownership = self.ownership
            try:
                if not self.storage.path.exists() and (self.journal_dir / 'account.json').exists():
                    return self._migrate_legacy()
                saved = self.storage.inspect()
                if saved is None:
                    return self.state()
                events = self._all_events()
                inputs = [bar for s in SYMBOLS for interval in ('4h', '15m') for bar in self.storage.inputs(s, interval)]
                candidate = CausalRunner.restore(saved['config'], saved['machine']['runner'], inputs, events)
                self.legacy_fingerprints = saved['machine'].get('legacy_fingerprints', {})
                self.catalog = saved['machine']['catalog']
                if any(recipe_snapshot(r['strategy_id'], saved['config'], utc(r['available_at_utc'])) != r for r in self.catalog):
                    raise ValueError('frozen research catalog identity changed')
                self.research = deepcopy(saved['machine']['research'])
                if self.research['status'] in ('ACQUIRING_DATA', 'EVALUATING', 'HOLDOUT_CLAIMED'):
                    self.research['status'] = 'RESEARCH_INTERRUPTED'
                self.session_id = saved['account_id']
                self._saved, self._event_keys = saved, {e['key'] for e in events}
                self._adopt(candidate)
                self.error = None
                self._consume_controls()
                if self.runner.intent == 'STOPPED':
                    self.status = 'STOPPED'
                    return self.state()
                self.status = 'WAITING_CONNECTION'
                self._sync_history('REPLAY')
                self.status = 'STOPPED' if self.runner.intent == 'STOPPED' else 'WAITING_CONNECTION'
                self.stream_error = 'checkpoint restored; waiting for fresh verified WebSocket'
                self.reconnect_required = self.status != 'STOPPED'
            except PaperInterrupted:
                self.stream_connected, self.reconnect_required = False, False
            except requests.RequestException as exc:
                self.status, self.error = 'WAITING_CONNECTION', f'public recovery transport blocked: {exc}'
                self.reconnect_required = True
            except Exception as exc:
                self.status, self.error = 'RECOVERY_REQUIRED', f'exact paper recovery blocked: {exc}'
                self.reconnect_required = False
            return self.state()

    def _migrate_legacy(self):
        """Only provable v2 machines/seed boundaries migrate; originals never change.

        A v2 sliding feature window or an unprocessed public funding gap cannot
        be guessed. Such accounts require a separately authorized reconciliation.
        """
        legacy = LocalPaperSession(source=self.source, journal_dir=self.journal_dir, ownership=self.ownership)
        existing, view, reason = legacy.storage.inspect()
        self.recovery_snapshot = view
        if not existing or view is None or legacy.storage.machine is None:
            raise ValueError(reason or 'legacy account has no exact v2 machinery')
        restore_session(legacy, legacy.storage.machine, view)
        if legacy.broker.is_finalized and (legacy.broker.positions or legacy.broker.pending_orders):
            raise ValueError('legacy terminal exposure is unreconciled')
        from src.features.indicators import _PANDAS_TA_AVAILABLE
        if _PANDAS_TA_AVAILABLE:
            raise ValueError('legacy optional indicator convention cannot be proven identical to v3 fallback')
        journal = self.journal_dir / (legacy.session_id + '.jsonl')
        raw = journal.read_bytes()
        start_record = json.loads(raw.splitlines()[0])
        server = self.source.server_time_ms()
        boundary = _utc(server // INTERVAL_MS['15m'] * INTERVAL_MS['15m'])
        if any(t + timedelta(minutes=15) != boundary for t in legacy.last_open.values()):
            raise ValueError('legacy outage/public funding and historical feature seed are not exactly reconstructible; no fixed-model debt erasure')
        warmup, baseline = {}, {}
        for symbol in SYMBOLS:
            warmup[symbol], _ = parse_klines(start_record['raw_warmup_4h'][symbol], '4h', server)
            if warmup[symbol][-1]['open_time'] != legacy.last_4h[symbol]:
                raise ValueError('legacy signal windows were reseeded; exact retained prefix unavailable')
            bars, _ = parse_klines(self.source.klines(symbol, '15m', 4), '15m', server)
            baseline[symbol] = next(b for b in bars if b['open_time'] == legacy.last_open[symbol])
        config = deepcopy(legacy.config)
        config['paper_funding_model'] = fixed_model_config(boundary)
        candidate = CausalRunner(config, 'trend_following', boundary)
        candidate.initialize(warmup, baseline)
        candidate.broker = deepcopy(legacy.broker)
        candidate.broker.config = deepcopy(config)
        candidate.trial_events.extend(candidate.trials.observe(candidate.broker.equity, boundary))
        for symbol in SYMBOLS:
            candidate.strategies[symbol].setup = deepcopy(legacy.strategies[symbol].setup)
            candidate.strategies[symbol].setup_count = legacy.strategies[symbol].setup_count
            candidate.strategies[symbol].candidate_count = legacy.strategies[symbol].candidate_count
        candidate.intent = 'STOPPED' if legacy.status == 'STOPPED' else 'RUNNING'
        if candidate.intent == 'STOPPED':
            candidate.controls.append({'intent': 'STOPPING', 'effective_at_utc': boundary.isoformat()})
        self.session_id = legacy.session_id
        self.legacy_fingerprints = {journal.name: sha256(raw).hexdigest(),
                                    'account.json': sha256((self.journal_dir / 'account.json').read_bytes()).hexdigest()}
        event = {'key': 'legacy-migration', 'kind': 'LEGACY_MIGRATION',
                 'original_config_sha256': legacy.config_hash,
                 'original_evidence_sha256': dict(self.legacy_fingerprints),
                 'funding_effective_at_utc': boundary.isoformat(),
                 'processed_at_utc': datetime.now(UTC).isoformat()}
        CausalRunner.restore(candidate.config, candidate.capture(), candidate.all_inputs(), candidate.ledger_events())
        self._persist(candidate, candidate.all_inputs(), [event], 'legacy-migration', migration=True)
        self.status = 'STOPPED' if candidate.intent == 'STOPPED' else 'WAITING_CONNECTION'
        self.stream_error = 'verified v2 migration; awaiting fresh public stream'
        self.error = None
        self.recovery_snapshot = None
        self.server_ms = server
        return self.state()

    def _sync_history(self, mode, expected=None):
        if self.runner is None:
            raise ValueError('runner not restored')
        server = self.source.server_time_ms()
        target = _utc(server // INTERVAL_MS['15m'] * INTERVAL_MS['15m'])
        start = self.last_open['BTCUSDT'] + timedelta(minutes=15)
        if target < start:
            raise ValueError('source clock precedes committed processing boundary')
        self.replay = {'target_close_utc': target.isoformat(), 'processed_batches': 0,
                       'remaining_batches': int((target - start).total_seconds() // 900)}
        if target == start:
            self.server_ms = server
            return
        # Validate every requested page/symbol before any new financial mutation.
        execution = {s: fetch_closed_range(self.source, s, '15m', start, target, server, self.cancel_event) for s in SYMBOLS}
        signal_end = _utc(int(target.timestamp() * 1000) // INTERVAL_MS['4h'] * INTERVAL_MS['4h'])
        signals = {s: fetch_closed_range(self.source, s, '4h', self.last_4h[s] + timedelta(hours=4),
                                        signal_end, server, self.cancel_event) for s in SYMBOLS}
        by_signal = {s: {b['close_time']: b for b in signals[s]} for s in SYMBOLS}
        if expected is not None:
            for symbol in SYMBOLS:
                bar = next((b for b in execution[symbol] if b['open_time'] == expected[symbol]['open_time']), None)
                if bar is None or any(bar[k] != expected[symbol][k] for k in ('open_time', 'close_time', 'open', 'high', 'low', 'close', 'volume')):
                    raise ValueError('closed WebSocket/REST candle disagreement')
        for index in range(len(execution['BTCUSDT'])):
            check_interruption(self.cancel_event)
            bars = {s: dict(execution[s][index], symbol=s, timeframe='15m') for s in SYMBOLS}
            closed = bars['BTCUSDT']['close_time']
            signal = {s: by_signal[s][closed] for s in SYMBOLS} if closed.hour % 4 == 0 and closed.minute == 0 else None
            if FixedFundingModel.from_config(self.runner.config) is None:
                for symbol, b in bars.items():
                    if symbol in self.broker.positions and b['open_time'].hour in self.broker.funding_hours and b['open_time'].minute == 0:
                        b.update(self._funding_metadata(symbol, b['open_time']))
            # Durable acceptance cannot interleave after the control check and
            # before this financial batch commits. Downloads remain outside.
            with self.storage.lock:
                candidate = self.runner.fork()
                self._drain_controls(candidate)
                if candidate.intent == 'STOPPED':
                    self._persist(candidate, [], [], 'operator-stop:' + digest(candidate.controls))
                    self.status = 'STOPPED'
                    return
                batch_mode = ('REALTIME' if mode == 'REALTIME' and expected is not None
                              and bars['BTCUSDT']['open_time'] == expected['BTCUSDT']['open_time'] else 'REPLAY')
                candidate.advance(bars, signal, batch_mode)
                receipt = datetime.now(UTC).isoformat()
                inputs = [stored_bar(validate_bar(b, s, '15m'), b.get('received_at_utc', receipt)) for s, b in bars.items()]
                if signal is not None:
                    inputs.extend(stored_bar(validate_bar(b, s, '4h'), b.get('received_at_utc', receipt)) for s, b in signal.items())
                event = {'key': 'batch-' + bars['BTCUSDT']['open_time'].isoformat(), 'kind': 'PAPER_BATCH',
                         'execution_mode': batch_mode, 'simulated_at_utc': closed.isoformat(), 'processed_at_utc': receipt,
                         'equity_usd': candidate.broker.equity, 'trial_id': candidate.trial_id}
                self._persist(candidate, inputs, [event], event['key'])
            if self.runner.trials.current['status'] == 'FAILED':
                self.run_research()
            if self.status == 'RECOVERY_REQUIRED':
                return
            self.server_ms, self.received_at = server, receipt
            self.replay['processed_batches'] += 1
            self.replay['remaining_batches'] -= 1
            if self.replay['processed_batches'] % 16 == 0:
                self._published = self._state_unlocked()
            if self.runner.intent == 'STOPPED':
                break

    def _research_inputs(self, cutoff):
        windows = research_windows(cutoff)
        train_start = windows['train'][0]
        signal_start = _utc(int(train_start.timestamp()) // 14400 * 14400) - timedelta(hours=4 * 210)
        signal_end = _utc(int(cutoff.timestamp()) // 14400 * 14400)
        ranges = {'4h': (signal_start, signal_end), '15m': (train_start - timedelta(minutes=15), cutoff)}
        server = self.source.server_time_ms()
        result = {}
        for symbol in SYMBOLS:
            result[symbol] = {}
            for interval, (start, end) in ranges.items():
                cache = {utc(b['open_time']): validate_bar(b, symbol, interval)
                         for b in self.storage.inputs(symbol, interval) if start <= utc(b['open_time']) < end}
                step = timedelta(milliseconds=INTERVAL_MS[interval])
                cursor = start
                while cursor < end:
                    check_interruption(self.cancel_event)
                    page_end = min(cursor + step * 500, end)
                    count = int((page_end - cursor) / step)
                    if any(cursor + step * n not in cache for n in range(count)):
                        page = fetch_closed_range(self.source, symbol, interval, cursor, page_end, server, self.cancel_event)
                        receipt = datetime.now(UTC).isoformat()
                        inputs = [stored_bar(validate_bar(b, symbol, interval), b.get('received_at_utc', receipt)) for b in page]
                        key = f'research-input:{symbol}:{interval}:{cursor.isoformat()}:{page_end.isoformat()}'
                        self._persist(self.runner.fork(), inputs, [], key)
                        cache.update({b['open_time']: validate_bar(b, symbol, interval) for b in page})
                    cursor = page_end
                result[symbol][interval] = [cache[t] for t in sorted(cache)]
        return result

    def run_research(self):
        """One bounded internal round. No endpoint accepts caller-supplied scores."""
        with self.lock:
            if self.runner is not None and self.status != 'RECOVERY_REQUIRED':
                self._consume_controls()
            runner = self.runner
            if (self._closed or runner is None or self.status == 'RECOVERY_REQUIRED'
                    or runner.trials.current['status'] != 'FAILED' or runner.intent != 'RUNNING'
                    or runner.broker.positions or runner.broker.pending_orders or runner.broker.pending_closes):
                return self.state()
            cutoff = runner.last_open['BTCUSDT'] + timedelta(minutes=15)
            if runner.intent_at(cutoff) != 'RUNNING':
                return self.state()
            verdict = self.research.get('last_verdict')
            if (verdict and verdict.get('eligible') is True
                    and verdict.get('identity') not in runner.trials.allocations):
                try:
                    with self.storage.lock:
                        candidate = self.runner.fork()
                        self._drain_controls(candidate)
                        if candidate.intent == 'RUNNING' and candidate.intent_at(cutoff) == 'RUNNING':
                            recipe = self._checked_research_recipe(verdict, persisted=True)
                            if utc(verdict['cutoff_utc']) > cutoff:
                                raise ValueError('research verdict is unavailable at promotion time')
                            candidate.promote(recipe, verdict, cutoff)
                            event = {'key': 'research-promotion:' + verdict['identity'], 'kind': 'RESEARCH_PROMOTION',
                                     'verdict_identity': verdict['identity'], 'recipe_identity': recipe['identity'],
                                     'simulated_at_utc': cutoff.isoformat(), 'processed_at_utc': utc(self.clock()).isoformat()}
                            self._persist(candidate, [], [event], event['key'])
                        elif candidate.trial_events:
                            self._persist(candidate, [], [], 'operator-controls:' + digest(candidate.trial_events))
                            if candidate.intent in ('STOPPING', 'STOPPED'):
                                self.status = candidate.intent
                except Exception as exc:
                    self.status, self.error = 'RECOVERY_REQUIRED', f'frozen paper promotion blocked: {exc}'
                    self.stream_connected, self.reconnect_required = False, False
                return self.state()
            next_time = self.research.get('next_attempt_after_utc')
            if next_time and cutoff < utc(next_time):
                return self.state()
            self.research.update(status='ACQUIRING_DATA', cutoff_utc=cutoff.isoformat(),
                                 next_attempt_after_utc=(cutoff + timedelta(days=1)).isoformat())
            key = 'research-round:' + cutoff.isoformat()
            try:
                self._persist(runner.fork(), [], [{'key': key, 'kind': 'RESEARCH_ROUND',
                                                  'cutoff_utc': cutoff.isoformat()}], key)
                try:
                    inputs = self._research_inputs(cutoff)
                    self.research['status'] = 'EVALUATING'
                    def claim(value):
                        self.research['status'] = 'HOLDOUT_CLAIMED'
                        self.research['used_holdouts'].append(value['holdout_interval_utc'])
                        self._persist(self.runner.fork(), [], [value], value['key'])
                    verdict = evaluate_research(self.config, self.catalog, inputs, cutoff,
                                                self.research['used_holdouts'], on_holdout_claim=claim,
                                                cancel_event=self.cancel_event)
                except (requests.RequestException, ValueError) as exc:
                    verdict = {'eligible': False, 'status': 'DATA_BLOCKED', 'cutoff_utc': cutoff.isoformat(),
                               'reason': str(exc), 'holdout_consumed': False}
                    verdict['identity'] = digest(verdict)
                with self.storage.lock:
                    candidate = self.runner.fork()
                    self._drain_controls(candidate)
                    if verdict.get('eligible') is True and candidate.intent == 'RUNNING':
                        recipe = self._checked_research_recipe(verdict)
                        candidate.promote(recipe, verdict, cutoff)
                    self.research.update(status=verdict['status'], last_verdict=verdict)
                    event = {'key': 'research-verdict:' + verdict['identity'], 'kind': 'RESEARCH_VERDICT',
                             'verdict': verdict, 'processed_at_utc': datetime.now(UTC).isoformat()}
                    self._persist(candidate, [], [event], event['key'])
            except PaperInterrupted:
                self.stream_connected, self.reconnect_required = False, False
            except Exception as exc:
                self.status, self.error = 'RECOVERY_REQUIRED', f'paper research persistence/admission blocked: {exc}'
                self.stream_connected, self.reconnect_required = False, False
            return self.state()

    def _checked_research_recipe(self, verdict, persisted=False):
        if promotion_block_reason(self.config):
            raise ValueError('automatic promotion lacks independent evidence and a declared risk contract')
        if (digest({k: v for k, v in verdict.items() if k != 'identity'}) != verdict['identity']
                or not verdict.get('holdout_consumed')
                or verdict.get('holdout_interval_utc') not in self.research['used_holdouts']
                or promotion_verdict(verdict['folds'], verdict['stressed_folds'])['eligible'] is not True):
            raise ValueError('research promotion evidence/claim integrity mismatch')
        recipes = [r for r in self.catalog if r['identity'] == verdict['selected_recipe_identity']]
        if len(recipes) != 1:
            raise ValueError('research selected recipe is missing or ambiguous')
        recipe = recipes[0]
        if (recipe['config'] != self.config or utc(recipe['available_at_utc']) > utc(verdict['cutoff_utc'])
                or recipe_snapshot(recipe['strategy_id'], self.config, utc(recipe['available_at_utc'])) != recipe):
            raise ValueError('research frozen recipe/config changed')
        if persisted:
            events = self._all_events()
            originals = [e['verdict'] for e in events if e['kind'] == 'RESEARCH_VERDICT'
                         and e.get('verdict', {}).get('identity') == verdict['identity']]
            claims = [e for e in events if e['kind'] == 'RESEARCH_HOLDOUT_CLAIM'
                      and e.get('holdout_interval_utc') == verdict['holdout_interval_utc']]
            if (originals != [verdict] or len(claims) != 1
                    or any(claims[0].get(k) != verdict.get(k)
                           for k in ('selected_recipe_identity', 'cutoff_utc', 'data_sha256'))):
                raise ValueError('persisted research verdict/holdout provenance mismatch')
        return recipe

    def on_connection(self, connected, reason):
        with self.lock:
            if self._closed or self.status in ('RECOVERY_REQUIRED', 'STOPPED', 'IDLE'):
                self.stream_connected = False
                return self.state()
            self.stream_connected = False
            self.stream_closed.clear()
            self.stream_error = reason or 'awaiting fresh market events'
            self.reconnect_required = not connected
            self.status = 'WAITING_CONNECTION'
            if connected:
                try:
                    self._sync_history('REPLAY')
                    self.status = 'STOPPED' if self.runner.intent == 'STOPPED' else 'WAITING_SYNC'
                    self.stream_connected = self.status != 'STOPPED'
                    self.reconnect_required = False
                    self.error = None
                except PaperInterrupted:
                    self.stream_connected, self.reconnect_required = False, False
                except requests.RequestException as exc:
                    self.error = f'public history transport blocked: {exc}'
                    self.reconnect_required = True
                except Exception as exc:
                    self.status, self.error = 'RECOVERY_REQUIRED', f'public history integrity blocked: {exc}'
                    self.reconnect_required = False
            return self.state()

    def on_stream_event(self, event):
        with self.lock:
            if self._closed or not self.stream_connected or self.status not in ('SCANNING', 'WAITING_SYNC', 'STOPPING'):
                return self.state()
            try:
                symbol, interval = event['symbol'], event['interval']
                if symbol not in SYMBOLS or interval not in ('1m', '15m') or type(event['closed']) is not bool:
                    raise ValueError('unexpected public stream identity/flag')
                validate_bar(dict(event, provisional=False), symbol, interval)
                emitted, received, available = (utc(event[k]) for k in ('event_time', 'received_at', 'available_at'))
                if (not emitted <= received == available or (received - emitted).total_seconds() > 30
                        or not 0 <= (self.clock() - received).total_seconds() <= 30
                        or emitted < event['open_time'] or event['closed'] and emitted < event['close_time']
                        or not event['closed'] and emitted >= event['close_time']):
                    raise ValueError('invalid stream event/receipt/availability freshness')
                self.stream_last_event_at = event['received_at'].isoformat()
                self.stream_error = None
                self.markets.setdefault(symbol, {})['forming_15m'] = {
                    'price': event['close'], 'open_time_utc': event['open_time'].isoformat(),
                    'event_time_utc': event['event_time'].isoformat(), 'received_at_utc': event['received_at'].isoformat(),
                    'source': 'Binance USD-M WebSocket', 'closed': event['closed'], 'interval': interval}
                if interval == '1m' or not event['closed']:
                    return self.state()
                if event['open_time'] <= self.last_open[symbol]:
                    previous = self.storage.input_at(symbol, interval, event['open_time'].isoformat())
                    if previous is None or any(validate_bar(previous, symbol, interval)[k] != event[k]
                                               for k in ('open_time', 'close_time', 'open', 'high', 'low', 'close', 'volume')):
                        raise ValueError('duplicate stream candle conflicts with committed input')
                    return self.state()
                if symbol in self.stream_closed and any(self.stream_closed[symbol][k] != event[k]
                        for k in ('open_time', 'close_time', 'open', 'high', 'low', 'close', 'volume')):
                    return self.on_connection(False, 'same-symbol partial closed batch changed; reconnect required')
                self.stream_closed[symbol] = event
                self.status = 'WAITING_SYNC'
                if len(self.stream_closed) == len(SYMBOLS):
                    if len({b['open_time'] for b in self.stream_closed.values()}) != 1:
                        return self.on_connection(False, 'closed stream candles disagree across symbols')
                    expected = dict(self.stream_closed)
                    self.stream_closed.clear()
                    self._sync_history('REALTIME', expected)
                    self.status = 'STOPPED' if self.runner.intent == 'STOPPED' else 'SCANNING'
                return self.state()
            except PaperInterrupted:
                self.stream_connected, self.reconnect_required = False, False
                return self.state()
            except requests.RequestException as exc:
                return self.on_connection(False, f'public validation transport blocked: {exc}')
            except Exception as exc:
                self.status, self.error = 'RECOVERY_REQUIRED', f'public decision input blocked: {exc}'
                self.stream_connected = False
                return self.state()

    def poll(self, expected=None):
        with self.lock:
            if self._closed or self.runner is None or self.status in ('STOPPED', 'RECOVERY_REQUIRED'):
                return self.state()
            try:
                self._sync_history('REALTIME' if self.stream_connected else 'REPLAY', expected)
                self.status = 'STOPPED' if self.runner.intent == 'STOPPED' else 'SCANNING' if self.stream_connected else 'WAITING_CONNECTION'
            except PaperInterrupted:
                self.stream_connected, self.reconnect_required = False, False
            except requests.RequestException as exc:
                return self.on_connection(False, str(exc))
            except Exception as exc:
                self.status, self.error = 'RECOVERY_REQUIRED', str(exc)
            return self.state()

    def accept_control_request(self, command):
        """Capture operator time durably before waiting for the account writer."""
        if command['name'] in ('start', 'restore'):
            return dict(command)
        if (self._closed or self.runner is None or self.status == 'RECOVERY_REQUIRED'
                or self.runner.intent == 'STOPPED' and command['name'] != 'stop'):
            raise RuntimeError('paper control requires a verified nonterminal account')
        self.storage.record_control(command['id'], command['name'], command['requested_at_utc'])
        return dict(command, durable=True)

    def _drain_controls(self, candidate):
        requests = self.storage.pending_controls()
        for request in requests:
            intent = {'pause': 'PAUSED', 'resume': 'RUNNING', 'stop': 'STOPPING'}[request['name']]
            stamp = utc(request['requested_at_utc'])
            completion = {'key': 'operator-applied:' + request['request_id'],
                'kind': 'OPERATOR_INTENT', 'request_id': request['request_id'], 'name': request['name'],
                'effective_at_utc': stamp.isoformat(), 'processed_at_utc': utc(self.clock()).isoformat()}
            if candidate.intent == 'STOPPED':
                if intent != 'STOPPING':
                    completion.update(kind='OPERATOR_REJECTED', reason='terminal paper trial cannot resume or pause')
            else:
                candidate.set_intent(intent, stamp)
            candidate.trial_events.append(dict(completion, intent=candidate.intent))
        return bool(requests)

    def _consume_controls(self):
        with self.storage.lock:
            candidate = self.runner.fork()
            if self._drain_controls(candidate):
                self._persist(candidate, [], [], 'operator-controls:' + digest(candidate.trial_events))
                if candidate.intent in ('STOPPING', 'STOPPED'):
                    self.status = candidate.intent

    def apply_control_request(self, command):
        with self.lock:
            if self._closed or self.runner is None or self.status == 'RECOVERY_REQUIRED':
                raise RuntimeError('paper account cannot apply the operator request')
            try:
                self._consume_controls()
            except Exception as exc:
                self.status, self.error = 'RECOVERY_REQUIRED', f'operator intent storage failed: {exc}'
                self.stream_connected, self.reconnect_required = False, False
                raise
            application = self.storage.control_application(command['id'])
            if application is None:
                raise RuntimeError('operator request has no durable application')
            if application['kind'] == 'OPERATOR_REJECTED':
                raise ValueError(application['reason'])
            return self.state()

    def _control(self, intent):
        name = {'PAUSED': 'pause', 'RUNNING': 'resume', 'STOPPING': 'stop'}[intent]
        command = {'id': 'control-' + uuid4().hex, 'name': name,
                   'requested_at_utc': utc(self.clock()).isoformat()}
        try:
            self.accept_control_request(command)
            return self.apply_control_request(command)
        except Exception as exc:
            if self.runner is not None and self.runner.intent != 'STOPPED':
                self.status, self.error = 'RECOVERY_REQUIRED', f'operator intent storage failed: {exc}'
                self.stream_connected, self.reconnect_required = False, False
            return self.state()

    def pause(self):
        return self._control('PAUSED')

    def resume(self):
        return self._control('RUNNING')

    def stop(self):
        return self._control('STOPPING')

    def history(self, cursor=0, limit=100):
        if not self.lock.acquire(blocking=False):
            raise BlockingIOError('account writer busy; retry history after reconciliation')
        try:
            if self.status == 'RECOVERY_REQUIRED':
                raise BlockingIOError('history unavailable until account evidence is verified: ' + (self.error or 'unknown state'))
            return self.storage.events(cursor, limit)
        finally:
            self.lock.release()

    def request_shutdown(self):
        self.cancel_event.set()

    def state(self):
        if not self.lock.acquire(blocking=False):
            view = deepcopy(self._published)
            view.update(backend_busy=True, api_time_utc=datetime.now(UTC).isoformat())
            view['risk_gate'].update(admission_open=False, reason='backend reconciling or researching; published checkpoint is read-only')
            view['connection']['connected'] = False
            for price in view.get('current_prices', {}).values():
                price.update(price=None, valid=False, kind='STALE_OR_UNAVAILABLE')
            return view
        try:
            view = self._state_unlocked()
            view['backend_busy'] = False
            self._published = deepcopy(view)
            return view
        finally:
            self.lock.release()

    def chart_data(self, symbol, interval='1m', limit=90):
        if symbol not in SYMBOLS or interval not in INTERVAL_MS or type(limit) is not int or not 1 <= limit <= 500:
            raise ValueError('unsupported symbol, interval or limit')
        server = self.source.server_time_ms()
        raw = self.source.klines(symbol, interval, limit)
        bars, provisional = parse_klines(raw, interval, server)
        return {'symbol': symbol, 'interval': interval, 'server_time_utc': _utc(server).isoformat(),
                'candles': [{**{k: b[k] for k in ('open', 'high', 'low', 'close', 'provisional')},
                             'time_utc': b['open_time'].isoformat()} for b in bars + ([provisional] if provisional else [])]}

    def shutdown(self):
        with self.lock:
            if self._closed:
                return self.state()
            try:
                if self.runner is not None and self.status != 'RECOVERY_REQUIRED':
                    self.checkpoint()
                self.storage.close()
            finally:
                self._closed = True
                self.stream_connected, self.reconnect_required = False, False
                if self.ownership is not None:
                    self.ownership.release()
            return self.state()

    def _state_unlocked(self):
        state = super()._state_unlocked()
        if self.broker is None:
            state['account'] = {k: None for k in state['account']}
            state['recovery'].update(account_known=False, reconciled=False, view='UNKNOWN')
        state['api_version'] = 3
        state['account_as_of_utc'] = (self.last_open['BTCUSDT'] + timedelta(minutes=15)).isoformat() if self.runner else None
        state['valuation_kind'] = 'LAST_RECONCILED_CLOSED_15M'
        state['account_profile'] = 'windows-paper-v3' if self.journal_dir.resolve() == DEFAULT_ACCOUNT_DIR.resolve() else '<CUSTOM_ACCOUNT>'
        state['operation'] = None
        state['operator_intent'] = self.runner.intent if self.runner else None
        state['execution_mode'] = self.runner.mode if self.runner else None
        state['replay'] = dict(self.replay)
        model = FixedFundingModel.from_config(self.runner.config) if self.runner else None
        state['funding_model'] = model.describe() if model else {'kind': 'PUBLIC_OBSERVED' if self.runner else 'NOT_CONFIGURED'}
        state['strategy'] = self.runner.recipe['strategy_id'] if self.runner else None
        state['recipe'] = {k: v for k, v in self.runner.recipe.items() if k != 'config'} if self.runner else None
        state['trial_id'] = self.runner.trial_id if self.runner else None
        state['trials'] = self.runner.trials.capture() if self.runner else None
        failed = bool(self.runner and self.runner.trials.current['status'] == 'FAILED')
        state['research'] = deepcopy(self.research)
        if failed and self.research['status'] == 'NOT_REQUIRED':
            state['research']['status'] = 'WAITING_RESEARCH'
        state['research']['automatic_promotion_connected'] = promotion_block_reason(self.config) is None
        state['research']['promotion_block_reason'] = promotion_block_reason(self.config)
        state['research']['historical_verified'] = False
        state['research']['risk_contract_status'] = 'NOT_EVALUATED'
        state['risk_gate']['admission_open'] = bool(state['risk_gate']['admission_open'] and self.runner
                                                   and self.runner.intent == 'RUNNING' and not failed)
        state['current_prices'] = {}
        now = utc(self.clock())
        for symbol in SYMBOLS:
            forming = self.markets.get(symbol, {}).get('forming_15m')
            fresh = bool(self.stream_connected and forming and
                         0 <= (now - datetime.fromisoformat(forming['received_at_utc'])).total_seconds() <= 15)
            state['current_prices'][symbol] = {'price': forming['price'] if fresh else None,
                                               'valid': fresh, 'kind': 'PUBLIC_FUTURES' if fresh else 'STALE_OR_UNAVAILABLE',
                                               'as_of_utc': forming['event_time_utc'] if forming else None}
        fresh_all = all(p['valid'] for p in state['current_prices'].values())
        state['risk_gate']['admission_open'] = bool(state['risk_gate']['admission_open'] and fresh_all)
        if not fresh_all:
            state['risk_gate']['reason'] = state['error'] or 'waiting for fresh public prices for BTC/ETH/SOL'
        elif self.runner and self.runner.intent != 'RUNNING':
            state['risk_gate']['reason'] = 'operator intent: ' + self.runner.intent
        elif failed:
            state['risk_gate']['reason'] = 'failed trial; new entries blocked until eligible research'
        for key in ('orders', 'trades', 'funding_events'):
            state[key] = state[key][-100:]
        state['history'] = {'endpoint': '/api/history', 'page_size': 100, 'sample_unit': 'whole_position'}
        return state
