"""Delta-neutral spot-long/perpetual-short funding arbitrage simulator."""
from dataclasses import dataclass, asdict
from datetime import datetime
import math
from typing import Any, Dict, Optional

import pandas as pd


@dataclass
class FundingArbitrageResult:
    entered: bool
    exited: bool
    entry_time: Optional[datetime]
    exit_time: Optional[datetime]
    quantity: float
    spot_notional: float
    perp_notional: float
    fees_paid: float
    funding_cashflow: float
    spot_pnl: float
    perp_pnl: float
    net_pnl: float
    max_abs_delta_usd: float
    exit_reason: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class FundingArbitrageSimulator:
    """Simulate both legs with explicit spot/perp prices and fail-closed inputs."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        cfg = config.get("funding_arbitrage", {})
        self.min_apr = float(cfg.get("min_apr", 0.15))
        self.funding_period_hours = float(cfg.get("funding_period_hours", 8.0))
        self.negative_cycles_to_exit = int(cfg.get("negative_cycles_to_exit", 2))
        self.fee_rate = float(config.get("fees", {}).get("taker_pct", 0.0005))
        self.slippage_rate = float(config.get("fees", {}).get("slippage_pct", 0.0003))
        if not math.isfinite(self.min_apr) or self.min_apr < 0:
            raise ValueError("min_apr must be finite and non-negative")
        if not math.isfinite(self.funding_period_hours) or self.funding_period_hours <= 0:
            raise ValueError("funding_period_hours must be finite and positive")

    def simulate(self, frame: pd.DataFrame, initial_capital: float, notional_usd: Optional[float] = None) -> FundingArbitrageResult:
        if type(initial_capital) is bool or not math.isfinite(float(initial_capital)) or initial_capital <= 0:
            raise ValueError("initial_capital must be finite and positive")
        required = {"spot_close", "perp_close", "funding_rate"}
        missing = required.difference(frame.columns)
        if missing:
            raise ValueError(f"Funding arbitrage requires explicit columns: {sorted(missing)}")
        if frame.empty:
            return FundingArbitrageResult(False, False, None, None, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, None)
        notional = float(notional_usd or initial_capital)
        if notional <= 0 or notional > initial_capital:
            raise ValueError("notional_usd must be within initial capital")
        entry = None
        negative_cycles = 0
        funding_cashflow = 0.0
        fees_paid = 0.0
        max_delta = 0.0
        spot_pnl = perp_pnl = 0.0
        exit_time = None
        exit_reason = None
        quantity = 0.0

        for timestamp, row in frame.iterrows():
            spot = self._price(row["spot_close"], "spot_close")
            perp = self._price(row["perp_close"], "perp_close")
            rate = self._rate(row["funding_rate"])
            apr = rate * (24.0 * 365.0 / self.funding_period_hours)
            if entry is None:
                if apr < self.min_apr:
                    continue
                quantity = notional / spot
                entry = (timestamp, spot, perp)
                fees_paid += (spot * quantity + perp * quantity) * (self.fee_rate + self.slippage_rate)
                continue

            entry_time, entry_spot, entry_perp = entry
            delta = abs(quantity * spot - quantity * perp)
            max_delta = max(max_delta, delta)
            funding_cashflow += rate * (quantity * perp)  # short receives when funding is positive
            negative_cycles = negative_cycles + 1 if rate < 0 else 0
            if negative_cycles >= self.negative_cycles_to_exit:
                exit_time = timestamp
                exit_reason = "NEGATIVE_FUNDING_TWO_CYCLES"
                spot_pnl = quantity * (spot - entry_spot)
                perp_pnl = quantity * (entry_perp - perp)
                fees_paid += (spot * quantity + perp * quantity) * (self.fee_rate + self.slippage_rate)
                break

        if entry is None:
            return FundingArbitrageResult(False, False, None, None, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, max_delta, None)
        if exit_time is None:
            last_time, spot, perp = frame.index[-1], self._price(frame.iloc[-1]["spot_close"], "spot_close"), self._price(frame.iloc[-1]["perp_close"], "perp_close")
            spot_pnl = quantity * (spot - entry[1])
            perp_pnl = quantity * (entry[2] - perp)
        return FundingArbitrageResult(
            True, exit_time is not None, entry[0], exit_time, quantity, quantity * entry[1], quantity * entry[2],
            fees_paid, funding_cashflow, spot_pnl, perp_pnl, spot_pnl + perp_pnl + funding_cashflow - fees_paid,
            max_delta, exit_reason,
        )

    @staticmethod
    def _price(value: Any, name: str) -> float:
        if type(value) is bool:
            raise TypeError(f"{name} cannot be boolean")
        result = float(value)
        if not math.isfinite(result) or result <= 0:
            raise ValueError(f"{name} must be finite and positive")
        return result

    @staticmethod
    def _rate(value: Any) -> float:
        if type(value) is bool:
            raise TypeError("funding_rate cannot be boolean")
        result = float(value)
        if not math.isfinite(result):
            raise ValueError("funding_rate must be finite")
        return result
