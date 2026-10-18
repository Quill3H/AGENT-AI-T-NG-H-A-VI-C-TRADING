"""Name -> directional strategy class, shared by the CLI and research scripts."""
from src.strategies.breakout_retest import BreakoutRetestStrategy
from src.strategies.donchian_trend import DonchianTrendStrategy
from src.strategies.indicator_suite import (
    ADXDonchian,
    MultiTimeframeTrend,
    RegimeSwitch,
    RSI2Reversion,
    SignalSeries,
    SqueezeBreakout,
    SupertrendStrategy,
    TimeSeriesMomentum,
)
from src.strategies.style_suite import (
    CandleContinuation,
    CandlePullback,
    CandleReversal,
    DayOpeningRange,
    DayVwapReclaim,
    ScalpBollingerRevert,
    ScalpEmaCross,
    ScalpRsiPullback,
    SupportResistanceCandles,
    SwingEmaPullback,
    WyckoffSpring,
)
from src.strategies.contrarian_suite import ExtremeFade
from src.strategies.ichimoku_suite import IchimokuKumoBreakout, IchimokuTkCross, IchimokuTkDaily, IchimokuTkTrail
from src.strategies.wyckoff_suite import WyckoffSosLps, WyckoffSpringRun
from src.strategies.session_suite import (
    HeikinAshiScalp,
    HolyGrail,
    LondonBreakout,
    LondonBreakoutTrend,
    NarrowRangeBreakout,
    VolatilityBreakout,
    ZoneSwingBreak,
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
    "regime_switch": RegimeSwitch,
    "signal_series": SignalSeries,
    "swing_ema_pullback": SwingEmaPullback,
    "sr_candles": SupportResistanceCandles,
    "wyckoff_spring": WyckoffSpring,
    "day_orb": DayOpeningRange,
    "day_vwap": DayVwapReclaim,
    "scalp_ema": ScalpEmaCross,
    "scalp_bb": ScalpBollingerRevert,
    "scalp_bb_15m": ScalpBollingerRevert,
    "scalp_bb_1h": ScalpBollingerRevert,
    "scalp_rsi_15m": ScalpRsiPullback,
    "scalp_rsi_1h": ScalpRsiPullback,
    "scalp_ema_1m": ScalpEmaCross,
    "scalp_bb_1m": ScalpBollingerRevert,
    "candle_pullback": CandlePullback,
    "candle_reversal": CandleReversal,
    "candle_continuation": CandleContinuation,
    "candle_pullback_1h": CandlePullback,
    "london_breakout": LondonBreakout,
    "london_breakout_trend": LondonBreakoutTrend,
    "heikin_ashi_scalp": HeikinAshiScalp,
    "zone_swing_break": ZoneSwingBreak,
    "swing_ema_pullback_1h": SwingEmaPullback,
    "holy_grail": HolyGrail,
    "volatility_breakout": VolatilityBreakout,
    "nr7_breakout": NarrowRangeBreakout,
    "swing_ema_pullback_long": SwingEmaPullback,
    "blowoff_fade": ExtremeFade,
    "flush_buy": ExtremeFade,
    "ichimoku_tk_4h": IchimokuTkCross,
    "ichimoku_kumo_4h": IchimokuKumoBreakout,
    "ichimoku_tk_1h": IchimokuTkCross,
    "ichimoku_kumo_1h": IchimokuKumoBreakout,
    "ichimoku_tk_15m": IchimokuTkCross,
    "ichimoku_kumo_15m": IchimokuKumoBreakout,
    "ichimoku_tk_4h_long": IchimokuTkCross,
    "ichimoku_kumo_4h_long": IchimokuKumoBreakout,
    "wyckoff_spring_run_4h": WyckoffSpringRun,
    "wyckoff_spring_run_1h": WyckoffSpringRun,
    "wyckoff_sos_lps_4h": WyckoffSosLps,
    "wyckoff_sos_lps_1h": WyckoffSosLps,
    "ichimoku_tk_4h_daily": IchimokuTkDaily,
    "ichimoku_tk_4h_trail": IchimokuTkTrail,
}


def directional_strategy(name, config, symbol="BTCUSDT"):
    if name not in DIRECTIONAL_STRATEGIES:
        raise ValueError(f"unknown directional strategy {name!r}; choose from {sorted(DIRECTIONAL_STRATEGIES)}")
    return DIRECTIONAL_STRATEGIES[name](config=config, symbol=symbol)
