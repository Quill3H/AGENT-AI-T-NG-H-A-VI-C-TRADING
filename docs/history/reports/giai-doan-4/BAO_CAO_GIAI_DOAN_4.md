# BÁO CÁO TỔNG KẾT GIAI ĐOẠN 4: PAPER EXECUTION ENGINE

**Thời điểm hoàn thành:** 2026-09-19  
**Tác giả:** Quill3H & Antigravity  
**Kiến trúc tham chiếu:** ADR 0007  
**Trạng thái kiểm thử:** 175/175 tests PASSED (170 offline + 5 network) — 100% Xanh

---

## 1. MỤC TIÊU VÀ TỔNG QUAN KIẾN TRÚC

Giai đoạn 4 xây dựng **Paper Execution Engine** — động cơ mô phỏng khớp lệnh phái sinh tiền mã hóa (Linear USDT-Margined Futures) hoạt động theo cơ chế ký quỹ cô lập (**Isolated Margin**) và loại bỏ triệt để mọi thiên lệch nhìn trước (**Lookahead Bias**).

Động cơ hoạt động hoàn toàn bằng mô phỏng cục bộ (offline/cached), không yêu cầu API key, không đặt lệnh thật và không sử dụng testnet.

### Các module đã xây dựng:
1. `src/execution/order_models.py`:
   - Định nghĩa các Enum: `OrderDirection` (LONG/SHORT), `OrderStatus` (PENDING, FILLED, REJECTED, CANCELED), `ExitReason` (STOP_LOSS, TAKE_PROFIT, LIQUIDATION, DAILY_LOSS_HALT, EXPLICIT_CLOSE).
   - Data class immutable / có kiểm soát:
     - `OrderRequest`: Yêu cầu mở lệnh với kiểm tra kiểu chặt chẽ, sinh `client_order_id` tất định từ SHA-256 (`ORD_{SYMBOL}_{YYYYMMDDHHMM}_{HASH8}`).
     - `OrderExecutionRecord`: Bản ghi chi tiết kết quả thẩm định và khớp lệnh (giá tham chiếu, giá fill thực tế kèm slippage, phí entry, lý do từ chối).
     - `Position`: Vị thế mở với mô hình Isolated Margin riêng biệt, lưu vết `initial_margin`, `isolated_collateral`, `cumulative_funding`, `liquidation_price`.
     - `FundingEventRecord`: Bản ghi sự kiện thanh toán funding định kỳ.
     - `TradeRecord`: Bản ghi giao dịch đã đóng hoàn tất với đầy đủ chi phí (gross PnL, entry fee, exit fee, funding cashflow, net PnL).
     - `AccountSnapshot`: Ảnh chụp số dư ví, ký quỹ bảo lưu, ký quỹ khả dụng và vốn tại cuối mỗi nến.

2. `src/execution/paper_broker.py`:
   - Động cơ khớp lệnh hướng sự kiện triển khai quy trình **5 Pha Xử lý Nến Bất biến**:
     - **Pha 1 (Open Time & Gap Exits):** Phát hiện nến mở cửa nhảy gap qua SL hoặc giá thanh lý của vị thế đang mở từ nến trước. Thoát vị thế ngay tại giá Open thực tế (có slippage bán/mua), tuyệt đối không khớp giá SL cũ.
     - **Pha 2 (Funding Settlement):** Kích hoạt vào đúng các mốc giờ cấu hình (00:00, 08:00, 16:00 UTC). Chỉ áp dụng cho các vị thế đã tồn tại trước mốc này và sống sót qua Pha 1. Tính toán dòng tiền funding chính xác và đồng bộ vào cả ví và collateral.
     - **Pha 3 (Pending Market Entry & Risk Gate Admission):** Khớp các lệnh chờ có `signal_time <= open_time` tại giá Open + Slippage. Chụp snapshot tài khoản và đưa qua cổng kiểm soát rủi ro toàn diện `check_all_invariants` từ Giai đoạn 3.
     - **Pha 4 (Intrabar Protection):** Quét biên độ $[Low, High]$ theo thứ tự ưu tiên bảo thủ tuyệt đối:
       $$\mathbf{Liquidation} \succ \mathbf{Stop\ Loss} \succ \mathbf{Take\ Profit}$$
       (Nếu nến quét qua cả TP và SL thì bắt buộc coi là dính SL; nếu quét qua cả SL và Liquidation thì bắt buộc coi là bị thanh lý).
     - **Pha 5 (Close Time & Mark-to-Market):** Tiến đồng hồ tới `close_time`, đánh giá lại `unrealized_pnl` theo giá Close, cập nhật `equity`, lưu snapshot tài khoản và đối soát các bất biến kế toán.
   - **Chính sách vị thế:** Tối đa 1 vị thế mở trên mỗi symbol (cấm nhồi lệnh, cấm hedging 2 chiều, cấm tự động đảo chiều). Chỉ cho phép thắt chặt Stop Loss một chiều (`update_stop_loss` tightening-only).
   - **Tích hợp hai chiều với Circuit Breaker:** Khi đóng lệnh, cập nhật kết quả ròng vào Circuit Breaker. Chuỗi 3 thua giảm 50% risk, chuỗi 3 thắng sau đó phục hồi 100% risk. Chạm ngưỡng lỗ ngày 5% lập tức đóng toàn bộ vị thế và khóa 24 giờ.

