"""Regressions for the 2026-09-23 review's chronology and input-fidelity findings."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest
import yaml

from src.data_layer.fetcher import _candles_to_dataframe, merge_ohlcv_with_oi_and_funding
from src.execution.paper_broker import PaperBroker
from src.risk.circuit_breakers import CircuitBreakerState
from src.features.cvd import calculate_cvd
from src.research.rl_env import RiskAwareTradingEnv, evaluate_saved_ppo, market_vectors, train_ppo
from src.research.synthetic import smc_config
from src.execution.order_models import OrderDirection, OrderRequest, OrderStatus


T = datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc)


def batch_config():
    with (Path(__file__).resolve().parents[1] / "config" / "default_config.yaml").open(encoding="utf-8") as source:
        config = yaml.safe_load(source)
    config["fees"].update(taker_pct=0.0, slippage_pct=0.0)
    config["leverage_brackets"]["ETHUSDT"] = deepcopy(config["leverage_brackets"]["BTCUSDT"])
    return config


def candle(t, symbol="BTCUSDT", low=99.5, timeframe="1m"):
    return {
        "open_time": t, "symbol": symbol, "timeframe": timeframe,
        "open": 100.0, "high": 100.5, "low": low, "close": 100.0,
    }


def frame(index):
    return pd.DataFrame(
        {"open": 100.0, "high": 101.0, "low": 99.0,
         "close": 100.0, "volume": 10.0},
        index=pd.DatetimeIndex(index, tz="UTC"),
    )


def order(symbol, signal_time=T):
    return OrderRequest(
        symbol=symbol, direction=OrderDirection.LONG, signal_price=100.0,
        stop_loss_price=95.0, signal_time=signal_time, leverage=2.0,
        base_risk_percent=0.02, requested_quantity=1.0,
    )


def broker_clock_state(broker):
    return deepcopy({
        "current_time": broker.current_time,
        "batch_open": broker.current_batch_open_time,
        "batch_symbols": broker.symbols_in_current_batch,
        "last_open": broker.last_candle_open_time_per_symbol,
        "marks": broker.last_mark_prices,
        "wallet": broker.wallet_balance,
        "orders": len(broker.order_history),
        "trades": len(broker.trade_history),
        "snapshots": len(broker.account_snapshots),
        "breaker": vars(broker.circuit_breaker),
    })


@pytest.mark.parametrize("first,second", [("BTCUSDT", "ETHUSDT"), ("ETHUSDT", "BTCUSDT")])
def test_same_open_batch_keeps_exit_at_close_and_reconciles(first, second):
    """A future intrabar exit must not preclude another symbol's same-open admission."""
    broker = PaperBroker(batch_config())
    broker.process_batch([candle(T, first), candle(T, second)])
    broker.submit_order(order(first))
    broker.submit_order(order(second))
    broker.process_batch([
        candle(T + timedelta(minutes=1), first),
        candle(T + timedelta(minutes=1), second),
    ])
    assert set(broker.positions) == {first, second}
    broker.process_batch([
        candle(T + timedelta(minutes=2), first, low=94.0),
        candle(T + timedelta(minutes=2), second),
    ])
    assert first not in broker.positions and second in broker.positions
    assert broker.trade_history[-1].exit_time == T + timedelta(minutes=3)
    assert broker.circuit_breaker.current_timestamp == T + timedelta(minutes=3)
    broker.verify_accounting_invariants()


def test_invalid_direct_candle_after_intrabar_exit_preserves_state():
    broker = PaperBroker({"fees": {"taker_pct": 0.0, "slippage_pct": 0.0}})
    broker.process_candle(candle(T))
    broker.submit_order(order("BTCUSDT"))
    broker.process_candle(candle(T + timedelta(minutes=1)))
    broker.process_candle(candle(T + timedelta(minutes=2), low=94.0))
    before = broker_clock_state(broker)
    with pytest.raises(ValueError, match="(?i)time|batch"):
        broker.process_candle(candle(T + timedelta(minutes=2), "ETHUSDT"))
    assert broker_clock_state(broker) == before


def test_direct_broker_rejects_overlapping_15m_candles_without_mutation():
    broker = PaperBroker({})
    broker.process_candle(candle(T, timeframe="15m"))
    before = broker_clock_state(broker)
    with pytest.raises(ValueError, match="(?i)overlap"):
        broker.process_candle(candle(T + timedelta(minutes=5), timeframe="15m"))
    assert broker_clock_state(broker) == before


