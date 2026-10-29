"""Run the one-basket funding simulator back to back over a long window.

After a basket closes, the next one may open from the following quote with the
equity the previous basket left.  One circuit breaker spans the whole run, so
loss streaks and lockouts carry across baskets.
"""
import pandas as pd

from src.risk.circuit_breakers import CircuitBreakerState
from src.strategies.funding_arbitrage import FundingArbitrageSimulator


def simulate_carry_sequence(frame, config, initial_capital):
    breaker = CircuitBreakerState.from_config(config)
    equity, cursor = float(initial_capital), 0
    snapshots, baskets = [], []
    while cursor < len(frame):
        segment = frame.iloc[cursor:]
        result = FundingArbitrageSimulator(config, circuit_breaker=breaker).simulate(segment, equity, force_close=True, stop_after_exit=True)
        stop = len(result.snapshots)
        snapshots.extend(result.snapshots)
        if result.entered:
            baskets.append({
                "entry_time": result.entry_time,
                "exit_time": result.exit_time,
                "exit_reason": result.exit_reason,
                "net_pnl": result.net_pnl,
                "funding": result.funding_cashflow,
                "fees": result.fees_paid,
            })
        equity = result.equity
        if not result.entered:
            break
        cursor += stop
    curve = pd.Series([s["equity"] for s in snapshots], index=pd.DatetimeIndex([s["timestamp"] for s in snapshots]))
    return curve, baskets