---

## 2. BÀI TOÁN ORACLE KẾ TOÁN BẮT BUỘC (MỤC 8 SPEC)

Hệ thống đã được kiểm chứng với bài toán Oracle độc lập (manual ground-truth) được đặc tả trong `ANTIGRAVITY_STAGE_04_TASK.md`:
- **Thông số:** Vốn 10,000 USD, Đòn bẩy 2x, Entry actual 100, SL 98, TP 104, Base risk 0.002, Low tier, Số lượng 10, Slippage 0, Phí Taker 0.0005 (0.05%), 1 kỳ settlement funding lúc 08:00 UTC với rate +0.0001, mark 100.
- **Kết quả đối soát trên mã nguồn (`tests/test_execution_accounting.py::test_mandatory_oracle_long_trade`):**

| Chỉ số kế toán | Giá trị kỳ vọng (Oracle) | Giá trị động cơ khớp lệnh | Sai số | Trạng thái |
| :--- | :--- | :--- | :--- | :--- |
| Notional Entry | 1,000.00 USD | 1,000.00 USD | 0.00 | **KHỚP 100%** |
| Initial Reserved Margin | 500.00 USD | 500.00 USD | 0.00 | **KHỚP 100%** |
| Entry Fee (0.05%) | 0.50 USD | 0.50 USD | 0.00 | **KHỚP 100%** |
| Funding Cashflow (08:00 UTC) | -0.10 USD | -0.10 USD | 0.00 | **KHỚP 100%** |
| Isolated Collateral sau Funding | 499.90 USD | 499.90 USD | 0.00 | **KHỚP 100%** |
| Gross Price PnL tại TP (104.0) | +40.00 USD | +40.00 USD | 0.00 | **KHỚP 100%** |
| Exit Fee (10 x 104 x 0.0005) | 0.52 USD | 0.52 USD | 0.00 | **KHỚP 100%** |
| Net Trade PnL | +38.88 USD | +38.88 USD | 0.00 | **KHỚP 100%** |
| Final Wallet Balance / Equity | 10,038.88 USD | 10,038.88 USD | 0.00 | **KHỚP 100%** |
| Final Reserved Margin | 0.00 USD | 0.00 USD | 0.00 | **KHỚP 100%** |
| Final Available Margin | 10,038.88 USD | 10,038.88 USD | 0.00 | **KHỚP 100%** |

---

## 3. KẾT QUẢ KIỂM THỬ TỰ ĐỘNG (PYTEST SUITE)

### 3.1 Bộ kiểm thử Offline (170/170 tests PASSED)
Lệnh thực thi: `venv\Scripts\pytest -m "not network" -q`
```text
============================= test session starts =============================
platform win32 -- Python 3.13.14, pytest-9.1.1, pluggy-1.6.0
rootdir: D:\Tài liệu\Default Project\crypto-paper-agent
configfile: pytest.ini
testpaths: tests
plugins: cov-7.1.0
collected 175 items / 5 deselected / 170 selected

tests\test_circuit_breakers.py ................                          [  9%]
tests\test_cvd.py ....                                                   [ 11%]
tests\test_data_layer.py ....................                            [ 23%]
tests\test_execution_accounting.py ...                                   [ 25%]
tests\test_execution_models.py ....                                      [ 27%]
tests\test_execution_no_lookahead.py ...                                 [ 29%]
tests\test_indicators.py .........                                       [ 34%]
tests\test_invariant_checks.py ......................................... [ 58%]
......                                                                   [ 62%]
tests\test_liquidation_calc.py ...............                           [ 71%]
tests\test_news_calendar.py .........                                    [ 76%]
tests\test_no_lookahead.py ......                                        [ 80%]
tests\test_oi_features.py ......                                         [ 83%]
tests\test_paper_broker.py .......                                       [ 87%]
tests\test_position_sizing.py .....................                      [100%]

================ 170 passed, 5 deselected, 1 warning in 1.63s =================
```

