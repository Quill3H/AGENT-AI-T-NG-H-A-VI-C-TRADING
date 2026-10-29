"""Offline crypto ORB/FVG portfolio research using the project's PaperBroker."""
from calendar import monthrange
from collections import Counter
from dataclasses import asdict
from datetime import date, timedelta
import hashlib
import json
import math
from pathlib import Path
import re
from zipfile import ZipFile

import numpy as np
import pandas as pd
import yaml

from src.data_layer.vision_dataset import snap_funding_to_settlement
from src.execution.order_models import OrderRequest, OrderStatus
from src.execution.paper_broker import PaperBroker

ROOT = Path(__file__).resolve().parent.parent
NY = 'America/New_York'
DEFAULTS = dict(symbols=['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT',
                         'DOGEUSDT', 'ADAUSDT', 'AVAXUSDT', 'LINKUSDT', 'DOTUSDT'],
                start='2026-09-01', end='2026-09-30', initial_equity=10000.,
                max_concurrent_positions=4, risk_per_trade=.0025,
                position_notional_fraction=.25, weekly_target=60, monthly_target=240,
                taker_fee=.0005, slippage=.0002, cost_multiplier=1.)


def load_settings(raw):
    if not isinstance(raw, dict) or set(raw) - set(DEFAULTS):
        raise ValueError('unknown portfolio configuration fields')
    cfg = DEFAULTS | raw
    symbols = cfg['symbols']
    if (not isinstance(symbols, list) or not symbols or len(set(symbols)) != len(symbols)
            or not all(isinstance(s, str) and re.fullmatch('[A-Z0-9]+USDT', s) for s in symbols)):
        raise ValueError('unique uppercase crypto USDT perpetual symbols required')
    for key in ('max_concurrent_positions', 'weekly_target', 'monthly_target'):
        if type(cfg[key]) is not int or cfg[key] < 1:
            raise ValueError(f'{key} must be a positive integer')
    if cfg['max_concurrent_positions'] > 4:
        raise ValueError('owner ceiling is four simultaneous positions')
    for key in ('initial_equity', 'risk_per_trade', 'position_notional_fraction',
                'taker_fee', 'slippage', 'cost_multiplier'):
        value = cfg[key]
        if type(value) not in (float, int) or not math.isfinite(value) or value < 0:
            raise ValueError(f'invalid {key}')
        if key not in ('taker_fee', 'slippage') and value == 0:
            raise ValueError(f'{key} must be positive')
    if cfg['risk_per_trade'] > .02 or cfg['position_notional_fraction'] > .25:
        raise ValueError('research risk/notional ceiling exceeded')
    for fee in ('taker_fee', 'slippage'):
        if cfg[fee] * cfg['cost_multiplier'] >= 1:
            raise ValueError('cost must be below one')
    for key in ('start', 'end'):
        cfg[key] = date.fromisoformat(str(cfg[key])).isoformat()
    if cfg['start'] > cfg['end']:
        raise ValueError('start must precede end')
    return cfg


def validate_bars(frame, expected, label):
    if (not isinstance(frame.index, pd.DatetimeIndex) or str(frame.index.tz) != 'UTC'
            or not frame.index.equals(expected) or frame.index.has_duplicates):
        raise ValueError(f'{label}: non-UTC, duplicate, missing or unordered bars')
    values = frame[['open', 'high', 'low', 'close', 'volume']].to_numpy(float)
    o, h, l, c, v = values.T
    if (not np.isfinite(values).all() or (values[:, :4] <= 0).any() or (v < 0).any()
            or (h < np.maximum(o, c)).any() or (l > np.minimum(o, c)).any() or (h < l).any()):
        raise ValueError(f'{label}: invalid OHLCV')


def observed_increment(frame):
    grid = np.rint(frame[['open', 'high', 'low', 'close']].to_numpy() * 1e8).astype(np.int64)
    tick = int(np.gcd.reduce(grid.ravel())) / 1e8
    if tick <= 0:
        raise ValueError('cannot infer observed price increment')
    return tick


