"""Name -> directional strategy class, shared by the CLI and research scripts."""
from src.strategies.breakout_retest import BreakoutRetestStrategy
from src.strategies.donchian_trend import DonchianTrendStrategy
from src.strategies.indicator_suite import (
    ADXDonchian,
    MultiTimeframeTrend,
    RSI2Reversion,
    SqueezeBreakout,
    SupertrendStrategy,
    TimeSeriesMomentum,
)
from src.strategies.smc_liquidity_sweep import SMCLiquiditySweepStrategy
from src.strategies.trend_following import TrendFollowingStrategy

DIRECTIONAL_STRATEGIES = {
    "trend_following": TrendFollowingStrategy,
    "breakout_retest": BreakoutRetestStrategy,
    "smc_liquidity_sweep": SMCLiquiditySweepStrategy,
    "donchian_trend": DonchianTrendStrategy,
    "tsmom": TimeSeriesMomentum,
    "rsi2_reversion": RSI2Reversion,
    "squeeze_breakout": SqueezeBreakout,
    "mtf_trend": MultiTimeframeTrend,
    "adx_donchian": ADXDonchian,
    "supertrend": SupertrendStrategy,
}


def directional_strategy(name, config, symbol="BTCUSDT"):
    if name not in DIRECTIONAL_STRATEGIES:
        raise ValueError(f"unknown directional strategy {name!r}; choose from {sorted(DIRECTIONAL_STRATEGIES)}")
    return DIRECTIONAL_STRATEGIES[name](config=config, symbol=symbol)