### 3.2 Bộ kiểm thử Network (5/5 tests PASSED)
Lệnh thực thi: `venv\Scripts\pytest -m "network" -q`
```text
============================= test session starts =============================
platform win32 -- Python 3.13.14, pytest-9.1.1, pluggy-1.6.0
rootdir: D:\Tài liệu\Default Project\crypto-paper-agent
configfile: pytest.ini
testpaths: tests
plugins: cov-7.1.0
collected 175 items / 170 deselected / 5 selected

tests\test_data_layer.py .....                                           [100%]

================ 5 passed, 170 deselected, 1 warning in 12.24s ================
```

**Tổng cộng toàn bộ dự án: 175/175 tests PASSED (100% hoàn thành)**

---

## 4. KỊCH BẢN MÔ PHỎNG VÀ KIỂM CHỨNG THỰC TẾ

Script thực thi: `scripts/simulate_paper_execution.py`

### 4.1 Phần A: Mô phỏng Tổng hợp Deterministic (Synthetic Simulation)
Kiểm thử toàn bộ các tình huống phức tạp:
1. Lệnh LONG có lãi khớp TP, đi qua 1 kỳ settlement funding lúc 08:00 UTC.
2. Chuỗi 3 trận thua liên tiếp chạm SL $\implies$ Circuit Breaker hạ `risk_multiplier` xuống 0.50.
3. Nến mở cửa nhảy Gap Down mạnh xuyên thủng Stop Loss $\implies$ lệnh bị cưỡng chế thoát ở giá Open thực tế (44,986.50 USD) kèm slippage bán, không thể khớp giá SL 48,000.00 USD.
4. Tổng lỗ 24h vượt 5% equity $\implies$ Circuit Breaker kích hoạt khóa giao dịch 24 giờ.
5. Sau thời gian khóa 24h $\implies$ hệ thống tự động mở lại quyền giao dịch.
6. Chuỗi 3 trận thắng liên tiếp sau đó $\implies$ Circuit Breaker phục hồi `risk_multiplier` về 1.00.
7. **Đối soát kế toán:** Vốn cuối = 9,440.94 USD = Vốn ban đầu (10,000.00 USD) + Tổng Net PnL (-559.06 USD).

