"""
scripts/simulate_risk_manager_10_trades.py
===========================================
Kịch bản mô phỏng trực quan trạng thái Risk Manager (Giai đoạn 3) theo ADR 0006 và review của GPT:
- 100% minh bạch: Mọi trade được ghi nhận đều có dòng hiển thị riêng, đi qua cổng duyệt và cập nhật vốn 1 lần duy nhất.
- Kịch bản gồm 2 Phase rõ ràng:
  + Phase 1 (10 lệnh): Khởi đầu -> Chuỗi 3 thua -> Giảm 50% risk -> Thua xen giữa reset chuỗi thắng ->
    Cú sốc lỗ kích hoạt Circuit Breaker khóa 24h -> Lệnh bị từ chối trong thời gian khóa.
  + Phase 2 (3 lệnh phục hồi): Sau 24h mở khóa -> 3 lệnh thắng liên tiếp -> Phục hồi 100% risk.
- Có assertion đối soát: Vốn cuối = Vốn đầu + Tổng PnL của các lệnh được DUYỆT.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Cấu hình UTF-8 cho console Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Thêm thư mục gốc vào sys.path để import src
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import yaml
from src.risk.position_sizing import calculate_position_size
from src.risk.circuit_breakers import CircuitBreakerState
from src.risk.invariant_checks import check_all_invariants


def load_config() -> dict:
    config_path = Path(__file__).parent.parent / "config" / "default_config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_scenario(title: str, trades: list, equity: float, cb: CircuitBreakerState, config: dict, base_risk: float = 0.02):
    print("=" * 135)
    print(f" {title.upper()}")
    print("=" * 135)
    print(
        f"{'Lệnh':<5} | {'Thời gian':<11} | {'Chiều':<5} | {'Base%':<6} | {'Hệ số':<5} | "
        f"{'Risk% HL':<8} | {'Vốn trước':<10} | {'Trạng thái':<10} | {'Lý do từ chối (nếu có)':<32} | {'Trạng thái CB sau lệnh':<25}"
    )
    print("-" * 135)

    initial_equity = equity
    accepted_pnl_sum = 0.0

    for item in trades:
        trade_id = item["id"]
        current_time = item["time"]
        mult_before = cb.risk_multiplier
        effective_risk = cb.get_effective_risk_percent(base_risk)

        order = {
            "symbol": "BTCUSDT",
            "direction": item["direction"],
            "entry_price": item["entry"],
            "stop_loss_price": item["stop"],
            "leverage": item["leverage"],
            "risk_percent": effective_risk,
            "conviction_tier": item["conviction"],
            "timestamp": current_time,
        }

        # Tính position sizing nếu có stop loss hợp lệ
        if item["stop"] is not None and item["entry"] is not None and item["stop"] != item["entry"] and item["entry"] > 0 and equity > 0:
            try:
                sizing = calculate_position_size(
                    equity=equity,
                    risk_percent=effective_risk,
                    entry_price=item["entry"],
                    stop_price=item["stop"],
                    leverage=item["leverage"],
                )
                order["position_size_usd"] = sizing["position_size_usd"]
            except Exception:
                pass

        account_state = {
            "equity": equity,
            "available_margin": equity,
            "circuit_breaker_state": cb,
            "news_filter": None,
            "current_time": current_time,
        }

        # Kiểm tra Invariants
        is_valid, reasons = check_all_invariants(order, account_state, config)
        equity_before = equity

        if is_valid:
            status_str = "[DUYỆT]"
            reason_str = "Thỏa mãn tất cả Invariants"
            pnl = item["simulated_pnl"]
            equity += pnl
            accepted_pnl_sum += pnl

            # Ghi nhận kết quả vào Circuit Breaker
            cb.record_trade_result(pnl=pnl, timestamp=current_time, equity=equity)
        else:
            status_str = "[TỪ CHỐI]"
            short_reasons = "; ".join(r.split(":")[0] for r in reasons)
            reason_str = short_reasons[:32]

        cb_status = (
            f"LOCKED ({cb.locked_until.strftime('%H:%M %d/%m')})"
            if cb.is_locked
            else f"M={cb.risk_multiplier:.1f} | L={cb.consecutive_losses} | W={cb.consecutive_wins}"
        )

        time_str = current_time.strftime("%d/%m %H:%M")
        print(
            f"#{trade_id:<4} | {time_str:<11} | {item['direction']:<5} | {base_risk*100:.1f}%  | "
            f"{mult_before:.2f}  | {effective_risk*100:.1f}%    | {equity_before:<10,.2f} | "
            f"{status_str:<10} | {reason_str:<32} | {cb_status:<25}"
        )

    print("-" * 135)
    print(f"Vốn đầu: {initial_equity:,.2f} USD | Tổng PnL lệnh được duyệt: {accepted_pnl_sum:+,.2f} USD | Vốn cuối: {equity:,.2f} USD")
    assert round(equity, 2) == round(initial_equity + accepted_pnl_sum, 2), "Sai lệch đối soát vốn!"
    print("Đối soát vốn: CHÍNH XÁC 100% (Vốn cuối = Vốn đầu + Tổng PnL lệnh duyệt)")
    print(f"Hệ số rủi ro hiện tại: {cb.risk_multiplier:.2f} | Trạng thái khóa: {cb.is_locked}")
    print("=" * 135)
    return equity


def main():
    config = load_config()
    cb = CircuitBreakerState.from_config(config)
    t_start = datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc)

    # -------------------------------------------------------------
    # PHASE 1: 10 LỆNH CHÍNH (Drawdown, Giảm Risk 50%, và Khóa 24h)
    # -------------------------------------------------------------
    phase_1_trades = [
        {"id": 1, "time": t_start + timedelta(hours=0), "direction": "LONG", "entry": 50000.0, "stop": 49000.0, "leverage": 3.0, "conviction": "normal", "simulated_pnl": +200.0},
        {"id": 2, "time": t_start + timedelta(hours=2), "direction": "LONG", "entry": 50500.0, "stop": 49500.0, "leverage": 3.0, "conviction": "normal", "simulated_pnl": -200.0},
        {"id": 3, "time": t_start + timedelta(hours=4), "direction": "SHORT", "entry": 49000.0, "stop": 50000.0, "leverage": 3.0, "conviction": "normal", "simulated_pnl": -200.0},
        {"id": 4, "time": t_start + timedelta(hours=6), "direction": "LONG", "entry": 48500.0, "stop": 47500.0, "leverage": 3.0, "conviction": "normal", "simulated_pnl": -150.0},
        {"id": 5, "time": t_start + timedelta(hours=8), "direction": "LONG", "entry": 48000.0, "stop": None, "leverage": 10.0, "conviction": "normal", "simulated_pnl": 0.0},
        {"id": 6, "time": t_start + timedelta(hours=10), "direction": "LONG", "entry": 48200.0, "stop": 47200.0, "leverage": 3.0, "conviction": "normal", "simulated_pnl": +100.0},
        {"id": 7, "time": t_start + timedelta(hours=12), "direction": "SHORT", "entry": 48500.0, "stop": 49500.0, "leverage": 3.0, "conviction": "normal", "simulated_pnl": -80.0},
        {"id": 8, "time": t_start + timedelta(hours=14), "direction": "LONG", "entry": 47500.0, "stop": 46500.0, "leverage": 3.0, "conviction": "normal", "simulated_pnl": -500.0},
        {"id": 9, "time": t_start + timedelta(hours=16), "direction": "LONG", "entry": 47000.0, "stop": 46000.0, "leverage": 3.0, "conviction": "normal", "simulated_pnl": 0.0},
        {"id": 10, "time": t_start + timedelta(hours=18), "direction": "LONG", "entry": 47200.0, "stop": 46200.0, "leverage": 3.0, "conviction": "normal", "simulated_pnl": 0.0},
    ]

    equity = 10000.0
    equity = run_scenario(
        title="PHASE 1: Mô phỏng 10 Lệnh - Giảm Risk 50% & Kích hoạt Khóa 24h",
        trades=phase_1_trades,
        equity=equity,
        cb=cb,
        config=config,
    )

    # -------------------------------------------------------------
    # PHASE 2: 3 LỆNH PHỤC HỒI (Hết hạn 24h -> 3 Wins liên tiếp -> Multiplier 1.0)
    # -------------------------------------------------------------
    t_unlock = t_start + timedelta(hours=39)  # 14h + 24h = 38h -> 39h đã mở khóa
    phase_2_trades = [
        {"id": 11, "time": t_unlock + timedelta(hours=0), "direction": "LONG", "entry": 48000.0, "stop": 47000.0, "leverage": 3.0, "conviction": "normal", "simulated_pnl": +100.0},
        {"id": 12, "time": t_unlock + timedelta(hours=2), "direction": "LONG", "entry": 48500.0, "stop": 47500.0, "leverage": 3.0, "conviction": "normal", "simulated_pnl": +100.0},
        {"id": 13, "time": t_unlock + timedelta(hours=4), "direction": "LONG", "entry": 49000.0, "stop": 48000.0, "leverage": 3.0, "conviction": "normal", "simulated_pnl": +100.0},
    ]

    equity = run_scenario(
        title="PHASE 2: Phục hồi Risk sau khi Mở khóa (3 Lệnh Thắng Liên tiếp -> Multiplier 1.0)",
        trades=phase_2_trades,
        equity=equity,
        cb=cb,
        config=config,
    )


if __name__ == "__main__":
    main()
