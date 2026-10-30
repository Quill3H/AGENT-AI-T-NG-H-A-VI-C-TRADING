"""Exact forensic broker regressions plus phase-boundary repair coverage.

Original probes copied verbatim from tmp/remaining-branches-20261030/original-regressions.py.
Mixed-duration wording-only probe intentionally excluded.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from src.execution.paper_broker import PaperBroker
from src.risk.circuit_breakers import CircuitBreakerState
from src.execution.order_models import ExitReason, OrderDirection, OrderRequest, OrderStatus

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



def _seed_pair(config=None, start=T, direction=OrderDirection.LONG):
    broker = PaperBroker(config or batch_config())
    broker.process_batch([candle(start, s) for s in ("BTCUSDT", "ETHUSDT")])
    broker.submit_order(order("BTCUSDT", start))
    peer = order("ETHUSDT", start)
    if direction == OrderDirection.SHORT:
        peer = OrderRequest("ETHUSDT", direction, 100.0, 105.0, start,
                            leverage=2.0, base_risk_percent=0.02, requested_quantity=1.0)
    broker.submit_order(peer)
    broker.process_batch([candle(start + timedelta(minutes=1), s) for s in ("BTCUSDT", "ETHUSDT")])
    return broker


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("peer_rate", [0.01, -0.01])
def test_funding_lock_books_both_signs_before_any_forced_exit(reverse, peer_rate):
    config = batch_config()
    config["circuit_breakers"]["daily_loss_limit_pct"] = 0.00001
    start = T.replace(hour=7, minute=58)
    broker = _seed_pair(config, start)
    settlement = start + timedelta(minutes=2)
    bars = [candle(settlement, s) for s in ("BTCUSDT", "ETHUSDT")]
    for bar, rate in zip(bars, (0.02, peer_rate)):
        bar.update(funding_rate=rate, funding_time=settlement, funding_readiness=True)
    broker.process_batch(bars[::-1] if reverse else bars)
    assert {f.symbol: f.cashflow_usd for f in broker.funding_history} == {
        "BTCUSDT": -2.0, "ETHUSDT": -100.0 * peer_rate}
    assert broker.wallet_balance == pytest.approx(9998.0 - 100.0 * peer_rate)
    assert len(broker.settled_funding_keys) == 2
    assert broker.circuit_breaker.is_locked and not broker.positions
    assert all(t.exit_time == settlement for t in broker.trade_history)
    broker.process_batch([candle(settlement + timedelta(minutes=1), s) for s in ("BTCUSDT", "ETHUSDT")])
    assert len(broker.funding_history) == 2
    broker.verify_accounting_invariants()


@pytest.mark.parametrize("reverse", [False, True])
def test_gap_lock_preserves_peer_due_funding_and_open_mark(reverse):
    config = batch_config()
    config["circuit_breakers"]["daily_loss_limit_pct"] = 0.00001
    start = T.replace(hour=7, minute=58)
    broker = _seed_pair(config, start)
    settlement = start + timedelta(minutes=2)
    btc = candle(settlement)
    btc.update(open=94.0, high=94.5, low=93.5, close=94.0)
    eth = candle(settlement, "ETHUSDT")
    eth.update(open=102.0, high=104.0, low=101.0, close=103.0,
               funding_rate=0.01, funding_time=settlement, funding_readiness=True)
    broker.process_batch([eth, btc] if reverse else [btc, eth])
    assert [(f.symbol, f.cashflow_usd) for f in broker.funding_history] == [("ETHUSDT", -1.02)]
    trades = {t.symbol: t for t in broker.trade_history}
    assert trades["BTCUSDT"].exit_reason == ExitReason.STOP_LOSS
    assert trades["ETHUSDT"].exit_reason == ExitReason.CIRCUIT_BREAKER_LOCK
    assert trades["ETHUSDT"].exit_price == 102.0
    assert broker.wallet_balance == pytest.approx(9994.98)
    broker.verify_accounting_invariants()


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("direction", [OrderDirection.LONG, OrderDirection.SHORT])
def test_intrabar_lock_preserves_peer_touched_stop_in_either_order(reverse, direction):
    config = batch_config()
    config["circuit_breakers"]["daily_loss_limit_pct"] = 0.00001
    broker = _seed_pair(config, direction=direction)
    when = T + timedelta(minutes=2)
    btc, eth = candle(when, low=94.0), candle(when, "ETHUSDT", low=94.0)
    eth.update(high=106.0, close=102.0)
    broker.process_batch([eth, btc] if reverse else [btc, eth])
    trades = {t.symbol: t for t in broker.trade_history}
    assert trades["ETHUSDT"].exit_reason == ExitReason.STOP_LOSS
    assert trades["ETHUSDT"].exit_price == (95.0 if direction == OrderDirection.LONG else 105.0)
    assert all(t.exit_time == when + timedelta(minutes=1) for t in trades.values())
    assert not broker.positions
    broker.verify_accounting_invariants()


def test_invalid_peer_funding_preflight_preserves_complete_broker_state():
    start = T.replace(hour=7, minute=58)
    broker = _seed_pair(start=start)
    settlement = start + timedelta(minutes=2)
    first, invalid = [candle(settlement, s) for s in ("BTCUSDT", "ETHUSDT")]
    first.update(funding_rate=0.01, funding_time=settlement, funding_readiness=True)
    before = deepcopy({k: v for k, v in vars(broker).items() if k not in {"news_filter", "circuit_breaker"}})
    breaker_before = deepcopy(vars(broker.circuit_breaker))
    with pytest.raises(ValueError, match="funding rate"):
        broker.process_batch([first, invalid])
    assert {k: v for k, v in vars(broker).items() if k not in {"news_filter", "circuit_breaker"}} == before
    assert vars(broker.circuit_breaker) == breaker_before


@pytest.mark.parametrize("batched", [False, True])
def test_no_close_information_can_be_added_to_an_already_completed_interval(batched):
    broker = PaperBroker(batch_config())
    broker.process_candle(candle(T, timeframe="15m"))
    before = broker_clock_state(broker)
    bars = [candle(T + timedelta(minutes=5), "ETHUSDT", timeframe="15m")]
    with pytest.raises(ValueError, match="(?i)overlap|time"):
        broker.process_batch(bars) if batched else broker.process_candle(bars[0])
    assert broker_clock_state(broker) == before


def test_entry_fee_lock_refuses_peer_fill_and_unwinds_at_open_marks():
    config = batch_config()
    config["circuit_breakers"]["daily_loss_limit_pct"] = 0.000001
    broker = PaperBroker(config)
    broker.process_candle(candle(T, "ETHUSDT"))
    broker.submit_order(order("ETHUSDT", T + timedelta(minutes=1)))
    broker.process_candle(candle(T + timedelta(minutes=1), "ETHUSDT"))
    when = T + timedelta(minutes=2)
    broker.taker_fee_pct = 0.001
    broker.submit_order(order("BTCUSDT", when))
    peer = broker.submit_order(order("SOLUSDT", when))
    eth = candle(when, "ETHUSDT")
    eth.update(open=102.0, high=110.0, low=101.0, close=110.0)
    broker.process_batch([candle(when), candle(when, "SOLUSDT"), eth])
    assert peer.status in (OrderStatus.REJECTED, OrderStatus.CANCELLED)
    assert not broker.positions
    assert len([r for r in broker.order_history if r.status == OrderStatus.FILLED]) == 2
    assert {t.symbol: t.exit_price for t in broker.trade_history} == {"ETHUSDT": 102.0, "BTCUSDT": 100.0}
    assert all(t.exit_time == when for t in broker.trade_history)
    assert broker._defer_cb_lock_for_batch is False
    broker.verify_accounting_invariants()


def test_manual_lock_unwinds_peer_before_intrabar_using_open_marks():
    config = batch_config()
    config["circuit_breakers"]["daily_loss_limit_pct"] = 0.00001
    broker = _seed_pair(config)
    when = T + timedelta(minutes=2)
    broker.request_close("BTCUSDT", when)
    btc, eth = candle(when), candle(when, "ETHUSDT")
    btc.update(open=99.0, high=100.0, low=98.0, close=100.0)
    eth.update(open=102.0, high=110.0, low=94.0, close=110.0)
    broker.process_batch([btc, eth])
    trades = {t.symbol: t for t in broker.trade_history}
    assert trades["BTCUSDT"].exit_reason == ExitReason.MANUAL
    assert trades["ETHUSDT"].exit_reason == ExitReason.CIRCUIT_BREAKER_LOCK
    assert trades["ETHUSDT"].exit_price == 102.0
    assert all(t.exit_time == when for t in trades.values())
    assert not broker.positions
    broker.verify_accounting_invariants()