```text
=================================================================================================================================================
 PHẦN A: MÔ PHỎNG TỔNG HỢP DETERMINISTIC (OFFLINE SYNTHETIC SIMULATION)
=================================================================================================================================================
Vốn khởi tạo: 10,000.00 USD | Đòn bẩy tối đa: 5.0x | Phí Taker: 0.05% | Slippage: 0.03%
-------------------------------------------------------------------------------------------------------------------------------------------------
STT  | Thời gian (UTC)   | Loại sự kiện   | Chiều | Giá khớp  | KL (Qty) | Ký quỹ    | Phí (Fee) | Funding  | Net PnL    | Số dư Ví    | Vốn (Equity) | Risk Multiplier
-------------------------------------------------------------------------------------------------------------------------------------------------
1    | 2026-09-01 07:31  | ENTRY_FILLED   | LONG  | 50015.00  | 0.099    | 2482.13   | 2.482    | 0.000    | 0.000      | 9997.52     | 10000.99     | 1.00           
2    | 2026-09-01 08:00  | FUNDING_SETTLE | LONG  | 50200.00  | 0.099    | 2481.64   | 0.000    | -0.498   | 0.000      | 9997.02     | 10020.34     | 1.00           
3    | 2026-09-01 08:01  | TAKE_PROFIT    | LONG  | 51984.40  | 0.099    | 0.00      | 2.580    | -0.498   | 189.91     | 10189.91    | 10189.91     | 1.00           
4    | 2026-09-01 08:04  | STOP_LOSS #1   | LONG  | 48985.30  | 0.201    | 0.00      | 4.918    | 0.000    | -216.69    | 9973.22     | 9973.22      | 1.00           
5    | 2026-09-01 08:07  | STOP_LOSS #2   | LONG  | 48985.30  | 0.197    | 0.00      | 4.813    | 0.000    | -212.08    | 9761.14     | 9761.14      | 1.00           
6    | 2026-09-01 08:10  | STOP_LOSS #3   | LONG  | 48985.30  | 0.192    | 0.00      | 4.711    | 0.000    | -207.57    | 9553.57     | 9553.57      | 0.50           
>>> Circuit Breaker: Đã phát hiện 3 trận thua liên tiếp -> Giảm Risk Multiplier xuống 0.50!
7    | 2026-09-01 08:13  | GAP_DOWN_EXIT  | LONG  | 44986.50  | 0.047    | 0.00      | 1.066    | 0.000    | -240.66    | 9312.91     | 9312.91      | 0.50           
>>> Gap Exit: Lệnh thoát tại giá Open thực tế 44,986.50 USD (kèm slippage bán), không thể thoát ở giá SL 48,000.00!
>>> Circuit Breaker: Đã chờ 25 giờ qua thời gian khóa 24h. Hệ thống tự động mở khóa giao dịch!
8    | 2026-09-02 09:16  | TAKE_PROFIT #1 | LONG  | 50984.70  | 0.046    | 0.00      | 1.178    | 0.000    | 42.48      | 9355.39     | 9355.39      | 0.50           
9    | 2026-09-02 09:19  | TAKE_PROFIT #2 | LONG  | 50984.70  | 0.046    | 0.00      | 1.184    | 0.000    | 42.68      | 9398.07     | 9398.07      | 0.50           
10   | 2026-09-02 09:22  | TAKE_PROFIT #3 | LONG  | 50984.70  | 0.047    | 0.00      | 1.189    | 0.000    | 42.87      | 9440.94     | 9440.94      | 1.00           
>>> Circuit Breaker Recovery: Đạt đủ 3 trận thắng liên tiếp -> Phục hồi Risk Multiplier về 1.00!
-------------------------------------------------------------------------------------------------------------------------------------------------
Đối soát Kế toán Phần A THÀNH CÔNG: Vốn cuối = 9,440.94 USD = Vốn ban đầu (10,000.00) + Tổng Net PnL (-559.06)
Tổng số giao dịch đã thực hiện: 8 | Vị thế mở còn lại: 0
=================================================================================================================================================
```

### 4.2 Phần B: Mô phỏng trên Dữ liệu Thật Binance Cached (BTCUSDT 15m + Funding Rate 8h)
- Nguồn dữ liệu nến: `data/raw/binance/BTCUSDT/15m/ohlcv.parquet` (6,720 nến)
- Nguồn dữ liệu funding: `data/raw/binance/BTCUSDT/8h/funding_rate.parquet` (210 bản ghi)
- Đoạn dữ liệu thực thi: 120 nến 15m (từ 2026-08-01 00:00:00 UTC đến 2026-08-02 05:45:00 UTC).
- Đi qua **3 mốc thanh toán Funding Rate thực tế**: 08:00 UTC, 16:00 UTC ngày 01/08 và 00:00 UTC ngày 02/08.
- Khớp Take Profit tại nến 115 khi giá chạm 63,600 USD.
- Thử nghiệm gửi lệnh vi phạm đòn bẩy (10x > max 5x) tại nến 117 $\implies$ Cổng Risk Gate chặn đứng ngay lập tức với lý do `INVARIANT_FAIL_LEVERAGE_EXCEEDED`.

