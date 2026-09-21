"""Load PPO plus its train-only scaler and evaluate without training."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pandas as pd
import yaml
from src.research.rl_env import evaluate_saved_ppo


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeframe", default="1m")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    report = evaluate_saved_ppo(
        args.model_dir,
        pd.read_parquet(args.input),
        yaml.safe_load(Path(args.config).read_text(encoding="utf-8")),
        args.output,
        args.timeframe,
        args.seed,
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
