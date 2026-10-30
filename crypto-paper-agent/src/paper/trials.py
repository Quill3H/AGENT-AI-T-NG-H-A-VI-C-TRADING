"""Explicit imaginary capital allocations; a restart is never a new trial."""
from copy import deepcopy
from datetime import datetime
import math

from src.paper.compact_store import digest


def utc(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset().total_seconds() != 0:
        raise ValueError('trial timestamp must be UTC')
    return value


def finite(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('trial equity must be finite numeric')
    return float(value)


def checked_recipe(recipe, timestamp):
    if (type(recipe) is not dict or not recipe.get('identity')
            or recipe.get('strategy_id') not in ('trend_following', 'breakout_retest')
            or utc(recipe.get('available_at_utc')) > timestamp):
        raise ValueError('recipe is unavailable at the trial allocation time')
    return deepcopy(recipe)


class TrialBook:
    def __init__(self, initial_recipe, available_at):
        stamp = utc(available_at)
        recipe = checked_recipe(initial_recipe, stamp)
        self.trials = [self._trial(recipe, stamp, 1)]
        self.allocations = {}

    @staticmethod
    def _trial(recipe, timestamp, number):
        return {'trial_id': f'trial-{number:04d}', 'recipe': recipe,
                'started_at_utc': timestamp.isoformat(), 'initial_capital_usd': 10000.0,
                'current_equity_usd': 10000.0, 'final_equity_usd': None,
                'status': 'ACTIVE', 'target_reached': False,
                'target_at_utc': None, 'failed_at_utc': None, 'last_observed_at_utc': timestamp.isoformat()}

    @property
    def current(self):
        return self.trials[-1]

    @property
    def total_capital_injected(self):
        return 10000.0 * len(self.trials)

    def observe(self, equity, timestamp):
        value, stamp = finite(equity), utc(timestamp)
        trial = self.current
        if stamp < utc(trial['last_observed_at_utc']):
            raise ValueError('trial observation time reversal')
        trial['current_equity_usd'] = value
        trial['last_observed_at_utc'] = stamp.isoformat()
        events = []
        if trial['status'] == 'FAILED':
            trial['final_equity_usd'] = value
            return events
        if value < 5000:
            trial.update(status='FAILED', failed_at_utc=stamp.isoformat(), final_equity_usd=value)
            events.append(self._event('TRIAL_FAILED', stamp, value))
        elif value >= 15000 and not trial['target_reached']:
            trial.update(target_reached=True, target_at_utc=stamp.isoformat())
            events.append(self._event('TRIAL_TARGET_REACHED', stamp, value))
        return events

    def _event(self, kind, stamp, value):
        return {'key': f'{self.current["trial_id"]}:{kind}', 'kind': kind,
                'trial_id': self.current['trial_id'], 'equity_usd': value,
                'simulated_at_utc': stamp.isoformat()}

    def promote(self, recipe, timestamp, reconciled, verdict):
        stamp = utc(timestamp)
        checked = checked_recipe(recipe, stamp)
        if (reconciled is not True or type(verdict) is not dict or verdict.get('eligible') is not True
                or not verdict.get('identity') or verdict.get('selected_recipe_identity') != checked['identity']
                or utc(verdict.get('cutoff_utc')) > stamp):
            raise ValueError('promotion requires reconciled exposure and a causal eligible verdict')
        key = verdict['identity']
        if key in self.allocations:
            prior = self.allocations[key]
            if prior['recipe_identity'] != checked['identity'] or prior['simulated_at_utc'] != stamp.isoformat():
                raise ValueError('promotion allocation identity conflict')
            return deepcopy(prior)
        if self.current['status'] != 'FAILED' or stamp < utc(self.current['last_observed_at_utc']):
            raise ValueError('only a reconciled failed trial can receive replacement capital')
        old = self.current['trial_id']
        trial = self._trial(checked, stamp, len(self.trials) + 1)
        event = {'key': f'capital:{key}', 'kind': 'PAPER_CAPITAL_ALLOCATION',
                 'previous_trial_id': old, 'trial_id': trial['trial_id'], 'capital_usd': 10000.0,
                 'recipe_identity': checked['identity'], 'verdict_identity': key,
                 'simulated_at_utc': stamp.isoformat()}
        self.trials.append(trial)
        self.allocations[key] = event
        return deepcopy(event)

    def capture(self):
        data = {'version': 1, 'trials': deepcopy(self.trials), 'allocations': deepcopy(self.allocations),
                'total_capital_injected_usd': self.total_capital_injected}
        return {**data, 'checksum': digest(data)}

    @classmethod
    def restore(cls, payload):
        if type(payload) is not dict or set(payload) != {'version', 'trials', 'allocations', 'total_capital_injected_usd', 'checksum'}:
            raise ValueError('incomplete trial book')
        data = {k: v for k, v in payload.items() if k != 'checksum'}
        if type(data['version']) is not int or data['version'] != 1 or digest(data) != payload['checksum'] or not data['trials']:
            raise ValueError('trial book checksum/version mismatch')
        if (finite(data['total_capital_injected_usd']) != 10000 * len(data['trials'])
                or len(data['allocations']) != len(data['trials']) - 1):
            raise ValueError('trial allocation count mismatch')
        for index, trial in enumerate(data['trials'], 1):
            stamp = utc(trial['started_at_utc'])
            observed = utc(trial['last_observed_at_utc'])
            checked_recipe(trial['recipe'], stamp)
            if (trial['trial_id'] != f'trial-{index:04d}' or trial['initial_capital_usd'] != 10000
                    or trial['status'] not in ('ACTIVE', 'FAILED')
                    or type(trial['target_reached']) is not bool or observed < stamp):
                raise ValueError('invalid trial lifecycle')
            finite(trial['current_equity_usd'])
            if trial['target_reached']:
                if not stamp <= utc(trial['target_at_utc']) <= observed:
                    raise ValueError('invalid target availability')
            elif trial['target_at_utc'] is not None:
                raise ValueError('target timestamp without target milestone')
            if trial['status'] == 'FAILED':
                finite(trial['final_equity_usd'])
                if not stamp <= utc(trial['failed_at_utc']) <= observed:
                    raise ValueError('invalid trial failure availability')
            elif (trial['failed_at_utc'] is not None or trial['final_equity_usd'] is not None
                  or trial['current_equity_usd'] < 5000):
                raise ValueError('active trial contradicts failure threshold/history')
            if index < len(data['trials']) and trial['status'] != 'FAILED':
                raise ValueError('previous trial was not reconciled as failed')
            if index > 1:
                previous = data['trials'][index - 2]
                if stamp < utc(previous['last_observed_at_utc']):
                    raise ValueError('trial allocation precedes prior reconciliation')
                allocations = [(key, a) for key, a in data['allocations'].items() if a.get('trial_id') == trial['trial_id']]
                if len(allocations) != 1:
                    raise ValueError('missing/duplicate trial allocation')
                key, allocation = allocations[0]
                if (allocation.get('key') != 'capital:' + key or allocation.get('kind') != 'PAPER_CAPITAL_ALLOCATION'
                        or allocation.get('previous_trial_id') != previous['trial_id']
                        or finite(allocation.get('capital_usd')) != 10000
                        or allocation.get('recipe_identity') != trial['recipe']['identity']
                        or allocation.get('verdict_identity') != key
                        or utc(allocation.get('simulated_at_utc')) != stamp):
                    raise ValueError('trial allocation provenance mismatch')
        result = cls(data['trials'][0]['recipe'], utc(data['trials'][0]['started_at_utc']))
        result.trials, result.allocations = deepcopy(data['trials']), deepcopy(data['allocations'])
        return result
