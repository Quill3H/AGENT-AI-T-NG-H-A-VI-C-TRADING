"""
src/strategies/indicator_suite.py
=================================
Round-3 indicator strategies (docs/research/2026-10-16-indicator-search.md).

Every rule reads only closed signal bars (the engine passes history up to and
including the bar that just closed); entries and exits fill at the next
execution open.  Parameters are the published defaults named in the research
log, not values fitted to our data.  Each position always carries a stop-loss.
"""
import math
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd

from src.execution.order_models import OrderDirection, OrderRequest, _ensure_utc
from src.strategies.base_strategy import BaseStrategy

LONG, SHORT = OrderDirection.LONG, OrderDirection.SHORT


# ----------------------------------------------------------------- indicators
def ema(series: pd.Series, bars: int) -> pd.Series:
    return series.ewm(span=bars, adjust=False).mean()


def true_range(frame: pd.DataFrame) -> pd.Series:
    prev_close = frame["close"].shift(1)
    return pd.concat(
        [frame["high"] - frame["low"], (frame["high"] - prev_close).abs(), (frame["low"] - prev_close).abs()], axis=1
    ).max(axis=1)


def atr(frame: pd.DataFrame, bars: int) -> pd.Series:
    """Simple-average ATR, as in the Donchian strategy."""
    return true_range(frame).rolling(bars).mean()


def rsi(close: pd.Series, bars: int) -> pd.Series:
    """Wilder RSI."""
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1.0 / bars, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1.0 / bars, adjust=False).mean()
    rs = gain / loss.replace(0.0, np.nan)
    return (100.0 - 100.0 / (1.0 + rs)).fillna(100.0)


def adx(frame: pd.DataFrame, bars: int = 14) -> pd.Series:
    """Wilder ADX."""
    up = frame["high"].diff()
    down = -frame["low"].diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=frame.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=frame.index)
    smoothed_tr = true_range(frame).ewm(alpha=1.0 / bars, adjust=False).mean()
    plus_di = 100.0 * plus_dm.ewm(alpha=1.0 / bars, adjust=False).mean() / smoothed_tr
    minus_di = 100.0 * minus_dm.ewm(alpha=1.0 / bars, adjust=False).mean() / smoothed_tr
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)
    return dx.ewm(alpha=1.0 / bars, adjust=False).mean()


def supertrend(frame: pd.DataFrame, bars: int = 10, multiple: float = 3.0) -> Tuple[np.ndarray, np.ndarray]:
    """Return (line, direction) arrays; direction +1 up-trend, -1 down-trend."""
    high, low, close = frame["high"].to_numpy(), frame["low"].to_numpy(), frame["close"].to_numpy()
    band_atr = true_range(frame).ewm(alpha=1.0 / bars, adjust=False).mean().to_numpy()
    mid = (high + low) / 2.0
    upper, lower = mid + multiple * band_atr, mid - multiple * band_atr
    line = np.full(len(close), np.nan)
    direction = np.ones(len(close))
    final_upper, final_lower = upper.copy(), lower.copy()
    for i in range(1, len(close)):
        final_upper[i] = upper[i] if upper[i] < final_upper[i - 1] or close[i - 1] > final_upper[i - 1] else final_upper[i - 1]
        final_lower[i] = lower[i] if lower[i] > final_lower[i - 1] or close[i - 1] < final_lower[i - 1] else final_lower[i - 1]
        if direction[i - 1] < 0 and close[i] > final_upper[i - 1]:
            direction[i] = 1.0
        elif direction[i - 1] > 0 and close[i] < final_lower[i - 1]:
            direction[i] = -1.0
        else:
            direction[i] = direction[i - 1]
        line[i] = final_lower[i] if direction[i] > 0 else final_upper[i]
    return line, direction


def completed_daily(history: pd.DataFrame) -> pd.DataFrame:
    """Daily bars built only from days whose final 4h bar has closed."""
    days = history.resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    last_open = history.index[-1]
    if last_open.hour != 20:  # the 20:00 bar closes the UTC day
        days = days.iloc[:-1]
    return days