def test_batch_rejects_different_close_times_atomically():
    broker = PaperBroker(batch_config())
    before = broker_clock_state(broker)
    with pytest.raises(ValueError, match="(?i)same.*close"):
        broker.process_batch([
            candle(T, "BTCUSDT", timeframe="15m"),
            candle(T, "ETHUSDT", timeframe="1m"),
        ])
    assert broker_clock_state(broker) == before


def test_batch_preserves_supplied_breaker_identity_and_state():
    config = batch_config()
    breaker = CircuitBreakerState.from_config(config)
    broker = PaperBroker(config, circuit_breaker=breaker)
    broker.process_batch([candle(T, "BTCUSDT"), candle(T, "ETHUSDT")])
    assert broker.circuit_breaker is breaker
    assert breaker.current_timestamp == T


def test_batch_input_order_does_not_change_result():
    def run(candles):
        broker = PaperBroker(batch_config())
        broker.process_batch([candle(T, "BTCUSDT"), candle(T, "ETHUSDT")])
        broker.submit_order(order("BTCUSDT"))
        broker.submit_order(order("ETHUSDT"))
        broker.process_batch([candle(T + timedelta(minutes=1), "BTCUSDT"),
                              candle(T + timedelta(minutes=1), "ETHUSDT")])
        broker.process_batch(candles)
        broker.verify_accounting_invariants()
        return broker

    btc = candle(T + timedelta(minutes=2), "BTCUSDT", low=94.0)
    eth = candle(T + timedelta(minutes=2), "ETHUSDT")
    a, b = run([btc, eth]), run([eth, btc])
    assert a.wallet_balance == b.wallet_balance
    assert [(t.symbol, t.net_pnl, t.exit_time) for t in a.trade_history] == [
        (t.symbol, t.net_pnl, t.exit_time) for t in b.trade_history
    ]
    assert set(a.positions) == set(b.positions) == {"ETHUSDT"}


def test_batch_breaker_force_close_uses_other_symbol_close_mark():
    config = batch_config()
    config["circuit_breakers"]["daily_loss_limit_pct"] = 0.00001
    broker = PaperBroker(config)
    broker.process_batch([candle(T, "BTCUSDT"), candle(T, "ETHUSDT")])
    broker.submit_order(order("BTCUSDT"))
    broker.submit_order(order("ETHUSDT"))
    broker.process_batch([candle(T + timedelta(minutes=1), "BTCUSDT"),
                          candle(T + timedelta(minutes=1), "ETHUSDT")])
    eth = candle(T + timedelta(minutes=2), "ETHUSDT")
    eth.update(high=103.0, close=102.0)
    broker.process_batch([candle(T + timedelta(minutes=2), "BTCUSDT", low=94.0), eth])
    assert broker.circuit_breaker.is_locked
    assert not broker.positions
    forced = next(t for t in broker.trade_history if t.symbol == "ETHUSDT")
    assert forced.exit_price == 102.0
    broker.verify_accounting_invariants()


def test_batch_breaker_cannot_bypass_other_symbol_touched_stop():
    config = batch_config()
    config["circuit_breakers"]["daily_loss_limit_pct"] = 0.00001
    broker = PaperBroker(config)
    broker.process_batch([candle(T, "BTCUSDT"), candle(T, "ETHUSDT")])
    broker.submit_order(order("BTCUSDT"))
    broker.submit_order(order("ETHUSDT"))
    broker.process_batch([candle(T + timedelta(minutes=1), "BTCUSDT"),
                          candle(T + timedelta(minutes=1), "ETHUSDT")])
    eth = candle(T + timedelta(minutes=2), "ETHUSDT", low=94.0)
    eth.update(high=103.0, close=102.0)
    broker.process_batch([candle(T + timedelta(minutes=2), "BTCUSDT", low=94.0), eth])
    forced = next(t for t in broker.trade_history if t.symbol == "ETHUSDT")
    assert forced.exit_price <= 95.0
    broker.verify_accounting_invariants()


