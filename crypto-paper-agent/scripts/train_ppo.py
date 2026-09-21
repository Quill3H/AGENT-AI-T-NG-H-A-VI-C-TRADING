"""PPO CPU train and holdout evaluation over explicit chronological partitions."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import pandas as pd
import yaml
from src.research.rl_env import train_ppo

def main():
    p=argparse.ArgumentParser();p.add_argument('--train',required=True);p.add_argument('--validation',required=True);p.add_argument('--holdout',required=True);p.add_argument('--config',required=True);p.add_argument('--output',required=True);p.add_argument('--timesteps',type=int,default=256);p.add_argument('--seed',type=int,default=42);p.add_argument('--timeframe',default='1m')
    args=p.parse_args();config=yaml.safe_load(Path(args.config).read_text(encoding='utf-8'))
    report=train_ppo(*(pd.read_parquet(x) for x in (args.train,args.validation,args.holdout)),config,args.output,args.timesteps,args.seed,args.timeframe)
    print(json.dumps(report,indent=2,default=str));return 0
if __name__=='__main__':raise SystemExit(main())
