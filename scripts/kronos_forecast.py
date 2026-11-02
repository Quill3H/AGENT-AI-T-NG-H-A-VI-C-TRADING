"""Pinned CPU Kronos advisory worker. No credentials, trading or network market data."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import time

SOURCE = '67b630e67f6a18c9e9be918d9b4337c960db1e9a'
MODEL = dict(model='NeoQuasar/Kronos-small', modelRevision='901c26c1332695a2a8f243eb2f37243a37bea320',
    tokenizerRevision='0e0117387f39004a9016484a186a908917e22426', sourceRevision=SOURCE, seed=123, sampleCount=3)
INTERVALS = {'15m':900000, '1h':3600000, '4h':14400000}
SYMBOLS = {'BTCUSDT','ETHUSDT','SOLUSDT','HYPEUSDT'}

def decode_input(item):
    raw = item['inputJson']
    if hashlib.sha256(raw.encode()).hexdigest() != item['inputSha256']:
        raise ValueError('Input hash mismatch')
    d = json.loads(raw)
    if (d['frame'] not in INTERVALS or d['intervalMs'] != INTERVALS[d['frame']]
            or d['venue'] != 'OKX' or d['symbol'] != item['symbol'] or d['symbol'] not in SYMBOLS
            or type(d['cycleAt']) is not int or d['cycleAt'] % d['intervalMs']
            or d['firstOpenTime'] != d['cycleAt'] - 40*d['intervalMs']
            or d['columns'] not in [['open','high','low','close','volume'],['open','high','low','close','volume','amount']]
            or len(d['rows']) != 40):
        raise ValueError('Invalid candle identity/coverage')
    for row in d['rows']:
        if (len(row) != len(d['columns']) or any(type(v) not in (int,float) or not math.isfinite(v) for v in row)
                or min(row[:4]) <= 0 or min(row[4:]) < 0 or row[1] < max(row[0],row[2],row[3])
                or row[2] > min(row[0],row[1],row[3])):
            raise ValueError('Invalid candle values')
    return d

def main():
    parser = argparse.ArgumentParser()
    for name in ['input','output','source','models']: parser.add_argument('--'+name, required=True, type=Path)
    args = parser.parse_args()
    revision = subprocess.check_output(['git','-C',str(args.source),'rev-parse','HEAD'], text=True).strip()
    dirty = subprocess.check_output(['git','-C',str(args.source),'status','--porcelain','--untracked-files=no'],text=True).strip()
    if revision != SOURCE or dirty: raise ValueError('Kronos source must be pinned and unmodified')
    sys.path.insert(0, str(args.source.resolve()))
    import numpy as np
    import pandas as pd
    import torch
    from huggingface_hub import snapshot_download
    from model import Kronos, KronosTokenizer, KronosPredictor

    payload = json.loads(args.input.read_text(encoding='utf-8-sig'))
    if payload.get('version') != 1 or not isinstance(payload.get('frames'),list) or len(payload['frames'])>3:
        raise ValueError('Invalid input envelope')
    torch.set_num_threads(2)
    artifacts = {}
    for name,repo,revision in [('Kronos-small',MODEL['model'],MODEL['modelRevision']),('Kronos-Tokenizer-base','NeoQuasar/Kronos-Tokenizer-base',MODEL['tokenizerRevision'])]:
        folder=args.models/name
        snapshot_download(repo_id=repo, revision=revision, local_dir=folder, allow_patterns=['config.json','model.safetensors'])
        for filename in ['config.json','model.safetensors']:
            artifacts[name+'/'+filename] = hashlib.sha256((folder/filename).read_bytes()).hexdigest()
    tokenizer=KronosTokenizer.from_pretrained(str(args.models/'Kronos-Tokenizer-base'),local_files_only=True)
    expected = json.loads(Path(__file__).with_name('kronos-model-manifest.json').read_text())
    if artifacts != expected: raise ValueError('Pinned model artifact hash mismatch')
    model=Kronos.from_pretrained(str(args.models/'Kronos-small'),local_files_only=True)
    predictor=KronosPredictor(model,tokenizer,device='cpu',max_context=512)
    frames=[]; errors=dict(payload.get('errors',{}))
    for frame in payload['frames']:
        try:
            if frame['frame'] not in INTERVALS or frame['venue']!='OKX': raise ValueError('Invalid frame')
            symbols=[]
            for item in frame['symbols']:
                d=decode_input(item)
                if d['frame']!=frame['frame'] or d['cycleAt']!=frame['cycleAt']: raise ValueError('Frame input mismatch')
                torch.manual_seed(MODEL['seed']); np.random.seed(MODEL['seed'])
                x=pd.Series(pd.to_datetime([d['firstOpenTime']+i*d['intervalMs'] for i in range(40)],unit='ms',utc=True))
                y=pd.Series(pd.to_datetime([d['cycleAt']+i*d['intervalMs'] for i in range(4)],unit='ms',utc=True))
                pred=predictor.predict(df=pd.DataFrame(d['rows'],columns=d['columns']),x_timestamp=x,y_timestamp=y,
                    pred_len=4,T=1.0,top_p=0.9,sample_count=3,verbose=False)
                if pred.shape!=(4,6) or not np.isfinite(pred.to_numpy()).all(): raise ValueError('Invalid model output')
                rows=[]
                for i,row in enumerate(pred.to_dict(orient='records')):
                    if min(row[k] for k in ['open','high','low','close'])<=0 or min(row['volume'],row['amount'])<0 or row['high']<max(row['open'],row['close'],row['low']) or row['low']>min(row['open'],row['close'],row['high']):
                        raise ValueError('Predicted OHLC geometry invalid; no repair/fallback')
                    rows.append(dict(openTime=d['cycleAt']+i*d['intervalMs'],closeTime=d['cycleAt']+(i+1)*d['intervalMs']-1,**row))
                symbols.append(dict(symbol=item['symbol'],inputSha256=item['inputSha256'],forecast=rows))
            frames.append(dict(version=1,**MODEL,frame=frame['frame'],venue='OKX',cycleAt=frame['cycleAt'],generatedAt=int(time.time()*1000),
                symbols=symbols,artifacts=artifacts,runtime=dict(torch=torch.__version__,numpy=np.__version__,pandas=pd.__version__),device='cpu'))
        except Exception as exc:
            errors[frame.get('frame','unknown')]=str(exc)[:500]
    args.output.write_text(json.dumps(dict(version=1,frames=frames,errors=errors),allow_nan=False),encoding='utf-8')
    print(json.dumps(dict(forecastFrames=[f['frame'] for f in frames],errors=errors)))

if __name__ == '__main__': main()
