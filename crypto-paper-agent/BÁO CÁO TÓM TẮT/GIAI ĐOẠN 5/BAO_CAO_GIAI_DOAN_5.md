# BÁO CÁO TỔNG KẾT GIAI ĐOẠN 5: TREND FOLLOWING STRATEGY & BACKTEST ENGINE
*(Bản cập nhật hoàn thiện theo 3 blocker bắt buộc của GPT Review 10)*

**Thời điểm hoàn thành:** 2026-09-19  
**Tác giả:** Quill3H & Antigravity  
**Trạng thái nghiệm thu:** **CHƯA NGHIỆM THU — ĐANG CHỜ GPT REVIEW 10 ĐÁNH GIÁ**  
**Kiến trúc tham chiếu:** ADR 0008 (Trạng thái: PENDING REVIEW)  
**Code-under-test commit:** `060f8a8d72e0eb2acbb6bd327ae67fbcb0805aac`  
**Documentation commit:** *(Commit B chứa báo cáo này)*  
**Trạng thái kiểm thử:**
- **Unit & Integration Tests (`tests/`):** 240/240 tests PASSED (235 offline + 5 network) — 100% Xanh
- **Historical Probes (`docs/reviews/`):** 40/40 tests PASSED (Review 05: 26, Review 06: 11, Review 07: 3) — 100% Xanh
**Dữ liệu Benchmark:** 3 năm BTCUSDT (2021-01-01 đến 2023-12-31) — **AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED**  

---

## 1. MỤC TIÊU VÀ TỔNG QUAN KIẾN TRÚC

Giai đoạn 5 triển khai chiến lược giao dịch xu hướng (**Trend Following Strategy**) theo cơ chế nhân quả đa khung thời gian (**Multi-Timeframe Causal Execution**) và động cơ kiểm thử quá khứ (**Backtest Engine**) tối thiểu, vận hành trên nền tảng Paper Execution Engine (Giai đoạn 4), Risk Engine (Giai đoạn 3), Feature Engineering (Giai đoạn 2) và Data Layer (Giai đoạn 1).

### Các nguyên tắc thực thi cốt lõi:
1. **Loại trừ nhìn trước (Zero Lookahead Bias):** Tín hiệu và bộ lọc xác định hoàn toàn trên nến 4h đã đóng (`candle[t-1]`), lệnh được khớp vào nến 15m tiếp theo tại giá Open (`candle[t]`).
2. **Kế toán bất biến đóng kín:** Tính toán đầy đủ chi phí (phí taker 0.05%, trượt giá slippage 0.03%, funding rate settlement định kỳ), bảo toàn dòng tiền ví và ký quỹ cô lập (Isolated Margin).
3. **Fail-Closed Funding Provenance:** Không ép kiểu lỏng lẻo (`bool(row_15m["funding_readiness"])`). Dữ liệu sai kiểu (string, int, float, NaN), missing, future hoặc stale bị từ chối tuyệt đối (fail-closed) trước khi gây ra bất kỳ biến đổi trạng thái nào trên broker/account.
4. **Độc lập CWD & Hermetic Cache:** CLI runner và đường dẫn cấu hình, dữ liệu cache được resolve tuyệt đối từ `PROJECT_ROOT`, hoạt động độc lập với thư mục thực thi hiện hành. Bộ kiểm thử CWD tự tạo cache tạm cô lập trong `tmp_path`, không phụ thuộc thư mục `data/raw` bị gitignore.

---

## 2. CHI TIẾT KHẮC PHỤC CÁC BLOCKER GPT REVIEW 10

