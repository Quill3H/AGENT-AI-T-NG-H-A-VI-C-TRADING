"""
src/report/generator.py - Multi-format Report Generator
======================================================
Tạo lập tự động bộ artifacts hoàn chỉnh cho mỗi phiên backtest/paper trading
dưới thư mục `reports/<run_id>/`:
1. summary.json      - Tổng hợp toàn bộ metrics & provenance (JSON chuẩn RFC 8259, allow_nan=False, fail-closed)
2. summary.md        - Báo cáo Markdown chi tiết kèm accounting audit, benchmark caveats & disclosures
3. trades.json       - Danh sách trade chuẩn hoá theo Master Spec Section 4.6
4. equity_curve.csv  - Chuỗi dữ liệu equity, balance và drawdown theo thời gian
5. equity_curve.png  - Biểu đồ 2 khung (Equity Curve + Underwater Drawdown)
6. trades.sqlite     - File SQLite cơ sở dữ liệu lưu toàn bộ sự kiện của run
"""
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, Dict, List, Optional, Union
from loguru import logger
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from src.execution.order_models import (
    AccountSnapshot,
    ExitReason,
    OrderExecutionRecord,
    TradeRecord,
    _ensure_utc,
)
from src.logging.trade_logger import TradeLogger, _clean_float, _to_epoch, _to_iso, parse_config_metadata
from src.report.metrics import _to_dt


ACCOUNTING_TOLERANCE = 1e-4


def _atomic_write_text(path: Path, content: str) -> None:
    """Write one artifact atomically in its destination directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_file.write(content)
            temp_file.flush()
            os.fsync(temp_file.fileno())
            temp_name = temp_file.name
        os.replace(temp_name, path)
    except Exception:
        if temp_name:
            Path(temp_name).unlink(missing_ok=True)
        raise


def _atomic_copy(source: Path, destination: Path) -> None:
    """Copy a completed artifact without exposing a partially copied target."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
    try:
        shutil.copy2(source, temp_path)
        os.replace(temp_path, destination)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def _validate_accounting(metrics: Dict[str, Any], broker: Any) -> Dict[str, Any]:
    """Reconcile report values against broker ledger truth and fail on mismatch."""
    broker.verify_accounting_invariants()
    trades = list(getattr(broker, "trade_history", []))
    positions = getattr(broker, "positions", {})
    open_positions = positions.values() if isinstance(positions, dict) else positions

    def field(item: Any, name: str, default: float = 0.0) -> float:
        value = item.get(name, default) if isinstance(item, dict) else getattr(item, name, default)
        if type(value) is bool:
            raise TypeError(f"Accounting field '{name}' cannot be boolean")
        result = float(value)
        if not math.isfinite(result):
            raise ValueError(f"Accounting field '{name}' must be finite, got {result}")
        return result

    gross = sum(field(t, "gross_price_pnl") for t in trades)
    fees = sum(field(t, "entry_fee") + field(t, "exit_fee") for t in trades)
    fees += sum(field(p, "entry_fee") for p in open_positions)
    funding_events = list(getattr(broker, "funding_history", []))
    if funding_events:
        funding = sum(field(event, "cashflow_usd", field(event, "payment")) for event in funding_events)
    else:
        funding = sum(field(t, "funding_cashflow") for t in trades)

    initial = field(broker, "initial_balance")
    wallet = field(broker, "wallet_balance")
    equity = field(broker, "equity")
    unrealized = field(broker, "unrealized_pnl", equity - wallet)
    net = gross - fees + funding
    expected_wallet = initial + net
    expected_equity = expected_wallet + unrealized

    comparisons = {
        "initial_capital": initial,
        "total_gross_pnl": gross,
        "total_fees": fees,
        "total_funding_trades": funding,
        "total_net_pnl": net,
        "final_equity": equity,
    }
    for key, actual in comparisons.items():
        if key in metrics and metrics[key] is not None:
            supplied = field(metrics, key)
            if abs(supplied - actual) > ACCOUNTING_TOLERANCE:
                raise AssertionError(
                    f"Report accounting mismatch for {key}: supplied {supplied:.8f}, ledger {actual:.8f}"
                )

    if abs(wallet - expected_wallet) > ACCOUNTING_TOLERANCE:
        raise AssertionError(
            f"Report accounting mismatch: wallet {wallet:.8f} != expected {expected_wallet:.8f}"
        )
    if abs(equity - expected_equity) > ACCOUNTING_TOLERANCE:
        raise AssertionError(
            f"Report accounting mismatch: equity {equity:.8f} != expected {expected_equity:.8f}"
        )

    return {
        "accounting_invariants_verified": True,
        "formula": "final_equity = initial_equity + gross_price_pnl - fees + funding_cashflow + unrealized_pnl",
        "tolerance": ACCOUNTING_TOLERANCE,
        "initial_capital": initial,
        "final_equity": equity,
        "wallet_balance": wallet,
        "reserved_collateral": field(broker, "reserved_collateral"),
        "available_margin": field(broker, "available_margin"),
        "unrealized_pnl": unrealized,
        "gross_price_pnl": gross,
        "fees_paid": fees,
        "funding_cashflow": funding,
        "net_realized_pnl": net,
        "expected_wallet_balance": expected_wallet,
        "wallet_difference": wallet - expected_wallet,
        "expected_final_equity": expected_equity,
        "equity_difference": equity - expected_equity,
        "adjustments": 0.0,
    }


