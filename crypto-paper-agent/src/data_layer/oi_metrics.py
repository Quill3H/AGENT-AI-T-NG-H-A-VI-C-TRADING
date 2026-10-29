"""
src/data_layer/oi_metrics.py
============================
Binance Vision USDⓈ-M daily `metrics` files (5m open-interest snapshots) for the
btc_oi_contraction_reclaim_v1 study (docs/research/2026-10-22-btc-oi-reclaim-v1.md).

Only `sum_open_interest` (contracts, here BTC) measures position contraction: the USDT value
`sum_open_interest_value` falls with price alone. Rows are parsed as UTC and sorted; the CSV row
order is not trusted. Nothing is filled, interpolated or carried forward: a duplicate time with a
different value, a non-finite or non-positive OI, or a missing row fails or is reported.
"""
import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd

OI_COLUMN = "sum_open_interest"
SNAPSHOT = pd.Timedelta("5min")


class OIDataError(ValueError):
    """The OI file cannot be used as is."""


def parse_oi(frame, invalid="raise"):
    """Raw metrics rows -> float Series of OI quantity indexed by UTC create_time, sorted.
    Exact duplicate rows collapse to one; the same time with different values fails.
    invalid="raise" fails on a missing, non-finite or non-positive OI; invalid="drop" removes
    those rows (they become missing snapshots, never filled) and returns (series, dropped_times)."""
    if OI_COLUMN not in frame.columns or "create_time" not in frame.columns:
        raise OIDataError(f"metrics rows need create_time and {OI_COLUMN}, got {list(frame.columns)}")
    times = pd.to_datetime(frame["create_time"], utc=True, errors="coerce")
    if times.isna().any():
        raise OIDataError(f"unparseable create_time in {int(times.isna().sum())} rows")
    values = pd.to_numeric(frame[OI_COLUMN], errors="coerce").astype(float)
    bad = ~np.isfinite(values) | (values <= 0)
    dropped = pd.DatetimeIndex(times[bad]).unique().sort_values()
    if bad.any() and invalid == "drop":
        frame, times, values = frame[~bad.to_numpy()], times[~bad], values[~bad]
    elif bad.any():
        first = times[bad].iloc[0]
        raise OIDataError(f"{int(bad.sum())} rows with missing, non-finite or non-positive {OI_COLUMN}, first at {first}")
    series = pd.Series(values.to_numpy(), index=pd.DatetimeIndex(times), name=OI_COLUMN).sort_index(kind="stable")
    dup = series.index.duplicated(keep=False)
    if dup.any():
        groups = series[dup].groupby(level=0).nunique()
        conflicts = groups[groups > 1]
        if len(conflicts):
            raise OIDataError(f"{len(conflicts)} times with conflicting {OI_COLUMN}, first at {conflicts.index[0]}")
        series = series[~series.index.duplicated(keep="first")]
    if invalid == "drop":
        return series, dropped  # a dropped time may still hold a valid row: callers report both
    return series


def load_raw(path):
    """Read <SYMBOL>_metrics_raw.csv.gz written by the device downloader."""
    with gzip.open(path, "rt") as handle:
        frame = pd.read_csv(handle, dtype=str)
    return frame


def _utc(x):
    x = pd.Timestamp(x)
    return x.tz_localize("UTC") if x.tzinfo is None else x.tz_convert("UTC")


def coverage(series, start, end):
    """Expected 5m grid on [start, end) vs present snapshots: counts and the missing times."""
    grid = pd.date_range(_utc(start), _utc(end), freq=SNAPSHOT, inclusive="left")
    present = series.index[(series.index >= grid[0]) & (series.index <= grid[-1])]
    off_grid = present[(present - grid[0]) % SNAPSHOT != pd.Timedelta(0)]
    missing = grid.difference(present)
    return {"expected": len(grid), "present_on_grid": len(grid) - len(missing), "missing": len(missing),
            "off_grid": len(off_grid), "missing_times": missing, "off_grid_times": off_grid}


def manifest_summary(manifest_path):
    rows = json.loads(Path(manifest_path).read_text())
    status = {}
    for row in rows:
        status[row["status"]] = status.get(row["status"], 0) + 1
    return {"days": len(rows), "status": status,
            "not_ok": [r["day"] for r in rows if r["status"] != "OK"]}