### 2.1 Blocker 1 (Sơ bộ): Funding Provenance Fail-Closed & Zero Mutation
- **Vấn đề cũ:** Tại `BacktestEngine.run()`, dòng lệnh `bool(row_15m["funding_readiness"])` đã biến các giá trị sai như chuỗi `"False"`, số `1`, hoặc `NaN` thành `True`, làm lách qua tầng kiểm soát của `PaperBroker`.
- **Khắc phục:**
  - Loại bỏ hoàn toàn `bool(...)` ép kiểu lỏng lẻo.
  - Phân lập kiểu dữ liệu:
    - Nếu là `numpy.bool_` thì chuyển về `bool` chuẩn Python.
    - Nếu là chuỗi, số, `NaN` hoặc object: giữ nguyên giá trị thô để `PaperBroker` kiểm tra `type(...) is bool` và fail-closed với `TypeError` hoặc `ValueError`.
  - Bổ sung kiểm thử tích hợp (`test_funding_metadata_fail_closed_and_zero_mutation`) cho 7 trường hợp lỗi: `missing`, `bool_False`, `str_False`, `int_1`, `nan`, `future`, `stale`.
  - Khẳng định tính bất biến trạng thái: Trong mọi trường hợp lỗi, `broker.wallet_balance`, `broker.positions["BTCUSDT"].isolated_collateral`, `broker.reserved_collateral`, và `broker.trade_history` không bị biến đổi bất kỳ giá trị nào (Zero Mutation).
  - Bổ sung kiểm thử `test_funding_metadata_valid_zero_rate` kiểm chứng `funding_rate = 0.0` hợp lệ với đầy đủ provenance được thanh toán bình thường với dòng tiền bằng 0.

### 2.2 Blocker 2 (Sơ bộ): Future-Perturbation Test Phi-Rỗng & Tái Tính Chỉ Báo
- **Vấn đề cũ:** Test cũ tạo danh sách `trades_before_T_1` và `trades_before_T_2` nhưng không assert, đồng thời giữ nguyên các cột chỉ báo đã tính sẵn sau khi sửa dữ liệu OHLC.
- **Khắc phục (`test_future_perturbation_invariance`):**
  - Xây dựng kịch bản dữ liệu thực tế tạo ra setup ARMED, lệnh chờ và giao dịch đã khớp/đóng hoàn tất trước thời điểm $T$.
  - Khẳng định tính phi-rỗng (non-vacuous): `len(orders_before_T_1) >= 1`, `len(trades_before_T_1) >= 1`, `len(snaps_before_T_1) > 0`.
  - Nhiễu toàn bộ dữ liệu OHLC 15m và 4h sau $T$ (nhân 2.5x).
  - Đưa dữ liệu 4h nhiễu qua pipeline tính toán chỉ báo thật (`add_all_features`) để các chỉ báo sau $T$ thay đổi thực sự theo dữ liệu mới.
  - Kiểm chứng bất biến: Toàn bộ orders, trades và account snapshots trước hoặc tại $T$ giữa 2 lần chạy giống hệt nhau 100%.

### 2.3 Blocker 1 (Chính thức): Làm Test CWD Hoàn Toàn Hermetic
- **Vấn đề cũ:** `test_cli_cwd_independence` dựa vào cache cục bộ `data/raw` (vốn bị `.gitignore`), dẫn đến nguy cơ fail trên một clean clone.
- **Khắc phục:**
  - Tự động sinh dữ liệu tổng hợp tối thiểu đa khung 4h và 15m (3 ngày) trực tiếp trong `tmp_path/mock_cache`.
  - Đảm bảo đầy đủ các tệp: `4h/ohlcv.parquet`, `15m/ohlcv.parquet`, `4h/open_interest.parquet`, `15m/open_interest.parquet`, `8h/funding_rate.parquet`, `15m/funding_rate.parquet`.
  - Tạo cấu hình YAML tạm `hermetic_test_config.yaml` trong `tmp_path` trỏ `data.raw_data_dir` về `mock_cache`.
  - Nâng cấp `run_backtest.py` cho phép `config_path` và `raw_data_dir` nhận cả đường dẫn tuyệt đối lẫn tương đối từ CWD hiện hành.
  - Nâng cấp `has_complete_cache` trong `cache_manager.py` đọc đúng schema column `__index_level_0__` khi index name mặc định.
  - Chạy subprocess với `cwd=str(tmp_path)` bên ngoài project root với các cờ: `--config`, `--strategy trend_following`, `--start 2023-01-01`, `--end 2023-01-02`, `--no-fetch`.
  - Xác nhận test pass 100% trên clean clone mà không cần bất kỳ tệp dữ liệu nào trong `data/raw`.

