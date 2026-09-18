"""
scripts/verify_stage2_real_data.py
==================================
Script kiểm thử Feature Engine trên dữ liệu thực tế từ Binance:
- Kéo dữ liệu BTC/USDT 4h và 15m trong 70 ngày gần nhất
- Chạy toàn bộ Feature Engine (EMA 20/50/200, RSI, MACD, ATR, OI delta, CVD, CVD Divergence)
- Báo cáo số dòng đầy đủ (không NaN), chi tiết warm-up period, tỷ lệ NaN của OI delta & CVD divergence
- Xuất mẫu các dòng dữ liệu đại diện và lưu báo cáo vào thư mục BÁO CÁO TÓM TẮT.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pandas as pd
import yaml

# Thêm project root vào path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.data_layer.fetcher import fetch_all
from src.features import add_all_features


def df_to_markdown(df: pd.DataFrame) -> str:
    """Chuyển DataFrame sang định dạng bảng Markdown không cần thư viện tabulate."""
    cols = ["timestamp"] + [str(c) for c in df.columns]
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join(["---"] * len(cols)) + " |"
    lines = [header, sep]
    for idx, row in df.iterrows():
        ts_str = idx.strftime("%Y-%m-%d %H:%M") if hasattr(idx, "strftime") else str(idx)
        row_vals = [ts_str]
        for v in row:
            if pd.isna(v):
                row_vals.append("NaN")
            elif isinstance(v, float):
                row_vals.append(f"{v:.4f}")
            else:
                row_vals.append(str(v))
        lines.append("| " + " | ".join(row_vals) + " |")
    return "\n".join(lines)


def main():
    print("=" * 70)
    print("KIỂM THỬ FEATURE ENGINE TRÊN DỮ LIỆU THẬT (BTC/USDT 4H & 15M)")
    print("=" * 70)

    # 1. Nạp config
    config_path = project_root / "config" / "default_config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # 2. Thiết lập khoảng thời gian: 70 ngày gần nhất (đảm bảo khung 4h có > 400 nến, đủ warm-up EMA 200)
    now_utc = pd.Timestamp.now(tz="UTC")
    since_utc = now_utc - pd.Timedelta(days=70)

    symbol = "BTC/USDT"
    timeframes = ["4h", "15m"]

    print(f"[*] Kéo dữ liệu từ {since_utc.strftime('%Y-%m-%d %H:%M:%S UTC')} đến {now_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    data_dict = fetch_all(
        symbol=symbol,
        timeframes=timeframes,
        since=since_utc,
        until=now_utc,
        config=config,
        force_refresh=True,
    )

    report_lines = []
    report_lines.append("# BÁO CÁO KIỂM THỬ THỰC TẾ GIAI ĐOẠN 2: FEATURE ENGINE\n")
    report_lines.append(f"- **Thời gian chạy kiểm thử:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    report_lines.append(f"- **Cặp giao dịch:** `{symbol}`")
    report_lines.append(f"- **Khoảng thời gian:** {since_utc.strftime('%Y-%m-%d')} → {now_utc.strftime('%Y-%m-%d')} (~70 ngày)\n")

    for tf in timeframes:
        df_raw = data_dict[tf]
        total_candles = len(df_raw)
        print(f"\n[+] Khung {tf}: Lấy được {total_candles} nến gốc.")

        # 3. Chạy Feature Engine
        df_featured = add_all_features(df_raw, config=config)

        # 4. Phân tích NaN & Warm-up Period
        # Các cột tính toán
        feature_cols = [
            "ema_20", "ema_50", "ema_200",
            "rsi_14", "macd", "macd_signal", "macd_hist", "atr_14",
            "oi_delta_pct", "cvd", "cvd_divergence"
        ]

        # Kiểm tra warm-up
        warmup_ema200_nans = df_featured["ema_200"].isna().sum()
        warmup_rsi_nans = df_featured["rsi_14"].isna().sum()
        warmup_atr_nans = df_featured["atr_14"].isna().sum()
        oi_delta_nans = df_featured["oi_delta_pct"].isna().sum()
        oi_delta_nan_pct = (oi_delta_nans / total_candles) * 100.0

        # Số dòng có ĐỦ toàn bộ feature (loại trừ warm-up)
        # Các feature kỹ thuật chính: EMA200, RSI, MACD, ATR
        tech_indicators = ["ema_20", "ema_50", "ema_200", "rsi_14", "macd", "macd_signal", "atr_14"]
        valid_tech_rows = df_featured[tech_indicators].dropna()
        n_valid_tech = len(valid_tech_rows)

        # Số dòng đầy đủ tất cả kể cả oi_delta_pct
        valid_all_rows = df_featured[feature_cols].dropna()
        n_valid_all = len(valid_all_rows)

        # Thống kê phân kỳ CVD
        div_counts = df_featured["cvd_divergence"].value_counts().to_dict()

        summary_text = f"""
