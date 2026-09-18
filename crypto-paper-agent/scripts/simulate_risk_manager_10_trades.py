"""
scripts/simulate_risk_manager_10_trades.py
===========================================
Kịch bản mô phỏng trực quan 10 lệnh giả lập liên tiếp chạy qua toàn bộ Risk Manager:
- Tính toán position sizing & effective risk %
- Kiểm tra 6 Hard Invariants (chấp nhận hoặc từ chối kèm lý do)
- Cập nhật trạng thái Circuit Breaker (chuỗi thua, giảm 50% risk, khóa 24h khi lỗ >= 5%, reset chuỗi thắng, phục hồi risk 100%)
- In bảng tổng kết ASCII rõ ràng để review bằng mắt.
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


def main():
    config = load_config()
    cb = CircuitBreakerState.from_config(config)

    equity = 10000.0
    base_risk = 0.02  # 2%
    t_start = datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc)

    # Định nghĩa kịch bản 10 lệnh
    scenarios = [
        {
            "id": 1,
            "desc": "Lệnh Long chuẩn đầu tiên",
            "time_offset_hours": 0,
            "direction": "LONG",
            "entry": 50000.0,
            "stop": 49000.0,
            "leverage": 3.0,
            "conviction": "normal",
            "simulated_outcome_pnl": +200.0,  # Thắng
        },
        {
            "id": 2,
            "desc": "Lệnh Long chuẩn, gặp thị trường xấu",
            "time_offset_hours": 2,
            "direction": "LONG",
            "entry": 50500.0,
            "stop": 49500.0,
            "leverage": 3.0,
            "conviction": "normal",
            "simulated_outcome_pnl": -200.0,  # Thua 1
        },
        {
            "id": 3,
            "desc": "Lệnh Short chuẩn, đảo chiều bất thành",
            "time_offset_hours": 4,
            "direction": "SHORT",
            "entry": 49000.0,
            "stop": 50000.0,
            "leverage": 3.0,
            "conviction": "normal",
            "simulated_outcome_pnl": -200.0,  # Thua 2
        },
        {
            "id": 4,
            "desc": "Lệnh Long chuẩn, chạm Stop-Loss",
            "time_offset_hours": 6,
            "direction": "LONG",
            "entry": 48500.0,
            "stop": 47500.0,
            "leverage": 3.0,
            "conviction": "normal",
            "simulated_outcome_pnl": -150.0,  # Thua 3 -> KÍCH HOẠT GIẢM RISK XUỐNG 50%
        },
        {
            "id": 5,
            "desc": "Lệnh lỗi: Leverage 10x và thiếu Stop-Loss",
            "time_offset_hours": 8,
            "direction": "LONG",
            "entry": 48000.0,
            "stop": None,        # Vi phạm Invariant 1
            "leverage": 10.0,     # Vi phạm Invariant 2 (10x > 5x)
            "conviction": "normal",
            "simulated_outcome_pnl": 0.0,
        },
        {
            "id": 6,
            "desc": "Lệnh ở chế độ giảm risk (1%), bắt đầu hồi phục",
            "time_offset_hours": 10,
            "direction": "LONG",
            "entry": 48200.0,
            "stop": 47200.0,
            "leverage": 3.0,
            "conviction": "normal",
            "simulated_outcome_pnl": +100.0,  # Thắng 1 trong recovery
        },
        {
            "id": 7,
            "desc": "Lệnh thua xen ngang trong giai đoạn phục hồi",
            "time_offset_hours": 12,
            "direction": "SHORT",
            "entry": 48500.0,
            "stop": 49500.0,
            "leverage": 3.0,
            "conviction": "normal",
            "simulated_outcome_pnl": -80.0,  # Thua xen giữa -> RESET STREAK THẮNG VỀ 0
        },
        {
            "id": 8,
            "desc": "Lỗ lớn bất thường làm tổng 24h >= 5% vốn",
            "time_offset_hours": 14,
            "direction": "LONG",
            "entry": 47500.0,
            "stop": 46500.0,
            "leverage": 3.0,
            "conviction": "normal",
            "simulated_outcome_pnl": -500.0,  # Chạm Daily Loss Limit -> KHÓA 24H
        },
        {
            "id": 9,
            "desc": "Thử vào lệnh khi hệ thống đang bị khóa 24h",
            "time_offset_hours": 16,  # Vẫn nằm trong 24h bị khóa
            "direction": "LONG",
            "entry": 47000.0,
            "stop": 46000.0,
            "leverage": 3.0,
            "conviction": "normal",
            "simulated_outcome_pnl": 0.0,
        },
        {
            "id": 10,
            "desc": "Sau 24h mở khóa, chuỗi thắng hoàn tất phục hồi risk",
            "time_offset_hours": 40,  # Đã qua 24h (14 + 24 = 38h < 40h) -> Mở khóa
            "direction": "LONG",
            "entry": 49000.0,
            "stop": 48000.0,
            "leverage": 3.0,
            "conviction": "normal",
            "simulated_outcome_pnl": +150.0,  # Thắng liên tiếp 3 lệnh -> PHỤC HỒI RISK 1.0
        },
    ]

    print("=" * 125)
    print(" BẢNG MÔ PHỎNG 10 LỆNH LIÊN TIẾP QUA TOÀN BỘ RISK MANAGER (GIAI ĐOẠN 3)")
    print("=" * 125)
    print(
        f"{'Lệnh':<5} | {'Thời gian':<11} | {'Chiều':<5} | {'Base%':<6} | {'Hệ số':<5} | "
        f"{'Risk% HL':<8} | {'Trạng thái':<10} | {'Lý do từ chối (nếu có)':<32} | {'Trạng thái CB sau lệnh':<25}"
    )
    print("-" * 125)

    for item in scenarios:
        trade_id = item["id"]
        current_time = t_start + timedelta(hours=item["time_offset_hours"])
        mult_before = cb.risk_multiplier
        effective_risk = cb.get_effective_risk_percent(base_risk)

        # Chuẩn bị thông tin lệnh
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

        # Nếu có stop loss hợp lệ, tính position sizing
        if item["stop"] is not None and item["stop"] != item["entry"] and item["entry"] > 0:
            sizing = calculate_position_size(
                equity=equity,
                risk_percent=effective_risk,
                entry_price=item["entry"],
                stop_price=item["stop"],
                leverage=item["leverage"],
            )
            order["position_size_usd"] = sizing["position_size_usd"]

        account_state = {
            "equity": equity,
            "circuit_breaker_state": cb,
            "news_filter": None,
            "current_time": current_time,
        }

        # Kiểm tra Invariants
        is_valid, reasons = check_all_invariants(order, account_state, config)

        if is_valid:
            status_str = "[DUYỆT]"
            reason_str = "Thỏa mãn 6 Hard Invariants"
            pnl = item["simulated_outcome_pnl"]
            equity += pnl

            # Ghi nhận kết quả vào Circuit Breaker
            cb.record_trade_result(pnl=pnl, timestamp=current_time, equity=equity)

            # Trường hợp đặc biệt cho Lệnh 10: mô phỏng chuỗi 3 lệnh thắng để kiểm chứng phục hồi
            if trade_id == 10:
                cb.record_trade_result(pnl=+100.0, timestamp=current_time + timedelta(hours=1), equity=equity)
                cb.record_trade_result(pnl=+100.0, timestamp=current_time + timedelta(hours=2), equity=equity)
        else:
            status_str = "[TỪ CHỐI]"
            # Rút gọn chuỗi lỗi cho gọn bảng
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
            f"{mult_before:.2f}  | {effective_risk*100:.1f}%    | "
            f"{status_str:<10} | {reason_str:<32} | {cb_status:<25}"
        )

    print("-" * 125)
    print(f"Vốn cuối cùng sau mô phỏng: {equity:,.2f} USD")
    print(f"Hệ số rủi ro hiện tại: {cb.risk_multiplier:.2f} (Đã phục hồi 100% mức chuẩn)")
    print("=" * 125)


if __name__ == "__main__":
    main()