# ---------------------------------------------------------------- base class
class RuleStrategy(BaseStrategy):
    """Shared plumbing: one position per symbol, stop on every entry, causal market exits."""

    name = "RULE"
    window = 300  # bars of history the rules need
    columns = ("open", "high", "low", "close")  # add "volume" in a subclass that reads it

    def __init__(self, config: Dict[str, Any], symbol: str = "BTCUSDT"):
        super().__init__(config, symbol)
        self.rules = config.get("rules", {})
        self.allow_short = bool(self.rules.get("allow_short", True))
        self.default_conviction = config.get("default_conviction", "normal")
        self.leverage = min(float(config.get("leverage", 2.0)), 5.0)
        self.base_risk_percent = float(config.get("base_risk_percent", 0.02))
        self.setup_count = 0
        self.candidate_count = 0
        self.held_bars = 0  # closed signal bars since the current position was seen open

    # subclasses implement these three
    def entry(self, frame: pd.DataFrame) -> Optional[Tuple]:
        """Return (direction, stop) or (direction, stop, take_profit), or None."""
        raise NotImplementedError

    def should_exit(self, frame: pd.DataFrame, direction: OrderDirection) -> bool:
        return False

    def trail(self, frame: pd.DataFrame, direction: OrderDirection) -> Optional[float]:
        return None

    def on_candle_close(self, candle_4h: Dict[str, Any], history_4h: pd.DataFrame, broker_state: Any) -> Optional[OrderRequest]:
        if history_4h is None or len(history_4h) < self.window:
            return None
        frame = history_4h.iloc[-self.window:][list(self.columns)].astype(float)
        signal_time = _ensure_utc(candle_4h.get("close_time") or candle_4h.get("timestamp"))
        position = getattr(broker_state, "positions", {}).get(self.symbol) if broker_state is not None else None
        if position is not None:
            self.held_bars += 1
            if self.should_exit(frame, position.direction):
                broker_state.request_close(self.symbol, signal_time)
            else:
                candidate = self.trail(frame, position.direction)
                if candidate is not None and math.isfinite(candidate) and candidate > 0:
                    broker_state.update_stop_loss(self.symbol, candidate)
            return None
        self.held_bars = 0
        if any(getattr(o, "symbol", None) == self.symbol for o in getattr(broker_state, "pending_orders", []) or []):
            return None
        signal = self.entry(frame)
        if signal is None:
            return None
        direction, stop = signal[0], signal[1]
        take_profit = signal[2] if len(signal) > 2 else None
        close = float(frame["close"].iloc[-1])
        if direction == SHORT and not self.allow_short:
            return None
        if not (math.isfinite(stop) and stop > 0) or (direction == LONG and stop >= close) or (direction == SHORT and stop <= close):
            return None
        if take_profit is not None and (not math.isfinite(take_profit) or (direction == LONG and take_profit <= close)
                                        or (direction == SHORT and take_profit >= close)):
            return None
        self.setup_count += 1
        self.candidate_count += 1
        return OrderRequest(
            symbol=self.symbol,
            direction=direction,
            signal_price=close,
            stop_loss_price=stop,
            signal_time=signal_time,
            conviction_tier=self.default_conviction,
            take_profit_price=take_profit,
            leverage=self.leverage,
            base_risk_percent=self.base_risk_percent,
            metadata={"strategy": self.name},
        )

    def update_trailing_stop(self, candle_4h: Dict[str, Any], broker: Any) -> None:
        """Trailing needs bar history, so it happens in on_candle_close."""


# ---------------------------------------------------------------- strategies
class TimeSeriesMomentum(RuleStrategy):
    """I1: daily 30-bar return sign, EMA(50) confirmation, exit on sign change, 3 ATR stop."""

    name = "TSMOM"
    window = 80

    def _momentum(self, frame):
        return float(frame["close"].iloc[-1] / frame["close"].iloc[-31] - 1.0)

    def entry(self, frame):
        mom, close = self._momentum(frame), float(frame["close"].iloc[-1])
        trend = float(ema(frame["close"], 50).iloc[-1])
        stop_gap = 3.0 * float(atr(frame, 20).iloc[-1])
        if mom > 0 and close > trend:
            return LONG, close - stop_gap
        if mom < 0 and close < trend:
            return SHORT, close + stop_gap
        return None

    def should_exit(self, frame, direction):
        mom = self._momentum(frame)
        return (direction == LONG and mom <= 0) or (direction == SHORT and mom >= 0)


