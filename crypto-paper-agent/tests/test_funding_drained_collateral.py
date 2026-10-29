"""A long winning trade held through months of positive funding can have its isolated
collateral drained below the entry maintenance margin.  The liquidation price then sits
above entry (still far below the market), and the broker must keep solving it instead of
crashing the backtest.  Seen on SOLUSDT, Feb-Jun 2021."""
import pytest

from src.execution.order_models import OrderDirection
from src.execution.paper_broker import PaperBroker


def _solve(config, direction, collateral, qty=56.191417637542045, entry=6.4379308):
    broker = PaperBroker(config=config, initial_balance=10000.0)
    return broker._calculate_liquidation_price_for_collateral(
        symbol="SOLUSDT", direction=direction, quantity=qty, entry_price=entry, collateral=collateral)


def test_long_with_collateral_below_entry_maintenance_margin_liquidates_above_entry(config):
    qty, entry, collateral, mmr = 56.191417637542045, 6.4379308, 3.2792082873687054, 0.01
    price = _solve(config, OrderDirection.LONG, collateral)
    assert price > entry
    assert price == pytest.approx((qty * entry - collateral) / (qty * (1 - mmr)))


def test_short_with_collateral_below_entry_maintenance_margin_liquidates_below_entry(config):
    qty, entry, collateral, mmr = 56.191417637542045, 6.4379308, 1.0, 0.01
    price = _solve(config, OrderDirection.SHORT, collateral)
    assert price < entry
    assert price == pytest.approx((qty * entry + collateral) / (qty * (1 + mmr)))


def test_healthy_long_still_liquidates_below_entry(config):
    assert _solve(config, OrderDirection.LONG, 181.0) < 6.4379308
