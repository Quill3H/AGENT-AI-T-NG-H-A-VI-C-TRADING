"""Independent regression probes for GPT Stage 4 Review 07."""
import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from src.execution.paper_broker import PaperBroker
from src.execution.order_models import OrderDirection, OrderRequest

ROOT = Path(__file__).resolve().parents[2]
T = datetime(2026, 9, 1, 7, 58, tzinfo=timezone.utc)


def cfg():
    with open(ROOT / "config" / "default_config.yaml", encoding="utf-8") as f:
        c = yaml.safe_load(f)
    c["leverage_brackets"]["ETHUSDT"] = copy.deepcopy(
        c["leverage_brackets"]["BTCUSDT"]
    )
    return c


def candle(t, symbol="BTCUSDT", price=100.0, **kwargs):
    d = {
        "open_time": t,
        "symbol": symbol,
        "open": price,
        "high": price,
        "low": price,
        "close": price,
        "timeframe": "1m",
    }
    d.update(kwargs)
    return d


def request(t, symbol="BTCUSDT"):
    return OrderRequest(
        symbol=symbol,
        direction=OrderDirection.LONG,
        signal_price=100.0,
        stop_loss_price=95.0,
        take_profit_price=110.0,
        signal_time=t,
        leverage=2.0,
        base_risk_percent=0.02,
        conviction_tier="normal",
        requested_quantity=10.0,
    )


def open_one():
    b = PaperBroker(config=cfg())
    b.process_candle(candle(T))
    b.submit_order(request(T))
    b.process_candle(candle(T + timedelta(minutes=1)))
    assert "BTCUSDT" in b.positions
    return b


def financial_state(b):
    pos = b.positions.get("BTCUSDT")
    return {
        "wallet": b.wallet_balance,
        "collateral": None if pos is None else pos.isolated_collateral,
        "cumulative_funding": None if pos is None else pos.cumulative_funding,
        "funding_count": len(b.funding_history),
        "cashflows": list(b.circuit_breaker.trade_history_24h),
        "settled_keys": set(b.settled_funding_keys),
    }


def test_J1_missing_funding_provenance_and_readiness_fail_closed():
    b = open_one()
    before = financial_state(b)
    with pytest.raises((ValueError, TypeError)):
        b.process_candle(candle(T + timedelta(minutes=2), funding_rate=0.001))
    assert financial_state(b) == before


def test_J2_solver_failure_during_settlement_has_zero_mutation():
    b = open_one()
    before = financial_state(b)
    b.config["leverage_brackets"]["BTCUSDT"] = "corrupt"
    with pytest.raises((ValueError, TypeError)):
        b.process_candle(
            candle(
                T + timedelta(minutes=2),
                funding_rate=0.001,
                funding_time=T + timedelta(minutes=2),
                funding_readiness=True,
            )
        )
    assert financial_state(b) == before


def test_J3_finalize_force_close_survives_nested_breaker_closure():
    b = PaperBroker(config=cfg())
    for symbol in ("BTCUSDT", "ETHUSDT"):
        b.process_candle(candle(T, symbol=symbol))
        b.submit_order(request(T, symbol=symbol))
    for symbol in ("BTCUSDT", "ETHUSDT"):
        b.process_candle(candle(T + timedelta(minutes=1), symbol=symbol))

    # The first forced close exceeds daily loss; breaker closes the other position.
    b.last_mark_prices["BTCUSDT"] = 1.0
    b.last_mark_prices["ETHUSDT"] = 1.0

    summary = b.finalize(timestamp=T + timedelta(minutes=2), force_close=True)
    assert b.is_finalized
    assert summary["open_positions_count"] == 0
    assert not b.positions
    assert len(b.trade_history) == 2

    # Idempotence: no double-close and same terminal summary.
    again = b.finalize(timestamp=T + timedelta(minutes=3), force_close=True)
    assert again == summary
    assert len(b.trade_history) == 2