```text
=================================================================================================================================================
 PHẦN B: MÔ PHỎNG KHỚP LỆNH TRÊN DỮ LIỆU THẬT BINANCE CACHED (BTCUSDT 15M + FUNDING 8H)
=================================================================================================================================================
Nguồn dữ liệu OHLCV: data\raw\binance\BTCUSDT\15m\ohlcv.parquet (6720 nến)
Nguồn dữ liệu Funding: data\raw\binance\BTCUSDT\8h\funding_rate.parquet (210 bản ghi)
Khoảng thời gian mô phỏng: 2026-08-01 00:00:00+00:00 -> 2026-08-02 05:45:00+00:00 (120 nến 15m)
-------------------------------------------------------------------------------------------------------------------------------------------------
Nến # | Thời gian (UTC)   | Loại sự kiện   | Chiều | Giá khớp  | KL (Qty) | Ký quỹ    | Phí (Fee) | Funding  | Net PnL    | Số dư Ví    | Vốn (Equity) | Risk Multiplier
-------------------------------------------------------------------------------------------------------------------------------------------------
2     | 2026-08-01 00:30  | ENTRY_FILLED   | LONG  | 62960.88  | 0.0287   | 904.50    | 0.904    | 0.000    | 0.000      | 9999.10     | 9999.40      | 1.00           
32    | 2026-08-01 08:00  | FUNDING_EVENT  | LONG  | 63019.60  | HOLD     | N/A       | 0.000    | -0.0573  | 0.000      | 9999.04     | 10002.24     | 1.00           
64    | 2026-08-01 16:00  | FUNDING_EVENT  | LONG  | 62976.40  | HOLD     | N/A       | 0.000    | -0.0641  | 0.000      | 9998.97     | 9997.85      | 1.00           
96    | 2026-08-02 00:00  | FUNDING_EVENT  | LONG  | 62792.30  | HOLD     | N/A       | 0.000    | -0.0817  | 0.000      | 9998.89     | 9997.03      | 1.00           
115   | 2026-08-02 04:45  | TAKE_PROFIT    | LONG  | 63580.92  | 0.0287   | 0.00      | 0.913    | -0.2031  | 15.79      | 10015.79    | 10015.79     | 1.00           
117   | 2026-08-02 05:15  | GATE_REJECT    | LONG  | N/A       | 0.000    | 0.00      | 0.000    | 0.000    | 0.000      | 10015.79    | 10015.79     | INVARIANT_FAIL_LEVERAGE_EXCE
-------------------------------------------------------------------------------------------------------------------------------------------------
Tổng số nến đã xử lý: 120 nến 15m
Tổng số lệnh đóng: 1 | Vị thế đang mở: 0
Số dư Ví cuối kỳ: 10,015.79 USD | Vốn (Equity): 10,015.79 USD
Ký quỹ khả dụng: 10,015.79 USD | Ký quỹ bảo lưu: 0.00 USD
Đối soát bất biến kế toán: HOÀN TOÀN KHỚP (PASS)
=================================================================================================================================================
```

---

## 5. GIỚI HẠN HIỆN TẠI (KNOWN LIMITATIONS) & ĐỀ XUẤT GIAI ĐOẠN 5

1. **Giới hạn số vị thế đồng thời:** Động cơ hiện tại áp dụng chính sách nghiêm ngặt 1 vị thế mở trên mỗi symbol. Khi mở rộng sang danh mục đa tài sản (BTC, ETH, SOL) ở Giai đoạn 6, sẽ cần cơ chế phân bổ vốn danh mục (Portfolio Margin Allocator).
2. **Loại lệnh:** Giai đoạn 4 tập trung vào lệnh Market Order tại Open kèm Slippage. Lệnh Limit Order chờ khớp (Maker) chưa được đưa vào phạm vi mô phỏng này.
3. **Mức độ phụ thuộc chiến lược:** Động cơ khớp lệnh hoàn toàn trung lập, không tự sinh tín hiệu. Tín hiệu chiến lược sẽ được phát triển chuyên biệt tại Giai đoạn 5 (Alpha Models).

---

## 6. KẾT LUẬN & BÀN GIAO

Giai đoạn 4 — **Paper Execution Engine** đã hoàn thành xuất sắc 100% mục tiêu:
- Kiến trúc Isolated Margin chuẩn xác, đối soát kế toán khớp từng bit với bài toán Oracle.
- Quy trình 5 pha chống nhìn trước bảo đảm tính khách quan, bảo thủ và trung thực của kết quả mô phỏng.
- Toàn bộ 175 unit/integration tests (cả cũ và mới) đều pass 100%.
- Kịch bản mô phỏng chạy trơn tru trên cả dữ liệu tổng hợp và dữ liệu thật Binance cache.
- Tài liệu kiến trúc ADR 0007 đã được lập đầy đủ.

**Hệ thống DỪNG TẠI ĐÂY ĐỂ CHỜ GPT REVIEW THEO ĐÚNG YÊU CẦU CỦA USER. Tuyệt đối không tự ý bắt đầu Giai đoạn 5.**