def test_batch_gap_lock_uses_other_symbols_same_open_price():
    config = batch_config()
    config["circuit_breakers"]["daily_loss_limit_pct"] = 0.00001
    broker = PaperBroker(config)
    broker.process_batch([candle(T, "BTCUSDT"), candle(T, "ETHUSDT")])
    broker.submit_order(order("BTCUSDT"))
    broker.submit_order(order("ETHUSDT"))
    broker.process_batch([candle(T + timedelta(minutes=1), "BTCUSDT"),
                          candle(T + timedelta(minutes=1), "ETHUSDT")])
    btc = candle(T + timedelta(minutes=2), "BTCUSDT")
    btc.update(open=94.0, high=94.5, low=93.5, close=94.0)
    eth = candle(T + timedelta(minutes=2), "ETHUSDT")
    eth.update(open=102.0, high=102.5, low=101.5, close=102.0)
    broker.process_batch([btc, eth])
    forced = next(t for t in broker.trade_history if t.symbol == "ETHUSDT")
    assert forced.exit_price == 102.0
    broker.verify_accounting_invariants()


def test_batch_settles_both_symbols_funding_before_breaker_force_close():
    config = batch_config()
    config["circuit_breakers"]["daily_loss_limit_pct"] = 0.00001
    broker = PaperBroker(config)
    start = datetime(2024, 1, 1, 7, 58, tzinfo=timezone.utc)
    broker.process_batch([candle(start, "BTCUSDT"), candle(start, "ETHUSDT")])
    broker.submit_order(order("BTCUSDT", start))
    broker.submit_order(order("ETHUSDT", start))
    broker.process_batch([candle(start + timedelta(minutes=1), "BTCUSDT"),
                          candle(start + timedelta(minutes=1), "ETHUSDT")])
    settlement = start + timedelta(minutes=2)
    pair = [candle(settlement, symbol) for symbol in ("BTCUSDT", "ETHUSDT")]
    for bar in pair:
        bar.update(funding_rate=0.01, funding_time=settlement, funding_readiness=True)
    broker.process_batch(pair)
    assert {event.symbol for event in broker.funding_history} == {"BTCUSDT", "ETHUSDT"}
    assert broker.circuit_breaker.is_locked and not broker.positions
    assert broker.wallet_balance == pytest.approx(9998.0)
    broker.verify_accounting_invariants()


def test_rl_rejects_overlapping_candles_and_partitions_before_training(tmp_path):
    config = smc_config()
    train = frame([T, T + timedelta(minutes=15)])
    validation = frame([T + timedelta(minutes=16), T + timedelta(minutes=31)])
    holdout = frame([T + timedelta(minutes=32), T + timedelta(minutes=47)])
    with pytest.raises(ValueError, match="(?i)overlap"):
        train_ppo(train, validation, holdout, config, tmp_path, timeframe="15m", total_timesteps=64)
    assert not (tmp_path / "ppo_model.zip").exists()
    bad_episode = frame([T, T + timedelta(minutes=5)])
    with pytest.raises(ValueError, match="(?i)overlap"):
        RiskAwareTradingEnv(bad_episode, config, None, timeframe="15m")


def test_evaluate_only_rejects_frame_overlapping_saved_validation(tmp_path):
    config = smc_config()
    train = frame([T, T + timedelta(minutes=15), T + timedelta(minutes=30)])
    validation = frame([T + timedelta(minutes=45), T + timedelta(minutes=60)])
    holdout = frame([T + timedelta(minutes=75), T + timedelta(minutes=90)])
    train_ppo(train, validation, holdout, config, tmp_path / "model", timeframe="15m", total_timesteps=64)
    with pytest.raises(ValueError, match="(?i)validation.*overlap"):
        evaluate_saved_ppo(
            tmp_path / "model", frame([T + timedelta(minutes=60), T + timedelta(minutes=75)]),
            config, tmp_path / "bad_eval", timeframe="15m",
        )
    assert not (tmp_path / "bad_eval").exists()


def test_oi_source_time_and_freshness_are_preserved():
    ohlcv = frame([T, T + timedelta(minutes=15), T + timedelta(days=30)])
    oi = pd.DataFrame({"open_interest": [123.0]}, index=pd.DatetimeIndex([T]))
    merged = merge_ohlcv_with_oi_and_funding(ohlcv, oi, pd.DataFrame(), "15m", {})
    assert merged["open_interest"].iloc[0] == 123.0
    assert merged["oi_source_time"].iloc[0] == pd.Timestamp(T)
    assert bool(merged["oi_available"].iloc[0]) is True
    assert np.isnan(merged["open_interest"].iloc[-1])
    assert bool(merged["oi_available"].iloc[-1]) is False
    assert pd.isna(merged["oi_source_time"].iloc[-1])


