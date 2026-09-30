"""Closed, versioned PAPER recipe catalog. Registration is not economic validation."""
from copy import deepcopy
from datetime import timezone
from hashlib import sha256
import json
from pathlib import Path

from src.logging.trade_logger import canonicalize_config
from src.strategies.trend_following import TrendFollowingStrategy
from src.strategies.breakout_retest import BreakoutRetestStrategy


CATALOG = {'trend_following': TrendFollowingStrategy,
           'breakout_retest': BreakoutRetestStrategy}


def make_strategy(name, config, symbol):
    if name not in CATALOG:
        raise ValueError('recipe is not in the fixed paper catalog')
    return CATALOG[name](deepcopy(config), symbol=symbol)


def recipe_snapshot(name, config, available_at):
    if name not in CATALOG:
        raise ValueError('recipe is not in the fixed paper catalog')
    if available_at.tzinfo is None or available_at.utcoffset().total_seconds() != 0:
        raise ValueError('recipe availability must be UTC')
    root = Path(__file__).resolve().parents[1]
    sources = [root / 'strategies' / f'{name}.py', root / 'features' / 'indicators.py']
    payload = {'strategy_id': name, 'recipe_version': 'paper-recipe-v1',
               'formula_version': 'pandas-fallback-v1',
               'available_at_utc': available_at.astimezone(timezone.utc).isoformat(),
               'config': canonicalize_config(deepcopy(config)),
               'source_sha256': {p.name: sha256(p.read_bytes()).hexdigest() for p in sources}}
    payload['identity'] = sha256(json.dumps(payload, sort_keys=True, allow_nan=False,
                                          separators=(',', ':')).encode()).hexdigest()
    return payload