### 2.4 Blocker 2 (Chính thức): Chạy Đầy Đủ Probe Lịch Sử
- **Thực thi probe độc lập:** Vì `pytest.ini` chỉ thu thập thư mục `tests/`, các probe lịch sử Giai đoạn 4 trong `docs/reviews/` đã được chạy riêng và đối chiếu:
  - Lệnh: `python -m pytest docs/reviews/test_stage_04_review_05.py docs/reviews/test_stage_04_review_06.py docs/reviews/test_stage_04_review_07.py -q`
  - Kết quả: **40/40 probes PASSED** (Review 05: 26/26, Review 06: 11/11, Review 07: 3/3).
  - Không có bất kỳ probe nào bị né tránh, bỏ qua hay sửa đổi assertion.

### 2.5 Blocker 3 (Chính thức): Luồng Commit Có Truy Vết & Báo Cáo Trung Thực
- **Commit A (`060f8a8d72e0eb2acbb6bd327ae67fbcb0805aac`):** Chứa toàn bộ code triển khai (`run_backtest.py`, `src/data_layer/cache_manager.py`) và test hoàn thiện (`tests/test_backtest_engine.py`).
- **Thực thi kiểm thử trên Commit A:** Toàn bộ test suites (offline, network, probes) được chạy trực tiếp trên cây git của Commit A để lấy số liệu thực.
- **Commit B:** Cập nhật tài liệu, báo cáo nghiệm thu và changelog trỏ đúng vào Commit A SHA.
- **Tuyên bố Benchmark:** Gắn nhãn minh bạch `AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED` cho toàn bộ kết quả backtest 3 năm.

---

## 3. KẾT QUẢ KIỂM THỬ TỰ ĐỘNG (TRÊN COMMIT A: `060f8a8d72e0eb2acbb6bd327ae67fbcb0805aac`)

### 3.1 Môi trường thực thi
- **Hệ điều hành:** Windows 11 (win32)
- **Python:** 3.13.14
- **Thư viện chính:** `pytest-9.1.1`, `pandas-3.0.6`, `numpy-2.2.6`, `pandas-ta`

### 3.2 Bộ kiểm thử Offline (235/235 tests PASSED)
Lệnh thực thi: `python -m pytest -m "not network" -q`
```text
tests\test_backtest_engine.py ...............                            [  6%]
tests\test_circuit_breakers.py ................                          [ 13%]
tests\test_cvd.py ....                                                   [ 14%]
tests\test_data_layer.py ....................                            [ 23%]
tests\test_execution_accounting.py ...                                   [ 24%]
tests\test_execution_models.py ....                                      [ 26%]
tests\test_execution_no_lookahead.py ...                                 [ 27%]
tests\test_indicators.py .........                                       [ 31%]
tests\test_invariant_checks.py ......................................... [ 48%]
......                                                                   [ 51%]
tests\test_liquidation_calc.py ...............                           [ 57%]
tests\test_news_calendar.py .........                                    [ 61%]
tests\test_no_lookahead.py ......                                        [ 64%]
tests\test_oi_features.py ......                                         [ 66%]
tests\test_paper_broker.py .......                                       [ 69%]
tests\test_position_sizing.py .....................                      [ 78%]
tests\test_stage_04_review_06_coverage.py ...........                    [ 83%]
tests\test_stage_04_review_07_coverage.py ................               [ 90%]
tests\test_trend_following_strategy.py .......................           [100%]

================ 235 passed, 5 deselected, 1 warning in 6.95s =================
```

### 3.3 Bộ kiểm thử Network (5/5 tests PASSED)
Lệnh thực thi: `python -m pytest -m "network" -q`
```text
tests\test_data_layer.py .....                                           [100%]
================ 5 passed, 235 deselected, 1 warning in 12.34s ================
```

### 3.4 Bộ kiểm thử Probe Lịch Sử (40/40 tests PASSED)
Lệnh thực thi: `python -m pytest docs/reviews/test_stage_04_review_05.py docs/reviews/test_stage_04_review_06.py docs/reviews/test_stage_04_review_07.py -q`
```text
docs\reviews\test_stage_04_review_05.py ..........................       [ 65%]
docs\reviews\test_stage_04_review_06.py ...........                      [ 92%]
docs\reviews\test_stage_04_review_07.py ...                              [100%]

======================== 40 passed, 1 warning in 0.86s ========================
```
- `docs/reviews/test_stage_04_review_05.py`: **26/26 passed** (0.94s)
- `docs/reviews/test_stage_04_review_06.py`: **11/11 passed** (0.60s)
- `docs/reviews/test_stage_04_review_07.py`: **3/3 passed** (0.54s)