def test_missing_taker_volume_never_looks_like_observed_cvd():
    raw = [
        [int(pd.Timestamp(T).timestamp() * 1000), 100, 101, 99, 100, 10],
        [int(pd.Timestamp(T + timedelta(minutes=1)).timestamp() * 1000), 100, 101, 99, 100, 10],
    ]
    observed = _candles_to_dataframe(raw)
    assert observed["taker_buy_base_volume"].isna().all()
    features = calculate_cvd(observed)
    assert features["cvd"].isna().all()
    assert market_vectors(features)[:, -1].tolist() == [0.0, 0.0]


def test_cvd_after_missing_delta_remains_unobserved():
    inputs = pd.DataFrame({"volume": [10.0, 10.0, 10.0],
                           "taker_buy_base_volume": [6.0, np.nan, 7.0]})
    result = calculate_cvd(inputs)
    assert result["cvd"].iloc[0] == 2.0
    assert result["cvd"].iloc[1:].isna().all()


def test_funding_cli_rejects_explicit_dates_it_does_not_apply(tmp_path):
    idx = pd.date_range("2024-01-01", periods=5, freq="8h", tz="UTC")
    basket = pd.DataFrame({
        "spot_close": [100, 100, 100.5, 101, 101],
        "perp_close": [100, 100, 100.6, 101.1, 101.2],
        "observed_funding_rate": [0.0002] * 5,
        "observed_funding_time": idx,
        "funding_rate": [0.0002, 0.0002, 0.0002, -0.0001, -0.0001],
        "funding_time": idx,
        "funding_readiness": True,
    }, index=idx)
    source = tmp_path / "basket.parquet"
    basket.to_parquet(source)
    output = tmp_path / "out"
    result = subprocess.run([
        sys.executable, str(Path(__file__).resolve().parents[1] / "run_backtest.py"),
        "--strategy", "funding_arbitrage", "--basket-input", str(source),
        "--start", "2030-01-01", "--end", "2030-01-02",
        "--output-dir", str(output),
    ], capture_output=True, text=True, timeout=30)
    assert result.returncode == 2
    assert "UNSUPPORTED_DATE_RANGE" in result.stderr
    assert not output.exists()


def test_comparison_cli_rejects_explicit_dates_before_loading_files(tmp_path):
    result = subprocess.run([
        sys.executable, str(Path(__file__).resolve().parents[1] / "run_backtest.py"),
        "--strategy", "all", "--comparison-data-dir", str(tmp_path),
        "--start", "2030-01-01", "--end", "2030-01-02",
        "--output-dir", str(tmp_path / "out"),
    ], capture_output=True, text=True, timeout=30)
    assert result.returncode == 2
    assert "UNSUPPORTED_DATE_RANGE" in result.stderr
    assert not (tmp_path / "out").exists()


def test_ui_example_matches_synthetic_replay():
    path = Path(__file__).resolve().parents[1] / "docs" / "reviews" / "evidence" / "review-high-priority-fixes" / "ui-example.json"
    example = json.loads(path.read_text(encoding="utf-8"))
    broker = PaperBroker(batch_config())
    broker.process_batch([candle(T, "BTCUSDT"), candle(T, "ETHUSDT")])
    broker.submit_order(order("BTCUSDT"))
    broker.submit_order(order("ETHUSDT"))
    broker.process_batch([candle(T + timedelta(minutes=1), "BTCUSDT"),
                          candle(T + timedelta(minutes=1), "ETHUSDT")])
    broker.process_batch([candle(T + timedelta(minutes=2), "BTCUSDT", low=94.0),
                          candle(T + timedelta(minutes=2), "ETHUSDT")])
    broker.verify_accounting_invariants()
    assert example["evidence_status"] == "SYNTHETIC_OFFLINE_DEMO"
    assert example["as_of_utc"] == (T + timedelta(minutes=3)).isoformat()
    assert example["source"]["venue"] == "SYNTHETIC"
    assert example["account"]["wallet_balance_usd"] == broker.wallet_balance
    assert example["account"]["equity_usd"] == broker.equity
    assert example["account"]["realized_net_pnl_usd"] == sum(t.net_pnl for t in broker.trade_history)
    assert example["account"]["completed_trades"] == len(broker.trade_history)
    assert example["account"]["open_positions"] == sorted(broker.positions)
    assert example["execution"]["orders_filled"] == sum(r.status == OrderStatus.FILLED for r in broker.order_history)
    assert example["risk"]["breaker_locked"] == broker.circuit_breaker.is_locked
    assert not example["input_quality"]["open_interest"]["available"]
    assert not example["input_quality"]["cvd"]["available"]