def _get_git_commit_sha() -> str:
    """Lấy commit SHA hiện tại qua git CLI an toàn."""
    try:
        project_root = Path(__file__).resolve().parent.parent.parent
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception:
        return "UNKNOWN_GIT_COMMIT"


def _sanitize_for_json(obj: Any) -> Any:
    """
    Đảm bảo mọi giá trị trong object đều an toàn với RFC 8259 JSON (allow_nan=False).
    Fail-closed: Nếu phát hiện NaN hoặc Inf trong float, ném ValueError thay vì âm thầm ép sang null.
    """
    if obj is None:
        return None
    if type(obj) is bool or isinstance(obj, (str, int)):
        return obj
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            raise ValueError(f"Float value {obj} is NaN/Inf and cannot be converted to RFC 8259 JSON (fail-closed)")
        return obj
    if isinstance(obj, (datetime, pd.Timestamp)):
        return _to_iso(obj)
    if isinstance(obj, dict):
        return {str(k): _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_sanitize_for_json(v) for v in obj]
    if hasattr(obj, "__dict__"):
        return _sanitize_for_json(obj.__dict__)
    return str(obj)


def _portable_config(obj: Any, key: str = "") -> Any:
    """Remove machine-specific absolute paths from persisted report config."""
    if isinstance(obj, dict):
        return {str(k): _portable_config(v, str(k)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_portable_config(v, key) for v in obj]
    if isinstance(obj, tuple):
        return tuple(_portable_config(v, key) for v in obj)
    if isinstance(obj, str) and any(token in key.lower() for token in ("path", "dir", "file")):
        candidate = Path(obj)
        if candidate.is_absolute():
            return candidate.name
    return obj


class ReportGenerator:
    """
    Sinh báo cáo đa định dạng cho mỗi phiên chạy backtest.
    """

    def __init__(self, base_reports_dir: Union[str, Path] = "reports"):
        self.base_reports_dir = Path(base_reports_dir).resolve()

    def generate_all(
        self,
        run_id: str,
        config: Dict[str, Any],
        metrics: Dict[str, Any],
        broker: Any,
        custom_output_dir: Optional[Union[str, Path]] = None,
        db_path: Optional[Union[str, Path]] = None,
    ) -> Dict[str, Path]:
        """
        Sinh toàn bộ 6 artifacts cho run_id được chỉ định.
        Trả về dictionary chứa đường dẫn Path tới từng artifact.
        """
        run_id = str(run_id).strip()
        if not run_id:
            raise ValueError("run_id cannot be empty")

        if custom_output_dir is not None:
            out_dir = Path(custom_output_dir).resolve()
            if out_dir.name != run_id:
                out_dir = out_dir / run_id
        else:
            out_dir = self.base_reports_dir / run_id

        out_dir.mkdir(parents=True, exist_ok=True)
        artifacts: Dict[str, Path] = {}

        artifact_config = _portable_config(config)
        meta = parse_config_metadata(artifact_config)
        config_canonical_str = json.dumps(artifact_config, sort_keys=True, ensure_ascii=False, default=str)
        config_hash = hashlib.sha256(config_canonical_str.encode("utf-8")).hexdigest()
        accounting_rec = _validate_accounting(metrics, broker)
        metrics = dict(metrics)
        metrics.update({
            "initial_capital": accounting_rec["initial_capital"],
            "final_equity": accounting_rec["final_equity"],
            "wallet_balance": accounting_rec["wallet_balance"],
            "reserved_collateral": accounting_rec["reserved_collateral"],
            "available_margin": accounting_rec["available_margin"],
            "unrealized_pnl": accounting_rec["unrealized_pnl"],
            "total_gross_pnl": accounting_rec["gross_price_pnl"],
            "total_fees": accounting_rec["fees_paid"],
            "total_funding_trades": accounting_rec["funding_cashflow"],
            "total_net_pnl": accounting_rec["net_realized_pnl"],
            "accounting_invariants_verified": True,
        })
        code_commit_sha = metrics.get("code_commit_sha") or _get_git_commit_sha()

        # 1. SQLite Database: Ghi nhận sự kiện vào SQLite
        sqlite_file = out_dir / "trades.sqlite"
        target_db = Path(db_path).resolve() if db_path else sqlite_file

        target_db.parent.mkdir(parents=True, exist_ok=True)
        database_was_new = not target_db.exists()
        working_db = (
            target_db.with_name(f".{target_db.name}.{os.getpid()}.tmp")
            if database_was_new else target_db
        )
        try:
            logger_instance = TradeLogger(working_db)
            logger_instance.log_backtest_run(
                run_id=run_id,
                config=artifact_config,
                metrics=metrics,
                orders=broker.order_history,
                trades=broker.trade_history,
                funding_events=broker.funding_history,
                account_snapshots=broker.account_snapshots,
            )
            if database_was_new:
                os.replace(working_db, target_db)
                logger_instance = TradeLogger(target_db)
        except Exception:
            if database_was_new:
                working_db.unlink(missing_ok=True)
            raise

        if target_db != sqlite_file:
            _atomic_copy(target_db, sqlite_file)
        artifacts["trades.sqlite"] = sqlite_file

        # 2. summary.json
        summary_json_path = out_dir / "summary.json"

        data_cfg = artifact_config.get("data", {})
        raw_data_dir = Path(str(data_cfg.get("raw_data_dir", "data/raw")))
        safe_raw_data_dir = raw_data_dir.name if raw_data_dir.is_absolute() else raw_data_dir.as_posix()
        data_prov = {
            "exchange": data_cfg.get("exchange", "binance"),
            "futures_symbol": meta["symbol"],
            "raw_data_dir": safe_raw_data_dir,
            "fetch_mode": "no_fetch" if metrics.get("no_fetch") else "auto",
        }

        candle_counts = {
            "bars_15m_count": int(metrics.get("bars_15m_count", 0)),
            "bars_4h_count": int(metrics.get("bars_4h_count", 0)),
        }

        candle_gaps = {
            "gaps_detected_count": int(metrics.get("candle_gaps_count", 0)),
            "max_gap_duration_seconds": int(metrics.get("max_gap_duration_seconds", 0)),
        }

        reproduction_cmd = str(
            metrics.get("reproduction_command")
            or f"python run_backtest.py --config config/default_config.yaml --strategy {meta['strategy_name'].lower()} --start {meta['start_date'] or '2021-01-01'} --end {meta['end_date'] or '2023-12-31'} --no-fetch"
        )

        clean_metrics = _sanitize_for_json(metrics)
        summary_payload = dict(clean_metrics)
        summary_payload.update({
            "run_id": run_id,
            "code_commit_sha": code_commit_sha,
            "config_hash": config_hash,
            "strategy": meta["strategy_name"],
            "symbol": meta["symbol"],
            "timeframe_signal": meta["timeframe_signal"],
            "timeframe_execution": meta["timeframe_execution"],
            "timeframes": [meta["timeframe_signal"], meta["timeframe_execution"]],
            "start_time": _to_iso(metrics.get("start_time")),
            "end_time": _to_iso(metrics.get("end_time")),
            "data_provenance": data_prov,
            "candle_counts": candle_counts,
            "candle_gaps": candle_gaps,
            "accounting_reconciliation": accounting_rec,
            "verification_status": "AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED",
            "reproduction_command": reproduction_cmd,
        })

        summary_json = json.dumps(
            summary_payload,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
        )
        _atomic_write_text(summary_json_path, summary_json)
        artifacts["summary.json"] = summary_json_path

        # 3. trades.json
        trades_json_path = out_dir / "trades.json"
        logger_instance.export_trades_json(run_id=run_id, output_path=trades_json_path)
        artifacts["trades.json"] = trades_json_path

        # 4. equity_curve.csv
        equity_csv_path = out_dir / "equity_curve.csv"
        self._export_equity_csv(broker, equity_csv_path)
        artifacts["equity_curve.csv"] = equity_csv_path

        # 5. equity_curve.png
        chart_png_path = out_dir / "equity_curve.png"
        self._render_chart(broker, metrics, run_id, chart_png_path)
        artifacts["equity_curve.png"] = chart_png_path

        # 6. summary.md
        summary_md_path = out_dir / "summary.md"
        self._export_summary_md(run_id, artifact_config, metrics, summary_md_path)
        artifacts["summary.md"] = summary_md_path

        logger.info(f"Generated all Stage 6 artifacts in: {out_dir}")
        return artifacts

    def _export_equity_csv(self, broker: Any, output_path: Path) -> None:
        """Xuất chuỗi dữ liệu tài khoản ra file CSV."""
        rows = []
        start_eq = float(broker.initial_balance)
        peak = start_eq

        for snap in broker.account_snapshots:
            s = snap if isinstance(snap, dict) else snap.__dict__
            eq = float(s.get("equity", 0.0))
            if eq > peak:
                peak = eq
            dd_usd = peak - eq
            dd_pct = (dd_usd / peak * 100.0) if peak > 0 else 0.0

            rows.append({
                "timestamp": _to_iso(s.get("timestamp")),
                "equity": round(eq, 4),
                "wallet_balance": round(float(s.get("wallet_balance", 0.0)), 4),
                "unrealized_pnl": round(float(s.get("unrealized_pnl", 0.0)), 4),
                "margin_used": round(float(s.get("reserved_collateral", s.get("margin_used", 0.0))), 4),
                "available_balance": round(float(s.get("available_margin", s.get("available_balance", 0.0))), 4),
                "drawdown_usd": round(dd_usd, 4),
                "drawdown_pct": round(dd_pct, 4),
            })

        columns = [
            "timestamp", "equity", "wallet_balance", "unrealized_pnl",
            "margin_used", "available_balance", "drawdown_usd", "drawdown_pct",
        ]
        df = pd.DataFrame(rows, columns=columns)
        _atomic_write_text(output_path, df.to_csv(index=False))

    def _render_chart(
        self,
        broker: Any,
        metrics: Dict[str, Any],
        run_id: str,
        output_path: Path,
    ) -> None:
        """Vẽ đồ thị 2 panel: Equity Curve (trên) và Underwater Drawdown (dưới)."""
        snapshots = broker.account_snapshots
        if not snapshots:
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.text(0.5, 0.5, "No snapshot data available", ha="center", va="center")
            plt.tight_layout()
            self._save_figure_atomic(fig, output_path)
            return

        times = []
        equities = []
        peak_equities = []
        drawdowns_pct = []

        start_eq = float(broker.initial_balance)
        peak = start_eq

        for s in snapshots:
            snap_dict = s if isinstance(s, dict) else s.__dict__
            dt = _to_dt(snap_dict.get("timestamp"))
            eq = float(snap_dict.get("equity", 0.0))
            if dt is not None:
                times.append(dt)
                equities.append(eq)
                if eq > peak:
                    peak = eq
                peak_equities.append(peak)
                dd_pct = ((peak - eq) / peak * 100.0) if peak > 0 else 0.0
                drawdowns_pct.append(-dd_pct)

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True, gridspec_kw={"height_ratios": [2.5, 1]})

        ax1.plot(times, equities, label="Equity", color="#1f77b4", linewidth=1.5)
        ax1.plot(times, peak_equities, label="High Watermark", color="#2ca02c", linestyle="--", linewidth=1.0, alpha=0.7)
        ax1.axhline(start_eq, color="#7f7f7f", linestyle=":", label="Initial Capital", linewidth=1.0)

        symbol = str(metrics.get("symbol", "BTCUSDT"))
        strat = str(metrics.get("strategy", "Trend Following"))
        ret_pct = metrics.get("total_return_pct", 0.0)
        max_dd = metrics.get("max_drawdown_pct", 0.0)
        sharpe = metrics.get("sharpe_ratio")
        sharpe_str = f"{sharpe:.2f}" if sharpe is not None else "N/A"

        ax1.set_title(
            f"Backtest Performance: {strat} on {symbol} (Run: {run_id})\n"
            f"Return: {ret_pct:+.2f}% | Max DD: {max_dd:.2f}% | Sharpe: {sharpe_str}",
            fontsize=12,
            fontweight="bold",
        )
        ax1.set_ylabel("Equity (USDT)", fontsize=10)
        ax1.grid(True, linestyle="--", alpha=0.5)
        ax1.legend(loc="upper left")

        ax2.plot(times, drawdowns_pct, color="#d62728", linewidth=1.0)
        ax2.fill_between(times, drawdowns_pct, 0, color="#d62728", alpha=0.3, label="Drawdown (%)")
        ax2.set_ylabel("Drawdown (%)", fontsize=10)
        ax2.set_xlabel("Time (UTC)", fontsize=10)
        ax2.grid(True, linestyle="--", alpha=0.5)
        ax2.legend(loc="lower left")

        ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        fig.autofmt_xdate()

        plt.tight_layout()
        self._save_figure_atomic(fig, output_path)

    @staticmethod
    def _save_figure_atomic(fig: Any, output_path: Path) -> None:
        """Save a PNG fully before replacing the visible artifact."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = output_path.with_name(f".{output_path.stem}.{os.getpid()}.tmp.png")
        try:
            fig.savefig(temp_path, dpi=150)
            os.replace(temp_path, output_path)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise
        finally:
            plt.close(fig)

    def _export_summary_md(
        self,
        run_id: str,
        config: Dict[str, Any],
        metrics: Dict[str, Any],
        output_path: Path,
    ) -> None:
        """Tạo file báo cáo tóm tắt Markdown chi tiết kèm đầy đủ provenance và disclosures bắt buộc."""
        meta = parse_config_metadata(config)
        symbol = meta["symbol"]
        strategy = meta["strategy_name"]
        tf_sig = meta["timeframe_signal"]
        tf_exec = meta["timeframe_execution"]
        start_t = _to_iso(metrics.get("start_time")) or meta["start_date"] or "N/A"
        end_t = _to_iso(metrics.get("end_time")) or meta["end_date"] or "N/A"

        code_commit_sha = str(metrics.get("code_commit_sha") or _get_git_commit_sha())
        config_canonical_str = json.dumps(config, sort_keys=True, ensure_ascii=False, default=str)
        config_hash = hashlib.sha256(config_canonical_str.encode("utf-8")).hexdigest()

        init_cap = float(metrics.get("initial_capital", 10000.0))
        fin_eq = float(metrics.get("final_equity", init_cap))
        tot_ret = float(metrics.get("total_return_pct", 0.0))
        max_dd_usd = float(metrics.get("max_drawdown_usd", 0.0))
        max_dd_pct = float(metrics.get("max_drawdown_pct", 0.0))
        sharpe = metrics.get("sharpe_ratio")
        sharpe_str = f"{sharpe:.2f}" if sharpe is not None else "N/A"
        calmar = metrics.get("calmar_ratio")
        calmar_str = f"{calmar:.2f}" if calmar is not None else "N/A"
        pf = metrics.get("profit_factor")
        pf_str = f"{pf:.2f}" if pf is not None else "N/A (Loss = 0)"
        exp_usd = float(metrics.get("expectancy_usd", 0.0))
        exp_r = metrics.get("expectancy_r")
        exp_r_str = f"{exp_r:+.2f} R" if exp_r is not None else "N/A"

        tot_trades = int(metrics.get("total_trades", 0))
        win_rate = float(metrics.get("win_rate", 0.0))
        win_cnt = int(metrics.get("win_trades_count", 0))
        loss_cnt = int(metrics.get("loss_trades_count", 0))
        be_cnt = int(metrics.get("breakeven_trades_count", 0))

        tot_fees = float(metrics.get("total_fees", 0.0))
        tot_funding = float(metrics.get("total_funding_trades", 0.0))
        tot_net_pnl = float(metrics.get("total_net_pnl", 0.0))

        rejection_reasons = metrics.get("rejection_reasons", {})
        exit_reasons = metrics.get("exit_reasons", {})

        reproduction_cmd = str(
            metrics.get("reproduction_command")
            or f"python run_backtest.py --config config/default_config.yaml --strategy {strategy.lower()} --start {start_t[:10]} --end {end_t[:10]} --no-fetch"
        )

        cb_status = str(metrics.get("circuit_breaker_status", "ACTIVE"))
        cb_multiplier = metrics.get("circuit_breaker_risk_multiplier", 1.0)
        cb_rej = metrics.get("circuit_breaker_rejections_count", 0)
        margin_rej = metrics.get("margin_rejections_count", metrics.get("orders_rejected_count", 0))
        audit_status = "PASSED" if metrics.get("accounting_invariants_verified") is True else "FAILED"
        benchmark = metrics.get("benchmark_comparison", {})
        benchmark_status = benchmark.get("status", "NOT_AVAILABLE") if isinstance(benchmark, dict) else "NOT_AVAILABLE"

        bars_15m = metrics.get("bars_15m_count", 0)
        bars_4h = metrics.get("bars_4h_count", 0)

        md_content = f"""# Performance Report: {strategy} ({symbol})
