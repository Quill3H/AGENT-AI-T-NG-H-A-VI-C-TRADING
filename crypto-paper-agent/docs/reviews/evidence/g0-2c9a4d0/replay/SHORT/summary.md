# Performance Report: SMC_LIQUIDITY_SWEEP (BTCUSDT)
> **Report Status**: AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED  
> **Run ID**: `SHORT`  
> **Code Commit SHA**: `2c9a4d0985fc9eafd29386482793425c26d47835`  
> **Config Hash**: `9a82e52cfd430937c59020cd6b3c66b67873b7afb03d1799c16743589b900726`  
> **Verification Status**: AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED  
> **Reproduction Command**: `python scripts/verify_g0_replay.py --output-dir <NEW_DIRECTORY>`  
> **Generated At**: `2026-09-21T18:31:01.230243+00:00`  

---

## 1. Executive Summary

| Chỉ số (Metric) | Giá trị |
| :--- | :--- |
| **Strategy** | `SMC_LIQUIDITY_SWEEP` |
| **Symbol / Timeframes** | `BTCUSDT` (Signal: `5m`, Execution: `1m`) |
| **Backtest Period (UTC)** | `2024-01-01T01:00:00+00:00` $\rightarrow$ `2024-01-01T02:04:00+00:00` |
| **Bars Processed** | 1m=`65`, 5m=`13` |
| **Candle Gaps Detected** | `0` (Max gap: `0s`) |
| **Initial Capital** | `$10,000.00 USDT` |
| **Final Equity** | `$10,448.80 USDT` |
| **Net PnL** | `$+448.80 USDT` |
| **Total Return** | `+4.49%` |
| **Max Drawdown** | `-$169.74 USDT` (`1.67%`) |
| **Daily Sharpe Ratio** | `N/A` |
| **Calmar Ratio** | `2.69` |
| **Profit Factor** | `N/A (Loss = 0)` |
| **Expectancy (USD)** | `$+448.80` |
| **Expectancy (R)** | `+2.24 R` |
| **Loss Rate** | `0.00%` |
| **Average Realized RRR** | `+2.24 R` |
| **Completed Position Lifecycles** | `1` |
| **Realization Slices** | `3` |

Win rate, expectancy and SQN use completed position lifecycles. Realization slices
remain separate ledger rows; cash PnL also includes realized portions of open positions.

---

## 2. Accounting Reconciliation & Risk Audit

| Mục Đối Soát Kế Toán | Giá Trị (USDT) | Trạng Thái / Ghi Chú |
| :--- | :--- | :--- |
| **Vốn khởi điểm (Initial Capital)** | `$10,000.00` | Điểm neo ban đầu |
| **Số dư ví thực tế (Wallet Balance)** | `$10,448.80` | Trạng thái cuối kỳ |
| **Ký quỹ bị giữ (Reserved Collateral)** | `$0.00` | 0 khi kết thúc (force close) |
| **Hạn mức khả dụng (Available Margin)** | `$10,448.80` | Khả dụng mở vị thế mới |
| **Lãi/Lỗ chưa thực hiện (Unrealized PnL)** | `$0.00` | 0 khi tất toán |
| **Gross Price PnL** | `$+451.38` | Chênh lệch giá thuần |
| **Tổng phí giao dịch (Fees Paid)** | `-$2.59` | Phí taker |
| **Dòng tiền Funding (Funding Cashflow)** | `$+0.00` | Thanh toán định kỳ sàn |
| **Net Realized PnL** | `$+448.80` | Gross - Fees + Funding |
| **Kiểm toán Bất biến Kế toán** | `PASSED` | Sai lệch vượt tolerance sẽ làm report thất bại |
| **Trạng thái Circuit Breaker** | `ACTIVE` | Multiplier: `1.0` |
| **Circuit Breaker Activations / Lock Count** | `0` lần | Số lần khóa được ghi nhận |
| **Từ chối Lệnh do Ký quỹ (Margin Gate)** | `0` lần | Độc lập với Circuit Breaker |
| **Từ chối Lệnh do Circuit Breaker** | `0` lần | Khóa khi chạm ngưỡng rủi ro |

---

## 3. Trade Statistics

| Thống kê Giao dịch | Chi tiết |
| :--- | :--- |
| **Total Closed Trades** | `1` |
| **Win / Loss / Breakeven** | `1` / `0` / `0` |
| **Win Rate** | `100.00%` |
| **Average Trade PnL** | `$+448.80` |
| **Average Win / Loss** | `$+448.80` / `-$0.00` |
| **Win / Loss Ratio** | `N/A` |
| **Max Consecutive Wins / Losses** | `1` / `0` |
| **Total Trading Fees** | `$2.59 USDT` |
| **Total Funding Cashflow** | `$+0.00 USDT` |
| **Benchmark Win-rate 35-45%** | `ABOVE_EXPECTED_RANGE` (comparison only; not a future-performance guarantee) |

### Phân bổ lý do đóng vị thế (Exit Reasons)
- **TAKE_PROFIT**: `2` vị thế
- **STOP_LOSS**: `1` vị thế

### Phân bổ lý do từ chối lệnh (Rejection Reasons)
- Không có lệnh nào bị từ chối.

---

## 4. Disclosures & Benchmark Caveats (Bắt buộc)

> [!IMPORTANT]
> **Tuyên bố miễn trừ trách nhiệm và Giới hạn mô phỏng:**
> 1. **Nhãn dữ liệu**: Tất cả chỉ số trong báo cáo này được gắn cờ `AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED` và chưa được xác nhận bởi bên đánh giá độc lập.
> 2. **Giả định thực thi**: Mô hình khớp lệnh dựa trên dữ liệu nến lịch sử 15 phút với slippage tuyến tính và giả định thanh khoản tức thời tại giá mở cửa. Trong điều kiện thị trường biến động mạnh hoặc khoảng trống giá thực tế (slippage thực tế), kết quả có thể kém khả quan hơn.
> 3. **Phí & Funding**: Chi phí giao dịch tính theo biểu phí taker cố định và funding rate lịch sử. Không tính đến chi phí trượt giá thanh lý quy mô lớn hoặc độ trễ mạng (network latency).
> 4. **Quá khứ không đại diện tương lai**: Hiệu suất trong quá khứ của chiến lược trend following không đảm bảo kết quả tương tự trong tương lai.
