#!/usr/bin/env python3
"""Extend the Binance Vision perp bars with daily archives for forward paper runs (paper only).

  python scripts/extend_vision_daily.py --base <binance-vision-usdm dir> --daily <dir of *_dailyfill.csv.gz> \
      --output <new dir> --symbol BTCUSDT --symbol ETHUSDT

The daily archives are fetched on the owner's computer with checksum checks (the cloud
proxy blocks Binance). The base files are never modified: each output parquet is the base
history plus the new days, so earlier rows stay byte-for-byte the same values. 1d bars for
the new days are built from 1h bars. Binance Vision publishes funding monthly, so funding
for the new days comes from the public REST endpoint /fapi/v1/fundingRate (no keys), saved
on the owner's computer as <SYMBOL>_funding_api.json and passed with --funding. A manifest records
row counts, missing bars and sha256 of every file written.
"""
import argparse
import csv
import gzip
import hashlib
import json
import shutil
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.download_vision_history import FREQ, to_frame  # noqa: E402

TIMEFRAMES = ("5m", "15m", "1h", "4h")
AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum", "quote_volume": "sum",
       "trades": "sum", "taker_buy_base_volume": "sum", "taker_buy_quote": "sum"}


def read_rows(path):
    with gzip.open(path, "rt") as handle:
        return [r for r in csv.reader(handle) if r and r[0][:1].isdigit()]


def extend(base, new):
    """Base rows win on overlap; only bars after the base's last bar are added."""
    new = new[new.index > base.index[-1]] if len(base) else new
    return pd.concat([base, new]).sort_index()


def funding_from_api(path):
    """Rows of a saved /fapi/v1/fundingRate response, in the base funding file's columns."""
    rows = json.loads(Path(path).read_text(encoding="utf-8"))["rows"]
    frame = pd.DataFrame({"funding_interval_hours": 8, "funding_rate": [float(r["fundingRate"]) for r in rows]},
                         index=pd.to_datetime([int(r["fundingTime"]) for r in rows], unit="ms", utc=True))
    frame.index.name = "timestamp"
    return frame


def daily_from_hourly(hourly):
    days = hourly.resample("1D").agg(AGG)
    counts = hourly["close"].resample("1D").count()
    return days[counts == 24]  # complete days only


def check(frame, tf):
    full = pd.date_range(frame.index[0], frame.index[-1], freq=FREQ[tf])
    missing = full.difference(frame.index)
    return {"rows": len(frame), "start": str(frame.index[0]), "end": str(frame.index[-1]), "missing_bars": len(missing),
            "missing_days": sorted({str(t.date()) for t in missing})}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--daily", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--symbol", action="append", required=True)
    parser.add_argument("--funding", help="dir of <SYMBOL>_funding_api.json files")
    args = parser.parse_args()
    base_dir, daily_dir, out_dir = Path(args.base), Path(args.daily), Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"base": str(base_dir), "files": {}}
    for symbol in args.symbol:
        frames = {}
        for tf in TIMEFRAMES:
            if not (base_dir / f"{symbol}_perp_{tf}.parquet").is_file():
                continue  # no history to extend (e.g. 5m exists only for a few coins)
            base = pd.read_parquet(base_dir / f"{symbol}_perp_{tf}.parquet")
            frames[tf] = extend(base, to_frame(tf, read_rows(daily_dir / f"{symbol}_perp_{tf}_dailyfill.csv.gz")))
        base_daily = pd.read_parquet(base_dir / f"{symbol}_perp_1d.parquet")
        frames["1d"] = extend(base_daily, daily_from_hourly(frames["1h"]))
        for tf, frame in frames.items():
            path = out_dir / f"{symbol}_perp_{tf}.parquet"
            frame.to_parquet(path)
            manifest["files"][path.name] = {**check(frame, tf), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        funding = pd.read_parquet(base_dir / f"{symbol}_perp_funding.parquet")
        if args.funding:
            api = funding_from_api(Path(args.funding) / f"{symbol}_funding_api.json")
            funding = extend(funding, api.astype({"funding_interval_hours": funding["funding_interval_hours"].dtype}))
            shutil.copy2(Path(args.funding) / f"{symbol}_funding_api.json", out_dir / f"{symbol}_funding_api.json")
        path = out_dir / f"{symbol}_perp_funding.parquet"
        funding.to_parquet(path)
        manifest["files"][path.name] = {"rows": len(funding), "end": str(funding.index[-1]), "missing_bars": 0,
                                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        source = daily_dir / f"{symbol}_{'_'.join(TIMEFRAMES)}_dailyfill_manifest.json"
        if source.is_file():
            shutil.copy2(source, out_dir / source.name)
    (out_dir / "extension_manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(json.dumps({k: (v["end"], v["missing_bars"]) for k, v in manifest["files"].items()}, indent=1))


if __name__ == "__main__":
    main()
