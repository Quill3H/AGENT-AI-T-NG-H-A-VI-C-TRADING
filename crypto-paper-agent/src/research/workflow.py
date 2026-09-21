"""Shared data interval, four separate accounts, no fitted rule parameters."""

from copy import deepcopy
from pathlib import Path
import pandas as pd
from src.backtest.engine import BacktestEngine
from src.execution.paper_broker import PaperBroker
from src.features.news_calendar import NewsCalendarFilter
from src.strategies.trend_following import TrendFollowingStrategy
from src.strategies.breakout_retest import BreakoutRetestStrategy
from src.strategies.smc_liquidity_sweep import SMCLiquiditySweepStrategy
from src.strategies.funding_arbitrage import FundingArbitrageSimulator
from src.research.comparison import walk_forward_splits, compare_metrics
from src.research.artifacts import (
    dataset_manifest,
    persist_research_run,
    persist_basket,
)
from src.report.generator import ReportGenerator
from src.data_layer.cache_manager import timeframe_to_timedelta
from src.research.validation import time_index
from src.logging.trade_logger import snapshot_run_config


def run_comparison(
    datasets,
    config,
    output,
    train_bars,
    test_bars,
    step_bars=None,
    source="supplied_dataset",
):
    required = {"4h", "15m", "5m", "1m", "basket"}
    if required.difference(datasets):
        raise ValueError(f"missing datasets: {sorted(required.difference(datasets))}")
    for key, frame in datasets.items():
        time_index(frame)
    if any(f.empty for f in datasets.values()):
        raise ValueError("empty comparison dataset")
    common_start = max(f.index[0] for f in datasets.values())
    # Inclusive end of coverage; OHLC is timestamped at open, quotes at availability.
    common_end = min(f.index[-1] for f in datasets.values())
    anchor = datasets["1m"].loc[common_start:common_end]
    folds = walk_forward_splits(anchor, train_bars, test_bars, step_bars)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    news = NewsCalendarFilter(config)
    frozen_config = snapshot_run_config(config, news)
    rows = []
    summary = {}
    manifests = {
        k: dataset_manifest(
            v,
            source,
            "BTCUSDT",
            "spot_and_perpetual" if k == "basket" else "perpetual",
            (
                (
                    "1m"
                    if v.index.to_series().diff().dropna().min() < pd.Timedelta(hours=8)
                    else "8h"
                )
                if k == "basket"
                else k
            ),
        )
        for k, v in datasets.items()
    }
    strategies = {
        "trend_following": (TrendFollowingStrategy, "4h", "15m"),
        "breakout_retest": (BreakoutRetestStrategy, "4h", "15m"),
        "smc_liquidity_sweep": (SMCLiquiditySweepStrategy, "5m", "1m"),
    }
    root = Path(__file__).resolve().parents[2]
    from run_backtest import _deep_merge_dict, _load_yaml

    for fold in folds:
        start = fold["test_start"]
        end = fold["test_end"] + pd.Timedelta(minutes=1)
        for name in (*strategies, "funding_arbitrage"):
            strategy_config = _load_yaml(
                root / "config" / "strategies" / f"{name}.yaml"
            )
            cfg = _deep_merge_dict(strategy_config, config)
            cfg.setdefault("strategy", {})["name"] = name.upper()
            folder = output / f"fold_{fold['fold']:03d}" / name
            if name == "funding_arbitrage":
                quotes = datasets["basket"].loc[
                    (datasets["basket"].index >= start)
                    & (datasets["basket"].index < end)
                ]
                if len(quotes) < 2:
                    raise ValueError(
                        "OOS fold needs at least two basket quotes; enlarge test window"
                    )
                simulator = FundingArbitrageSimulator(cfg, news_filter=news)
                result = simulator.simulate(
                    quotes, cfg.get("account", {}).get("initial_equity_usd", 10000)
                )
                metrics = result.metrics()
                persist_basket(
                    folder,
                    result,
                    simulator.persisted_config,
                    dataset_manifest(
                        quotes,
                        source,
                        "BTCUSDT",
                        "spot_and_perpetual",
                        "1m" if len(quotes) > test_bars / 2 else "8h",
                    ),
                )
                bars = len(quotes)
            else:
                cls, slow_tf, fast_tf = strategies[name]
                fast = datasets[fast_tf]
                fast = fast.loc[
                    (fast.index >= start)
                    & (
                        fast.index + pd.Timedelta(timeframe_to_timedelta(fast_tf))
                        <= end
                    )
                ]
                slow = datasets[slow_tf]
                slow = slow.loc[
                    (slow.index >= fold["train_start"])
                    & (
                        slow.index + pd.Timedelta(timeframe_to_timedelta(slow_tf))
                        <= end
                    )
                ]
                if fast.empty or slow.empty:
                    raise ValueError(f"{name} has insufficient OOS coverage")
                strategy = cls(cfg)
                # Warm features use earlier history; warm-up setups/positions are not carried.
                engine = BacktestEngine(
                    cfg,
                    slow,
                    fast,
                    strategy,
                    broker=PaperBroker(cfg, news_filter=deepcopy(news)),
                )
                metrics = engine.run(force_close=True)
                bars = len(fast)
                metrics["no_fetch"] = True
                frozen = snapshot_run_config(cfg, engine.broker.news_filter)
                ReportGenerator(folder).generate_all(
                    f"fold_{fold['fold']}_{name}",
                    frozen,
                    metrics,
                    engine.broker,
                    custom_output_dir=folder,
                )
            row = {
                "fold": fold["fold"],
                "strategy": name,
                "test_start": start.isoformat(),
                "test_end_exclusive": end.isoformat(),
                "total_net_pnl": metrics["total_net_pnl"],
                "sample_count": metrics["total_trades"],
                "bars": bars,
                "initial_capital": cfg.get("account", {}).get(
                    "initial_equity_usd", 10000
                ),
            }
            rows.append(row)
            agg = summary.setdefault(
                name, {"total_net_pnl": 0.0, "sample_count": 0, "fold_count": 0}
            )
            agg["total_net_pnl"] += row["total_net_pnl"]
            agg["sample_count"] += int(row["sample_count"])
            agg["fold_count"] += 1
    initial = config.get("account", {}).get("initial_equity_usd", 10000)
    for agg in summary.values():
        agg["mean_fold_return_pct"] = (
            100 * agg["total_net_pnl"] / (initial * agg["fold_count"])
        )
    table = compare_metrics(summary)
    pd.DataFrame(rows).to_csv(output / "fold_reports.csv", index=False)
    table.to_csv(output / "aggregate_oos.csv", index=False)
    report = {
        "status": "AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED",
        "account_mode": "independent_reset_accounts_per_fold",
        "aggregation": "sum_of_fold_pnl_and_mean_fold_return; not portfolio equity or compounded return",
        "fit_policy": "fixed rule configs; validation reserved and unused; no parameter search",
        "boundary_policy": "past-only indicator warm-up; no warm-up positions; force-close with costs each test end",
        "common_start": common_start.isoformat(),
        "common_end": common_end.isoformat(),
        "datasets": manifests,
        "folds": rows,
        "aggregate": table.to_dict(orient="records"),
    }
    persist_research_run(output, "walk_forward", frozen_config, report)
    return report