def find_signals(frame, cfg, tick=None):
    """Each row is a decision AFTER that minute closes; only past/current bars used."""
    found = []
    local = frame.index.tz_convert(NY)
    minutes = local.hour * 60 + local.minute
    session = frame.loc[(minutes >= 570) & (minutes < 960)]
    for day, bars in session.groupby(session.index.tz_convert(NY).date):
        if not cfg['start'] <= str(day) <= cfg['end'] or len(bars) < 22:
            continue
        m = bars.index.tz_convert(NY).hour * 60 + bars.index.tz_convert(NY).minute
        opening = bars.loc[m < 585]
        if len(opening) != 15:
            continue
        session_tick = tick if tick is not None else observed_increment(opening)
        or_high, or_low = opening.high.max(), opening.low.min()
        tr = pd.concat([bars.high - bars.low, (bars.high - bars.close.shift()).abs(),
                        (bars.low - bars.close.shift()).abs()], axis=1).max(axis=1)
        median = tr.rolling(20).median().shift(2)
        body = bars.close.shift() - bars.open.shift()
        spread = bars.high.shift() - bars.low.shift()
        volume = bars.volume.cumsum()
        vwap = (((bars.high + bars.low + bars.close) / 3 * bars.volume).cumsum() / volume)
        quant = (body.abs() >= 1.5 * median) & (body.abs() >= .6 * spread) & (spread > 0)
        long = ((bars.low - bars.high.shift(2) >= session_tick - 1e-10)
                & (bars.high.shift(2) > or_high) & (body > 0) & (bars.close > vwap))
        short = ((bars.low.shift(2) - bars.high >= session_tick - 1e-10)
                 & (bars.low.shift(2) < or_low) & (body < 0) & (bars.close < vwap))
        for i in np.flatnonzero((quant & (long | short) & (m >= 591) & (m <= 944)).to_numpy()):
            direction = 'LONG' if long.iloc[i] else 'SHORT'
            stop = bars.low.iloc[i - 2] - session_tick if direction == 'LONG' else bars.high.iloc[i - 2] + session_tick
            price = bars.close.iloc[i]
            target = 2 * price - stop
            if stop <= 0 or target <= 0 or (price - stop) * (1 if direction == 'LONG' else -1) <= 0:
                continue
            found.append(dict(time=bars.index[i], first_bar=bars.index[i - 2],
                              direction=direction, price=float(price), stop=float(stop), target=float(target)))
    return pd.DataFrame(found, columns=['time', 'first_bar', 'direction', 'price', 'stop', 'target']).set_index('time')


def sample_report(trades, start, end, weekly_target, monthly_target):
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    counts = Counter(pd.Timestamp(t['exit_time']).tz_convert(NY).date() for t in trades)
    def window(a, b, target):
        lo, hi = max(a, first), min(b, last)
        full = a >= first and b <= last
        n = sum(counts[d] for d in counts if lo <= d <= hi)
        return dict(start=str(a), end=str(b), covered_start=str(lo), covered_end=str(hi),
                    full_window=full, completed_trades=n, target=target,
                    status=('PASS' if n >= target else 'FAIL') if full else 'PARTIAL')
    weeks, months = [], []
    a = first - timedelta(days=first.weekday())
    while a <= last:
        weeks.append(window(a, a + timedelta(days=6), weekly_target))
        a += timedelta(days=7)
    a = first.replace(day=1)
    while a <= last:
        b = a.replace(day=monthrange(a.year, a.month)[1])
        months.append(window(a, b, monthly_target))
        a = b + timedelta(days=1)
    return dict(weeks=weeks, months=months)


def read_zip(path):
    checksum = path.with_suffix(path.suffix + '.CHECKSUM').read_text().split()[0]
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != checksum:
        raise ValueError(f'checksum mismatch: {path.name}')
    with ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != 1 or not names[0].endswith('.csv'):
            raise ValueError(f'unexpected archive: {path.name}')
        with archive.open(names[0]) as stream:
            return pd.read_csv(stream)


