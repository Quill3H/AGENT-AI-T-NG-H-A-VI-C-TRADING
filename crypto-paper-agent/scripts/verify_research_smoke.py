"""Persist nonempty synthetic E2E evidence and optional public-data evaluations."""

import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pandas as pd
import yaml
from src.research.synthetic import (
    smc_frames,
    smc_config,
    breakout_frames,
    comparison_datasets,
)
from src.strategies.smc_liquidity_sweep import SMCLiquiditySweepStrategy
from src.strategies.breakout_retest import BreakoutRetestStrategy
from src.backtest.engine import BacktestEngine
from src.report.generator import ReportGenerator
from src.research.artifacts import dataset_manifest, persist_research_run
from src.research.workflow import run_comparison
from src.research.rl_env import train_ppo
from src.data_layer.cache_manager import save_to_cache


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True)
    p.add_argument("--public-dir")
    args = p.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    results = {}
    for kind in ("smc", "breakout"):
        for short in (False, True):
            name = f'{kind}_{"short" if short else "long"}'
            signal, execution = (
                smc_frames(short) if kind == "smc" else breakout_frames(short)
            )
            cfg = (
                smc_config()
                if kind == "smc"
                else {
                    "strategy": {
                        "name": "BREAKOUT_RETEST",
                        "timeframe_signal": "4h",
                        "timeframe_execution": "15m",
                    },
                    "breakout": {"lookback_bars": 3},
                    "account": {"initial_equity_usd": 10000},
                }
            )
            cls = SMCLiquiditySweepStrategy if kind == "smc" else BreakoutRetestStrategy
            engine = BacktestEngine(cfg, signal, execution, cls(cfg))
            metrics = engine.run()
            if metrics["orders_filled_count"] < 1 or metrics["total_trades"] < 1:
                raise AssertionError(f"{name} failed nonempty trade gate")
            metrics["no_fetch"] = True
            folder = out / "synthetic" / name
            ReportGenerator(folder).generate_all(
                name, cfg, metrics, engine.broker, custom_output_dir=folder
            )
            manifests = {
                tf: dataset_manifest(
                    frame, "SYNTHETIC_TEST", "BTCUSDT", "perpetual", tf
                )
                for tf, frame in [
                    (cfg["strategy"]["timeframe_signal"], signal),
                    (cfg["strategy"]["timeframe_execution"], execution),
                ]
            }
            persist_research_run(folder, "dataset", cfg, {"datasets": manifests})
            results[name] = {
                "fills": metrics["orders_filled_count"],
                "realizations": metrics["total_trades"],
                "total_net_pnl": metrics["total_net_pnl"],
            }
            # Hermetic CLI fixture paths, explicitly outside persisted reports.
            cache = out / "cli-cache" / name
            for tf, frame in (
                (cfg["strategy"]["timeframe_signal"], signal),
                (cfg["strategy"]["timeframe_execution"], execution),
            ):
                save_to_cache(
                    frame[["open", "high", "low", "close", "volume"]],
                    str(cache),
                    "binance",
                    "BTCUSDT",
                    tf,
                    "ohlcv",
                )
            funding = (
                execution.loc[
                    execution.index.isin(execution.funding_time), ["funding_rate"]
                ]
                if "funding_time" in execution
                else pd.DataFrame({"funding_rate": [0.0002]}, index=execution.index[:1])
            )
            save_to_cache(
                funding, str(cache), "binance", "BTCUSDT", "8h", "funding_rate"
            )
            cfg["data"] = {
                "raw_data_dir": "<RAW_DATA_DIR>",
                "start_date": signal.index[0].isoformat(),
                "end_date": execution.index[-1].isoformat(),
            }
            (out / f"{name}.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    synthetic = run_comparison(
        comparison_datasets(),
        {"account": {"initial_equity_usd": 10000}},
        out / "synthetic" / "walk",
        1440,
        1440,
        source="SYNTHETIC_TEST",
    )
    results["synthetic_walk"] = synthetic["aggregate"]
    if args.public_dir:
        public = Path(args.public_dir)
        datasets = {
            k: pd.read_parquet(public / f"{k}.parquet")
            for k in ("4h", "15m", "5m", "1m", "basket")
        }
        cfg = yaml.safe_load(
            (ROOT / "config/default_config.yaml").read_text(encoding="utf-8")
        )
        cfg["research"] = {"source": "Binance Vision public archives"}
        real = run_comparison(
            datasets,
            cfg,
            out / "public" / "walk",
            1440,
            1440,
            source="Binance Vision public archives",
        )
        results["public_walk"] = real["aggregate"]
        f = datasets["1m"]
        ppo = train_ppo(
            f.iloc[:1440],
            f.iloc[1440:2880],
            f.iloc[2880:],
            cfg,
            out / "public" / "ppo",
            total_timesteps=256,
        )
        results["ppo"] = {
            k: v
            for k, v in ppo.items()
            if k
            in (
                "actual_timesteps",
                "save_load_equal",
                "no_trade",
                "rule_based_ma_5_20",
                "final_holdout",
            )
        }
        for item in results["ppo"].values():
            if isinstance(item, dict):
                item.pop("actions", None)
    (out / "smoke_results.json").write_text(
        json.dumps(results, indent=2, allow_nan=False), encoding="utf-8"
    )
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
