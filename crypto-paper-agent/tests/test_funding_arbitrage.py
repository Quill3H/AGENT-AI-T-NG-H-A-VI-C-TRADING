from datetime import datetime, timezone

import pandas as pd
import pytest

from src.strategies.funding_arbitrage import FundingArbitrageSimulator


def _config():
    return {"fees": {"taker_pct": 0.0005, "slippage_pct": 0.0001}, "funding_arbitrage": {"min_apr": 0.15, "funding_period_hours": 8, "negative_cycles_to_exit": 2}}


def test_delta_neutral_entry_funding_and_two_cycle_exit():
    idx = pd.date_range(datetime(2023, 1, 1, tzinfo=timezone.utc), periods=4, freq="8h")
    frame = pd.DataFrame({"spot_close": [100, 101, 102, 103], "perp_close": [100.1, 101.1, 102.1, 103.1], "funding_rate": [0.0002, 0.0002, -0.0001, -0.0001]}, index=idx)
    result = FundingArbitrageSimulator(_config()).simulate(frame, 10000.0, 5000.0)
    assert result.entered is True
    assert result.exited is True
    assert result.exit_reason == "NEGATIVE_FUNDING_TWO_CYCLES"
    assert result.spot_notional == 5000.0
    assert result.perp_notional == pytest.approx(5005.0)
    assert result.funding_cashflow == pytest.approx(-0.015)


def test_missing_spot_leg_fails_closed():
    frame = pd.DataFrame({"perp_close": [100.0], "funding_rate": [0.01]})
    with pytest.raises(ValueError, match="explicit columns"):
        FundingArbitrageSimulator(_config()).simulate(frame, 10000.0)