def load_archive(data_dir, cfg):
    frames, funding, audits = {}, {}, {}
    months = pd.period_range(cfg['start'], cfg['end'], freq='M')
    for symbol in cfg['symbols']:
        parts, events, checks = [], [], []
        for month in months:
            start = pd.Timestamp(str(month), tz='UTC')
            end = start + pd.offsets.MonthBegin()
            expected = pd.date_range(start, end, freq='min', inclusive='left')
            one = read_zip(data_dir / f'klines_{symbol}-1m-{month}.zip')
            one.index = pd.to_datetime(one.pop('open_time'), unit='ms', utc=True)
            one = one[['open', 'high', 'low', 'close', 'volume']].astype(float)
            validate_bars(one, expected, f'{symbol}/{month}/1m')
            fifteen = read_zip(data_dir / f'klines_{symbol}-15m-{month}.zip')
            fifteen.index = pd.to_datetime(fifteen.pop('open_time'), unit='ms', utc=True)
            fifteen = fifteen[['open', 'high', 'low', 'close', 'volume']].astype(float)
            validate_bars(fifteen, expected[::15], f'{symbol}/{month}/15m')
            aggregate = one.resample('15min').agg(dict(open='first', high='max', low='min', close='last', volume='sum'))
            mismatch = ~np.isclose(aggregate.to_numpy(), fifteen.to_numpy(), rtol=0, atol=1e-6).all(axis=1)
            checks.append(dict(month=str(month), minute_bars=len(one),
                               mismatched_15m_bars=int(mismatch.sum())))
            raw = read_zip(data_dir / f'fundingRate_{symbol}-fundingRate-{month}.zip')
            raw.index = pd.to_datetime(raw.calc_time, unit='ms', utc=True)
            if (not raw.index.is_monotonic_increasing or raw.index.has_duplicates
                    or not np.isfinite(raw[['last_funding_rate', 'funding_interval_hours']].to_numpy()).all()
                    or (raw.funding_interval_hours <= 0).any()):
                raise ValueError(f'{symbol}: invalid funding events')
            f = snap_funding_to_settlement(raw.rename(columns={'last_funding_rate': 'funding_rate'}))
            intervals = pd.to_timedelta(raw.funding_interval_hours.to_numpy(), unit='h')
            if (not len(f) or f.index[0] != start or f.index[-1] + intervals[-1] < end
                    or not ((f.index[1:] - f.index[:-1]) == intervals[1:]).all()):
                raise ValueError(f'{symbol}: incomplete archived funding schedule')
            checks[-1]['funding_events'] = len(f)
            checks[-1]['funding_snapped_events'] = int((f.funding_source_time.array != f.index.array).sum())
            parts.append(one)
            events.append(f)
        frame = pd.concat(parts)
        tick = observed_increment(frame)  # audit diagnostic only, never a decision input
        lo = pd.Timestamp(cfg['start'], tz='UTC')
        hi = pd.Timestamp(cfg['end'], tz='UTC') + pd.Timedelta(days=1)
        frames[symbol] = frame.loc[(frame.index >= lo) & (frame.index < hi)]
        funding[symbol] = pd.concat(events)
        audits[symbol] = dict(observed_grid_increment=tick, months=checks,
                              status='PASS' if not any(c['mismatched_15m_bars'] for c in checks) else 'SOURCE_CONFLICT')
    return frames, funding, audits


