#!/usr/bin/env python3
"""Download BTCUSDT monthly archives from Binance Vision (public, no keys), verify, write parquet.

Every zip is checked against Binance's own .CHECKSUM file; any mismatch or
failed download stops the run with no output written.  Spot files from 2025
on use microsecond timestamps and are converted to milliseconds.

  python scripts/download_vision_history.py --output <new dir> --allow-network
"""
import argparse
import concurrent.futures as cf
import csv
import hashlib
import io
import json
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

BASE = "https://data.binance.vision/data"
DATASETS = [("futures/um/monthly/klines/{s}/{tf}/{s}-{tf}-{ym}.zip", "perp", tf) for tf in ("5m", "15m", "1h", "4h", "1d")]
DATASETS += [("spot/monthly/klines/{s}/{tf}/{s}-{tf}-{ym}.zip", "spot", tf) for tf in ("15m", "1h")]
DATASETS += [("futures/um/monthly/fundingRate/{s}/{s}-fundingRate-{ym}.zip", "perp", "funding")]
KLINE_COLUMNS = ["open_time", "open", "high", "low", "close", "volume", "close_time",
                 "quote_volume", "trades", "taker_buy_base_volume", "taker_buy_quote", "ignore"]
FREQ = {"5m": "5min", "15m": "15min", "1h": "1h", "4h": "4h", "1d": "1D"}


def months(first, last):
    for period in pd.period_range(first, last, freq="M"):
        yield str(period)


def get(url, tries=4):
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            last = error
        except OSError as error:
            last = error
        time.sleep(2 ** attempt)
    raise RuntimeError(f"download failed after {tries} attempts: {url}: {last}")


def fetch(job):
    pattern, market, tf, ym, symbol = job
    url = f"{BASE}/" + pattern.format(s=symbol, tf=tf, ym=ym)
    raw = get(url)
    if raw is None:
        return {"url": url, "status": "MISSING"}
    sha = hashlib.sha256(raw).hexdigest()
    checksum = get(url + ".CHECKSUM")
    expected = checksum.decode().split()[0] if checksum else None
    if expected != sha:
        raise RuntimeError(f"checksum mismatch or missing for {url}: {sha} vs {expected}")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        text = archive.read(archive.namelist()[0]).decode()
    rows = [row for row in csv.reader(io.StringIO(text)) if row and row[0][:1].isdigit()]
    return {"url": url, "status": "OK", "sha256": sha, "market": market, "tf": tf, "rows": rows}


def to_frame(tf, rows):
    if tf == "funding":
        frame = pd.DataFrame(rows, columns=["calc_time", "funding_interval_hours", "funding_rate"]).astype(float)
        frame.index = pd.to_datetime(frame.pop("calc_time").astype("int64"), unit="ms", utc=True)
    else:
        frame = pd.DataFrame([r[:12] for r in rows], columns=KLINE_COLUMNS)
        stamp = frame.pop("open_time").astype("int64")
        stamp = stamp.where(stamp < 10 ** 14, stamp // 1000)
        frame.index = pd.to_datetime(stamp, unit="ms", utc=True)
        columns = ["open", "high", "low", "close", "volume", "quote_volume", "trades", "taker_buy_base_volume", "taker_buy_quote"]
        frame = frame[columns].astype(float)
    frame.index.name = "timestamp"
    return frame[~frame.index.duplicated(keep="first")].sort_index()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--first-month", default="2020-09")
    parser.add_argument("--last-month", default="2026-09")
    parser.add_argument("--allow-network", action="store_true")
    args = parser.parse_args()
    if not args.allow_network:
        sys.stderr.write("ERROR [NETWORK_DISABLED]: pass --allow-network to download public archives\n")
        return 2
    output = Path(args.output)
    if output.exists():
        sys.stderr.write(f"ERROR [OUTPUT_EXISTS]: {output}\n")
        return 2
    jobs = [(p, m, tf, ym, args.symbol) for p, m, tf in DATASETS for ym in months(args.first_month, args.last_month)]
    with cf.ThreadPoolExecutor(8) as pool:
        results = list(pool.map(fetch, jobs))
    groups = {}
    for result in results:
        if result["status"] == "OK":
            groups.setdefault((result["market"], result["tf"]), []).extend(result.pop("rows"))
    output.mkdir(parents=True)
    datasets = {}
    for (market, tf), rows in groups.items():
        frame = to_frame(tf, rows)
        path = output / f"{args.symbol}_{market}_{tf}.parquet"
        frame.to_parquet(path)
        missing = None
        if tf in FREQ:
            missing = len(pd.date_range(frame.index[0], frame.index[-1], freq=FREQ[tf])) - len(frame)
        datasets[path.name] = {"rows": len(frame), "start": str(frame.index[0]), "end": str(frame.index[-1]),
                               "missing_bars": missing, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    (output / "source_manifest.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    (output / "datasets.json").write_text(json.dumps(datasets, indent=1), encoding="utf-8")
    print(json.dumps(datasets, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
