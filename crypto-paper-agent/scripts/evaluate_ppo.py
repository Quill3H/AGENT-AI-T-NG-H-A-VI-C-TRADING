"""Load PPO plus its train-only scaler and evaluate without training."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.cli_contract import fail, missing_paths, output_exists


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeframe", default="1m")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    output = Path(args.output).resolve()
    if output_exists(output):
        return fail("OUTPUT_EXISTS", f"output target already exists: {output}")
    model_dir = Path(args.model_dir).resolve()
    input_path = Path(args.input).resolve()
    config_path = Path(args.config).resolve()
    required = [
        input_path,
        config_path,
        model_dir / "ppo_model.zip",
        model_dir / "ppo.report.json",
        model_dir / "manifest.json",
    ]
    missing = missing_paths(required)
    if missing:
        return fail("DATASET_UNAVAILABLE", f"required file not found: {missing[0]}")
    try:
        import pandas as pd
        import yaml
        from src.research.rl_env import evaluate_saved_ppo

        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        if not isinstance(config, dict):
            return fail("INVALID_CONFIG", "config root must be a mapping")
        report = evaluate_saved_ppo(
            model_dir,
            pd.read_parquet(input_path),
            config,
            output,
            args.timeframe,
            args.seed,
        )
        print(json.dumps(report, indent=2))
        return 0
    except Exception as exc:
        return fail("INVALID_INPUT", str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
