"""Frozen weekly, price-level ETH-on-BTC Engle–Granger research model.

Input indices label 4h OPENS. No observation is admitted until its close time.
This module neither knows funding rates nor submits exchange orders.
"""
from dataclasses import asdict, dataclass
import hashlib
import json
import math
import warnings

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import adfuller, coint

SYMBOLS = ('ETHUSDT', 'BTCUSDT')
FOUR_HOURS = pd.Timedelta(hours=4)


@dataclass(frozen=True)
class WeeklyModel:
    week: str
    alpha: float
    beta: float
    mu: float
    sigma: float
    phi: float
    half_life: float
    model_id: str

    def z(self, eth, btc):
        return (float(eth) - self.alpha - self.beta * float(btc) - self.mu) / self.sigma


def utc(value):
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        raise ValueError('timestamps must be timezone-aware')
    return stamp.tz_convert('UTC')


def crossing(before, now):
    if not (math.isfinite(before) and math.isfinite(now)) or abs(before) >= 2:
        return 0
    if 2 <= now < 4:
        return -1
    if -4 < now <= -2:
        return 1
    return 0


def simple_atr(frame):
    if len(frame) < 15:
        raise ValueError('ATR needs 15 closed bars')
    previous = frame['close'].shift()
    tr = pd.concat([frame['high']-frame['low'], (frame['high']-previous).abs(),
                    (frame['low']-previous).abs()], axis=1).max(axis=1)
    value = float(tr.tail(14).mean())
    if not math.isfinite(value) or value <= 0:
        raise ValueError('ATR must be finite positive')
    return value


def fit_week(closes, when):
    """Return diagnostics and, where estimable, a frozen model (even if rejected)."""
    when = utc(when)
    if when.weekday() != 0 or when != when.normalize():
        raise ValueError('formation must be Monday 00:00 UTC')
    expected = pd.date_range(when-pd.Timedelta(days=90), when-FOUR_HOURS, freq='4h')
    frame = closes.loc[(closes.index >= expected[0]) & (closes.index < when), list(SYMBOLS)]
    result = dict(week=when.isoformat(), rows=len(frame), eligible=False, reason='',
                  model=None, adf_pvalues={}, cointegration_pvalue=None)
    if not frame.index.as_unit('ns').equals(expected.as_unit('ns')):
        result['reason'] = 'FORMATION_GAP'
        return result
    values = frame.to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values <= 0).any() or (np.ptp(values, axis=0)==0).any():
        result['reason'] = 'FORMATION_INVALID'
        return result
    eth, btc = values.T
    options = dict(regression='c', maxlag=12, autolag='AIC')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            # statsmodels 0.15 announces a future return-container change; this
            # does not make a statistically valid window invalid. Keep genuine
            # numerical/collinearity warnings fail-closed.
            warnings.filterwarnings('ignore', message='adfuller currently returns a plain tuple.*', category=FutureWarning)
            pvalues = {f'{s}_{kind}': float(adfuller(v, **options)[1])
                       for s, series in zip(SYMBOLS, [eth, btc])
                       for kind, v in [('level',series),('difference',np.diff(series))]}
            p = float(coint(eth, btc, trend='c', maxlag=12, autolag='aic')[1])
        alpha, beta = np.linalg.lstsq(np.column_stack([np.ones(len(btc)), btc]), eth, rcond=None)[0]
        residual = eth-alpha-beta*btc
        intercept, phi = np.linalg.lstsq(np.column_stack([np.ones(len(residual)-1), residual[:-1]]),
                                         residual[1:], rcond=None)[0]
        sigma = float(residual.std(ddof=1))
        half = -math.log(2)/math.log(phi) if 0 < phi < 1 else float('nan')
        result['adf_pvalues'], result['cointegration_pvalue'] = pvalues, p
        finite = np.isfinite([alpha,beta,sigma,phi,half]).all() and sigma > 0
        if not finite:
            result['reason'] = 'MODEL_INVALID'
            return result
        identity = hashlib.sha256(values.astype('<f8').tobytes() + when.isoformat().encode()).hexdigest()
        model = WeeklyModel(when.isoformat(),float(alpha),float(beta),float(residual.mean()),
                            sigma,float(phi),float(half),identity)
        result['model'] = model
        i1 = all(pvalues[f'{s}_level'] >= .05 and pvalues[f'{s}_difference'] < .05 for s in SYMBOLS)
        result['eligible'] = bool(i1 and p < .01 and beta > 0 and 3 <= half <= 42)
        result['reason'] = 'ELIGIBLE' if result['eligible'] else 'STATISTICAL_GATE'
    except (ValueError, np.linalg.LinAlgError, Warning, FloatingPointError) as error:
        result['reason'] = 'MODEL_INVALID'
        result['error'] = type(error).__name__
    return result


def model_payload(diagnostic):
    result = dict(diagnostic)
    result['model'] = asdict(result['model']) if result.get('model') else None
    return result
