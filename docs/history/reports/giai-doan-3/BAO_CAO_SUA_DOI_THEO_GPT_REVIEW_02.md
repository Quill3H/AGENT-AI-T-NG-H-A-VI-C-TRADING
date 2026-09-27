# BÁO CÁO SỬA ĐỔI THEO GPT REVIEW LẦN 2 (STAGE 3: RISK MANAGER)

**Thời điểm thực hiện:** 2026-09-19  
**Tài liệu đánh giá đầu vào:** `crypto-paper-agent/docs/reviews/GPT_STAGE_03_REVIEW_02.md`  
**Trạng thái:** HOÀN THÀNH TOÀN BỘ 5 PHÁT HIỆN (F1 – F5) | TEST SUITE 135/135 PASS 100%  

---

## 1. TỔNG QUAN KẾT QUẢ XỬ LÝ (F1 – F5)

Đợt phản biện kỹ thuật độc lập lần 2 của GPT đã rà soát sâu các điều kiện biên và chỉ ra 5 lỗ hổng tiềm ẩn. Toàn bộ 5 nhóm vấn đề đã được khắc phục triệt để bằng mã nguồn cụ thể và bổ sung bộ regression unit test tương ứng:

| Mã | Hạng mục | Vấn đề phát hiện | Giải pháp kỹ thuật đã triển khai | Trạng thái |
|---|---|---|---|---|
| **F1** | Ngân sách rủi ro & Double Reduction | Lệnh khai báo `risk_percent` nhỏ hơn trần tier nhưng đối soát chỉ so với trần tier; rủi ro double reduction giữa `base_risk_percent` và `risk_percent`. | 1. Tính toán ngân sách rủi ro khai báo: $\text{order\_risk\_budget\_usd} = \text{equity} \times \text{order\_effective\_risk\_pct}$. Bắt buộc $\text{actual\_price\_risk\_usd} \le \text{order\_risk\_budget\_usd} + 10^{-4}$.<br>2. Ép buộc kiểm tra đẳng thức: $\text{risk\_percent} == \text{base\_risk\_percent} \times \text{cb\_multiplier}$ (sai số $10^{-6}$) nếu truyền cả hai. | **ĐÃ XỬ LÝ XONG** |
| **F2** | Ký quỹ & Tính bền vững Input | `available_margin` bị fallback ngầm sang `equity`; chưa dự trù phí vào lệnh; crash `TypeError` khi `conviction_tier` là list/dict; crash `AttributeError` khi breaker không callable; crash `OverflowError` khi timestamp quá lớn. | 1. Bắt buộc cung cấp `available_margin` hợp lệ hữu hạn $\ge 0$.<br>2. Kiểm tra tổng vốn cần: $\frac{\text{size}}{\text{lev}} + \text{size} \times \text{taker\_fee\_pct} \le \text{available\_margin}$.<br>3. Kiểm tra `isinstance(raw_tier, str)` trước khi tra dict.<br>4. Kiểm tra `callable(getattr(cb_state, "is_trading_allowed"))`.<br>5. Bọc try/except bắt `(OverflowError, OSError, ValueError)` khi parse timestamp. | **ĐÃ XỬ LÝ XONG** |
| **F3** | Phân lập Admission Time & Clock Thẩm quyền | Đánh giá breaker/news blackout theo `order['timestamp']` dẫn tới lỗ hổng dùng lệnh sinh ngoài giờ cấm để lách qua blackout; cấu hình news config enabled nhưng object filter disabled không bị phát hiện. | 1. Tách bạch `account_state['current_time']` làm **Admission Time** thẩm quyền duy nhất tại cổng.<br>2. Ràng buộc nhân quả: $\text{order['timestamp']} \le \text{account\_state['current\_time']}$.<br>3. Đánh giá trạng thái breaker và news blackout nghiêm ngặt tại Admission Time.<br>4. Kiểm tra nhất quán cấu hình news filter (`INVARIANT_FAIL_NEWS_FILTER_CONFIG_MISMATCH`). | **ĐÃ XỬ LÝ XONG** |
| **F4** | Đồng hồ Đơn nhất & Khóa Breaker | Lỗ hổng Scenario A (query không đồng bộ thời gian sự kiện) và Scenario B (hết hạn khóa không tự mở nếu không có query xen giữa); equity âm/cháy vốn chỉ khóa 10 năm; `recovery_mode` nhận chuỗi tùy ý. | 1. Xây dựng hàm chuẩn hóa `advance_time(current_timestamp)` dùng chung cho cả `is_trading_allowed` và `record_trade_result`, đảm bảo thời gian đơn điệu tuyệt đối.<br>2. Giải quyết triệt để Scenario A (truy vấn thời gian mới khóa chặt sự kiện quá khứ) và Scenario B (tự giải phóng khóa cũ và bắt vi phạm mới ngay khi ghi nhận sự kiện).<br>3. Khi `equity <= 0`: đặt `self.is_halted = True`, khóa giao dịch vĩnh viễn.<br>4. Validate nghiêm ngặt `recovery_mode` qua `SUPPORTED_RECOVERY_MODES = {"after_3_wins", "after_1_win"}`. | **ĐÃ XỬ LÝ XONG** |
| **F5** | Giải thuật Thanh lý Nghiêm ngặt | Solver ngầm fallback về tier cuối; chấp nhận nghiệm sai phương hướng (Long $P \ge Entry$); không kiểm tra tính liên tục của bracket; không chặn vị thế vượt trần bracket tối đa; không chặn vị thế đã cháy ngay tại entry. | 1. Kiểm tra tính liên tục hàm ký quỹ duy trì tại các ranh giới tier: $C_i \times \text{MMR}_i - \text{cum}_i == C_i \times \text{MMR}_{i+1} - \text{cum}_{i+1}$.<br>2. Từ chối vị thế vượt trần bracket tối đa với `ValueError`.<br>3. Từ chối vị thế có $\text{initial\_margin} \le \text{maintenance\_margin}_{\text{entry}}$ với `ValueError("already liquidatable")`.<br>4. Ràng buộc phương hướng nghiệm: Long $P_{cand} < P_{entry}$, Short $P_{cand} > P_{entry}$.<br>5. Bỏ hoàn toàn fallback tier cuối; raise `ValueError` nếu không có nghiệm hợp lệ trong miền bracket.<br>6. Kiểm chứng độc lập nghiệm với phương trình cân bằng ký quỹ độc lập: $\text{Margin}_{\text{initial}} \pm q(\Delta P) = q \cdot P_{\text{liq}} \cdot \text{MMR} - \text{cum}$. | **ĐÃ XỬ LÝ XONG** |