### 3.5 Độ bao phủ mã nguồn (Coverage: 73% tổng thể)
Lệnh thực thi: `python -m pytest -m "not network" --cov=src --cov-report=term-missing -q`
- `src/backtest/engine.py`: **90%**
- `src/strategies/trend_following.py`: **85%**
- `src/execution/order_models.py`: **92%**
- `src/features/indicators.py`: **91%**
- `src/features/oi_features.py`: **100%**
- `src/features/cvd.py`: **93%**
- `src/risk/position_sizing.py`: **91%**

---

## 4. KẾT QUẢ BENCHMARK 3 NĂM (2021-01-01 ĐẾN 2023-12-31)

> [!WARNING]
> **Tuyên bố Minh bạch:**  
> **STATUS: AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED**  
> Dữ liệu Parquet thô được tác giả tải từ API công khai của Binance và lưu tại cache cục bộ (`data/raw/`), không được đưa lên Git repo (do kích thước lớn và nằm trong `.gitignore`). Do đó, kết quả benchmark dưới đây là số liệu do tác giả báo cáo và chưa được reviewer xác minh độc lập trên môi trường của mình.

### 4.1 Lệnh tái hiện
```bash
python run_backtest.py --config config/default_config.yaml --strategy trend_following --start 2021-01-01 --end 2023-12-31 --no-fetch
```

### 4.2 Báo cáo Chi tiết từ CLI Runner
```text
======================================================================
                   BACKTEST EXECUTION REPORT
   [STATUS: AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED]
======================================================================
Git Commit SHA       : 060f8a8d72e0eb2acbb6bd327ae67fbcb0805aac
Python Environment   : Python 3.13.14 | pandas 3.0.6 | numpy 2.2.6
Strategy & Symbol    : trend_following | BTCUSDT
Time Range 15m       : 2021-01-01 00:00:00+00:00 -> 2023-12-31 23:45:00+00:00
Bars Processed       : 15m=105120, 4h=6570
Signals & Setups     : ARMED Setups=70, Candidates Generated=22
----------------------------------------------------------------------
Initial Balance      : 10,000.00 USDT
Final Equity         : 12,100.96 USDT
Total Return         : +21.01%
Max Drawdown         : -2,050.72 USDT (-16.15%)
----------------------------------------------------------------------
Total Orders Sent    : 22
Orders Filled        : 16
Orders Rejected      : 6
Orders Cancelled     : 0
Rejection Breakdown  :
  - INVARIANT_FAIL_INSUFFICIENT_MARGIN: 6
----------------------------------------------------------------------
Total Closed Trades  : 16 (Sample size N=16)
  - LONG Trades      : 10 (Win: 50.0%)
  - SHORT Trades     : 6 (Win: 50.0%)
Trade Outcomes       : 8 Win / 8 Loss / 0 Breakeven
Win Rate (Overall)   : 50.00% (Reference: 35-45%; note: 50.00% on N=16 not statistically generalizable)
Win Rate (LONG)      : 50.00%
Win Rate (SHORT)     : 50.00%
----------------------------------------------------------------------
Gross Price PnL      : +2,489.66 USDT
Trading Fees Paid    : -162.82 USDT
Funding Cashflow     : -225.89 USDT
Net Realized PnL     : +2,100.96 USDT
Exit Reasons         : {'STOP_LOSS': 16}
----------------------------------------------------------------------
Circuit Breaker      : ACTIVE (Risk multiplier: 0.50)
Risk Gate Rejections : 6 (Isolated margin gate check; distinct from circuit breaker)
Accounting Audit     : PASSED (wallet_balance matches ledger)
Finalize Mode        : force_close=True
======================================================================
```

---

## 5. PHÂN TÍCH HIỆU NĂNG VÀ ĐÍNH CHÍNH PHÁT BIỂU

