"""
src/report/metrics.py - Performance Metrics Calculation Engine
==============================================================
Triển khai các công thức tính toán chỉ số hiệu năng chuẩn hoá cho giao dịch
phái sinh (Master Spec Section 4.6), bao gồm:
- Expectancy (USD & R-multiple)
- Profit Factor (xử lý nghiêm ngặt trường hợp loss = 0 -> None/null)
- Peak-to-Valley Maximum Drawdown (USD & %)
- Daily Sharpe Ratio resampled theo UTC 1D returns với annualization sqrt(365)
- Win rate, SQN, Win/Loss ratio, Consecutive streaks
"""
from datetime import datetime, timezone
import math
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd

from src.execution.order_models import (
    AccountSnapshot,
    ExitReason,
    OrderDirection,
    OrderStatus,
    TradeRecord,
    _ensure_utc,
)


def _to_dt(ts: Any) -> Optional[datetime]:
    """Chuyển đổi timestamp sang UTC datetime."""
    if ts is None:
        return None
    if isinstance(ts, datetime):
        return _ensure_utc(ts)
    if isinstance(ts, str):
        try:
            return _ensure_utc(datetime.fromisoformat(ts))
        except Exception:
            return None
    if isinstance(ts, (int, float)):
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except Exception:
            return None
    return None


def calculate_daily_sharpe(
    snapshots: List[Union[AccountSnapshot, Dict[str, Any]]],
    risk_free_rate: float = 0.0,
    start_equity: Optional[float] = None,
) -> Optional[float]:
    """
    Tính toán Annualized Sharpe Ratio dựa trên chuỗi tỷ suất sinh lời hàng ngày (1D UTC).
    
    Quy trình:
    1. Trích xuất (timestamp, equity) từ danh sách snapshots.
    2. Resample theo ngày lịch UTC (lấy giá trị equity cuối cùng của mỗi ngày UTC).
    3. Tính daily returns: r_t = (E_t - E_{t-1}) / E_{t-1}.
    4. Nếu số ngày quan sát < 2 hoặc độ lệch chuẩn = 0: trả về None (null).
    5. Sharpe = sqrt(365) * (mean(r_t) - rf / 365) / std(r_t, ddof=1).
    """
    if not snapshots:
        return None

    parsed_rows: List[Dict[str, Any]] = []
    for s in snapshots:
        item = s if isinstance(s, dict) else s.__dict__
        dt = _to_dt(item.get("timestamp"))
        eq = item.get("equity")
        if dt is not None and eq is not None and not math.isnan(eq):
            parsed_rows.append({"timestamp": dt, "equity": float(eq)})

    if not parsed_rows:
        return None

    df = pd.DataFrame(parsed_rows)
    df.set_index("timestamp", inplace=True)
    df.sort_index(inplace=True)

    # Resample lấy giá trị equity cuối cùng của mỗi ngày UTC
    daily_series = df["equity"].resample("1D").last().dropna()

    # Nếu có start_equity và ngày đầu tiên không có snapshot điểm 0, có thể prepend
    if start_equity is not None and len(daily_series) >= 1:
        first_date = daily_series.index[0]
        # Prepend ngày trước đó nếu hợp lý
        prev_date = first_date - pd.Timedelta(days=1)
        if prev_date not in daily_series.index:
            prepend_s = pd.Series([start_equity], index=[prev_date])
            daily_series = pd.concat([prepend_s, daily_series])

    if len(daily_series) < 2:
        return None

    daily_returns = daily_series.pct_change().dropna()
    # Lọc bỏ giá trị inf/nan
    daily_returns = daily_returns[np.isfinite(daily_returns)]

    if len(daily_returns) < 2:
        return None

    std_dev = float(daily_returns.std(ddof=1))
    if std_dev <= 1e-12 or math.isnan(std_dev):
        return None

    mean_ret = float(daily_returns.mean())
    daily_rf = risk_free_rate / 365.0
    sharpe = math.sqrt(365.0) * (mean_ret - daily_rf) / std_dev

    if math.isnan(sharpe) or math.isinf(sharpe):
        return None

    return round(sharpe, 4)