class RSI2Reversion(RuleStrategy):
    """I2: Connors RSI(2) pullbacks in the SMA(200) direction, exit on SMA(5) cross, 2.5 ATR stop."""

    name = "RSI2_REVERSION"
    window = 260

    def entry(self, frame):
        close = frame["close"]
        last = float(close.iloc[-1])
        trend = float(close.rolling(200).mean().iloc[-1])
        value = float(rsi(close, 2).iloc[-1])
        stop_gap = 2.5 * float(atr(frame, 14).iloc[-1])
        if last > trend and value < 10:
            return LONG, last - stop_gap
        if last < trend and value > 90:
            return SHORT, last + stop_gap
        return None

    def should_exit(self, frame, direction):
        last, fast = float(frame["close"].iloc[-1]), float(frame["close"].rolling(5).mean().iloc[-1])
        return (direction == LONG and last > fast) or (direction == SHORT and last < fast)


class SqueezeBreakout(RuleStrategy):
    """I3: Bollinger inside the lowest-20% width of 120 bars, then a close outside Keltner(20, 1.5 ATR)."""

    name = "SQUEEZE_BREAKOUT"
    window = 160

    def entry(self, frame):
        close = frame["close"]
        mid = close.rolling(20).mean()
        width = 4.0 * close.rolling(20).std() / mid
        recent = width.iloc[-121:-1]
        squeezed = float(width.iloc[-2]) <= float(recent.quantile(0.2))
        if not squeezed:
            return None
        band_atr = float(atr(frame, 20).iloc[-1])
        centre, last = float(ema(close, 20).iloc[-1]), float(close.iloc[-1])
        if last > centre + 1.5 * band_atr:
            return LONG, last - 2.0 * band_atr
        if last < centre - 1.5 * band_atr:
            return SHORT, last + 2.0 * band_atr
        return None

    def should_exit(self, frame, direction):
        last, centre = float(frame["close"].iloc[-1]), float(ema(frame["close"], 20).iloc[-1])
        return (direction == LONG and last < centre) or (direction == SHORT and last > centre)


class MultiTimeframeTrend(RuleStrategy):
    """I4: completed-day EMA50/EMA200 regime + 4h Donchian 20 breakout in that direction, 10-bar trailing exit."""

    name = "MTF_TREND"
    window = 1400  # about 233 days of 4h bars, enough for a daily EMA(200)

    def entry(self, frame):
        days = completed_daily(frame)
        if len(days) < 200:
            return None
        regime_up = float(ema(days["close"], 50).iloc[-1]) > float(ema(days["close"], 200).iloc[-1])
        last = float(frame["close"].iloc[-1])
        previous = frame.iloc[-21:-1]
        stop_gap = 2.0 * float(atr(frame, 20).iloc[-1])
        if regime_up and last > float(previous["high"].max()):
            return LONG, last - stop_gap
        if not regime_up and last < float(previous["low"].min()):
            return SHORT, last + stop_gap
        return None

    def trail(self, frame, direction):
        window = frame.iloc[-10:]
        return float(window["low"].min()) if direction == LONG else float(window["high"].max())


class ADXDonchian(RuleStrategy):
    """I5: daily Donchian 20/10 breakout, taken only when ADX(14) > 25."""

    name = "ADX_DONCHIAN"
    window = 80

    def entry(self, frame):
        if float(adx(frame, 14).iloc[-1]) <= 25:
            return None
        last = float(frame["close"].iloc[-1])
        previous = frame.iloc[-21:-1]
        stop_gap = 2.0 * float(atr(frame, 20).iloc[-1])
        if last > float(previous["high"].max()):
            return LONG, last - stop_gap
        if last < float(previous["low"].min()):
            return SHORT, last + stop_gap
        return None

    def trail(self, frame, direction):
        window = frame.iloc[-10:]
        return float(window["low"].min()) if direction == LONG else float(window["high"].max())