def broker_config(cfg):
    config = yaml.safe_load((ROOT / 'config/default_config.yaml').read_text(encoding='utf-8'))
    config['account']['initial_equity_usd'] = cfg['initial_equity']
    config['execution'] = {'max_concurrent_positions': cfg['max_concurrent_positions']}
    config['risk']['max_notional_pct_of_equity'] = cfg['position_notional_fraction']
    config['risk']['max_gross_notional_pct_of_equity'] = 1.
    config['fees'] = dict(taker_pct=cfg['taker_fee'] * cfg['cost_multiplier'],
                          maker_pct=cfg['taker_fee'] * cfg['cost_multiplier'],
                          slippage_pct=cfg['slippage'] * cfg['cost_multiplier'])
    # shortcut: conservative synthetic isolated-margin brackets at 1x only;
    # reconstruct venue historical contract metadata before execution research.
    config['leverage_brackets'] = {s: [[1e9, .01, 0]] for s in cfg['symbols']}
    return config


def replay(frames, funding, audits, cfg):
    broker = PaperBroker(broker_config(cfg), funding_hours=set())
    symbols = cfg['symbols']
    index = frames[symbols[0]].index
    if not all(frames[s].index.equals(index) for s in symbols):
        raise ValueError('all portfolio clocks must match exactly')
    arrays = {s: frames[s].to_numpy(float) for s in symbols}
    candidates, fund = {}, {}
    for symbol in symbols:
        signals = find_signals(frames[symbol], cfg)
        candidates[symbol] = {t: r for t, r in signals.iterrows()}
        fund[symbol] = {t: r for t, r in funding[symbol].iterrows()}
    rejections, equity, last_exit = [], [], {}
    peak, ambiguous, seen_trades = 0, 0, 0
    one_minute = pd.Timedelta(minutes=1)
    for i, timestamp in enumerate(index):
        bars = []
        for symbol in symbols:
            o, h, l, c, v = arrays[symbol][i]
            bar = dict(symbol=symbol, open_time=timestamp.to_pydatetime(), timeframe='1m',
                       open=float(o), high=float(h), low=float(l), close=float(c))
            if timestamp in fund[symbol]:
                event = fund[symbol][timestamp]
                bar.update(funding_rate=float(event.funding_rate), funding_time=timestamp.to_pydatetime(),
                           funding_readiness=True)
            bars.append(bar)
        broker.process_batch(bars)
        peak = max(peak, broker.last_batch_peak_positions)
        assert peak <= cfg['max_concurrent_positions']
        # Count completed lifecycles; this setup never uses partial exits.
        for trade in broker.trade_history[seen_trades:]:
            last_exit[trade.symbol] = trade.exit_time
            bar = bars[symbols.index(trade.symbol)]
            stop, target = trade.initial_stop_loss_price, trade.take_profit_levels
            if stop is not None and target:
                ambiguous += int(bar['low'] <= min(stop, target[0]) and bar['high'] >= max(stop, target[0]))
        seen_trades = len(broker.trade_history)
        decision = timestamp + one_minute
        equity.append(dict(timestamp=decision, equity=broker.equity, open_positions=len(broker.positions)))
        local = decision.tz_convert(NY)
        if local.hour == 16 and local.minute == 0:
            for symbol in list(broker.positions):
                broker.request_close(symbol, decision.to_pydatetime())
        for symbol in symbols:
            signal = candidates[symbol].get(timestamp)
            if signal is None:
                continue
            reason = None
            if symbol in broker.positions or any(r.symbol == symbol for r in broker.pending_orders):
                reason = 'SYMBOL_BUSY'
            elif signal.first_bar < last_exit.get(symbol, pd.Timestamp.min.tz_localize('UTC')):
                reason = 'PATTERN_OVERLAPS_PREVIOUS_TRADE'
            elif broker.is_halted or not broker.circuit_breaker.is_trading_allowed(decision.to_pydatetime()):
                reason = 'RISK_LOCKED'
            if reason:
                rejections.append(dict(time=decision, symbol=symbol, reason=reason))
                continue
            # Size from known close, with a small gap allowance. Broker rechecks
            # actual opening price/equity/risk/margin; invalid gaps are rejected.
            risk = cfg['risk_per_trade'] * broker.circuit_breaker.risk_multiplier
            price = signal.price
            allowance = price * (broker.slippage_pct + .001)
            quantity = min(broker.equity * risk / (abs(price - signal.stop) + allowance),
                           broker.equity * cfg['position_notional_fraction'] / (price + allowance)) * .999
            request = OrderRequest(symbol, signal.direction, price, signal.stop, decision.to_pydatetime(),
                                   take_profit_price=signal.target, base_risk_percent=cfg['risk_per_trade'],
                                   requested_quantity=float(quantity), leverage=1.,
                                   metadata={'first_pattern_bar': str(signal.first_bar)})
            record = broker.submit_order(request)
            if record.status == OrderStatus.REJECTED:
                rejections.append(dict(time=decision, symbol=symbol, reason=';'.join(record.rejection_reasons)))
        if local.hour == 0 and local.minute == 0:
            print(f'{local.date()}: {len(broker.trade_history)} closed, equity={broker.equity:.2f}', flush=True)
    broker.finalize(timestamp=(index[-1] + one_minute).to_pydatetime(), force_close=True)
    broker.verify_accounting_invariants()
    trades = [asdict(t) for t in broker.trade_history]
    net = sum(t['net_pnl'] for t in trades)
    assert math.isclose(broker.wallet_balance - cfg['initial_equity'], net, abs_tol=1e-7)
    curve = np.array([cfg['initial_equity'], *(e['equity'] for e in equity), broker.equity])
    winners = sum(t['net_pnl'] for t in trades if t['net_pnl'] > 0)
    losers = -sum(t['net_pnl'] for t in trades if t['net_pnl'] < 0)
    entry_slippage = sum(r.slippage_usd for r in broker.order_history if r.status == OrderStatus.FILLED)
    exit_slippage = sum(t.quantity * abs(t.exit_price - t.exit_price /
                         (1 - broker.slippage_pct if t.direction.value == 'LONG' else 1 + broker.slippage_pct))
                        for t in broker.trade_history)
    summary = dict(initial_equity=cfg['initial_equity'], final_equity=broker.equity,
                   net_pnl=net, gross_price_pnl=sum(t['gross_price_pnl'] for t in trades),
                   fees=sum(t['entry_fee'] + t['exit_fee'] for t in trades),
                   funding=sum(t['funding_cashflow'] for t in trades),
                   slippage_embedded_in_price_pnl=entry_slippage + exit_slippage,
                   completed_trades=len(trades), peak_positions=peak,
                   max_drawdown_pct=float(((1 - curve / np.maximum.accumulate(curve)) * 100).max()),
                   win_rate_pct=100 * sum(t['net_pnl'] > 0 for t in trades) / len(trades) if trades else 0.,
                   profit_factor=winners / losers if losers else None,
                   ambiguous_stop_target_bars=ambiguous,
                   circuit_breaker_locks=broker.circuit_breaker.lock_count,
                   raw_signals=sum(len(c) for c in candidates.values()),
                   rejection_counts=dict(Counter(r['reason'] for r in rejections)),
                   broker_rejection_counts=dict(Counter(reason.split(':', 1)[0] for r in broker.order_history
                                                        if r.status == OrderStatus.REJECTED for reason in r.rejection_reasons)))
    return dict(summary=summary, trades=trades, equity=equity, rejections=rejections,
                orders=[asdict(r) for r in broker.order_history],
                funding_events=[asdict(f) for f in broker.funding_history],
                funding_sources=[dict(symbol=s, settlement_time=t, source_time=r.funding_source_time,
                                      funding_rate=float(r.funding_rate))
                                 for s in symbols for t, r in funding[s].iterrows()],
                sample_targets=sample_report(trades, cfg['start'], cfg['end'], cfg['weekly_target'], cfg['monthly_target']))


