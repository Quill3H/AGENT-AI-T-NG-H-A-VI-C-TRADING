"""Bounded, offline G0 replay with raw synthetic inputs and portable checksums.

Run from any CWD. All inputs are synthetic, not market observations/performance.
Output must be new/empty; a failing run never produces a success result manifest.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[variable] = "2"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd
from src.backtest.engine import BacktestEngine
from src.report.generator import ReportGenerator
from src.research.artifacts import serializable
from src.research.synthetic import smc_config, smc_frames
from src.strategies.funding_arbitrage import FundingArbitrageSimulator
from src.strategies.smc_liquidity_sweep import SMCLiquiditySweepStrategy


def write_json(path, value):
    path.write_text(
        json.dumps(serializable(value), indent=2, allow_nan=False), encoding="utf-8"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    output = parser.parse_args().output_dir.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("output-dir must be empty; preserve prior evidence")
    output.mkdir(parents=True, exist_ok=True)
    inputs = output / "inputs"
    inputs.mkdir()
    sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    result = {
        "code_commit_sha": sha,
        "verification_status": "AUTHOR_TESTED / INDEPENDENT_REVIEW_PENDING",
        "source": "synthetic fixtures; no downloaded market data",
        "cases": {},
    }
    for direction in ("LONG", "SHORT"):
        signal, execution = smc_frames(short=direction == "SHORT")
        cfg = smc_config()
        signal.to_parquet(inputs / f"{direction}-signal.parquet")
        execution.to_parquet(inputs / f"{direction}-execution.parquet")
        write_json(inputs / f"{direction}-config.json", cfg)
        engine = BacktestEngine(cfg, signal, execution, SMCLiquiditySweepStrategy(cfg))
        metrics = engine.run(force_close=True)
        if metrics["total_trades"] != 1 or len(engine.broker.trade_history) != 3:
            raise AssertionError(
                "G0 replay expected one completed position and three raw slices"
            )
        if any(t.direction.value != direction for t in engine.broker.trade_history):
            raise AssertionError("G0 replay did not execute the requested side")
        metrics.update(
            no_fetch=True,
            code_commit_sha=sha,
            reproduction_command="python scripts/verify_g0_replay.py --output-dir <NEW_DIRECTORY>",
        )
        ReportGenerator(base_reports_dir=output).generate_all(
            direction, cfg, metrics, engine.broker
        )
        result["cases"][direction] = {
            "completed_trades": metrics["total_trades"],
            "realization_slices": len(engine.broker.trade_history),
            "net_pnl": metrics["total_net_pnl"],
            "accounting_verified": metrics["accounting_invariants_verified"],
        }

    idx = pd.to_datetime(
        [
            "2024-01-01T00:00Z",
            "2024-01-01T01:00Z",
            "2024-01-01T08:00Z",
            "2024-01-01T16:00Z",
        ]
    )
    frame = pd.DataFrame(
        dict(
            spot_close=100.0,
            perp_close=100.0,
            observed_funding_rate=0.0002,
            observed_funding_time=idx,
            funding_rate=0.0002,
            funding_time=idx,
            funding_readiness=True,
        ),
        index=idx,
    )
    cfg = {"fees": {"taker_pct": 0.0, "slippage_pct": 0.0}}
    frame.to_parquet(inputs / "basket-valid.parquet")
    write_json(inputs / "basket-config.json", cfg)
    valid = FundingArbitrageSimulator(cfg).simulate(
        frame, 10000.0, 4000.0, force_close=False
    )
    if abs(valid.funding_cashflow - 1.6) > 1e-10:
        raise AssertionError(
            "distinct source events did not reconcile to hand oracle1.6"
        )
    write_json(output / "basket-valid-ledger.json", valid.ledger)
    frame.loc[idx[-1], "funding_time"] = idx[-2]
    frame.to_parquet(inputs / "basket-reused-source.parquet")
    sim = FundingArbitrageSimulator(cfg)
    try:
        sim.simulate(frame, 10000.0, 4000.0)
    except ValueError as exc:
        if "FUNDING_SOURCE_EVENT_MISMATCH" not in str(exc):
            raise
        if sim.cb.current_timestamp is not None:
            raise AssertionError("rejected basket mutated breaker clock") from exc
        result["funding"] = {
            "reused_source_rejected": True,
            "reason": str(exc),
            "distinct_settlement_cashflow": valid.funding_cashflow,
        }
    else:
        raise AssertionError("reused source event was not rejected")
    write_json(output / "g0_replay.json", result)
    write_json(
        output / "manifest.json",
        {
            "code_commit_sha": sha,
            "data_kind": "SYNTHETIC",
            "network_requests": 0,
            "market_raw_files": [],
            "market_performance": "NOT_EVALUATED",
            "source_file": "crypto-paper-agent/src/research/synthetic.py",
            "source_sha256": hashlib.sha256(
                (ROOT / "src/research/synthetic.py").read_bytes()
            ).hexdigest(),
            "input_files": [
                p.relative_to(output).as_posix() for p in sorted(inputs.iterdir())
            ],
            "normalization": "No fetch/forward-fill; exact generated UTC frames saved before replay",
        },
    )
    checksums = {
        p.relative_to(output).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(output.rglob("*"))
        if p.is_file()
    }
    write_json(output / "checksums.json", checksums)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