class SupertrendStrategy(RuleStrategy):
    """I6: 4h Supertrend(10, 3): enter on a flip, exit on the opposite flip, stop trails the line."""

    name = "SUPERTREND"
    window = 200

    def entry(self, frame):
        line, direction = supertrend(frame)
        if direction[-1] == direction[-2]:
            return None
        return (LONG, float(line[-1])) if direction[-1] > 0 else (SHORT, float(line[-1]))

    def should_exit(self, frame, held):
        _, direction = supertrend(frame)
        return (held == LONG and direction[-1] < 0) or (held == SHORT and direction[-1] > 0)

    def trail(self, frame, held):
        line, _ = supertrend(frame)
        return float(line[-1])


class RegimeSwitch(RuleStrategy):
    """N2: daily ADX regime. ADX > 25 -> Donchian 20 breakout (10-day trailing exit);
    ADX < 20 -> RSI(2) reversion around SMA(100), exit on SMA(5) cross; otherwise no entry."""

    name = "REGIME_SWITCH"
    window = 130

    def __init__(self, config, symbol="BTCUSDT"):
        super().__init__(config, symbol)
        self.mode = None

    def entry(self, frame):
        strength = float(adx(frame, 14).iloc[-1])
        last = float(frame["close"].iloc[-1])
        if strength > 25:
            previous = frame.iloc[-21:-1]
            gap = 2.0 * float(atr(frame, 20).iloc[-1])
            if last > float(previous["high"].max()):
                self.mode = "trend"
                return LONG, last - gap
            if last < float(previous["low"].min()):
                self.mode = "trend"
                return SHORT, last + gap
        elif strength < 20:
            trend = float(frame["close"].rolling(100).mean().iloc[-1])
            value = float(rsi(frame["close"], 2).iloc[-1])
            gap = 3.0 * float(atr(frame, 20).iloc[-1])
            if last > trend and value < 10:
                self.mode = "revert"
                return LONG, last - gap
            if last < trend and value > 90:
                self.mode = "revert"
                return SHORT, last + gap
        return None

    def should_exit(self, frame, direction):
        if self.mode != "revert":
            return False
        last, fast = float(frame["close"].iloc[-1]), float(frame["close"].rolling(5).mean().iloc[-1])
        return (direction == LONG and last > fast) or (direction == SHORT and last < fast)

    def trail(self, frame, direction):
        if self.mode == "revert":
            return None
        window = frame.iloc[-10:]
        return float(window["low"].min()) if direction == LONG else float(window["high"].max())


class SignalSeries(RuleStrategy):
    """N1/N3/N4: trade a precomputed daily position table (+1 long, -1 short, 0 flat).

    The table (rules.signal_path, parquet, one column per symbol, indexed by daily bar
    open) is produced by src/research/signals.py, whose value for day d only uses data
    up to d.  Every entry still carries a 3 x ATR(20) stop.
    """

    name = "SIGNAL_SERIES"
    window = 25

    def __init__(self, config, symbol="BTCUSDT"):
        super().__init__(config, symbol)
        table = pd.read_parquet(self.rules["signal_path"])
        self.signal = table[symbol] if symbol in table.columns else pd.Series(dtype=float)

    def _target(self, frame):
        value = self.signal.get(frame.index[-1], 0.0)
        return 0.0 if value is None or not np.isfinite(value) else float(value)

    def entry(self, frame):
        target, last = self._target(frame), float(frame["close"].iloc[-1])
        gap = 3.0 * float(atr(frame, 20).iloc[-1])
        if target > 0:
            return LONG, last - gap
        if target < 0:
            return SHORT, last + gap
        return None

    def should_exit(self, frame, direction):
        target = self._target(frame)
        return (direction == LONG and target <= 0) or (direction == SHORT and target >= 0)
