#!/usr/bin/env python3
"""Bounded public ETH/BTC archives, Sep2020..Sep2026; no spot or trading client.

Download: --output <NEW> --allow-network
Offline: --output <NEW> --raw-dir <existing-raw> --manifest <source-manifest.json>
"""
import argparse
import concurrent.futures as cf
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
import urllib.request
import zipfile

import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.download_vision_history import get, months, to_frame


def download(job,raw_dir):
    symbol,tf,ym=job
    suffix=(f'fundingRate/{symbol}/{symbol}-fundingRate-{ym}.zip' if tf=='funding'
            else f'klines/{symbol}/{tf}/{symbol}-{tf}-{ym}.zip')
    url='https://data.binance.vision/data/futures/um/monthly/'+suffix
    raw=get(url,tries=2)
    checksum=get(url+'.CHECKSUM',tries=2)
    if raw is None or checksum is None:
        raise ValueError(f'SOURCE_UNAVAILABLE: {url}')
    digest=hashlib.sha256(raw).hexdigest()
    if digest!=checksum.decode().split()[0]:
        raise ValueError(f'CHECKSUM_MISMATCH: {url}')
    path=raw_dir/url.rsplit('/',1)[1]
    path.write_bytes(raw)
    path.with_suffix('.zip.CHECKSUM').write_bytes(checksum)
    return dict(symbol=symbol,timeframe=tf,month=ym,url=url,sha256=digest,status='OK')


def read_archive(raw_dir,entry):
    if entry.get('status')!='OK':
        raise ValueError('SOURCE_UNAVAILABLE')
    name=entry['url'].rsplit('/',1)[1]
    if not name.endswith('.zip') or name in ('.','..'):
        raise ValueError('invalid archive name')
    path=Path(raw_dir)/name
    raw=path.read_bytes()
    expected=path.with_suffix('.zip.CHECKSUM').read_text().split()[0]
    digest=hashlib.sha256(raw).hexdigest()
    if digest!=expected or digest!=entry['sha256']:
        raise ValueError(f'CHECKSUM_MISMATCH: {name}')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if len(z.namelist())!=1:
            raise ValueError('ambiguous ZIP members')
        text=z.read(z.namelist()[0]).decode('utf-8')
    return [row for row in csv.reader(io.StringIO(text)) if row and row[0][:1].isdigit()]


def normalize(raw_dir,manifest,output):
    dataset={}
    expected_months=set(months('2020-09','2026-09'))
    for s in ['ETHUSDT','BTCUSDT']:
        for tf in ['4h','15m','funding']:
            entries=[e for e in manifest if e['symbol']==s and e['timeframe']==tf]
            if len(entries)!=len(expected_months) or {e['month'] for e in entries}!=expected_months:
                raise ValueError(f'SOURCE_UNAVAILABLE: incomplete monthly manifest {s} {tf}')
            rows=[]
            for entry in sorted(entries,key=lambda x:x['month']):
                rows.extend(read_archive(raw_dir,entry))
            # The legacy converter deduplicates; duplicates must instead stop this study.
            stamps=[row[0] for row in rows]
            if len(stamps)!=len(set(stamps)):
                raise ValueError(f'DUPLICATE_SOURCE_TIMESTAMP: {s} {tf}')
            frame=to_frame(tf,rows)
            if tf!='funding':
                step='4h' if tf=='4h' else '15min'
                if not frame.index.equals(pd.date_range(frame.index[0],frame.index[-1],freq=step)):
                    raise ValueError(f'DATA_GAP: {s} {tf}')
            path=output/f'{s}_perp_{tf}.parquet'
            frame.to_parquet(path)
            dataset[path.name]=dict(rows=len(frame),start=str(frame.index[0]),end=str(frame.index[-1]),
                                    sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    (output/'datasets.json').write_text(json.dumps(dataset,indent=2),encoding='utf-8')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    parser.add_argument('--allow-network',action='store_true')
    parser.add_argument('--raw-dir')
    parser.add_argument('--manifest')
    args=parser.parse_args(argv)
    output=Path(args.output)
    if output.exists():
        print('ERROR [OUTPUT_EXISTS]',file=sys.stderr)
        return 2
    if not args.raw_dir and not args.allow_network:
        print('ERROR [NETWORK_DISABLED]',file=sys.stderr)
        return 2
    if bool(args.raw_dir)!=bool(args.manifest):
        print('ERROR [INVALID_ARGUMENTS]: raw-dir requires manifest',file=sys.stderr)
        return 2
    output.mkdir(parents=True)
    try:
        if args.raw_dir:
            raw_dir=Path(args.raw_dir)
            manifest=json.loads(Path(args.manifest).read_text(encoding='utf-8'))
        else:
            raw_dir=output/'raw'
            raw_dir.mkdir()
            jobs=[(s,tf,ym) for s in ['ETHUSDT','BTCUSDT'] for tf in ['4h','15m','funding']
                  for ym in months('2020-09','2026-09')]
            with cf.ThreadPoolExecutor(8) as pool:
                manifest=list(pool.map(lambda job:download(job,raw_dir),jobs))
        (output/'source_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        normalize(raw_dir,manifest,output)
        print(f'Prepared {len(manifest)} verified source archives',flush=True)
        return 0
    except Exception as error:
        (output/'FAILED.txt').write_text(f'{type(error).__name__}: {error}',encoding='utf-8')
        print(f'ERROR [DATASET_UNAVAILABLE]: {error}',file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