def calculate_max_drawdown(
    snapshots: List[Union[AccountSnapshot, Dict[str, Any]]],
    initial_capital: float = 10000.0,
) -> Tuple[float, float]:
    """
    Tính Peak-to-Valley Maximum Drawdown tính bằng USD và phần trăm (%).
    
    Công thức:
    Peak_t = max(initial_capital, max_{s <= t} Equity_s)
    DD_usd_t = Peak_t - Equity_t
    DD_pct_t = (DD_usd_t / Peak_t) * 100.0
    Max_DD = max(DD_t)
    """
    if not snapshots:
        return 0.0, 0.0

    max_dd_usd = 0.0
    max_dd_pct = 0.0
    peak_equity = float(initial_capital)

    for s in snapshots:
        item = s if isinstance(s, dict) else s.__dict__
        eq = float(item.get("equity", 0.0))
        if eq > peak_equity:
            peak_equity = eq
        dd_usd = peak_equity - eq
        dd_pct = (dd_usd / peak_equity * 100.0) if peak_equity > 0 else 0.0

        if dd_usd > max_dd_usd:
            max_dd_usd = dd_usd
        if dd_pct > max_dd_pct:
            max_dd_pct = dd_pct

    return round(max_dd_usd, 4), round(max_dd_pct, 4)


def calculate_trade_metrics(
    trades: List[Union[TradeRecord, Dict[str, Any]]],
) -> Dict[str, Any]:
    """
    Tính toán các chỉ số chi tiết trên tập hợp các giao dịch đã đóng.
    """
    total_trades = len(trades)
    if total_trades == 0:
        return {
            "total_trades": 0,
            "win_trades_count": 0,
            "loss_trades_count": 0,
            "breakeven_trades_count": 0,
            "win_rate": 0.0,
            "profit_factor": None,
            "expectancy_usd": 0.0,
            "expectancy_r": None,
            "avg_trade_pnl": 0.0,
            "avg_win_usd": 0.0,
            "avg_loss_usd": 0.0,
            "win_loss_ratio": None,
            "total_gross_pnl": 0.0,
            "total_net_pnl": 0.0,
            "total_fees": 0.0,
            "total_funding_trades": 0.0,
            "max_consecutive_wins": 0,
            "max_consecutive_losses": 0,
            "sqn": None,
        }

    net_pnls = []
    r_multiples = []
    win_pnls = []
    loss_pnls = []
    gross_pnls = []
    entry_fees = []
    exit_fees = []
    funding_flows = []

    cur_win_streak = 0
    max_win_streak = 0
    cur_loss_streak = 0
    max_loss_streak = 0

    for tr in trades:
        t = tr if isinstance(tr, dict) else tr.__dict__
        npnl = float(t.get("net_pnl", 0.0))
        net_pnls.append(npnl)
        gross_pnls.append(float(t.get("gross_price_pnl", 0.0)))
        entry_fees.append(float(t.get("entry_fee", 0.0)))
        exit_fees.append(float(t.get("exit_fee", 0.0)))
        funding_flows.append(float(t.get("funding_cashflow", 0.0)))

        # R-multiple
        r_mult = t.get("realized_r_multiple")
        if r_mult is not None and not math.isnan(float(r_mult)):
            r_multiples.append(float(r_mult))

        if npnl > 0:
            win_pnls.append(npnl)
            cur_win_streak += 1
            cur_loss_streak = 0
            if cur_win_streak > max_win_streak:
                max_win_streak = cur_win_streak
        elif npnl < 0:
            loss_pnls.append(npnl)
            cur_loss_streak += 1
            cur_win_streak = 0
            if cur_loss_streak > max_loss_streak:
                max_loss_streak = cur_loss_streak
        else:
            cur_win_streak = 0
            cur_loss_streak = 0

    win_count = len(win_pnls)
    loss_count = len(loss_pnls)
    be_count = total_trades - win_count - loss_count
    win_rate = (win_count / total_trades) * 100.0

    total_win_usd = sum(win_pnls)
    total_loss_usd = abs(sum(loss_pnls))

    # Profit Factor: sum(wins) / sum(|losses|)
    if total_loss_usd == 0:
        profit_factor = None
    else:
        profit_factor = round(total_win_usd / total_loss_usd, 4)

    expectancy_usd = float(np.mean(net_pnls))
    avg_win_usd = float(np.mean(win_pnls)) if win_pnls else 0.0
    avg_loss_usd = float(np.mean(loss_pnls)) if loss_pnls else 0.0

    win_loss_ratio = round(abs(avg_win_usd / avg_loss_usd), 4) if avg_loss_usd != 0 else None
    expectancy_r = round(float(np.mean(r_multiples)), 4) if r_multiples else None

    # SQN (System Quality Number) = sqrt(N) * (mean / std)
    if total_trades >= 2:
        pnl_std = float(np.std(net_pnls, ddof=1))
        if pnl_std > 1e-9:
            sqn = round(math.sqrt(total_trades) * (expectancy_usd / pnl_std), 4)
        else:
            sqn = None
    else:
        sqn = None

    return {
        "total_trades": total_trades,
        "win_trades_count": win_count,
        "loss_trades_count": loss_count,
        "breakeven_trades_count": be_count,
        "win_rate": round(win_rate, 2),
        "profit_factor": profit_factor,
        "expectancy_usd": round(expectancy_usd, 4),
        "expectancy_r": expectancy_r,
        "avg_trade_pnl": round(expectancy_usd, 4),
        "avg_win_usd": round(avg_win_usd, 4),
        "avg_loss_usd": round(avg_loss_usd, 4),
        "win_loss_ratio": win_loss_ratio,
        "total_gross_pnl": round(sum(gross_pnls), 4),
        "total_net_pnl": round(sum(net_pnls), 4),
        "total_fees": round(sum(entry_fees) + sum(exit_fees), 4),
        "total_funding_trades": round(sum(funding_flows), 4),
        "max_consecutive_wins": max_win_streak,
        "max_consecutive_losses": max_loss_streak,
        "sqn": sqn,
    }


