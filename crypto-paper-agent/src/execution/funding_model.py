"""Predetermined PAPER funding, deliberately separate from exchange observations."""
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import re


@dataclass(frozen=True)
class FixedFundingModel:
    version: str
    effective_at: datetime
    rate: float = 0.0001

    @classmethod
    def from_config(cls, config):
        if 'paper_funding_model' not in config:
            return None
        data = config['paper_funding_model']
        required = {'kind', 'version', 'rate', 'effective_at_utc',
                    'settlement_hours_utc', 'price_proxy', 'symbols'}
        if type(data) is not dict or set(data) != required:
            raise ValueError('incomplete fixed simulated funding model')
        if data['kind'] != 'FIXED_SIMULATED' or data['price_proxy'] != 'CANDLE_OPEN':
            raise ValueError('unsupported fixed simulated funding kind/price proxy')
        if type(data['version']) is not str or not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', data['version']):
            raise ValueError('invalid fixed funding version')
        if (type(data['rate']) not in (int, float) or not math.isfinite(data['rate'])
                or data['rate'] != 0.0001):
            raise ValueError('fixed funding rate must equal approved positive 0.0001')
        if (type(data['settlement_hours_utc']) is not list
                or any(type(h) is not int for h in data['settlement_hours_utc'])
                or data['settlement_hours_utc'] != [0, 8, 16]):
            raise ValueError('fixed funding hours must be [0, 8, 16] UTC')
        if data['symbols'] != ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']:
            raise ValueError('fixed funding must cover all three registered symbols')
        if type(data['effective_at_utc']) is not str:
            raise ValueError('fixed funding effective time must be UTC ISO time')
        effective = datetime.fromisoformat(data['effective_at_utc'])
        if effective.tzinfo is None or effective.utcoffset().total_seconds() != 0:
            raise ValueError('fixed funding effective time must be aware UTC')
        return cls(data['version'], effective, float(data['rate']))

    def rate_at(self, symbol, timestamp):
        if (timestamp.tzinfo is None or timestamp.utcoffset().total_seconds() != 0
                or timestamp.hour not in (0, 8, 16) or timestamp.minute
                or timestamp.second or timestamp.microsecond):
            raise ValueError('not a fixed funding UTC settlement instant')
        if symbol not in ('BTCUSDT', 'ETHUSDT', 'SOLUSDT'):
            raise ValueError('fixed funding symbol not registered')
        if timestamp < self.effective_at:
            raise ValueError('fixed funding is not effective at this settlement')
        return self.rate

    def describe(self):
        return {'kind': 'FIXED_SIMULATED', 'version': self.version, 'rate': self.rate,
                'effective_at_utc': self.effective_at.isoformat(),
                'settlement_hours_utc': [0, 8, 16], 'price_proxy': 'CANDLE_OPEN',
                'symbols': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'],
                'display_timezone': 'UTC+07:00', 'settlement_hours_local': [7, 15, 23]}

    def event_id(self, position_id, symbol, timestamp):
        identity = [self.describe(), position_id, symbol, timestamp.isoformat()]
        return 'FIXED_' + sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:32]


def settlement_terms(config, candle, symbol, opened, ensure_utc):
    """Validate before mutation; fixed configuration is not public provenance."""
    model = FixedFundingModel.from_config(config)
    if model is not None:
        return model.rate_at(symbol, opened), opened
    raw_rate = candle.get('funding_rate')
    if raw_rate is None or type(raw_rate) is bool or not isinstance(raw_rate, (int, float)):
        raise ValueError(f'Missing or invalid funding rate at settlement boundary {opened.isoformat()}: {raw_rate!r}')
    rate = float(raw_rate)
    if not math.isfinite(rate):
        raise ValueError(f'Non-finite funding rate at settlement boundary {opened.isoformat()}')
    if 'funding_readiness' not in candle:
        raise ValueError(f'Missing funding_readiness at settlement boundary {opened.isoformat()} for {symbol}')
    readiness = candle['funding_readiness']
    if type(readiness) is not bool:
        raise TypeError(f'Invalid funding_readiness type: expected bool, got {type(readiness).__name__}')
    if not readiness:
        raise ValueError(f'Funding data marked not ready at settlement boundary {opened.isoformat()} for {symbol}')
    source = candle.get('funding_time')
    if source is None:
        source = candle.get('funding_timestamp') or candle.get('funding_source_time')
    if source is None:
        raise ValueError(f'Missing funding source timestamp at settlement boundary {opened.isoformat()} for {symbol}')
    if type(source) is bool or not isinstance(source, (datetime, str, int, float)):
        raise TypeError(f'Invalid funding timestamp type: {type(source).__name__}')
    stamp = ensure_utc(source)
    if stamp > opened:
        raise ValueError(f'Funding source time {stamp.isoformat()} is in future relative to open_time {opened.isoformat()} (lookahead bias)')
    from datetime import timedelta
    if stamp < opened - timedelta(hours=24):
        raise ValueError(f'Funding source time {stamp.isoformat()} is excessively stale (>24h before {opened.isoformat()})')
    if stamp != opened:
        raise ValueError(f'FUNDING_SOURCE_EVENT_MISMATCH: source time must match settlement boundary {opened.isoformat()}; received {stamp.isoformat()} (observation is not a settlement event)')
    return rate, stamp