> **Report Status**: AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED  
> **Run ID**: `{run_id}`  
> **Code Commit SHA**: `{code_commit_sha}`  
> **Config Hash**: `{config_hash}`  
> **Verification Status**: AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED  
> **Reproduction Command**: `{reproduction_cmd}`  
> **Generated At**: `{datetime.now(timezone.utc).isoformat()}`  

---

## 1. Executive Summary

| Chỉ số (Metric) | Giá trị |
| :--- | :--- |
| **Strategy** | `{strategy}` |
| **Symbol / Timeframes** | `{symbol}` (Signal: `{tf_sig}`, Execution: `{tf_exec}`) |
| **Backtest Period (UTC)** | `{start_t}` $\\rightarrow$ `{end_t}` |
| **Bars Processed** | 15m=`{bars_15m}`, 4h=`{bars_4h}` |
| **Candle Gaps Detected** | `{metrics.get("candle_gaps_count", 0)}` (Max gap: `{metrics.get("max_gap_duration_seconds", 0)}s`) |
| **Initial Capital** | `${init_cap:,.2f} USDT` |
| **Final Equity** | `${fin_eq:,.2f} USDT` |
| **Net PnL** | `${tot_net_pnl:+,.2f} USDT` |
| **Total Return** | `{tot_ret:+.2f}%` |
| **Max Drawdown** | `-${max_dd_usd:,.2f} USDT` (`{max_dd_pct:.2f}%`) |
| **Daily Sharpe Ratio** | `{sharpe_str}` |
| **Calmar Ratio** | `{calmar_str}` |
| **Profit Factor** | `{pf_str}` |
| **Expectancy (USD)** | `${exp_usd:+,.2f}` |
| **Expectancy (R)** | `{exp_r_str}` |