def calculate_backtest_metrics(
    broker: Any,
    config: Dict[str, Any],
    start_time: Any,
    end_time: Any,
    bars_15m_count: int,
    bars_4h_count: int,
    setup_count: int = 0,
    candidate_count: int = 0,
    submitted_orders_count: int = 0,
    force_close: bool = True,
    finalize_summary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Hàm tính toán và tổng hợp toàn bộ số liệu hiệu năng của phiên backtest.
    Đảm bảo 100% tương thích ngược với các key của Stage 5 đồng thời bổ sung
    đầy đủ các chỉ số của Stage 6.
    """
    trades = broker.trade_history
    orders = broker.order_history
    snapshots = broker.account_snapshots

    trade_stats = calculate_trade_metrics(trades)

    def _get_trade_field(item, name, default=None):
        if isinstance(item, dict):
            return item.get(name, default)
        return getattr(item, name, default)

    long_trades = [t for t in trades if _get_trade_field(t, "direction") == OrderDirection.LONG]
    short_trades = [t for t in trades if _get_trade_field(t, "direction") == OrderDirection.SHORT]
    long_wins = [t for t in long_trades if _get_trade_field(t, "net_pnl", 0.0) > 0]
    short_wins = [t for t in short_trades if _get_trade_field(t, "net_pnl", 0.0) > 0]

    win_rate_long = (len(long_wins) / len(long_trades) * 100.0) if len(long_trades) > 0 else 0.0
    win_rate_short = (len(short_wins) / len(short_trades) * 100.0) if len(short_trades) > 0 else 0.0

    start_equity = float(broker.initial_balance)
    final_equity = float(broker.equity)
    total_return_pct = ((final_equity - start_equity) / start_equity * 100.0) if start_equity > 0 else 0.0

    max_dd_usd, max_dd_pct = calculate_max_drawdown(snapshots, initial_capital=start_equity)
    sharpe_ratio = calculate_daily_sharpe(snapshots, risk_free_rate=0.0, start_equity=start_equity)

    # Calmar ratio
    calmar_ratio = None
    if max_dd_pct > 0:
        calmar_ratio = round(total_return_pct / max_dd_pct, 4)

    # Thống kê lệnh
    def _get_order_status(o):
        if isinstance(o, dict):
            return o.get("status")
        return getattr(o, "status", None)

    orders_filled = sum(1 for o in orders if _get_order_status(o) == OrderStatus.FILLED)
    orders_rejected = sum(1 for o in orders if _get_order_status(o) == OrderStatus.REJECTED)
    orders_cancelled = sum(1 for o in orders if _get_order_status(o) == OrderStatus.CANCELLED)

    rejection_reasons_tally: Dict[str, int] = {}
    for o in orders:
        reasons = o.get("rejection_reasons", []) if isinstance(o, dict) else getattr(o, "rejection_reasons", [])
        for r in reasons:
            reason_key = str(r).split(":")[0].strip()
            rejection_reasons_tally[reason_key] = rejection_reasons_tally.get(reason_key, 0) + 1

    exit_reasons_tally: Dict[str, int] = {}
    for t in trades:
        reason_val = _get_trade_field(t, "exit_reason")
        rk = reason_val.value if hasattr(reason_val, "value") else str(reason_val)
        exit_reasons_tally[rk] = exit_reasons_tally.get(rk, 0) + 1

    # Kiểm tra accounting invariants
    broker.verify_accounting_invariants()

    metrics = {
        # Metadata
        "symbol": str(config.get("symbol", "BTCUSDT")).upper(),
        "strategy": str(config.get("strategy", config.get("strategy_name", "trend_following"))),
        "timeframe_signal": str(config.get("timeframe_signal", "4h")),
        "timeframe_execution": str(config.get("timeframe_execution", "15m")),
        "start_time": start_time,
        "end_time": end_time,
        "bars_15m_count": bars_15m_count,
        "bars_4h_count": bars_4h_count,
        # Vốn & Equity
        "initial_capital": start_equity,
        "start_equity": start_equity,
        "final_equity": final_equity,
        "wallet_balance": broker.wallet_balance,
        "available_margin": broker.available_margin,
        "total_return_pct": round(total_return_pct, 4),
        # Rủi ro & Drawdown
        "max_drawdown_usd": max_dd_usd,
        "max_drawdown_pct": max_dd_pct,
        "sharpe_ratio": sharpe_ratio,
        "calmar_ratio": calmar_ratio,
        # Tín hiệu
        "setup_count": setup_count,
        "candidate_count": candidate_count,
        # Giao dịch
        "total_trades": trade_stats["total_trades"],
        "long_trades_count": len(long_trades),
        "short_trades_count": len(short_trades),
        "win_trades_count": trade_stats["win_trades_count"],
        "loss_trades_count": trade_stats["loss_trades_count"],
        "breakeven_trades_count": trade_stats["breakeven_trades_count"],
        "win_rate": trade_stats["win_rate"],
        "win_rate_long": round(win_rate_long, 2),
        "win_rate_short": round(win_rate_short, 2),
        "profit_factor": trade_stats["profit_factor"],
        "expectancy_usd": trade_stats["expectancy_usd"],
        "expectancy_r": trade_stats["expectancy_r"],
        "avg_trade_pnl": trade_stats["avg_trade_pnl"],
        "avg_win_usd": trade_stats["avg_win_usd"],
        "avg_loss_usd": trade_stats["avg_loss_usd"],
        "win_loss_ratio": trade_stats["win_loss_ratio"],
        "max_consecutive_wins": trade_stats["max_consecutive_wins"],
        "max_consecutive_losses": trade_stats["max_consecutive_losses"],
        "sqn": trade_stats["sqn"],
        # PnL & Chi phí
        "total_gross_pnl": trade_stats["total_gross_pnl"],
        "total_fees": trade_stats["total_fees"],
        "total_funding_trades": trade_stats["total_funding_trades"],
        "total_net_pnl": trade_stats["total_net_pnl"],
        # Lệnh
        "submitted_orders_count": submitted_orders_count,
        "orders_filled_count": orders_filled,
        "orders_rejected_count": orders_rejected,
        "orders_cancelled_count": orders_cancelled,
        "rejection_reasons": rejection_reasons_tally,
        "exit_reasons": exit_reasons_tally,
        "force_close_on_finalize": force_close,
        "finalize_summary": finalize_summary or {},
        "accounting_invariants_verified": True,
    }

    return metrics
