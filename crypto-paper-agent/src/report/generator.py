"""
src/report/generator.py - Multi-format Report Generator
======================================================
Tạo lập tự động bộ artifacts hoàn chỉnh cho mỗi phiên backtest/paper trading
dưới thư mục `reports/<run_id>/`:
1. summary.json      - Tổng hợp toàn bộ metrics (JSON chuẩn, allow_nan=False)
2. summary.md        - Báo cáo Markdown chi tiết kèm benchmark caveats & disclosures
3. trades.json       - Danh sách trade chuẩn hoá theo Master Spec Section 4.6
4. equity_curve.csv  - Chuỗi dữ liệu equity, balance và drawdown theo thời gian
5. equity_curve.png  - Biểu đồ 2 khung (Equity Curve + Underwater Drawdown)
6. trades.sqlite     - File SQLite cơ sở dữ liệu lưu toàn bộ sự kiện của run
"""
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import shutil
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
from src.logging.trade_logger import TradeLogger, _clean_float, _to_epoch, _to_iso
from src.report.metrics import _to_dt



def _sanitize_for_json(obj: Any) -> Any:
    """Đảm bảo mọi giá trị trong object đều an toàn với json.dumps(allow_nan=False)."""
    if obj is None:
        return None
    if isinstance(obj, (bool, str, int)):
        return obj
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
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
            # Nếu user truyền thẳng reports/<run_id>, không lồng thêm cấp con nếu tên trùng
            if out_dir.name != run_id:
                out_dir = out_dir / run_id
        else:
            out_dir = self.base_reports_dir / run_id

        out_dir.mkdir(parents=True, exist_ok=True)
        artifacts: Dict[str, Path] = {}

        # 1. SQLite Database: Ghi nhận sự kiện vào SQLite
        sqlite_file = out_dir / "trades.sqlite"
        target_db = Path(db_path).resolve() if db_path else sqlite_file
        
        logger_instance = TradeLogger(target_db)
        logger_instance.log_backtest_run(
            run_id=run_id,
            config=config,
            metrics=metrics,
            orders=broker.order_history,
            trades=broker.trade_history,
            funding_events=broker.funding_history,
            account_snapshots=broker.account_snapshots,
        )
        
        # Nếu db_path khác với file sqlite_file trong folder reports, sao chép hoặc ghi vào cả hai
        if target_db != sqlite_file:
            shutil.copy2(target_db, sqlite_file)
        artifacts["trades.sqlite"] = sqlite_file

        # 2. summary.json
        summary_json_path = out_dir / "summary.json"
        clean_metrics = _sanitize_for_json(metrics)
        with open(summary_json_path, "w", encoding="utf-8") as f:
            json.dump(clean_metrics, f, indent=2, ensure_ascii=False, allow_nan=False)
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
        self._export_summary_md(run_id, config, metrics, summary_md_path)
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
                "margin_used": round(float(s.get("margin_used", 0.0)), 4),
                "available_balance": round(float(s.get("available_balance", 0.0)), 4),
                "drawdown_usd": round(dd_usd, 4),
                "drawdown_pct": round(dd_pct, 4),
            })

        df = pd.DataFrame(rows)
        df.to_csv(output_path, index=False)

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
            # Tạo đồ thị trống nếu không có snapshot
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.text(0.5, 0.5, "No snapshot data available", ha="center", va="center")
            plt.tight_layout()
            plt.savefig(output_path, dpi=150)
            plt.close(fig)
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
                drawdowns_pct.append(-dd_pct)  # Biểu thị số âm cho underwater

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True, gridspec_kw={"height_ratios": [2.5, 1]})

        # Panel 1: Equity Curve
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

        # Panel 2: Underwater Drawdown
        ax2.plot(times, drawdowns_pct, color="#d62728", linewidth=1.0)
        ax2.fill_between(times, drawdowns_pct, 0, color="#d62728", alpha=0.3, label="Drawdown (%)")
        ax2.set_ylabel("Drawdown (%)", fontsize=10)
        ax2.set_xlabel("Time (UTC)", fontsize=10)
        ax2.grid(True, linestyle="--", alpha=0.5)
        ax2.legend(loc="lower left")

        # Format trục thời gian
        ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        fig.autofmt_xdate()

        plt.tight_layout()
        plt.savefig(output_path, dpi=150)
        plt.close(fig)

    def _export_summary_md(
        self,
        run_id: str,
        config: Dict[str, Any],
        metrics: Dict[str, Any],
        output_path: Path,
    ) -> None:
        """Tạo file báo cáo tóm tắt Markdown chi tiết kèm disclosures bắt buộc."""
        symbol = str(metrics.get("symbol", config.get("symbol", "BTCUSDT")))
        strategy = str(metrics.get("strategy", config.get("strategy", "Trend Following")))
        tf_sig = str(metrics.get("timeframe_signal", "4h"))
        tf_exec = str(metrics.get("timeframe_execution", "15m"))
        start_t = _to_iso(metrics.get("start_time")) or "N/A"
        end_t = _to_iso(metrics.get("end_time")) or "N/A"

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

        md_content = f"""# Performance Report: {strategy} ({symbol})
> **Report Status**: AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED  
> **Run ID**: `{run_id}`  
> **Generated At**: `{datetime.now(timezone.utc).isoformat()}`  

---

## 1. Executive Summary

| Chỉ số (Metric) | Giá trị |
| :--- | :--- |
| **Strategy** | `{strategy}` |
| **Symbol / Timeframes** | `{symbol}` (Signal: `{tf_sig}`, Execution: `{tf_exec}`) |
| **Backtest Period** | `{start_t}` $\\rightarrow$ `{end_t}` |
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

## 2. Trade Statistics

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

## 3. Disclosures & Benchmark Caveats (Bắt buộc)

> [!IMPORTANT]
> **Tuyên bố miễn trừ trách nhiệm và Giới hạn mô phỏng:**
> 1. **Nhãn dữ liệu**: Tất cả chỉ số trong báo cáo này được gắn cờ `AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED` và chưa được xác nhận bởi bên đánh giá độc lập.
> 2. **Giả định thực thi**: Mô hình khớp lệnh dựa trên dữ liệu nến lịch sử 15 phút với slippage tuyến tính và giả định thanh khoản tức thời tại giá mở cửa. Trong điều kiện thị trường biến động mạnh hoặc khoảng trống giá thực tế (slippage thực tế), kết quả có thể kém khả quan hơn.
> 3. **Phí & Funding**: Chi phí giao dịch tính theo biểu phí taker cố định và funding rate lịch sử. Không tính đến chi phí trượt giá thanh lý quy mô lớn hoặc độ trễ mạng (network latency).
> 4. **Quá khứ không đại diện tương lai**: Hiệu suất trong quá khứ của chiến lược trend following không đảm bảo kết quả tương tự trong tương lai.
"""
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(md_content)