---

## 2. Accounting Reconciliation & Risk Audit

| Mục Đối Soát Kế Toán | Giá Trị (USDT) | Trạng Thái / Ghi Chú |
| :--- | :--- | :--- |
| **Vốn khởi điểm (Initial Capital)** | `${init_cap:,.2f}` | Điểm neo ban đầu |
| **Số dư ví thực tế (Wallet Balance)** | `${float(metrics.get("wallet_balance", fin_eq)):,.2f}` | Trạng thái cuối kỳ |
| **Ký quỹ bị giữ (Reserved Collateral)** | `${float(metrics.get("reserved_collateral", 0.0)):,.2f}` | 0 khi kết thúc (force close) |
| **Hạn mức khả dụng (Available Margin)** | `${float(metrics.get("available_margin", fin_eq)):,.2f}` | Khả dụng mở vị thế mới |
| **Lãi/Lỗ chưa thực hiện (Unrealized PnL)** | `${float(metrics.get("unrealized_pnl", 0.0)):,.2f}` | 0 khi tất toán |
| **Gross Price PnL** | `${float(metrics.get("total_gross_pnl", 0.0)):+,.2f}` | Chênh lệch giá thuần |
| **Tổng phí giao dịch (Fees Paid)** | `-${tot_fees:,.2f}` | Phí taker |
| **Dòng tiền Funding (Funding Cashflow)** | `${tot_funding:+,.2f}` | Thanh toán định kỳ sàn |
| **Net Realized PnL** | `${tot_net_pnl:+,.2f}` | Gross - Fees + Funding |
| **Kiểm toán Bất biến Kế toán** | `{audit_status}` | Sai lệch vượt tolerance sẽ làm report thất bại |
| **Trạng thái Circuit Breaker** | `{cb_status}` | Multiplier: `{cb_multiplier}` |
| **Từ chối Lệnh do Ký quỹ (Margin Gate)** | `{margin_rej}` lần | Độc lập với Circuit Breaker |
| **Từ chối Lệnh do Circuit Breaker** | `{cb_rej}` lần | Khóa khi chạm ngưỡng rủi ro |