def execute(data_dir, config_path, output, cache_dir):
    """Explicit CLI run with immutable inputs and content-addressed artifact reuse."""
    from scripts import backtest_lab as lab
    data, output, cache, config_path = map(lab.io_path, (data_dir, output, cache_dir, config_path))
    if output.exists():
        raise ValueError('output already exists; choose a new directory')
    protected = [data, *(lab.io_path(ROOT / p) for p in ('src', 'scripts', 'config'))]
    for target in (output, cache):
        if any(target == p or target.is_relative_to(p) or p.is_relative_to(target) for p in protected):
            raise ValueError('output/cache must be outside source/config/input data')
    if output == cache or output.is_relative_to(cache) or cache.is_relative_to(output):
        raise ValueError('output and cache must be separate')
    cfg = load_settings(yaml.safe_load(config_path.read_text(encoding='utf-8')))
    files = []
    for symbol in cfg['symbols']:
        for month in pd.period_range(cfg['start'], cfg['end'], freq='M'):
            for name in (f'klines_{symbol}-1m-{month}.zip', f'klines_{symbol}-15m-{month}.zip',
                         f'fundingRate_{symbol}-fundingRate-{month}.zip'):
                files += [data / name, data / (name + '.CHECKSUM')]
    def identity():
        return dict(schema='crypto-orb-portfolio-v2-causal-session-grid', code=lab.code_identity(), runtime=lab.runtime_identity(),
                    data={p.name: lab.file_hash(p) for p in files}, config=cfg,
                    config_sha256=lab.file_hash(config_path))
    before = json.loads(json.dumps(identity(), default=str))
    run_id = lab.digest(before)
    cache_file = cache / f'{run_id}.json'
    result, cached = None, False
    if cache_file.is_file():
        try:
            entry = json.loads(cache_file.read_text(encoding='utf-8'))
            if entry.get('identity') == before and entry.get('sha256') == lab.digest(entry.get('result')):
                result, cached = entry['result'], True
        except (OSError, ValueError, TypeError, AttributeError):
            pass
    if result is None:
        frames, funding, audits = load_archive(data, cfg)
        if any(a['status'] != 'PASS' for a in audits.values()):
            output.mkdir(parents=True)
            lab.write_json(output / 'data_audit.json', audits)
            raise ValueError('SOURCE_CONFLICT: 1m/15m archives disagree; no PnL computed (see data_audit.json)')
        result = replay(frames, funding, audits, cfg) | {'data_audit': audits}
        result = json.loads(json.dumps(result, default=str, allow_nan=False))
    if lab.digest(before) != lab.digest(identity()):
        raise ValueError('inputs changed during replay; no results published')
    cache.mkdir(parents=True, exist_ok=True)
    if not cached:
        import tempfile
        with tempfile.NamedTemporaryFile(dir=cache, suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
        try:
            lab.write_json(temporary, dict(identity=before, result=result, sha256=lab.digest(result)))
            temporary.replace(cache_file)
        finally:
            temporary.unlink(missing_ok=True)
    output.mkdir(parents=True)
    lab.write_json(output / 'result.json', dict(label='RETROSPECTIVE_RESEARCH', evidence='AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED',
                                              identity=before, run_id=run_id, cached=cached, **result))
    for key in ('trades', 'equity', 'rejections', 'orders', 'funding_events', 'funding_sources'):
        pd.DataFrame(result[key]).to_csv(output / f'{key}.csv', index=False, encoding='utf-8-sig')
    lab.write_json(output / 'data_audit.json', result['data_audit'])
    text = ['# Crypto ORB + FVG portfolio', '', 'RETROSPECTIVE_RESEARCH; paper only.', '',
            '```json', json.dumps(result['summary'], indent=2), '```', '',
            '| Window | Completed | Target | Status |', '|---|---:|---:|---|']
    for row in result['sample_targets']['weeks'] + result['sample_targets']['months']:
        text.append(f"| {row['start']} to {row['end']} | {row['completed_trades']} | {row['target']} | {row['status']} |")
    (output / 'report.md').write_text('\n'.join(text) + '\n', encoding='utf-8')
    print(json.dumps(dict(run_id=run_id, cached=cached, **result['summary']), indent=2), flush=True)
    return 0
