"""Exercise real admission guards without training or substituting a PPO result."""
import hashlib
import json
import sys
from types import ModuleType, SimpleNamespace

import pandas as pd
import pytest

pytest.importorskip('gymnasium', reason='optional Gymnasium environment')
from src.research.rl_env import RiskAwareTradingEnv, train_ppo, evaluate_saved_ppo
from src.research.synthetic import smc_config
from src.logging.trade_logger import snapshot_run_config, compute_config_hash
from src.features.news_calendar import NewsCalendarFilter

T = pd.Timestamp('2024-01-01', tz='UTC')


def frame(minutes):
    return pd.DataFrame(dict(open=100., high=101., low=99., close=100., volume=10.),
                        index=pd.DatetimeIndex([T + pd.Timedelta(minutes=n) for n in minutes]))


@pytest.fixture
def no_training(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Invalid/overlapping input reached training or model loading')
    sb3 = ModuleType('stable_baselines3')
    sb3.PPO = SimpleNamespace(load=forbidden)
    checker = ModuleType('stable_baselines3.common.env_checker')
    checker.check_env = forbidden
    torch = ModuleType('torch')
    torch.set_num_threads = lambda *_: None
    monkeypatch.setitem(sys.modules, 'stable_baselines3', sb3)
    monkeypatch.setitem(sys.modules, 'stable_baselines3.common.env_checker', checker)
    monkeypatch.setitem(sys.modules, 'torch', torch)


def test_episode_rejects_overlapping_candles():
    with pytest.raises(ValueError, match='overlap'):
        RiskAwareTradingEnv(frame([0, 5]), smc_config(), None, timeframe='15m')


@pytest.mark.parametrize('parts', [([0, 15], [20, 35], [60, 75]),
                                  ([0, 15], [30, 45], [50, 65]),
                                  ([0, 5], [30, 45], [60, 75])])
def test_training_rejects_candle_interval_leakage_before_model_work(tmp_path, no_training, parts):
    with pytest.raises(ValueError, match='overlap'):
        train_ppo(*(frame(p) for p in parts), smc_config(), tmp_path,
                  timeframe='15m', total_timesteps=64)
    assert not list(tmp_path.iterdir())


def saved_metadata(path, config):
    path.mkdir()
    frozen = snapshot_run_config(config, NewsCalendarFilter(config))
    payload = dict(config_hash=compute_config_hash(frozen), report=dict(
        datasets=dict(train=dict(timeframe='15m', end=(T + pd.Timedelta(minutes=15)).isoformat()),
                      validation=dict(end=(T + pd.Timedelta(minutes=45)).isoformat())),
        scaler=dict(mean=[0.] * 11, scale=[1.] * 11)))
    (path / 'ppo.report.json').write_text(json.dumps(payload), encoding='utf-8')
    (path / 'ppo_model.zip').write_bytes(b'not a model: admission must reject before loading')
    manifest = dict(files={name: hashlib.sha256((path / name).read_bytes()).hexdigest()
                           for name in ('ppo.report.json', 'ppo_model.zip')})
    (path / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')


@pytest.mark.parametrize('minutes', [[45, 60], [50, 65], [60, 65]])
def test_evaluation_rejects_validation_overlap_and_overlapping_bars(tmp_path, no_training, minutes):
    config = smc_config()
    saved_metadata(tmp_path / 'model', config)
    with pytest.raises(ValueError, match='overlap'):
        evaluate_saved_ppo(tmp_path / 'model', frame(minutes), config,
                           tmp_path / 'evaluation', timeframe='15m')
    assert not (tmp_path / 'evaluation').exists()


def test_exact_close_to_next_open_boundaries_are_admitted(tmp_path, no_training):
    with pytest.raises(AssertionError, match='reached training'):
        train_ppo(frame([0, 15]), frame([30, 45]), frame([60, 75]), smc_config(),
                  tmp_path / 'train', timeframe='15m', total_timesteps=64)
    config = smc_config()
    saved_metadata(tmp_path / 'model', config)
    with pytest.raises(AssertionError, match='reached training'):
        evaluate_saved_ppo(tmp_path / 'model', frame([60, 75]), config,
                           tmp_path / 'evaluation', timeframe='15m')
