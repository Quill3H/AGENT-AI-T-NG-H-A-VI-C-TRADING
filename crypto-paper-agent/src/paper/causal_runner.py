"""Shared PAPER realtime/replay machinery; downloaded future suffixes never enter it."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import math

import pandas as pd

from src.execution.paper_broker import PaperBroker
from src.execution.order_models import (OrderStatus, OrderDirection, OrderType, PositionStatus, ExitReason,
    Position, OrderRequest, OrderExecutionRecord, TradeRecord, FundingEvent, AccountSnapshot)
from src.execution.funding_model import FixedFundingModel
from src.features import add_all_features
from src.paper.compact_store import digest, input_identity
from src.paper.public_stream import SYMBOLS, INTERVAL_MS
from src.paper.recipes import recipe_snapshot, make_strategy
from src.paper.recovery_state import pack, unpack, BROKER_STATIC
from src.paper.trials import TrialBook, utc, finite
from src.paper.exposure_reconciliation import verify_execution_reconciliation
from src.risk.circuit_breakers import CircuitBreakerState


LEDGERS = {'order_history': 'order_id', 'trade_history': 'trade_id',
           'funding_history': 'event_id', 'account_snapshots': None}
UTC = timezone.utc


def validate_bar(raw, symbol, interval):
    """Validate all values/availability before broker or feature mutation."""
    if type(raw) is not dict or interval not in INTERVAL_MS or symbol not in SYMBOLS:
        raise ValueError('invalid paper candle identity')
    if raw.get('symbol', symbol) != symbol or raw.get('provisional', False) is not False:
        raise ValueError('wrong symbol or provisional paper candle')
    opened, closed = raw.get('open_time'), raw.get('close_time')
    for name, value in [('open_time', opened), ('close_time', closed)]:
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
            if name == 'open_time':
                opened = value
            else:
                closed = value
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset().total_seconds() != 0:
            raise ValueError('paper candle timestamp must be UTC')
    step = timedelta(milliseconds=INTERVAL_MS[interval])
    if closed != opened + step or int(opened.timestamp() * 1000) % INTERVAL_MS[interval]:
        raise ValueError('invalid paper candle half-open interval')
    numbers = {}
    for name in ('open', 'high', 'low', 'close', 'volume'):
        val = raw.get(name)
        if type(val) not in (int, float) or not math.isfinite(val) or val < 0 or (name != 'volume' and val == 0):
            raise ValueError('invalid/non-finite paper candle numeric input')
        numbers[name] = float(val)
    if (numbers['high'] < max(numbers['open'], numbers['close'])
            or numbers['low'] > min(numbers['open'], numbers['close'])):
        raise ValueError('invalid paper candle OHLC geometry')
    return dict(symbol=symbol, timeframe=interval, open_time=opened, close_time=closed,
                provisional=False, **numbers,
                **{k: raw[k] for k in ('funding_rate', 'funding_time', 'funding_readiness') if k in raw})


def stored_bar(bar, received_at=None):
    result = {k: (v.isoformat() if isinstance(v, datetime) else v)
              for k, v in bar.items() if k not in ('timeframe', 'provisional', 'received_at_utc')}
    result['interval'] = bar['timeframe']
    result['source'] = 'Binance USD-M REST'
    result['exchange_close_ms'] = int(bar['close_time'].timestamp() * 1000) - 1
    receipt = bar.get('received_at_utc', received_at)
    if receipt is not None:
        result['received_at_utc'] = utc(receipt).isoformat()
    return result


def feature_frame(bars, config):
    frame = pd.DataFrame([{k: b[k] for k in ('open', 'high', 'low', 'close', 'volume')} for b in bars],
                         index=pd.DatetimeIndex([b['open_time'] for b in bars], tz='UTC'))
    # A versioned seed convention: installing an optional TA package cannot
    # change an already-running experiment on its next restart.
    return add_all_features(frame, config, use_fallback_indicators=True)


def decode_broker(config, packed, ledgers, news_sha256):
    broker = PaperBroker(config=config)
    values = unpack(packed)
    expected = set(vars(broker)) - {'config', 'news_filter'} - set(LEDGERS)
    if type(values) is not dict or set(values) != expected:
        raise ValueError('incomplete compact broker machine')
    if broker.news_filter.source_sha256 != news_sha256:
        raise ValueError('news source changed')
    for key in BROKER_STATIC:
        if values[key] != getattr(broker, key):
            raise ValueError('compact broker static configuration mismatch')
    breaker = values.pop('circuit_breaker')
    if type(breaker) is not dict or set(breaker) != {'__circuit_breaker__'}:
        raise ValueError('missing compact breaker state')
    state = breaker['__circuit_breaker__']
    if type(state) is not dict or set(state) != set(vars(broker.circuit_breaker)):
        raise ValueError('incomplete compact breaker state')
    for key in ('daily_loss_limit_pct', 'consecutive_losses_threshold', 'risk_reduction_on_streak',
                'consecutive_wins_to_recover', 'recovery_mode'):
        if state[key] != getattr(broker.circuit_breaker, key):
            raise ValueError('compact breaker rules differ from saved config')
    if (finite(state['risk_multiplier']) not in (1., broker.circuit_breaker.risk_reduction_on_streak)
            or any(type(state[k]) is not bool for k in ('is_locked', 'is_halted'))
            or any(type(state[k]) is not int or state[k] < 0
                   for k in ('consecutive_losses', 'consecutive_wins', 'lock_count'))
            or state['is_locked'] and not state['is_halted'] and state['locked_until'] is None
            or state['is_halted'] and not state['is_locked']):
        raise ValueError('invalid compact breaker lifecycle')
    for key in ('last_event_time', 'locked_until'):
        if state[key] is not None:
            utc(state[key])
    if not math.isclose(finite(state['rolling_24h_pnl']), sum(finite(p) for t, p in state['trade_history_24h']), abs_tol=1e-8):
        raise ValueError('compact breaker cashflows disagree')
    broker.circuit_breaker.__dict__.update(state)
    broker.__dict__.update(values)
    for key in LEDGERS:
        setattr(broker, key, ledgers[key])
    for category, cls, sequence in (('order_history', OrderExecutionRecord, '_order_seq'),
                                    ('trade_history', TradeRecord, '_trade_seq'),
                                    ('funding_history', FundingEvent, '_funding_seq')):
        records = getattr(broker, category)
        field = LEDGERS[category]
        if (any(type(r) is not cls for r in records) or type(getattr(broker, sequence)) is not int
                or getattr(broker, sequence) != len(records)
                or len({getattr(r, field) for r in records}) != len(records)):
            raise ValueError('compact ledger type/sequence identity mismatch')
    if any(type(r) is not AccountSnapshot for r in broker.account_snapshots):
        raise ValueError('invalid compact account snapshots')
    for record in [*broker.order_history, *broker.trade_history, *broker.funding_history,
                   *broker.positions.values(), *broker.pending_orders]:
        if type(record.direction) is not OrderDirection:
            raise ValueError('invalid execution direction type')
        if isinstance(record, OrderExecutionRecord) and (
                type(record.status) is not OrderStatus or type(record.order_type) is not OrderType):
            raise ValueError('invalid execution order status/type')
        if isinstance(record, TradeRecord) and type(record.exit_reason) is not ExitReason:
            raise ValueError('invalid execution realization exit reason')
        if isinstance(record, Position) and type(record.status) is not PositionStatus:
            raise ValueError('invalid execution position status')
    finite(broker.wallet_balance)
    if any(type(getattr(broker, flag)) is not bool for flag in ('is_halted', 'is_finalized')):
        raise ValueError('invalid execution account flags')
    if (type(broker.pending_closes) is not dict or any(s not in SYMBOLS
            or broker.current_time is None or utc(t) > utc(broker.current_time)
            for s, t in broker.pending_closes.items())):
        raise ValueError('invalid execution pending close decision')
    if type(broker.positions) is not dict or type(broker.pending_orders) is not list:
        raise ValueError('invalid compact exposure containers')
    for symbol, position in broker.positions.items():
        if (symbol not in SYMBOLS or type(position) is not Position or position.symbol != symbol
                or finite(position.stop_loss_price) <= 0 or not 1 <= finite(position.leverage) <= 5
                or finite(position.quantity) <= 0 or position.closed_at is not None):
            raise ValueError('invalid compact protected position')
    if any(type(r) is not OrderRequest or r.symbol not in SYMBOLS for r in broker.pending_orders):
        raise ValueError('invalid compact pending requests')
    pending = [(r.symbol, r.signal_time) for r in broker.pending_orders]
    recorded = [(r.symbol, r.requested_at) for r in broker.order_history if r.status == OrderStatus.PENDING]
    if len(set(pending)) != len(pending) or set(pending) != set(recorded) or len(recorded) != len(pending):
        raise ValueError('pending requests disagree with order ledger')
    model = FixedFundingModel.from_config(config)
    settled = {(e.event_id if model and e.timestamp >= model.effective_at else e.symbol, e.timestamp)
               for e in broker.funding_history}
    if settled != broker._settled_funding_keys:
        raise ValueError('funding ledger disagrees with exactly-once watermarks')
    if broker._is_handling_cb_lock or broker._defer_cb_lock_for_batch:
        raise ValueError('checkpoint captured inside unfinished broker batch')
    verify_execution_reconciliation(broker)
    broker.verify_accounting_invariants()
    return broker


class CausalRunner:
    def __init__(self, config, recipe_name, available_at):
        self.config = deepcopy(config)
        self.recipe = recipe_snapshot(recipe_name, config, available_at)
        self.broker = PaperBroker(config=deepcopy(config))
        self.strategies = {s: make_strategy(recipe_name, config, s) for s in SYMBOLS}
        self.signal_history = {s: [] for s in SYMBOLS}
        self.last_open = {}
        self.last_4h = {}
        self.intent = 'RUNNING'
        self.controls = [{'intent': 'RUNNING', 'effective_at_utc': available_at.isoformat()}]
        self.mode = 'REPLAY'
        self.trial_id = 'trial-0001'
        self.trials = TrialBook(self.recipe, available_at)
        self.trial_events = []
        self.execution_inputs = []
        self.signal_accumulators = {}

    def fork(self):
        memo = {id(self.broker): self.broker.fork(), id(self.execution_inputs): list(self.execution_inputs)}
        for bars in self.signal_history.values():
            memo[id(bars)] = list(bars)
        return deepcopy(self, memo)

    def intent_at(self, timestamp):
        applicable = [c for c in self.controls if datetime.fromisoformat(c['effective_at_utc']) <= timestamp]
        return applicable[-1]['intent'] if applicable else 'RUNNING'

    def set_intent(self, intent, timestamp):
        stamp = utc(timestamp)
        boundary = self.last_open.get('BTCUSDT')
        if intent not in ('RUNNING', 'PAUSED', 'STOPPING') or self.intent == 'STOPPED':
            raise ValueError('invalid/terminal operator intent')
        if (boundary is not None and stamp < boundary + timedelta(minutes=15)
                or stamp < datetime.fromisoformat(self.controls[-1]['effective_at_utc'])):
            raise ValueError('operator intent cannot backdate')
        if self.intent == intent:
            return
        self.controls.append({'intent': intent, 'effective_at_utc': stamp.isoformat()})
        self.intent = intent
        # Only already-reconciled boundaries can be acted upon immediately.
        if boundary is not None and stamp == boundary + timedelta(minutes=15):
            if intent != 'RUNNING':
                self.cancel_entries(stamp)
            if intent == 'STOPPING' and not self.broker.positions and not self.broker.pending_closes:
                self.intent = 'STOPPED'

    def initialize(self, warmup, baseline):
        if self.last_open or self.broker.positions or self.broker.pending_orders:
            raise ValueError('runner already initialized')
        if set(warmup) != set(SYMBOLS) or set(baseline) != set(SYMBOLS):
            raise ValueError('incomplete paper warmup/baseline')
        validated = {s: [validate_bar(b, s, '4h') for b in warmup[s]] for s in SYMBOLS}
        base = {s: validate_bar(baseline[s], s, '15m') for s in SYMBOLS}
        if len({b['open_time'] for b in base.values()}) != 1:
            raise ValueError('baseline synchronization mismatch')
        for symbol in SYMBOLS:
            bars = validated[symbol]
            if len(bars) < 200 or bars[-1]['close_time'] > base[symbol]['close_time']:
                raise ValueError('insufficient or future signal warmup')
            if any(b['open_time'] != a['close_time'] for a, b in zip(bars, bars[1:])):
                raise ValueError('warmup signal gap')
        for symbol in SYMBOLS:
            self.signal_history[symbol] = validated[symbol]
            self.last_open[symbol] = base[symbol]['open_time']
            self.last_4h[symbol] = validated[symbol][-1]['open_time']
        self._warm_strategies()
        self.execution_inputs = list(base.values())

    def _warm_strategies(self):
        for symbol in SYMBOLS:
            features = feature_frame(self.signal_history[symbol], self.config)
            for index in range(max(1, len(features) - 13), len(features)):
                current = features.iloc[index].to_dict()
                current.update(symbol=symbol, open_time=features.index[index].to_pydatetime(),
                               close_time=features.index[index].to_pydatetime() + timedelta(hours=4))
                # Warmup advances setup but discards requests, never trades.
                self.strategies[symbol].on_candle_close(current, features.iloc[:index + 1], self.broker)

    def advance(self, bars, signals=None, mode='REPLAY'):
        if mode not in ('REALTIME', 'REPLAY') or self.intent == 'STOPPED':
            raise ValueError('runner is not eligible to advance')
        if set(bars) != set(SYMBOLS):
            raise ValueError('incomplete synchronized execution batch')
        validated = {s: validate_bar(bars[s], s, '15m') for s in SYMBOLS}
        if len({b['open_time'] for b in validated.values()}) != 1:
            raise ValueError('execution synchronization mismatch')
        for symbol, bar in validated.items():
            if bar['open_time'] != self.last_open[symbol] + timedelta(minutes=15):
                raise ValueError('execution gap/duplicate/reversed bar')
        closed = validated['BTCUSDT']['close_time']
        needs_signal = closed.hour % 4 == 0 and closed.minute == 0
        signal_bars = None
        if needs_signal:
            if signals is None or set(signals) != set(SYMBOLS):
                raise ValueError('missing synchronized signal close')
            signal_bars = {s: validate_bar(signals[s], s, '4h') for s in SYMBOLS}
            if any(b['close_time'] != closed or b['open_time'] != self.last_4h[s] + timedelta(hours=4)
                   for s, b in signal_bars.items()):
                raise ValueError('signal gap or future availability')
        elif signals is not None:
            raise ValueError('signal supplied outside eligible close')
        candidate = self.fork()
        for symbol, bar in validated.items():
            group = int(bar['open_time'].timestamp()) // 14400 * 14400
            agg = candidate.signal_accumulators.get(symbol)
            if agg is None or agg['group'] != group:
                agg = {'group': group, 'count': 0, 'open': bar['open'], 'high': bar['high'],
                       'low': bar['low'], 'close': bar['close'], 'volume': 0.0}
                candidate.signal_accumulators[symbol] = agg
            agg.update(count=agg['count'] + 1, high=max(agg['high'], bar['high']),
                       low=min(agg['low'], bar['low']), close=bar['close'], volume=agg['volume'] + bar['volume'])
            # The first startup fragment may not have all 16 execution bars.
            # Every complete retained group must agree with the signal source.
            if signal_bars and agg['count'] == 16 and any(not math.isclose(
                    agg[k], signal_bars[symbol][k], rel_tol=1e-9, abs_tol=1e-8)
                    for k in ('open', 'high', 'low', 'close', 'volume')):
                raise ValueError('cross-timeframe signal aggregate disagreement')
        candidate.mode = mode
        opened = closed - timedelta(minutes=15)
        open_intent, close_intent = candidate.intent_at(opened), candidate.intent_at(closed)
        if open_intent != 'RUNNING' or candidate.trials.current['status'] == 'FAILED':
            candidate.cancel_entries(opened)
        if open_intent == 'STOPPING':
            for symbol in candidate.broker.positions:
                candidate.broker.request_close(symbol, opened)
        candidate.broker.process_batch([validated[s] for s in sorted(SYMBOLS)])
        candidate.trial_events.extend(candidate.trials.observe(candidate.broker.equity, closed))
        failed = candidate.trials.current['status'] == 'FAILED'
        if failed:
            candidate.cancel_entries(closed, 'PAPER_TRIAL_FAILED')
            for symbol in candidate.broker.positions:
                candidate.broker.request_close(symbol, closed)
        for symbol in SYMBOLS:
            candidate.last_open[symbol] = validated[symbol]['open_time']
        candidate.execution_inputs.extend(validated.values())
        if signal_bars is not None:
            for symbol in sorted(SYMBOLS):
                candidate.signal_history[symbol].append(signal_bars[symbol])
                features = feature_frame(candidate.signal_history[symbol], candidate.config)
                current = features.iloc[-1].to_dict()
                current.update(symbol=symbol, open_time=signal_bars[symbol]['open_time'], close_time=closed)
                strategy = candidate.strategies[symbol]
                strategy.update_trailing_stop(current, candidate.broker)
                request = strategy.on_candle_close(current, features, candidate.broker)
                if not failed and close_intent == 'RUNNING' and closed >= datetime.fromisoformat(candidate.recipe['available_at_utc']):
                    if request is not None:
                        request.metadata.update(recipe_identity=candidate.recipe['identity'], trial_id=candidate.trial_id)
                        candidate.broker.submit_order(request)
                candidate.last_4h[symbol] = signal_bars[symbol]['open_time']
        if close_intent == 'STOPPING' and not candidate.broker.positions and not candidate.broker.pending_closes:
            candidate.cancel_entries(closed)
            candidate.intent = 'STOPPED'
        candidate.broker.verify_accounting_invariants()
        self.__dict__.update(candidate.__dict__)
        return self

    def cancel_entries(self, timestamp, reason='PAPER_OPERATOR_ENTRY_PAUSED'):
        for request in self.broker.pending_orders:
            self.broker._update_order_record(request, OrderStatus.REJECTED, timestamp,
                                             reasons=[reason])
        self.broker.pending_orders.clear()

    def promote(self, recipe, verdict, timestamp):
        stamp = utc(timestamp)
        frozen = recipe_snapshot(recipe['strategy_id'], self.config, utc(recipe['available_at_utc']))
        if frozen != recipe or self.intent_at(stamp) != 'RUNNING' or self.intent in ('STOPPING', 'STOPPED'):
            raise ValueError('promotion cannot change config/formulas or ignore operator stop/pause')
        if stamp != self.last_open['BTCUSDT'] + timedelta(minutes=15):
            raise ValueError('promotion must use the reconciled simulated boundary')
        if verdict['identity'] in self.trials.allocations:
            return self.trials.promote(recipe, stamp, True, verdict)
        if self.broker.positions or self.broker.pending_orders or self.broker.pending_closes:
            raise ValueError('promotion requires a flat reconciled broker')
        self.broker.verify_accounting_invariants()
        candidate = self.fork()
        allocation = candidate.trials.promote(recipe, stamp, True, verdict)
        breaker = deepcopy(candidate.broker.circuit_breaker)
        replacement = CausalRunner(candidate.config, recipe['strategy_id'], utc(recipe['available_at_utc']))
        replacement.signal_history = {s: list(bars) for s, bars in candidate.signal_history.items()}
        replacement._warm_strategies()
        replacement.broker.circuit_breaker = breaker
        replacement.broker.current_time = stamp
        replacement.broker.last_mark_prices = dict(candidate.broker.last_mark_prices)
        candidate.recipe, candidate.strategies, candidate.broker = replacement.recipe, replacement.strategies, replacement.broker
        candidate.trial_id = candidate.trials.current['trial_id']
        candidate.trial_events.append(allocation)
        self.__dict__.update(candidate.__dict__)
        return allocation

    def all_inputs(self):
        return [stored_bar(b) for s in SYMBOLS for b in self.signal_history[s]] + [stored_bar(b) for b in self.execution_inputs]

    def ledger_events(self, since=None):
        events = []
        for category, identity_field in LEDGERS.items():
            records = getattr(self.broker, category)
            start = max(0, since.get(category, 0) - 1) if since and category != 'order_history' else 0
            for index in range(start, len(records)):
                record = records[index]
                identity = getattr(record, identity_field) if identity_field else str(index)
                payload = pack(record)
                events.append({'key': f'{self.trial_id}:{category}:{identity}:{digest(payload)}',
                               'kind': category, 'record_id': identity, 'trial_id': self.trial_id, 'payload': payload})
        return events

    def capture(self):
        return {'version': 3, 'recipe': deepcopy(self.recipe), 'trial_id': self.trial_id,
                'trials': self.trials.capture(),
                'signal_accumulators': deepcopy(self.signal_accumulators),
                'intent': self.intent, 'controls': deepcopy(self.controls), 'mode': self.mode, 'last_open': pack(self.last_open),
                'last_4h': pack(self.last_4h), 'news_source_sha256': self.broker.news_filter.source_sha256,
                'broker': pack({k: v for k, v in vars(self.broker).items() if k not in ('config', 'news_filter') and k not in LEDGERS}),
                'ledger_counts': {k: len(getattr(self.broker, k)) for k in LEDGERS},
                'strategies': pack({s: {k: v for k, v in vars(self.strategies[s]).items() if k != 'config'} for s in SYMBOLS}),
                'signal_prefix': {s: {'count': len(self.signal_history[s]),
                                      'first_open_utc': self.signal_history[s][0]['open_time'].isoformat(),
                                      'hash': digest([input_identity(stored_bar(b)) for b in self.signal_history[s]])} for s in SYMBOLS}}

    @classmethod
    def restore(cls, config, checkpoint, inputs, events):
        if checkpoint.get('version') != 3 or checkpoint.get('intent') not in ('RUNNING', 'PAUSED', 'STOPPING', 'STOPPED', 'WAITING_RESEARCH'):
            raise ValueError('invalid runner checkpoint')
        recipe = checkpoint['recipe']
        result = cls(config, recipe['strategy_id'], datetime.fromisoformat(recipe['available_at_utc']))
        if result.recipe != recipe:
            raise ValueError('recipe/formula/config identity changed')
        result.trial_id = checkpoint['trial_id']
        result.trials = TrialBook.restore(checkpoint['trials'])
        if result.trials.current['trial_id'] != result.trial_id or result.trials.current['recipe'] != recipe:
            raise ValueError('trial and recipe checkpoint identity mismatch')
        result.intent, result.mode = checkpoint['intent'], checkpoint['mode']
        result.controls = deepcopy(checkpoint['controls'])
        if (not result.controls or any(c.get('intent') not in ('RUNNING', 'PAUSED', 'STOPPING') for c in result.controls)
                or any(utc(b['effective_at_utc']) < utc(a['effective_at_utc'])
                       for a, b in zip(result.controls, result.controls[1:]))):
            raise ValueError('invalid persisted operator timeline')
        for control in result.controls:
            utc(control['effective_at_utc'])
        if result.controls[-1]['intent'] != ('STOPPING' if result.intent == 'STOPPED' else result.intent):
            raise ValueError('operator intent disagrees with persisted timeline')
        result.last_open, result.last_4h = unpack(checkpoint['last_open']), unpack(checkpoint['last_4h'])
        result.signal_accumulators = deepcopy(checkpoint['signal_accumulators'])
        if set(result.last_open) != set(SYMBOLS) or len(set(result.last_open.values())) != 1:
            raise ValueError('incomplete processing watermarks')
        histories = {k: {} for k in LEDGERS}
        for event in events:
            if event.get('kind') in LEDGERS and event.get('trial_id') == result.trial_id:
                histories[event['kind']][event['record_id']] = unpack(event['payload'])
        ledgers = {k: list(v.values()) for k, v in histories.items()}
        if any(len(ledgers[k]) != checkpoint['ledger_counts'][k] for k in LEDGERS):
            raise ValueError('compact financial history count mismatch')
        result.broker = decode_broker(config, checkpoint['broker'], ledgers, checkpoint['news_source_sha256'])
        if not math.isclose(result.trials.current['current_equity_usd'], result.broker.equity, abs_tol=1e-8):
            raise ValueError('trial equity disagrees with broker execution ledger')
        boundary = utc(result.last_open['BTCUSDT']) + timedelta(minutes=15)
        broker = result.broker
        if broker.last_candle_open_time_per_symbol and (
                broker.last_candle_open_time_per_symbol != result.last_open or broker.current_time != boundary
                or any(broker.last_candle_open_time_per_symbol.get(s) + timedelta(minutes=15) != boundary for s in SYMBOLS)):
            raise ValueError('broker clock disagrees with runner processing watermarks')
        if broker.circuit_breaker.last_event_time is not None and broker.circuit_breaker.last_event_time > boundary:
            raise ValueError('breaker clock exceeds reconciled processing boundary')
        strategies = unpack(checkpoint['strategies'])
        if set(strategies) != set(SYMBOLS):
            raise ValueError('incomplete strategy states')
        mutable = {'setup', 'setup_count', 'candidate_count', '_last_event'}
        for symbol in SYMBOLS:
            original = vars(result.strategies[symbol])
            saved = strategies[symbol]
            if set(saved) != set(original) - {'config'} or any(saved[k] != v for k, v in original.items() if k != 'config' and k not in mutable):
                raise ValueError('strategy static/state mismatch')
            result.strategies[symbol].__dict__.update(saved)
            result.signal_history[symbol] = [validate_bar(b, symbol, '4h') for b in inputs
                                              if b['symbol'] == symbol and b['interval'] == '4h'
                                              and datetime.fromisoformat(b['open_time']) >= datetime.fromisoformat(checkpoint['signal_prefix'][symbol]['first_open_utc'])
                                              and datetime.fromisoformat(b['open_time']) <= result.last_4h[symbol]]
            bars = result.signal_history[symbol]
            seed = checkpoint['signal_prefix'][symbol]
            if len(bars) != seed['count'] or digest([input_identity(stored_bar(b)) for b in bars]) != seed['hash']:
                raise ValueError('signal prefix unavailable/revised')
            if any(b['open_time'] != a['close_time'] for a, b in zip(bars, bars[1:])):
                raise ValueError('signal prefix gap')
            if not bars or bars[-1]['open_time'] != result.last_4h[symbol] or bars[-1]['close_time'] > boundary:
                raise ValueError('signal prefix disagrees with processing boundary')
        return result