---

## 2. KẾT QUẢ THỰC THI KIỂM THỬ (TEST SUITE)

Hệ thống đã chạy toàn bộ các bài kiểm thử unit test từ local đến network với kết quả pass 100%:

### 2.1 Bộ kiểm thử Offline (Unit & Regression Tests)
- **Lệnh thực thi:** `pytest -m "not network"`
- **Kết quả:** **130 passed, 5 deselected, 1 warning in 1.52s**
- **Chi tiết phân bổ 130 tests:**
  - `test_invariant_checks.py`: **30/30 tests PASSED** (Bao gồm 19 tests gốc + 11 tests regression F1, F2, F3).
  - `test_circuit_breakers.py`: **16/16 tests PASSED** (Bao gồm 10 tests gốc + 6 tests regression F4).
  - `test_liquidation_calc.py`: **15/15 tests PASSED** (Bao gồm 10 tests gốc + 5 tests regression F5).
  - `test_position_sizing.py`: **21/21 tests PASSED**.
  - `test_data_layer.py`: **20/20 tests PASSED**.
  - `test_indicators.py`: **9/9 tests PASSED**.
  - `test_no_lookahead.py`: **6/6 tests PASSED**.
  - `test_oi_features.py`: **6/6 tests PASSED**.
  - `test_cvd.py`: **4/4 tests PASSED**.
  - `test_news_calendar.py`: **3/3 tests PASSED**.

### 2.2 Bộ kiểm thử Network (Live Binance Data & Vision Download)
- **Lệnh thực thi:** `pytest -m "network"`
- **Kết quả:** **5 passed, 130 deselected, 1 warning in 13.37s**
- **Chi tiết:**
  - `test_fetch_real_ohlcv_7days`: PASSED
  - `test_fetch_real_funding_rate`: PASSED
  - `test_no_lookahead_in_live_merge`: PASSED
  - `test_vision_live_download_single_day`: PASSED
  - `test_hybrid_oi_fetch_recent_60d`: PASSED

**TỔNG CỘNG:** **135/135 tests PASSED (100%)**.

---

## 3. KẾT QUẢ CHẠY MÔ PHỎNG 10 LỆNH (`simulate_risk_manager_10_trades.py`)

Kịch bản mô phỏng chạy thông suốt toàn bộ 2 Phase với đối soát tài chính minh bạch:

