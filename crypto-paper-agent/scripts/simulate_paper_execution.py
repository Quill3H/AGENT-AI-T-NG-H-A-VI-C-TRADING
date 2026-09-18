"""
scripts/simulate_paper_execution.py
====================================
Kịch bản mô phỏng kiểm chứng Paper Execution Engine (Giai đoạn 4):
Phần A: Kịch bản tổng hợp (Synthetic Deterministic) kiểm thử toàn diện các case:
        LONG win, chuỗi thua kích hoạt giảm risk, funding settlement, gap exit, phục hồi risk.
Phần B: Demo khớp lệnh trên dữ liệu OHLCV thật từ Binance BTCUSDT 15m và Funding Rate 8h.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pandas as pd
import yaml

# Cấu hình UTF-8 cho console Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Thêm thư mục gốc vào sys.path để import src
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.execution.order_models import (
    ExitReason,
    OrderDirection,
    OrderRequest,
    OrderStatus,
)
from src.execution.paper_broker import PaperBroker


def load_config() -> dict:
    config_path = project_root / "config" / "default_config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_synthetic_simulation():
    print("=" * 145)
    print(" PHẦN A: MÔ PHỎNG TỔNG HỢP DETERMINISTIC (OFFLINE SYNTHETIC SIMULATION)")
    print("=" * 145)
    
    config = load_config()
    broker = PaperBroker(config=config, initial_balance=10000.0)
    
    print(f"Vốn khởi tạo: {broker.wallet_balance:,.2f} USD | Đòn bẩy tối đa: 5.0x | Phí Taker: 0.05% | Slippage: 0.03%")
    print("-" * 145)
    print(
        f"{'STT':<4} | {'Thời gian (UTC)':<17} | {'Loại sự kiện':<14} | {'Chiều':<5} | {'Giá khớp':<9} | "
        f"{'KL (Qty)':<8} | {'Ký quỹ':<9} | {'Phí (Fee)':<8} | {'Funding':<8} | {'Net PnL':<10} | "
        f"{'Số dư Ví':<11} | {'Vốn (Equity)':<12} | {'Risk Multiplier':<15}"
    )
    print("-" * 145)

    t = datetime(2026, 9, 1, 7, 30, tzinfo=timezone.utc)
    event_idx = 1

    # --- KỊCH BẢN 1: Giao dịch LONG có lãi, đóng tại Take Profit và đi qua 1 kỳ Funding ---
    # Nến 0: 07:30
    broker.process_candle({"open_time": t, "open": 50000.0, "high": 50100.0, "low": 49900.0, "close": 50000.0, "symbol": "BTCUSDT", "timeframe": "1m"})
    t += timedelta(minutes=1)

    # Gửi lệnh LONG lúc 07:31
    req1 = OrderRequest(
        symbol="BTCUSDT",
        direction=OrderDirection.LONG,
        signal_price=50000.0,
        stop_loss_price=48000.0,
        take_profit_price=52000.0,
        signal_time=t,
        leverage=2.0,
        base_risk_percent=0.02,
        conviction_tier="normal",
        requested_quantity=None,  # 0.1 BTC = ~5,000 USD notional
    )
    broker.submit_order(req1)

    # Nến 1: 07:31 - Khớp lệnh tại Open 50,000 + slippage
    broker.process_candle({"open_time": t, "open": 50000.0, "high": 50100.0, "low": 49950.0, "close": 50050.0, "symbol": "BTCUSDT", "timeframe": "1m"})
    pos1 = broker.positions["BTCUSDT"]
    print(
        f"{event_idx:<4} | {t.strftime('%Y-%m-%d %H:%M'):<17} | {'ENTRY_FILLED':<14} | {'LONG':<5} | {pos1.entry_price:<9.2f} | "
        f"{pos1.quantity:<8.3f} | {pos1.initial_margin:<9.2f} | {pos1.entry_fee:<8.3f} | {'0.000':<8} | {'0.000':<10} | "
        f"{broker.wallet_balance:<11.2f} | {broker.equity:<12.2f} | {broker.circuit_breaker.risk_multiplier:<15.2f}"
    )
    event_idx += 1
    t += timedelta(minutes=1)

    # Nến 07:32 - 07:59: Giá biến động nhẹ
    for _ in range(28):
        broker.process_candle({"open_time": t, "open": 50100.0, "high": 50200.0, "low": 50000.0, "close": 50150.0, "symbol": "BTCUSDT", "timeframe": "1m"})
        t += timedelta(minutes=1)

    # Nến 08:00: MỐC SETTLEMENT FUNDING
    broker.process_candle({
        "open_time": t, "open": 50200.0, "high": 50300.0, "low": 50100.0, "close": 50250.0,
        "symbol": "BTCUSDT", "timeframe": "1m", "funding_rate": 0.0001
    })
    f_evt = broker.funding_history[-1]
    print(
        f"{event_idx:<4} | {t.strftime('%Y-%m-%d %H:%M'):<17} | {'FUNDING_SETTLE':<14} | {'LONG':<5} | {50200.0:<9.2f} | "
        f"{pos1.quantity:<8.3f} | {pos1.isolated_collateral:<9.2f} | {'0.000':<8} | {f_evt.cashflow_usd:<8.3f} | {'0.000':<10} | "
        f"{broker.wallet_balance:<11.2f} | {broker.equity:<12.2f} | {broker.circuit_breaker.risk_multiplier:<15.2f}"
    )
    event_idx += 1
    t += timedelta(minutes=1)

    # Nến 08:01: Giá tăng mạnh chạm Take Profit 52,000
    broker.process_candle({"open_time": t, "open": 50300.0, "high": 52500.0, "low": 50200.0, "close": 52100.0, "symbol": "BTCUSDT", "timeframe": "1m"})
    trade1 = broker.trade_history[-1]
    print(
        f"{event_idx:<4} | {t.strftime('%Y-%m-%d %H:%M'):<17} | {'TAKE_PROFIT':<14} | {'LONG':<5} | {trade1.exit_price:<9.2f} | "
        f"{trade1.quantity:<8.3f} | {'0.00':<9} | {trade1.exit_fee:<8.3f} | {trade1.funding_cashflow:<8.3f} | {trade1.net_pnl:<10.2f} | "
        f"{broker.wallet_balance:<11.2f} | {broker.equity:<12.2f} | {broker.circuit_breaker.risk_multiplier:<15.2f}"
    )
    event_idx += 1
    t += timedelta(minutes=1)

    # --- KỊCH BẢN 2: Chuỗi 3 lệnh thua liên tiếp chạm SL -> Kích hoạt giảm Risk Multiplier xuống 0.5 ---
    for streak_i in range(1, 4):
        broker.process_candle({"open_time": t, "open": 50000.0, "high": 50050.0, "low": 49950.0, "close": 50000.0, "symbol": "BTCUSDT", "timeframe": "1m"})
        t += timedelta(minutes=1)
        req = OrderRequest(
            symbol="BTCUSDT", direction=OrderDirection.LONG, signal_price=50000.0, stop_loss_price=49000.0,
            signal_time=t, leverage=2.0, base_risk_percent=0.02, requested_quantity=None
        )
        broker.submit_order(req)
        # Nến khớp lệnh
        broker.process_candle({"open_time": t, "open": 50000.0, "high": 50050.0, "low": 49950.0, "close": 50000.0, "symbol": "BTCUSDT", "timeframe": "1m"})
        t += timedelta(minutes=1)
        # Nến sập chạm SL 49,000
        broker.process_candle({"open_time": t, "open": 49900.0, "high": 49950.0, "low": 48500.0, "close": 48800.0, "symbol": "BTCUSDT", "timeframe": "1m"})
        tr = broker.trade_history[-1]
        print(
            f"{event_idx:<4} | {t.strftime('%Y-%m-%d %H:%M'):<17} | {f'STOP_LOSS #{streak_i}':<14} | {'LONG':<5} | {tr.exit_price:<9.2f} | "
            f"{tr.quantity:<8.3f} | {'0.00':<9} | {tr.exit_fee:<8.3f} | {'0.000':<8} | {tr.net_pnl:<10.2f} | "
            f"{broker.wallet_balance:<11.2f} | {broker.equity:<12.2f} | {broker.circuit_breaker.risk_multiplier:<15.2f}"
        )
        event_idx += 1
        t += timedelta(minutes=1)

    assert broker.circuit_breaker.consecutive_losses == 3
    assert broker.circuit_breaker.risk_multiplier == 0.5
    print(">>> Circuit Breaker: Đã phát hiện 3 trận thua liên tiếp -> Giảm Risk Multiplier xuống 0.50!")

    # --- KỊCH BẢN 3: Nhảy Gap Down tại Pha 1 (Open Time) vượt qua Stop-Loss ---
    broker.process_candle({"open_time": t, "open": 50000.0, "high": 50050.0, "low": 49950.0, "close": 50000.0, "symbol": "BTCUSDT", "timeframe": "1m"})
    t += timedelta(minutes=1)
    req_gap = OrderRequest(
        symbol="BTCUSDT", direction=OrderDirection.LONG, signal_price=50000.0, stop_loss_price=48000.0,
        signal_time=t, leverage=2.0, base_risk_percent=0.02, requested_quantity=None
    )
    broker.submit_order(req_gap)
    # Khớp vào vị thế
    broker.process_candle({"open_time": t, "open": 50000.0, "high": 50050.0, "low": 49950.0, "close": 50000.0, "symbol": "BTCUSDT", "timeframe": "1m"})
    t += timedelta(minutes=1)
    # Nến tiếp theo mở cửa nhảy Gap cực mạnh xuống 45,000 (thủng cả SL 48,000)
    broker.process_candle({"open_time": t, "open": 45000.0, "high": 45500.0, "low": 44800.0, "close": 45200.0, "symbol": "BTCUSDT", "timeframe": "1m"})
    tr_gap = broker.trade_history[-1]
    print(
        f"{event_idx:<4} | {t.strftime('%Y-%m-%d %H:%M'):<17} | {'GAP_DOWN_EXIT':<14} | {'LONG':<5} | {tr_gap.exit_price:<9.2f} | "
        f"{tr_gap.quantity:<8.3f} | {'0.00':<9} | {tr_gap.exit_fee:<8.3f} | {'0.000':<8} | {tr_gap.net_pnl:<10.2f} | "
        f"{broker.wallet_balance:<11.2f} | {broker.equity:<12.2f} | {broker.circuit_breaker.risk_multiplier:<15.2f}"
    )
    event_idx += 1
    t += timedelta(minutes=1)
    print(f">>> Gap Exit: Lệnh thoát tại giá Open thực tế {tr_gap.exit_price:,.2f} USD (kèm slippage bán), không thể thoát ở giá SL 48,000.00!")

    # Sau khi bị khóa 24h, thời gian tiến tới ngày hôm sau (25 tiếng sau) để hết hạn khóa
    t += timedelta(hours=25)
    print(">>> Circuit Breaker: Đã chờ 25 giờ qua thời gian khóa 24h. Hệ thống tự động mở khóa giao dịch!")

    # --- KỊCH BẢN 4: Chuỗi 3 lệnh thắng liên tiếp -> Phục hồi Risk Multiplier về 1.0 ---
    for recov_i in range(1, 4):
        broker.process_candle({"open_time": t, "open": 50000.0, "high": 50050.0, "low": 49950.0, "close": 50000.0, "symbol": "BTCUSDT", "timeframe": "1m"})
        t += timedelta(minutes=1)
        req = OrderRequest(
            symbol="BTCUSDT", direction=OrderDirection.LONG, signal_price=50000.0, stop_loss_price=48000.0, take_profit_price=51000.0,
            signal_time=t, leverage=2.0, base_risk_percent=0.02, requested_quantity=None
        )
        broker.submit_order(req)
        # Nến khớp lệnh
        broker.process_candle({"open_time": t, "open": 50000.0, "high": 50050.0, "low": 49950.0, "close": 50000.0, "symbol": "BTCUSDT", "timeframe": "1m"})
        t += timedelta(minutes=1)
        # Nến chạm TP 51,000
        broker.process_candle({"open_time": t, "open": 50500.0, "high": 51500.0, "low": 50400.0, "close": 51200.0, "symbol": "BTCUSDT", "timeframe": "1m"})
        tr = broker.trade_history[-1]
        print(
            f"{event_idx:<4} | {t.strftime('%Y-%m-%d %H:%M'):<17} | {f'TAKE_PROFIT #{recov_i}':<14} | {'LONG':<5} | {tr.exit_price:<9.2f} | "
            f"{tr.quantity:<8.3f} | {'0.00':<9} | {tr.exit_fee:<8.3f} | {'0.000':<8} | {tr.net_pnl:<10.2f} | "
            f"{broker.wallet_balance:<11.2f} | {broker.equity:<12.2f} | {broker.circuit_breaker.risk_multiplier:<15.2f}"
        )
        event_idx += 1
        t += timedelta(minutes=1)

    assert broker.circuit_breaker.risk_multiplier == 1.0
    print(">>> Circuit Breaker Recovery: Đạt đủ 3 trận thắng liên tiếp -> Phục hồi Risk Multiplier về 1.00!")

    # Đối soát bất biến kế toán sau toàn bộ kịch bản Phần A
    broker.verify_accounting_invariants()
    total_trade_net_pnl = sum(tr.net_pnl for tr in broker.trade_history)
    expected_wallet = 10000.0 + total_trade_net_pnl
    assert abs(broker.wallet_balance - expected_wallet) < 1e-4
    print("-" * 145)
    print(f"Đối soát Kế toán Phần A THÀNH CÔNG: Vốn cuối = {broker.wallet_balance:,.2f} USD = Vốn ban đầu (10,000.00) + Tổng Net PnL ({total_trade_net_pnl:+,.2f})")
    print(f"Tổng số giao dịch đã thực hiện: {len(broker.trade_history)} | Vị thế mở còn lại: {len(broker.positions)}")
    print("=" * 145 + "\n")


def run_real_data_simulation():
    print("=" * 145)
    print(" PHẦN B: MÔ PHỎNG KHỚP LỆNH TRÊN DỮ LIỆU THẬT BINANCE CACHED (BTCUSDT 15M + FUNDING 8H)")
    print("=" * 145)

    ohlcv_path = project_root / "data" / "raw" / "binance" / "BTCUSDT" / "15m" / "ohlcv.parquet"
    funding_path = project_root / "data" / "raw" / "binance" / "BTCUSDT" / "8h" / "funding_rate.parquet"

    if not ohlcv_path.exists() or not funding_path.exists():
        print(f"LỖI: Không tìm thấy tệp cache dữ liệu tại {ohlcv_path}")
        return

    df_ohlcv = pd.read_parquet(ohlcv_path)
    df_funding = pd.read_parquet(funding_path)

    print(f"Nguồn dữ liệu OHLCV: {ohlcv_path.relative_to(project_root)} ({len(df_ohlcv)} nến)")
    print(f"Nguồn dữ liệu Funding: {funding_path.relative_to(project_root)} ({len(df_funding)} bản ghi)")
    
    # Chọn đoạn dữ liệu từ 2026-08-01 00:00 UTC (120 nến 15m)
    start_ts = pd.Timestamp("2026-08-01 00:00:00+0000")
    slice_ohlcv = df_ohlcv.loc[df_ohlcv.index >= start_ts].iloc[:120].copy()
    print(f"Khoảng thời gian mô phỏng: {slice_ohlcv.index[0]} -> {slice_ohlcv.index[-1]} ({len(slice_ohlcv)} nến 15m)")

    # Chuẩn bị mapping funding rate cho các mốc settlement 00, 08, 16 UTC
    funding_dict = {}
    for ts, row in df_funding.iterrows():
        norm_ts = ts.to_pydatetime().replace(minute=0, second=0, microsecond=0)
        funding_dict[norm_ts] = float(row["funding_rate"])

    config = load_config()
    broker = PaperBroker(config=config, initial_balance=10000.0)

    print("-" * 145)
    print(
        f"{'Nến #':<5} | {'Thời gian (UTC)':<17} | {'Loại sự kiện':<14} | {'Chiều':<5} | {'Giá khớp':<9} | "
        f"{'KL (Qty)':<8} | {'Ký quỹ':<9} | {'Phí (Fee)':<8} | {'Funding':<8} | {'Net PnL':<10} | "
        f"{'Số dư Ví':<11} | {'Vốn (Equity)':<12} | {'Risk Multiplier':<15}"
    )
    print("-" * 145)

    order_plan = [
        # Nến 2: Gửi lệnh hợp lệ (LONG tại giá Open của nến 2, SL 56k (buffer an toàn), TP 63.6k)
        {
            "trigger_idx": 2,
            "direction": OrderDirection.LONG,
            "stop_loss_price": 56000.0,
            "take_profit_price": 63600.0,
            "leverage": 2.0,
            "base_risk_percent": 0.02,
            "conviction_tier": "normal",
        },
        # Nến 117: Thử gửi lệnh VI PHẠM RISK INVARIANT (leverage 10x > max 5x) để kiểm tra Risk Gate
        {
            "trigger_idx": 117,
            "direction": OrderDirection.LONG,
            "stop_loss_price": 60000.0,
            "take_profit_price": 65000.0,
            "leverage": 10.0,
            "base_risk_percent": 0.02,
            "conviction_tier": "normal",
        },
    ]

    for i, (ts, row) in enumerate(slice_ohlcv.iterrows()):
        c_open_time = ts.to_pydatetime()
        norm_hour = c_open_time.replace(minute=0, second=0, microsecond=0)
        f_rate = funding_dict.get(norm_hour, None) if c_open_time.hour in {0, 8, 16} and c_open_time.minute == 0 else None

        candle = {
            "open_time": c_open_time,
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "funding_rate": f_rate,
        }

        # Kích hoạt signal ở nến này
        for item in order_plan:
            if item["trigger_idx"] == i:
                req = OrderRequest(
                    symbol="BTCUSDT",
                    direction=item["direction"],
                    signal_price=candle["open"],
                    stop_loss_price=item["stop_loss_price"],
                    take_profit_price=item.get("take_profit_price"),
                    signal_time=c_open_time,
                    leverage=item["leverage"],
                    base_risk_percent=item["base_risk_percent"],
                    conviction_tier=item.get("conviction_tier", "normal"),
                )
                broker.submit_order(req)

        # Xử lý nến theo 5 pha
        res = broker.process_candle(candle)

        # In log nếu có giao dịch fill hoặc đóng hoặc funding
        for ev in res["events"]:
            ev_type = ev["type"]
            if ev_type == "ORDER_FILLED":
                p = ev["position"]
                print(
                    f"{i:<5} | {c_open_time.strftime('%Y-%m-%d %H:%M'):<17} | {'ENTRY_FILLED':<14} | {p.direction.value:<5} | {p.entry_price:<9.2f} | "
                    f"{p.quantity:<8.4f} | {p.initial_margin:<9.2f} | {p.entry_fee:<8.3f} | {'0.000':<8} | {'0.000':<10} | "
                    f"{broker.wallet_balance:<11.2f} | {broker.equity:<12.2f} | {broker.circuit_breaker.risk_multiplier:<15.2f}"
                )
            elif ev_type == "FUNDING":
                fe = ev["event"]
                print(
                    f"{i:<5} | {c_open_time.strftime('%Y-%m-%d %H:%M'):<17} | {'FUNDING_EVENT':<14} | {'LONG':<5} | {candle['open']:<9.2f} | "
                    f"{'HOLD':<8} | {'N/A':<9} | {'0.000':<8} | {fe.cashflow_usd:<8.4f} | {'0.000':<10} | "
                    f"{broker.wallet_balance:<11.2f} | {broker.equity:<12.2f} | {broker.circuit_breaker.risk_multiplier:<15.2f}"
                )
            elif ev_type in ("INTRABAR_EXIT", "GAP_EXIT"):
                tr = ev["trade"]
                print(
                    f"{i:<5} | {c_open_time.strftime('%Y-%m-%d %H:%M'):<17} | {tr.exit_reason.value:<14} | {tr.direction.value:<5} | {tr.exit_price:<9.2f} | "
                    f"{tr.quantity:<8.4f} | {'0.00':<9} | {tr.exit_fee:<8.3f} | {tr.funding_cashflow:<8.4f} | {tr.net_pnl:<10.2f} | "
                    f"{broker.wallet_balance:<11.2f} | {broker.equity:<12.2f} | {broker.circuit_breaker.risk_multiplier:<15.2f}"
                )
            elif ev_type == "ORDER_REJECTED":
                print(
                    f"{i:<5} | {c_open_time.strftime('%Y-%m-%d %H:%M'):<17} | {'GATE_REJECT':<14} | {'LONG':<5} | "
                    f"{'N/A':<9} | {'0.000':<8} | {'0.00':<9} | {'0.000':<8} | {'0.000':<8} | {'0.000':<10} | "
                    f"{broker.wallet_balance:<11.2f} | {broker.equity:<12.2f} | {ev['reasons'][0][:28]}"
                )

    # Đối soát kế toán cuối phiên
    broker.verify_accounting_invariants()
    print("-" * 145)
    print(f"Tổng số nến đã xử lý: {len(slice_ohlcv)} nến 15m")
    print(f"Tổng số lệnh đóng: {len(broker.trade_history)} | Vị thế đang mở: {len(broker.positions)}")
    print(f"Số dư Ví cuối kỳ: {broker.wallet_balance:,.2f} USD | Vốn (Equity): {broker.equity:,.2f} USD")
    print(f"Ký quỹ khả dụng: {broker.available_margin:,.2f} USD | Ký quỹ bảo lưu: {broker.reserved_collateral:,.2f} USD")
    print("Đối soát bất biến kế toán: HOÀN TOÀN KHỚP (PASS)")
    print("=" * 145)


if __name__ == "__main__":
    run_synthetic_simulation()
    run_real_data_simulation()
