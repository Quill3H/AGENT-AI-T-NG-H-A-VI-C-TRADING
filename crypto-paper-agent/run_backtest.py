#!/usr/bin/env python3
"""
run_backtest.py - Entrypoint thực thi Backtest Giai đoạn 5
===========================================================
Chạy backtest chiến lược Trend Following end-to-end trên khung 4h/15m.
Tuân thủ nghiêm ngặt ANTIGRAVITY_STAGE_05_TASK.md:
- Hỗ trợ đầy đủ --config, --strategy, --start, --end, --no-fetch.
- Path độc lập với Current Working Directory (CWD).
- Fail rõ ràng nếu strategy chưa hỗ trợ hoặc cache thiếu khi dùng --no-fetch.
- KHÔNG kết nối API key thật, KHÔNG đặt lệnh thật.
"""
import argparse
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Thêm thư mục gốc vào sys.path để đảm bảo import đúng khi gọi từ bất kỳ đâu
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def _load_yaml(file_path: Path) -> Dict[str, Any]:
    """Đọc file YAML an toàn."""
    import yaml

    if not file_path.is_file():
        raise FileNotFoundError(f"Config file not found: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


def _deep_merge_dict(base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
    """Merge lồng nhau hai dictionary."""
    result = dict(base)
    for k, v in update.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge_dict(result[k], v)
        else:
            result[k] = v
    return result


def _config_reference(config_path: Path) -> str:
    """Return a truthful, portable config reference for reproduction metadata."""
    try:
        return config_path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return "<CONFIG_PATH>"


def _format_benchmark_note(metrics: Dict[str, Any]) -> str:
    """Describe the observed sample without embedding historical benchmark values."""
    total_trades = int(metrics.get("total_trades", 0))
    if total_trades == 0:
        return "insufficient data; no trade sample is available"
    return (
        f"observed {float(metrics.get('win_rate', 0.0)):.2f}% on N={total_trades}; "
        "small samples are not statistically generalizable"
    )


def _run_status(metrics: Dict[str, Any]) -> str:
    """Return the operator-facing outcome for a structurally valid run."""
    return "NO_TRADES" if int(metrics.get("total_trades", 0)) == 0 else "COMPLETED"


def _get_git_commit_sha() -> str:
    """Lấy commit SHA hiện tại qua git CLI."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception:
        return "UNKNOWN_GIT_COMMIT"


def main():
    parser = argparse.ArgumentParser(
        description="Crypto Futures Paper-Trading Research Agent (Backtest Runner - Stage 5)"
    )
    parser.add_argument(
        "--config",
        default="config/default_config.yaml",
        help="Path to YAML config file (default: config/default_config.yaml)",
    )
    parser.add_argument(
        "--strategy",
        default="trend_following",
        choices=["trend_following", "breakout_retest", "smc_liquidity_sweep", "funding_arbitrage", "all"],
        help="Strategy to backtest (default: trend_following)",
    )
    parser.add_argument(
        "--start",
        default=None,
        help="Override start date (YYYY-MM-DD or ISO8601 UTC)",
    )
    parser.add_argument(
        "--end",
        default=None,
        help="Override end date (YYYY-MM-DD or ISO8601 UTC)",
    )
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="Chỉ dùng cache local, không fetch dữ liệu mới từ network",
    )
    parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Explicitly allow public market-data network access",
    )
    parser.add_argument(
        "--force-close",
        action="store_true",
        default=True,
        help="Force close all open positions on finalize (default: True)",
    )
    parser.add_argument(
        "--output-dir",
        default="reports",
        help="Thư mục xuất báo cáo (default: reports)",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Mã định danh phiên backtest (default: tự động sinh run_{strategy}_{symbol}_{YYYYMMDD_HHMMSS})",
    )
    parser.add_argument(
        "--db-path",
        default=None,
        help="Đường dẫn file SQLite tuỳ chọn (mặc định: <output-dir>/<run-id>/trades.sqlite)",
    )
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Chạy backtest nhưng không xuất file báo cáo (artifacts)",
    )
    parser.add_argument("--basket-input", help="Explicit spot/perp quote Parquet for funding_arbitrage")
    parser.add_argument("--comparison-data-dir", help="Parquet directory for four-strategy walk-forward")
    parser.add_argument("--train-bars", type=int, default=1440)
    parser.add_argument("--test-bars", type=int, default=1440)
    parser.add_argument("--source", default="SUPPLIED_DATA_NOT_VERIFIED")
    args = parser.parse_args()

    if args.no_fetch and args.allow_network:
        sys.stderr.write(
            "ERROR [INVALID_ARGUMENTS]: --no-fetch and --allow-network are mutually exclusive.\n"
        )
        return 2
    # Offline/cache-only is the safe default. Network must be explicitly opted in.
    args.no_fetch = not args.allow_network

    # Validate special-mode paths before importing data/strategy modules or mutating output.
    if args.strategy == "funding_arbitrage" and not args.basket_input:
        sys.stderr.write(
            "ERROR: funding_arbitrage requires --basket-input with explicit spot/perp quotes.\n"
        )
        sys.exit(1)
    if args.strategy == "all" and not args.comparison_data_dir:
        sys.stderr.write("ERROR: all requires --comparison-data-dir.\n")
        return 2
    if args.strategy == "funding_arbitrage" and not Path(args.basket_input).is_file():
        sys.stderr.write(
            f"ERROR [DATASET_UNAVAILABLE]: required file not found: {Path(args.basket_input).resolve()}\n"
        )
        return 2
    if args.strategy == "all":
        comparison_dir = Path(args.comparison_data_dir).resolve()
        missing = [comparison_dir / f"{key}.parquet" for key in ("4h", "15m", "5m", "1m", "basket") if not (comparison_dir / f"{key}.parquet").is_file()]
        if missing:
            sys.stderr.write(
                f"ERROR [DATASET_UNAVAILABLE]: required file not found: {missing[0]}\n"
            )
            return 2

    import numpy as np
    import pandas as pd
    from src.backtest.engine import BacktestEngine
    from src.data_layer.cache_manager import has_complete_cache, load_from_cache
    from src.data_layer.fetcher import fetch_all, merge_ohlcv_with_oi_and_funding
    from src.report.generator import ReportGenerator
    from src.logging.trade_logger import compute_config_hash, snapshot_run_config
    from src.features.news_calendar import NewsCalendarFilter
    from src.execution.paper_broker import PaperBroker
    from src.strategies.trend_following import TrendFollowingStrategy
    from src.strategies.breakout_retest import BreakoutRetestStrategy
    from src.strategies.smc_liquidity_sweep import SMCLiquiditySweepStrategy

    # 1. Kiểm tra chiến lược được hỗ trợ (Test 13: fail rõ ràng nếu chưa hỗ trợ)

    # 2. Xử lý đường dẫn độc lập CWD
    config_path = Path(args.config)
    if not config_path.is_absolute():
        if config_path.is_file():
            config_path = config_path.resolve()
        else:
            config_path = (PROJECT_ROOT / config_path).resolve()

    if not config_path.is_file():
        sys.stderr.write(f"ERROR: Config file not found at: {config_path}\n")
        return 2

    # 3. Tải và hợp nhất cấu hình
    base_config = _load_yaml(config_path)
    if args.strategy in {"all", "funding_arbitrage"}:
        from src.research.artifacts import dataset_manifest, persist_basket
        output = Path(args.output_dir)
        if not output.is_absolute():
            output = PROJECT_ROOT / output
        if args.strategy == "all":
            from src.research.workflow import run_comparison
            directory = Path(args.comparison_data_dir)
            data = {k: pd.read_parquet(directory / f"{k}.parquet") for k in ("4h", "15m", "5m", "1m", "basket")}
            run_comparison(data, base_config, output, args.train_bars, args.test_bars, source=args.source)
        else:
            from src.strategies.funding_arbitrage import FundingArbitrageSimulator
            frame = pd.read_parquet(args.basket_input)
            simulator = FundingArbitrageSimulator(base_config)
            result = simulator.simulate(frame, base_config["account"]["initial_equity_usd"])
            persist_basket(output, result, simulator.persisted_config, dataset_manifest(frame, args.source, "BTCUSDT", "spot_and_perpetual", "1m"))
        return 0

    # Đọc thêm config riêng của chiến lược nếu có
    strat_cfg_path = PROJECT_ROOT / "config" / "strategies" / f"{args.strategy}.yaml"
    if strat_cfg_path.is_file():
        strat_cfg = _load_yaml(strat_cfg_path)
        config = _deep_merge_dict(strat_cfg, base_config)
    else:
        config = base_config
    config.setdefault("strategy", {})["name"] = args.strategy.upper()

    # Điều chỉnh raw_data_dir thành đường dẫn tuyệt đối
    raw_val = Path(config.get("data", {}).get("raw_data_dir", "data/raw"))
    if raw_val.is_absolute():
        raw_dir = raw_val.resolve()
    else:
        raw_dir = (PROJECT_ROOT / raw_val).resolve()
    config["data"]["raw_data_dir"] = str(raw_dir)
    calendar = Path(config.get("news_filter", {}).get("calendar_file", "data/news_calendar.csv"))
    if not calendar.is_absolute():
        calendar = PROJECT_ROOT / calendar
    config.setdefault("news_filter", {})["calendar_file"] = str(calendar)
    news_filter = NewsCalendarFilter(config)
    persisted_config = snapshot_run_config(config, news_filter)

    # 4. Xác định khoảng thời gian start và end
    start_str = args.start or config.get("data", {}).get("start_date", "2021-01-01")
    end_str = args.end or config.get("data", {}).get("end_date", "2023-12-31")

    try:
        start_dt = pd.to_datetime(start_str, utc=True)
        if len(start_str) == 10:  # Format YYYY-MM-DD
            start_dt = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    except Exception as e:
        sys.stderr.write(f"ERROR: Invalid start date format '{start_str}': {e}\n")
        return 2

    try:
        end_dt = pd.to_datetime(end_str, utc=True)
        if len(end_str) == 10:  # Format YYYY-MM-DD -> inclusive to end of day
            end_dt = end_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
    except Exception as e:
        sys.stderr.write(f"ERROR: Invalid end date format '{end_str}': {e}\n")
        sys.exit(1)

    if end_dt <= start_dt:
        sys.stderr.write(f"ERROR: end_date ({end_dt}) must be greater than start_date ({start_dt})\n")
        sys.exit(1)

    symbol = config.get("data", {}).get("futures_symbol", "BTCUSDT")
    exchange = config.get("data", {}).get("exchange", "binance")
    timeframes = [config.get("strategy", {}).get("timeframe_signal", "4h"),
                  config.get("strategy", {}).get("timeframe_execution", "15m")]

    # Xử lý output_dir, run_id và db_path (Stage 6)
    # Nguyên tắc: relative path phải resolve từ PROJECT_ROOT; absolute path giữ nguyên
    output_dir_val = Path(args.output_dir)
    if output_dir_val.is_absolute():
        output_dir = output_dir_val.resolve()
    else:
        output_dir = (PROJECT_ROOT / output_dir_val).resolve()

    if args.db_path:
        db_path_val = Path(args.db_path)
        if db_path_val.is_absolute():
            db_path = db_path_val.resolve()
        else:
            db_path = (PROJECT_ROOT / db_path_val).resolve()
    else:
        db_path = None

    # Run ID mặc định phải deterministic từ: code SHA + strategy + symbol + start/end + canonical config hash
    code_sha = _get_git_commit_sha()
    strat_clean = str(args.strategy).lower()
    sym_clean = symbol.replace("/", "").replace(":", "").lower()
    start_iso = start_dt.isoformat()
    end_iso = end_dt.isoformat()
    config_hash = compute_config_hash(persisted_config)

    run_seed = f"{code_sha}|{strat_clean}|{sym_clean}|{start_iso}|{end_iso}|{config_hash}"
    deterministic_hash = hashlib.sha256(run_seed.encode("utf-8")).hexdigest()[:12]

    run_id = args.run_id
    if not run_id:
        run_id = f"run_{strat_clean}_{sym_clean}_{deterministic_hash}"

    print("=" * 70)
    print(" CRYPTO FUTURES PAPER-TRADING RESEARCH AGENT - BACKTEST RUNNER")
    print(" OUT OF SCOPE: No real API keys, no live orders, pure simulation")
    print("=" * 70)
    print(f"Git Commit SHA : {_get_git_commit_sha()}")
    print(f"Config File    : {config_path}")
    print(f"Strategy       : {args.strategy}")
    print(f"Symbol         : {symbol}")
    print(f"Time Range UTC : {start_dt.isoformat()} -> {end_dt.isoformat()}")
    print(f"Cache Directory: {raw_dir}")
    print(f"Fetch Mode     : {'LOCAL CACHE ONLY (--no-fetch)' if args.no_fetch else 'AUTO FETCH/CACHE'}")
    print(f"Run ID         : {run_id}")
    print(f"Report Output  : {'DISABLED (--no-report)' if args.no_report else str(output_dir / run_id)}")
    print("=" * 70)

    # 5. Tải / Kiểm tra dữ liệu
    data: Dict[str, pd.DataFrame] = {}

    if args.no_fetch:
        print("\n[Data] Checking local parquet cache integrity...")
        for tf in timeframes:
            complete = has_complete_cache(
                base_dir=str(raw_dir),
                exchange=exchange,
                symbol=symbol,
                timeframe=tf,
                data_type="ohlcv",
                since=start_dt,
                until=end_dt,
            )
            if not complete:
                sys.stderr.write(
                    f"\nERROR: Incomplete local cache for {symbol} {tf} between {start_dt} and {end_dt}.\n"
                    f"Flag --no-fetch is active; network fetch is prohibited.\n"
                    f"Please download data or remove --no-fetch.\n"
                )
                sys.exit(1)

            # Load from cache
            ohlcv_df = load_from_cache(str(raw_dir), exchange, symbol, tf, "ohlcv", start_dt, end_dt)
            if ohlcv_df is None or ohlcv_df.empty:
                sys.stderr.write(f"\nERROR: Failed to load OHLCV data from cache for {tf}.\n")
                sys.exit(1)

            oi_df = load_from_cache(str(raw_dir), exchange, symbol, tf, "open_interest", start_dt, end_dt)
            if oi_df is None:
                oi_df = pd.DataFrame()

            funding_df = load_from_cache(str(raw_dir), exchange, symbol, "8h", "funding_rate", start_dt, end_dt)
            if funding_df is None or funding_df.empty:
                funding_df = load_from_cache(str(raw_dir), exchange, symbol, tf, "funding_rate", start_dt, end_dt)
            if funding_df is None:
                funding_df = pd.DataFrame()

            merged = merge_ohlcv_with_oi_and_funding(
                ohlcv_df=ohlcv_df,
                oi_df=oi_df,
                funding_df=funding_df,
                timeframe=tf,
                config=config,
            )
            filtered = merged.loc[start_dt:end_dt]
            if filtered.empty:
                sys.stderr.write(f"\nERROR: Filtered data for {tf} is empty in range {start_dt} to {end_dt}.\n")
                sys.exit(1)
            data[tf] = filtered
            print(f"  - Loaded {tf:4s}: {len(filtered):6d} bars ({filtered.index[0]} to {filtered.index[-1]})")
    else:
        print("\n[Data] Fetching / Loading data from cache and network...")
        try:
            fetched_data = fetch_all(
                symbol=config.get("data", {}).get("symbol", "BTC/USDT"),
                timeframes=timeframes,
                since=start_dt,
                until=end_dt,
                config=config,
                force_refresh=False,
            )
            for tf in timeframes:
                df_tf = fetched_data.get(tf, pd.DataFrame())
                filtered = df_tf.loc[start_dt:end_dt]
                if filtered.empty:
                    sys.stderr.write(f"\nERROR: Fetched data for {tf} is empty in range {start_dt} to {end_dt}.\n")
                    sys.exit(1)
                data[tf] = filtered
                print(f"  - Ready {tf:4s}: {len(filtered):6d} bars ({filtered.index[0]} to {filtered.index[-1]})")
        except Exception as e:
            sys.stderr.write(f"\nERROR: Failed to fetch/prepare data: {e}\n")
            sys.exit(1)

    # 6. Khởi tạo Strategy và BacktestEngine
    print(f"\n[Engine] Initializing {args.strategy} and BacktestEngine...")
    strategy_cls = {
        "trend_following": TrendFollowingStrategy,
        "breakout_retest": BreakoutRetestStrategy,
        "smc_liquidity_sweep": SMCLiquiditySweepStrategy,
    }[args.strategy]
    strategy = strategy_cls(config=config, symbol=symbol)
    engine = BacktestEngine(
        config=config,
        data_4h=data[timeframes[0]],
        data_15m=data[timeframes[1]],
        strategy=strategy,
        symbol=symbol,
        broker=PaperBroker(config=config, news_filter=news_filter),
    )

    # 7. Chạy Backtest
    print("\n[Engine] Running causal multi-timeframe backtest loop...")
    metrics = engine.run(force_close=args.force_close)
    metrics["run_status"] = _run_status(metrics)

    # 8. Xuất báo cáo kết quả chi tiết
    print("\n" + "=" * 70)
    print("                   BACKTEST EXECUTION REPORT")
    print("   [STATUS: AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED]")
    print("=" * 70)
    print(f"Git Commit SHA       : {_get_git_commit_sha()}")
    print(f"Run Status           : {metrics['run_status']}")
    print(f"Python Environment   : Python {sys.version.split()[0]} | pandas {pd.__version__} | numpy {np.__version__}")
    print(f"Strategy & Symbol    : {args.strategy} | {symbol}")
    print(f"Time Range 15m       : {metrics['start_time']} -> {metrics['end_time']}")
    print(f"Bars Processed       : 15m={metrics['bars_15m_count']}, 4h={metrics['bars_4h_count']}")
    print(f"Signals & Setups     : ARMED Setups={metrics.get('setup_count', 0)}, Candidates Generated={metrics.get('candidate_count', 0)}")
    print("-" * 70)
    print(f"Initial Balance      : {metrics['start_equity']:,.2f} USDT")
    print(f"Final Equity         : {metrics['final_equity']:,.2f} USDT")
    print(f"Total Return         : {metrics['total_return_pct']:+.2f}%")
    print(f"Max Drawdown         : -{metrics['max_drawdown_usd']:,.2f} USDT (-{metrics['max_drawdown_pct']:.2f}%)")
    sharpe_val = metrics.get("sharpe_ratio")
    sharpe_str = f"{sharpe_val:.2f}" if sharpe_val is not None else "N/A"
    pf_val = metrics.get("profit_factor")
    pf_str = f"{pf_val:.2f}" if pf_val is not None else "N/A (loss=0)"
    exp_r_val = metrics.get("expectancy_r")
    exp_r_str = f"{exp_r_val:+.2f} R" if exp_r_val is not None else "N/A"

    print(f"Daily Sharpe Ratio   : {sharpe_str}")
    print(f"Profit Factor        : {pf_str}")
    print(f"Expectancy (USD)     : {metrics.get('expectancy_usd', 0.0):+,.2f} USDT")
    print(f"Expectancy (R)       : {exp_r_str}")
    print("-" * 70)
    print(f"Total Orders Sent    : {metrics['submitted_orders_count']}")
    print(f"Orders Filled        : {metrics['orders_filled_count']}")
    print(f"Orders Rejected      : {metrics['orders_rejected_count']}")
    print(f"Orders Cancelled     : {metrics['orders_cancelled_count']}")
    if metrics['rejection_reasons']:
        print("Rejection Breakdown  :")
        for r_name, r_cnt in metrics['rejection_reasons'].items():
            print(f"  - {r_name}: {r_cnt}")
    print("-" * 70)
    print(f"Total Closed Trades  : {metrics['total_trades']} (Sample size N={metrics['total_trades']})")
    print(f"  - LONG Trades      : {metrics['long_trades_count']} (Win: {metrics['win_rate_long']:.1f}%)")
    print(f"  - SHORT Trades     : {metrics['short_trades_count']} (Win: {metrics['win_rate_short']:.1f}%)")
    print(f"Trade Outcomes       : {metrics['win_trades_count']} Win / {metrics['loss_trades_count']} Loss / {metrics['breakeven_trades_count']} Breakeven")
    benchmark_note = _format_benchmark_note(metrics)
    comparison = metrics["benchmark_comparison"]
    print(f"Win Rate (Overall)   : {metrics['win_rate']:.2f}% (Reference: {comparison['expected_min']:g}-{comparison['expected_max']:g}%; {benchmark_note})")
    print(f"Loss Rate (Overall)  : {metrics['loss_rate']:.2f}%")
    print(f"Win Rate (LONG)      : {metrics['win_rate_long']:.2f}%")
    print(f"Win Rate (SHORT)     : {metrics['win_rate_short']:.2f}%")
    print("-" * 70)
    print(f"Gross Price PnL      : {metrics['total_gross_pnl']:+,.2f} USDT")
    print(f"Trading Fees Paid    : -{metrics['total_fees']:,.2f} USDT")
    print(f"Funding Cashflow     : {metrics['total_funding_trades']:+,.2f} USDT")
    print(f"Net Realized PnL     : {metrics['total_net_pnl']:+,.2f} USDT")
    print(f"Exit Reasons         : {metrics['exit_reasons']}")
    print("-" * 70)
    cb_status = "HALTED" if engine.broker.circuit_breaker.is_halted else ("LOCKED" if engine.broker.circuit_breaker.is_locked else "ACTIVE")
    print(f"Circuit Breaker      : {cb_status} (Risk multiplier: {engine.broker.circuit_breaker.risk_multiplier:.2f})")
    print(f"CB Activations       : {metrics['circuit_breaker_lock_count']}")
    print(f"Risk Gate Rejections : {metrics['margin_rejections_count']} (Isolated margin gate check; distinct from circuit breaker)")
    print(f"Benchmark Comparison : {metrics['benchmark_comparison']['status']} (descriptive only)")
    print(f"Accounting Audit     : {'PASSED (wallet_balance matches ledger)' if metrics['accounting_invariants_verified'] else 'FAILED'}")
    print(f"Finalize Mode        : force_close={metrics['force_close_on_finalize']}")
    print("=" * 70)

    # 9. Ghi nhận sự kiện và xuất bộ artifacts báo cáo Giai đoạn 6
    if not args.no_report:
        print("\n[Report] Generating Stage 6 artifacts (SQLite, JSON, CSV, PNG, MD)...")
        metrics["code_commit_sha"] = code_sha
        metrics["no_fetch"] = args.no_fetch
        metrics["config_hash"] = config_hash
        # Keep artifacts portable: never embed author-machine absolute paths from
        # argv.  Exact data/config identity is carried separately by config_hash
        # and provenance fields.
        reproduction_parts = [
            "python", "run_backtest.py",
            "--config", _config_reference(config_path),
            "--strategy", args.strategy,
            "--start", str(args.start or config.get("data", {}).get("start_date", "2021-01-01")),
            "--end", str(args.end or config.get("data", {}).get("end_date", "2023-12-31")),
        ]
        if args.no_fetch:
            reproduction_parts.append("--no-fetch")
        metrics["reproduction_command"] = " ".join(reproduction_parts)

        generator = ReportGenerator(base_reports_dir=output_dir)
        artifacts = generator.generate_all(
            run_id=run_id,
            config=persisted_config,
            metrics=metrics,
            broker=engine.broker,
            custom_output_dir=output_dir,
            db_path=db_path,
        )
        report_folder = artifacts["summary.json"].parent
        print(f"  - Artifacts generated in: {report_folder}")
        for art_name, art_path in artifacts.items():
            print(f"    * {art_name}: {art_path.name}")

    print("\nBacktest completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