1. **Về Tỷ lệ Thắng (Win Rate 50.00%):**
   - Con số 50.00% (8 thắng / 8 thua) **nằm ngoài** khoảng tham chiếu lý thuyết 35% – 45% của các chiến lược Trend Following thông thường.
   - Tuy nhiên, quy mô mẫu chỉ gồm **16 giao dịch hoàn tất ($N = 16$)** trong suốt 3 năm. Do mẫu quá nhỏ, tỷ lệ thắng 50.00% và lợi nhuận +21.01% **không có ý nghĩa thống kê suy diễn** và không được khái quát hóa thành hiệu quả vượt trội trong tương lai.
2. **Về Bản chất của 6 Lệnh Bị Từ chối:**
   - 6 lệnh bị từ chối với lý do `INVARIANT_FAIL_INSUFFICIENT_MARGIN` xuất phát từ **Cổng Kiểm Soát Ký Quỹ (Risk Gate Isolated Margin)** trong `PaperBroker._precheck_order_invariants()`, do ký quỹ khả dụng không đủ đáp ứng mức rủi ro tối thiểu của lệnh.
   - Đây **không phải** là tác động của Circuit Breaker ngắt giao dịch. Circuit Breaker vẫn ở trạng thái hoạt động bình thường (`is_halted = False`, `is_locked = False`), và chỉ giảm `risk_multiplier` xuống 0.5 sau chuỗi 3 lệnh thua theo đúng thiết kế.
3. **Về Tuyên bố "Zero Overfitting":**
   - Không tuyên bố "zero overfitting" như một sự thật tuyệt đối.
   - Báo cáo xác nhận về mặt quy trình: Toàn bộ tham số chiến lược (EMA 20/50/200, RSI 14 > 50, Swing 5 bars, Trailing EMA50) được lấy trực tiếp từ đặc tả quy định trong `ANTIGRAVITY_STAGE_05_TASK.md`, không thực hiện bất kỳ vòng lặp tìm kiếm lưới (grid search) hay tối ưu hóa tham số (parameter tuning) nào để ép kết quả đẹp.
4. **Về Mức Sụt Giảm Tài Sản (Max Drawdown 16.15%):**
   - Max Drawdown là mức giảm tích lũy từ đỉnh vốn cao nhất xuống đáy vốn thấp nhất trong toàn bộ chu kỳ 3 năm (-2,050.72 USDT, tương đương -16.15%).
   - Chỉ số này hoàn toàn độc lập và khác biệt với **Daily Loss Limit (5%)** (giới hạn lỗ tối đa trong một cửa sổ trượt 24 giờ). Không sử dụng Daily Loss Limit để đánh giá Max Drawdown.

---

## 6. HỒ SƠ DỰ ÁN VÀ TRẠNG THÁI BÀN GIAO

- `PROJECT_STATE.md`: Đã khôi phục dòng Giai đoạn 4 trong checklist; cập nhật số lượng test của `test_backtest_engine.py` (15 tests); cập nhật Giai đoạn 5 ở trạng thái chờ nghiệm thu.
- `PLANNER_HANDOVER.md`: Đã ghi rõ Giai đoạn 5 do tác giả triển khai với Code-under-test commit `060f8a8d72e0eb2acbb6bd327ae67fbcb0805aac` nhưng chưa được nghiệm thu, đang chờ GPT Review 10.
- `ADR 0008`: Đã chuyển trạng thái sang `PENDING REVIEW`.
- `docs/reviews/GPT_STAGE_04_REVIEW_07.md`: Đã bổ sung ghi chú superseded trỏ tới Review 08 và Review 09.

---

## 7. KẾT LUẬN VÀ DỪNG CHỜ REVIEW

Tác giả đã hoàn thành việc sửa đổi toàn bộ các blocker theo yêu cầu của GPT Review 10:
- Đã làm test CWD hoàn toàn hermetic, không phụ thuộc `data/raw`.
- Đã chạy đầy đủ và chứng minh pass 100% cả 3 probe lịch sử Review 05, 06, 07.
- Đã thực hiện luồng commit có truy vết với Code-under-test commit `060f8a8d72e0eb2acbb6bd327ae67fbcb0805aac`.
- Không bắt đầu Giai đoạn 6.
- Không triển khai các chiến lược khác.
- Không kết nối testnet hay tiền thật.
- **DỪNG CHỜ GPT REVIEW 10 ĐÁNH GIÁ VÀ NGHIỆM THU CHÍNH THỨC.**
