"""PPO CPU train and holdout evaluation over explicit chronological partitions."""

import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.cli_contract import fail, missing_paths, output_exists


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--train", required=True)
    p.add_argument("--validation", required=True)
    p.add_argument("--holdout", required=True)
    p.add_argument("--config", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--timesteps", type=int, default=256)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--timeframe", default="1m")
    args = p.parse_args()
    output = Path(args.output).resolve()
    if output_exists(output):
        return fail("OUTPUT_EXISTS", f"output target already exists: {output}")
    paths = [Path(value).resolve() for value in (args.train, args.validation, args.holdout, args.config)]
    missing = missing_paths(paths)
    if missing:
        return fail("DATASET_UNAVAILABLE", f"required file not found: {missing[0]}")
    try:
        import pandas as pd
        import yaml
        from src.research.rl_env import train_ppo

        config = yaml.safe_load(paths[3].read_text(encoding="utf-8"))
        if not isinstance(config, dict):
            return fail("INVALID_CONFIG", "config root must be a mapping")
        report = train_ppo(
            *(pd.read_parquet(path) for path in paths[:3]),
            config,
            output,
            args.timesteps,
            args.seed,
            args.timeframe,
        )
        print(json.dumps(report, indent=2, default=str))
        return 0
    except Exception as exc:
        return fail("INVALID_INPUT", str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
