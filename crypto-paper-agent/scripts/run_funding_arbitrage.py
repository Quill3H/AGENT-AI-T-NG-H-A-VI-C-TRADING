"""Local explicit spot/perpetual quote basket runner, no network."""
import argparse
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import pandas as pd
import yaml
from src.strategies.funding_arbitrage import FundingArbitrageSimulator
from src.research.artifacts import dataset_manifest,persist_basket

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--source',required=True);p.add_argument('--config',default=str(ROOT/'config/default_config.yaml'));p.add_argument('--output',required=True);p.add_argument('--notional',type=float);p.add_argument('--keep-open',action='store_true')
    args=p.parse_args();cfg=yaml.safe_load(Path(args.config).read_text(encoding='utf-8'));frame=pd.read_parquet(args.input)
    result=FundingArbitrageSimulator(cfg).simulate(frame,cfg['account']['initial_equity_usd'],args.notional,not args.keep_open)
    persist_basket(args.output,result,cfg,dataset_manifest(frame,args.source,'BTCUSDT','spot_and_perpetual','8h'))
    return 0
if __name__=='__main__':raise SystemExit(main())
