"""SMC events become available at confirmation time, never at pivot time."""

from dataclasses import dataclass
import math
import numpy as np
import pandas as pd
from src.research.validation import number, positive_int, time_index


@dataclass
class SMCFeatureTracker:
    swing_n: int = 3
    min_bos_pct: float = 0.001
    high: object = None
    low: object = None
    broken_high: object = None
    broken_low: object = None
    trend: object = None
    last_bear_body: object = None
    last_bull_body: object = None

    def __post_init__(self):
        positive_int(self.swing_n, "swing_n")
        number(self.min_bos_pct, "min_bos_pct", maximum=1)

    def step(self, history):
        row = history.iloc[-1]
        o, h, l, c = (float(row[k]) for k in ("open", "high", "low", "close"))
        out = {
            k: False
            for k in (
                "swing_high_confirmed",
                "swing_low_confirmed",
                "liquidity_sweep_bullish",
                "liquidity_sweep_bearish",
                "bos_bullish",
                "bos_bearish",
                "choch_bullish",
                "choch_bearish",
            )
        }
        out.update(
            swing_high_price=np.nan,
            swing_low_price=np.nan,
            fvg_low=np.nan,
            fvg_high=np.nan,
            fvg_mid=np.nan,
            fvg_direction=None,
            order_block_low=np.nan,
            order_block_high=np.nan,
            order_block_direction=None,
        )
        # Only levels available before this candle can be swept or broken.
        out["liquidity_sweep_bullish"] = self.low is not None and l < self.low <= c
        out["liquidity_sweep_bearish"] = self.high is not None and h > self.high >= c
        bullish = (
            self.high is not None
            and c > self.high * (1 + self.min_bos_pct)
            and self.broken_high != self.high
        )
        bearish = (
            self.low is not None
            and c < self.low * (1 - self.min_bos_pct)
            and self.broken_low != self.low
        )
        for flag, direction, body in (
            (bullish, "BULLISH", self.last_bear_body),
            (bearish, "BEARISH", self.last_bull_body),
        ):
            if flag:
                suffix = "bullish" if direction == "BULLISH" else "bearish"
                out["bos_" + suffix] = True
                out["choch_" + suffix] = (
                    self.trend is not None and self.trend != direction
                )
                self.trend = direction
                if body:
                    out.update(
                        order_block_low=body[0],
                        order_block_high=body[1],
                        order_block_direction=direction,
                    )
        if bullish:
            self.broken_high = self.high
        if bearish:
            self.broken_low = self.low
        n = self.swing_n
        if len(history) >= 2 * n + 1:
            window = history.iloc[-(2 * n + 1) :]
            pivot = window.iloc[n]
            if (
                pivot.high > window.iloc[:n].high.max()
                and pivot.high > window.iloc[n + 1 :].high.max()
            ):
                self.high = float(pivot.high)
                out["swing_high_confirmed"] = True
                out["swing_high_price"] = self.high
            if (
                pivot.low < window.iloc[:n].low.min()
                and pivot.low < window.iloc[n + 1 :].low.min()
            ):
                self.low = float(pivot.low)
                out["swing_low_confirmed"] = True
                out["swing_low_price"] = self.low
        if len(history) >= 3:
            a = history.iloc[-3]
            if a.high < l:
                out.update(
                    fvg_low=float(a.high),
                    fvg_high=l,
                    fvg_mid=(a.high + l) / 2,
                    fvg_direction="BULLISH",
                )
            elif a.low > h:
                out.update(
                    fvg_low=h,
                    fvg_high=float(a.low),
                    fvg_mid=(h + a.low) / 2,
                    fvg_direction="BEARISH",
                )
        if c < o:
            self.last_bear_body = (c, o)
        if c > o:
            self.last_bull_body = (o, c)
        return out


def compute_smc_features(frame, swing_n=3, min_bos_pct=0.001):
    time_index(frame)
    missing = {"open", "high", "low", "close"}.difference(frame.columns)
    if missing:
        raise ValueError(f"SMC features require columns: {sorted(missing)}")
    tracker = SMCFeatureTracker(swing_n, min_bos_pct)
    events = [tracker.step(frame.iloc[: i + 1]) for i in range(len(frame))]
    return pd.concat([frame.copy(), pd.DataFrame(events, index=frame.index)], axis=1)
