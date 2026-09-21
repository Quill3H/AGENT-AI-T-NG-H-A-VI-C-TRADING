"""Strict reusable validation for research datasets and numerical inputs."""

from numbers import Real, Integral
import math
import numpy as np
import pandas as pd


def number(value, name, minimum=0.0, maximum=None, positive=False):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise TypeError(f"{name} must be numeric, not boolean or string")
    value = float(value)
    if (
        not math.isfinite(value)
        or value < minimum
        or (positive and value == minimum)
        or (maximum is not None and value >= maximum)
    ):
        raise ValueError(f"{name} is outside its finite domain")
    return value


def positive_int(value, name):
    if (
        isinstance(value, (bool, np.bool_))
        or not isinstance(value, Integral)
        or value < 1
    ):
        raise ValueError(f"{name} must be a positive integer")
    return int(value)


def time_index(frame):
    if not isinstance(frame, pd.DataFrame) or not isinstance(
        frame.index, pd.DatetimeIndex
    ):
        raise TypeError("dataset requires a DatetimeIndex")
    if frame.index.tz is None or str(frame.index.tz) not in ("UTC", "UTC+00:00"):
        raise ValueError("dataset requires UTC timestamps")
    if (
        frame.index.hasnans
        or frame.index.has_duplicates
        or not frame.index.is_monotonic_increasing
    ):
        raise ValueError("timestamps must be sorted, unique, non-missing")


def source_time(value, now, name, max_age_hours=24):
    if not isinstance(
        value, (pd.Timestamp, __import__("datetime").datetime)
    ) or pd.isna(value):
        raise ValueError(f"{name} must be a UTC timestamp")
    ts = pd.Timestamp(value)
    if ts.tz is None or ts.utcoffset().total_seconds() != 0:
        raise ValueError(f"{name} must be UTC")
    if ts > now or now - ts > pd.Timedelta(hours=max_age_hours):
        raise ValueError(f"{name} is future or stale")
    return ts