---

## 3. Trade Statistics

| Thống kê Giao dịch | Chi tiết |
| :--- | :--- |
| **Total Closed Trades** | `{tot_trades}` |
| **Win / Loss / Breakeven** | `{win_cnt}` / `{loss_cnt}` / `{be_cnt}` |
| **Win Rate** | `{win_rate:.2f}%` |
| **Average Trade PnL** | `${float(metrics.get("avg_trade_pnl", 0.0)):+,.2f}` |
| **Average Win / Loss** | `${float(metrics.get("avg_win_usd", 0.0)):+,.2f}` / `-${abs(float(metrics.get("avg_loss_usd", 0.0))):,.2f}` |
| **Win / Loss Ratio** | `{metrics.get("win_loss_ratio") or "N/A"}` |
| **Max Consecutive Wins / Losses** | `{metrics.get("max_consecutive_wins", 0)}` / `{metrics.get("max_consecutive_losses", 0)}` |
| **Total Trading Fees** | `${tot_fees:,.2f} USDT` |
| **Total Funding Cashflow** | `${tot_funding:+,.2f} USDT` |
| **Benchmark Win-rate 35-45%** | `{benchmark_status}` (comparison only; not a future-performance guarantee) |

### Phân bổ lý do đóng vị thế (Exit Reasons)
"""
        if exit_reasons:
            for rk, cnt in exit_reasons.items():
                md_content += f"- **{rk}**: `{cnt}` vị thế\n"
        else:
            md_content += "- Không có vị thế nào được đóng.\n"

        md_content += "\n### Phân bổ lý do từ chối lệnh (Rejection Reasons)\n"
        if rejection_reasons:
            for rk, cnt in rejection_reasons.items():
                md_content += f"- **{rk}**: `{cnt}` lần từ chối\n"
        else:
            md_content += "- Không có lệnh nào bị từ chối.\n"

        md_content += f"""
---

## 4. Disclosures & Benchmark Caveats (Bắt buộc)

> [!IMPORTANT]
> **Tuyên bố miễn trừ trách nhiệm và Giới hạn mô phỏng:**
> 1. **Nhãn dữ liệu**: Tất cả chỉ số trong báo cáo này được gắn cờ `AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED` và chưa được xác nhận bởi bên đánh giá độc lập.
> 2. **Giả định thực thi**: Mô hình khớp lệnh dựa trên dữ liệu nến lịch sử 15 phút với slippage tuyến tính và giả định thanh khoản tức thời tại giá mở cửa. Trong điều kiện thị trường biến động mạnh hoặc khoảng trống giá thực tế (slippage thực tế), kết quả có thể kém khả quan hơn.
> 3. **Phí & Funding**: Chi phí giao dịch tính theo biểu phí taker cố định và funding rate lịch sử. Không tính đến chi phí trượt giá thanh lý quy mô lớn hoặc độ trễ mạng (network latency).
> 4. **Quá khứ không đại diện tương lai**: Hiệu suất trong quá khứ của chiến lược trend following không đảm bảo kết quả tương tự trong tương lai.
"""
        _atomic_write_text(output_path, md_content)
