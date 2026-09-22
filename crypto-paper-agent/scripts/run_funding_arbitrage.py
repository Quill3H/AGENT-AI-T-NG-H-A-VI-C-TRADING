"""Local explicit spot/perpetual quote basket runner, no network."""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.cli_contract import fail, missing_paths, output_exists


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--source", required=True)
    p.add_argument("--config", default=str(ROOT / "config/default_config.yaml"))
    p.add_argument("--output", required=True)
    p.add_argument("--notional", type=float)
    p.add_argument("--keep-open", action="store_true")
    args = p.parse_args()
    output = Path(args.output).resolve()
    if output_exists(output):
        return fail("OUTPUT_EXISTS", f"output target already exists: {output}")
    input_path = Path(args.input).resolve()
    config_path = Path(args.config).resolve()
    missing = missing_paths([input_path, config_path])
    if missing:
        return fail("DATASET_UNAVAILABLE", f"required file not found: {missing[0]}")
    try:
        import pandas as pd
        import yaml
        from src.strategies.funding_arbitrage import FundingArbitrageSimulator
        from src.research.artifacts import dataset_manifest, persist_basket

        cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        if not isinstance(cfg, dict):
            return fail("INVALID_CONFIG", "config root must be a mapping")
        frame = pd.read_parquet(input_path)
        simulator = FundingArbitrageSimulator(cfg)
        result = simulator.simulate(
            frame,
            cfg["account"]["initial_equity_usd"],
            args.notional,
            not args.keep_open,
        )
        persist_basket(
            output,
            result,
            simulator.persisted_config,
            dataset_manifest(
                frame, args.source, "BTCUSDT", "spot_and_perpetual", "1m"
            ),
        )
        return 0
    except Exception as exc:
        return fail("INVALID_INPUT", str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
