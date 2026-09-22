"""Four-strategy independent-account walk-forward runner (local Parquet only)."""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.cli_contract import fail, missing_paths, output_exists


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", required=True)
    p.add_argument("--config", default=str(ROOT / "config/default_config.yaml"))
    p.add_argument("--output", required=True)
    p.add_argument("--train-bars", type=int, required=True)
    p.add_argument("--test-bars", type=int, required=True)
    p.add_argument("--step-bars", type=int)
    p.add_argument("--source", required=True)
    args = p.parse_args()
    output = Path(args.output).resolve()
    if output_exists(output):
        return fail("OUTPUT_EXISTS", f"output target already exists: {output}")
    folder = Path(args.data_dir).resolve()
    config_path = Path(args.config).resolve()
    dataset_paths = [folder / f"{k}.parquet" for k in ("4h", "15m", "5m", "1m", "basket")]
    missing = missing_paths([config_path, *dataset_paths])
    if missing:
        return fail("DATASET_UNAVAILABLE", f"required file not found: {missing[0]}")
    try:
        import pandas as pd
        import yaml
        from src.research.workflow import run_comparison

        datasets = {
            key: pd.read_parquet(path)
            for key, path in zip(("4h", "15m", "5m", "1m", "basket"), dataset_paths)
        }
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        if not isinstance(config, dict):
            return fail("INVALID_CONFIG", "config root must be a mapping")
        run_comparison(
            datasets,
            config,
            output,
            args.train_bars,
            args.test_bars,
            args.step_bars,
            args.source,
        )
        return 0
    except Exception as exc:
        return fail("INVALID_INPUT", str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