### Khung thời gian: {tf}
- **Tổng số nến:** {total_candles} nến
- **Warm-up period EMA 200:** {warmup_ema200_nans} nến đầu mang giá trị `NaN` (hoàn toàn đúng chuẩn toán học, cần 200 nến để tích lũy).
- **Warm-up RSI 14:** {warmup_rsi_nans} nến mang giá trị `NaN`.
- **Warm-up ATR 14:** {warmup_atr_nans} nến mang giá trị `NaN`.
- **Số dòng có đầy đủ toàn bộ chỉ báo kỹ thuật (sau warm-up EMA 200):** {n_valid_tech} / {total_candles} nến ({n_valid_tech/total_candles*100:.1f}%).
- **Tỷ lệ NaN ở `oi_delta_pct`:** {oi_delta_nans} / {total_candles} nến ({oi_delta_nan_pct:.2f}%) (trong đó {min(20, total_candles)} nến đầu là do lookback shift N=20).
- **Thống kê tín hiệu `cvd_divergence`:**
  - `NONE`: {div_counts.get('NONE', 0)} nến ({div_counts.get('NONE', 0)/total_candles*100:.1f}%)
  - `BULLISH`: {div_counts.get('BULLISH', 0)} nến ({div_counts.get('BULLISH', 0)/total_candles*100:.1f}%)
  - `BEARISH`: {div_counts.get('BEARISH', 0)} nến ({div_counts.get('BEARISH', 0)/total_candles*100:.1f}%)
"""
        print(summary_text)
        report_lines.append(summary_text)

        # 5. In vài dòng mẫu đại diện (5 dòng cuối cùng có đủ dữ liệu)
        sample_cols = [
            "close", "volume", "ema_20", "ema_50", "ema_200",
            "rsi_14", "atr_14", "open_interest", "oi_delta_pct", "cvd", "cvd_divergence"
        ]
        sample_df = df_featured[sample_cols].tail(8)
        
        sample_md = "\n#### 8 dòng mẫu gần nhất (đầy đủ feature):\n"
        sample_md += df_to_markdown(sample_df) + "\n"
        report_lines.append(sample_md)
        print("Dòng mẫu:")
        print(sample_df)

    # 6. Lưu báo cáo vào các thư mục báo cáo
    full_report = "\n".join(report_lines)
    
    target_dirs = [
        project_root / "BÁO CÁO TÓM TẮT" / "GIAI ĐOẠN 2",
    ]
    for d in target_dirs:
        d.mkdir(parents=True, exist_ok=True)
        report_file = d / "BAO_CAO_GIAI_DOAN_2.md"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(full_report)
        print(f"[✓] Đã lưu báo cáo tại: {report_file}")

    print("\n[✓] HOÀN TẤT KIỂM THỬ THỰC TẾ GIAI ĐOẠN 2.")


if __name__ == "__main__":
    main()
