"""Download a bounded public Binance Vision sample, with separate spot and perp.

This is a reproducibility utility, not a trading connector. No credentials.
Resampled OHLC bars are left-labelled and available only after their close.
"""

import argparse, hashlib, json, sys
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True)
    p.add_argument("--start", default="2024-01-01")
    p.add_argument("--days", type=int, default=3)
    p.add_argument("--retries", type=int, default=2)
    p.add_argument("--allow-network", action="store_true")
    args = p.parse_args()
    output = Path(args.output).resolve()
    if not args.allow_network:
        sys.stderr.write(
            "ERROR [NETWORK_DISABLED]: public archive download requires --allow-network.\n"
        )
        return 2
    if args.days < 1 or args.days > 7:
        sys.stderr.write("ERROR [INVALID_ARGUMENTS]: bounded sample requires 1..7 days.\n")
        return 2
    if args.retries < 0 or args.retries > 3:
        sys.stderr.write("ERROR [INVALID_ARGUMENTS]: retries must be between 0 and 3.\n")
        return 2
    if output.exists():
        sys.stderr.write(f"ERROR [OUTPUT_EXISTS]: output target already exists: {output}\n")
        return 2

    import pandas as pd
    from src.research.artifacts import dataset_manifest
    from src.data_layer.fetcher import funding_readiness

    records = []

    def download(url):
        last_error = None
        for attempt in range(args.retries + 1):
            try:
                content = urlopen(url, timeout=40).read()
                break
            except Exception as exc:
                last_error = exc
        else:
            raise RuntimeError(
                f"public archive unavailable after {args.retries + 1} attempts: {url}: {last_error}"
            ) from last_error
        with ZipFile(BytesIO(content)) as archive:
            name = next(n for n in archive.namelist() if n.endswith(".csv"))
            data = archive.read(name)
        records.append(
            {
                "url": url,
                "zip_sha256": hashlib.sha256(content).hexdigest(),
                "csv_sha256": hashlib.sha256(data).hexdigest(),
            }
        )
        return data

    dates = pd.date_range(args.start, periods=args.days, freq="D")
    frames = {}
    for market, path in [("spot", "spot"), ("perpetual", "futures/um")]:
        parts = []
        for day in dates:
            url = f"https://data.binance.vision/data/{path}/daily/klines/BTCUSDT/1m/BTCUSDT-1m-{day:%Y-%m-%d}.zip"
            raw = download(url)
            df = pd.read_csv(BytesIO(raw), header=None)
            if not str(df.iloc[0, 0]).isdigit():
                df = df.iloc[1:].copy()
            df = df.iloc[:, :6].astype(float)
            df.columns = ["timestamp", "open", "high", "low", "close", "volume"]
            # Binance spot moved to microsecond timestamps in 2025.
            unit = "us" if df.timestamp.iloc[0] > 1e14 else "ms"
            df.index = pd.to_datetime(df.pop("timestamp"), unit=unit, utc=True)
            df.index.name = "timestamp"
            parts.append(df)
        frames[market] = pd.concat(parts)
    funding_parts = []
    # Include prior month if sample starts at month boundary to preserve lagged observations.
    start = pd.Timestamp(args.start, tz="UTC")
    end = start + pd.Timedelta(days=args.days)
    months = pd.period_range(
        (start - pd.Timedelta(days=1)).tz_localize(None),
        end.tz_localize(None),
        freq="M",
    )
    for month in months:
        url = f"https://data.binance.vision/data/futures/um/monthly/fundingRate/BTCUSDT/BTCUSDT-fundingRate-{month}.zip"
        df = pd.read_csv(BytesIO(download(url)))
        df.index = pd.to_datetime(df.calc_time, unit="ms", utc=True)
        funding_parts.append(
            df[["last_funding_rate"]].rename(
                columns={"last_funding_rate": "funding_rate"}
            )
        )
    funding = pd.concat(funding_parts).sort_index()
    funding["funding_time"] = funding.index
    perp = frames["perpetual"]
    spot = frames["spot"]
    # Quote columns use opens, which are available at the labelled timestamp.
    merged = pd.merge_asof(
        perp, funding, left_index=True, right_index=True, direction="backward"
    )
    merged["funding_readiness"] = funding_readiness(merged)
    lag = pd.merge_asof(
        perp.iloc[:, :0],
        funding,
        left_index=True,
        right_index=True,
        direction="backward",
        allow_exact_matches=False,
    )
    basket = pd.DataFrame(
        {
            "spot_close": spot.open,
            "perp_close": perp.open,
            "observed_funding_rate": lag.funding_rate,
            "observed_funding_time": lag.funding_time,
            "funding_rate": merged.funding_rate,
            "funding_time": merged.funding_time,
            "funding_readiness": merged.funding_readiness,
        },
        index=perp.index,
    )
    datasets = {"1m": merged, "basket": basket}
    for tf in ("5m", "15m", "4h"):
        freq = tf.replace("m", "min") if tf.endswith("m") else tf
        bars = perp.resample(freq).agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        )
        bars = pd.merge_asof(
            bars, funding, left_index=True, right_index=True, direction="backward"
        )
        bars["funding_readiness"] = funding_readiness(bars)
        datasets[tf] = bars
    output.mkdir(parents=True, exist_ok=False)
    manifests = {}
    for name, df in datasets.items():
        df.to_parquet(output / f"{name}.parquet")
        manifests[name] = dataset_manifest(
            df,
            "Binance Vision public archives",
            "BTCUSDT",
            "spot_and_perpetual" if name == "basket" else "perpetual",
            "1m" if name == "basket" else name,
        )
    spot.to_parquet(output / "spot_1m.parquet")
    manifests["spot_1m"] = dataset_manifest(
        spot, "Binance Vision public archives", "BTCUSDT", "spot", "1m"
    )
    (output / "dataset_manifest.json").write_text(
        json.dumps(
            {
                "status": "AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED",
                "synthetic": False,
                "sources": records,
                "datasets": manifests,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps(manifests, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
