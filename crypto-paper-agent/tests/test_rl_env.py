import numpy as np, pandas as pd
from src.research.rl_env import ObservationScaler, RiskAwareTradingEnv
from src.research.synthetic import smc_config


def data(n=120):
    idx = pd.date_range("2024-01-01", periods=n, freq="min", tz="UTC")
    close = 100 + np.sin(np.arange(n) / 5)
    return pd.DataFrame(
        {
            "open": close,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": 10,
        },
        index=idx,
    )


def test_gym_reset_step_checker_contract():
    from gymnasium.utils.env_checker import check_env

    f = data()
    cfg = smc_config()
    scaler = ObservationScaler.fit_train(f)
    env = RiskAwareTradingEnv(f, cfg, scaler)
    check_env(env, warn=True)
    obs, info = env.reset(seed=7)
    assert env.observation_space.contains(obs)
    obs, r, t, tr, info = env.step(0)
    assert env.observation_space.contains(obs)


def test_scaler_train_only_and_invalid_action_is_penalized():
    f = data()
    cfg = smc_config()
    scaler = ObservationScaler.fit_train(f.iloc[:80])
    env = RiskAwareTradingEnv(f.iloc[80:], cfg, scaler)
    env.reset(seed=1)
    _, reward, _, _, info = env.step(99)
    assert info["risk_violation"] == 1 and reward <= -1


def test_actions_cannot_bypass_risk_and_realized_reward_matches_ledger():
    cfg = smc_config()
    cfg["rl"] = {"leverage": 10.0}
    f = data(10)
    env = RiskAwareTradingEnv(f, cfg, ObservationScaler.fit_train(f))
    env.reset(seed=2)
    _, reward, _, _, info = env.step(1)
    assert info["risk_violation"] == 1
    assert not env.broker.positions
    assert any(
        "LEVERAGE" in reason or "BUFFER" in reason
        for reason in env.broker.order_history[-1].rejection_reasons
    )
    cfg["rl"] = {"leverage": 2.0}
    env = RiskAwareTradingEnv(f, cfg, ObservationScaler.fit_train(f))
    env.reset(seed=2)
    infos = []
    for i in range(9):
        _, reward, _, _, info = env.step(1 if i == 0 else 3 if i == 2 else 0)
        infos.append(info)
    assert sum(i["realized_net_pnl"] for i in infos) == __import__("pytest").approx(
        sum(t.net_pnl for t in env.broker.trade_history)
    )
    assert env.broker.trade_history


def test_real_ppo_train_save_load_and_final_holdout(tmp_path):
    from src.research.rl_env import train_ppo

    f = data(320)
    report = train_ppo(
        f.iloc[:160],
        f.iloc[160:240],
        f.iloc[240:],
        smc_config(),
        tmp_path,
        total_timesteps=128,
    )
    from src.research.rl_env import evaluate_saved_ppo

    evaluated = evaluate_saved_ppo(
        tmp_path, f.iloc[240:], smc_config(), tmp_path / "eval"
    )
    assert evaluated["evaluation"] == report["final_holdout"]
    import pytest

    with pytest.raises(ValueError, match="after the training"):
        evaluate_saved_ppo(tmp_path, f.iloc[:80], smc_config(), tmp_path / "bad")
    assert report["save_load_equal"]
    assert report["actual_timesteps"] == 128
    assert report["no_trade"]["total_net_pnl"] == 0
    assert (tmp_path / "ppo_model.zip").is_file()
    assert (tmp_path / "research.sqlite").is_file()
    assert report["datasets"]["train"]["end"] < report["datasets"]["holdout"]["start"]


def test_future_perturbation_preserves_observations_and_actions():
    f = data(60)
    changed = f.copy()
    changed.loc[f.index[30] :, ["open", "high", "low", "close"]] *= 2
    scaler = ObservationScaler.fit_train(f.iloc[:20])
    out = []
    for frame in (f, changed):
        env = RiskAwareTradingEnv(frame, smc_config(), scaler)
        obs, _ = env.reset(seed=4)
        trace = [obs]
        for i in range(29):
            obs, r, _, _, info = env.step(1 if i == 0 else 0)
            trace.append(obs)
        out.append(trace)
    np.testing.assert_array_equal(out[0], out[1])