```text
=======================================================================================================================================
 PHASE 1: MÔ PHỎNG 10 LỆNH - GIẢM RISK 50% & KÍCH HOẠT KHÓA 24H
=======================================================================================================================================
Lệnh  | Thời gian   | Chiều | Base%  | Hệ số | Risk% HL | Vốn trước  | Trạng thái | Lý do từ chối (nếu có)           | Trạng thái CB sau lệnh   
---------------------------------------------------------------------------------------------------------------------------------------
#1    | 01/09 08:00 | LONG  | 2.0%  | 1.00  | 2.0%    | 10,000.00  | [DUYỆT]    | Thỏa mãn tất cả Invariants       | M=1.0 | L=0 | W=1        
#2    | 01/09 10:00 | LONG  | 2.0%  | 1.00  | 2.0%    | 10,200.00  | [DUYỆT]    | Thỏa mãn tất cả Invariants       | M=1.0 | L=1 | W=0        
#3    | 01/09 12:00 | SHORT | 2.0%  | 1.00  | 2.0%    | 10,000.00  | [DUYỆT]    | Thỏa mãn tất cả Invariants       | M=1.0 | L=2 | W=0        
#4    | 01/09 14:00 | LONG  | 2.0%  | 1.00  | 2.0%    | 9,800.00   | [DUYỆT]    | Thỏa mãn tất cả Invariants       | M=0.5 | L=3 | W=0        
#5    | 01/09 16:00 | LONG  | 2.0%  | 0.50  | 1.0%    | 9,650.00   | [TỪ CHỐI]  | INVARIANT_FAIL_LEVERAGE_EXCEEDED | M=0.5 | L=3 | W=0        
#6    | 01/09 18:00 | LONG  | 2.0%  | 0.50  | 1.0%    | 9,650.00   | [DUYỆT]    | Thỏa mãn tất cả Invariants       | M=0.5 | L=0 | W=1        
#7    | 01/09 20:00 | SHORT | 2.0%  | 0.50  | 1.0%    | 9,750.00   | [DUYỆT]    | Thỏa mãn tất cả Invariants       | M=0.5 | L=1 | W=0        
#8    | 01/09 22:00 | LONG  | 2.0%  | 0.50  | 1.0%    | 9,670.00   | [DUYỆT]    | Thỏa mãn tất cả Invariants       | LOCKED (22:00 02/09)     
#9    | 02/09 00:00 | LONG  | 2.0%  | 0.50  | 1.0%    | 9,170.00   | [TỪ CHỐI]  | INVARIANT_FAIL_CIRCUIT_BREAKER_L | LOCKED (22:00 02/09)     
#10   | 02/09 02:00 | LONG  | 2.0%  | 0.50  | 1.0%    | 9,170.00   | [TỪ CHỐI]  | INVARIANT_FAIL_CIRCUIT_BREAKER_L | LOCKED (22:00 02/09)     
---------------------------------------------------------------------------------------------------------------------------------------
Vốn đầu: 10,000.00 USD | Tổng PnL lệnh được duyệt: -830.00 USD | Vốn cuối: 9,170.00 USD
Đối soát vốn: CHÍNH XÁC 100% (Vốn cuối = Vốn đầu + Tổng PnL lệnh duyệt)
Hệ số rủi ro hiện tại: 0.50 | Trạng thái khóa: True
=======================================================================================================================================
=======================================================================================================================================
 PHASE 2: PHỤC HỒI RISK SAU KHI MỞ KHÓA (3 LỆNH THẮNG LIÊN TIẾP -> MULTIPLIER 1.0)
=======================================================================================================================================
Lệnh  | Thời gian   | Chiều | Base%  | Hệ số | Risk% HL | Vốn trước  | Trạng thái | Lý do từ chối (nếu có)           | Trạng thái CB sau lệnh   
---------------------------------------------------------------------------------------------------------------------------------------
#11   | 02/09 23:00 | LONG  | 2.0%  | 0.50  | 1.0%    | 9,170.00   | [DUYỆT]    | Thỏa mãn tất cả Invariants       | M=0.5 | L=0 | W=1        
#12   | 03/09 01:00 | LONG  | 2.0%  | 0.50  | 1.0%    | 9,270.00   | [DUYỆT]    | Thỏa mãn tất cả Invariants       | M=0.5 | L=0 | W=2        
#13   | 03/09 03:00 | LONG  | 2.0%  | 0.50  | 1.0%    | 9,370.00   | [DUYỆT]    | Thỏa mãn tất cả Invariants       | M=1.0 | L=0 | W=0        
---------------------------------------------------------------------------------------------------------------------------------------
Vốn đầu: 9,170.00 USD | Tổng PnL lệnh được duyệt: +300.00 USD | Vốn cuối: 9,470.00 USD
Đối soát vốn: CHÍNH XÁC 100% (Vốn cuối = Vốn đầu + Tổng PnL lệnh duyệt)
Hệ số rủi ro hiện tại: 1.00 | Trạng thái khóa: False
=======================================================================================================================================
```

---

## 4. TÀI LIỆU VÀ TRẠNG THÁI DỰ ÁN ĐÃ CẬP NHẬT
- Đã bổ sung Phụ lục quyết định Review 02 vào `docs/decisions/0006-circuit-breaker-and-risk-gate-refinements.md`.
- Đã ghi nhật ký thay đổi trong `CHANGELOG.md`.
- Đã cập nhật `PROJECT_STATE.md`: Giai đoạn 3 chuyển trạng thái sang **Đã hoàn thành sửa đổi Review 02, sẵn sàng nghiệm thu**.
- Tuyệt đối tuân thủ chỉ thị: **Dừng lại chờ người dùng review, chưa bắt đầu Giai đoạn 4**.
