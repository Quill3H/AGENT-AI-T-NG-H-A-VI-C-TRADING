"""Four-strategy independent-account walk-forward runner (local Parquet only)."""
import argparse
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import pandas as pd
import yaml
from src.research.workflow import run_comparison

def main():
    p=argparse.ArgumentParser();p.add_argument('--data-dir',required=True);p.add_argument('--config',default=str(ROOT/'config/default_config.yaml'));p.add_argument('--output',required=True);p.add_argument('--train-bars',type=int,required=True);p.add_argument('--test-bars',type=int,required=True);p.add_argument('--step-bars',type=int);p.add_argument('--source',required=True)
    args=p.parse_args();folder=Path(args.data_dir)
    datasets={k:pd.read_parquet(folder/f'{k}.parquet') for k in ('4h','15m','5m','1m','basket')}
    config=yaml.safe_load(Path(args.config).read_text(encoding='utf-8'))
    run_comparison(datasets,config,args.output,args.train_bars,args.test_bars,args.step_bars,args.source)
    return 0
if __name__=='__main__':raise SystemExit(main())
