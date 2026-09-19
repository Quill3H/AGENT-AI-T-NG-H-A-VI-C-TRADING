# BÁO CÁO TỔNG KẾT GIAI ĐOẠN 5: TREND FOLLOWING STRATEGY & BACKTEST ENGINE
*(Bản cập nhật hoàn thiện theo các blocker GPT Review 10 sơ bộ)*

**Thời điểm hoàn thành:** 2026-09-19  
**Tác giả:** Quill3H & Antigravity  
**Trạng thái nghiệm thu:** **CHƯA NGHIỆM THU — ĐANG CHỜ GPT REVIEW 10 ĐÁNH GIÁ**  
**Kiến trúc tham chiếu:** ADR 0008 (Trạng thái: PENDING REVIEW)  
**Trạng thái kiểm thử:** 240/240 tests PASSED (235 offline + 5 network) — 100% Xanh  
**Dữ liệu Benchmark:** 3 năm BTCUSDT (2021-01-01 đến 2023-12-31) — **AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED**  

---

## 1. MỤC TIÊU VÀ TỔNG QUAN KIẾN TRÚC

Giai đoạn 5 triển khai chiến lược giao dịch xu hướng (**Trend Following Strategy**) theo cơ chế nhân quả đa khung thời gian (**Multi-Timeframe Causal Execution**) và động cơ kiểm thử quá khứ (**Backtest Engine**) tối thiểu, vận hành trên nền tảng Paper Execution Engine (Giai đoạn 4), Risk Engine (Giai đoạn 3), Feature Engineering (Giai đoạn 2) và Data Layer (Giai đoạn 1).

### Các nguyên tắc thực thi cốt lõi:
1. **Loại trừ nhìn trước (Zero Lookahead Bias):** Tín hiệu và bộ lọc xác định hoàn toàn trên nến 4h đã đóng (`candle[t-1]`), lệnh được khớp vào nến 15m tiếp theo tại giá Open (`candle[t]`).
2. **Kế toán bất biến đóng kín:** Tính toán đầy đủ chi phí (phí taker 0.05%, trượt giá slippage 0.03%, funding rate settlement định kỳ), bảo toàn dòng tiền ví và ký quỹ cô lập (Isolated Margin).
3. **Fail-Closed Funding Provenance (Blocker 1):** Không ép kiểu lỏng lẻo (`bool(row_15m["funding_readiness"])`). Dữ liệu sai kiểu (string, int, float, NaN), missing, future hoặc stale bị từ chối tuyệt đối (fail-closed) trước khi gây ra bất kỳ biến đổi trạng thái nào trên broker/account.
4. **Độc lập CWD (Blocker 3):** CLI runner và đường dẫn cấu hình, dữ liệu cache được resolve tuyệt đối từ `PROJECT_ROOT`, hoạt động độc lập với thư mục thực thi hiện hành.

---

## 2. CHI TIẾT KHẮC PHỤC CÁC BLOCKER GPT REVIEW 10

### 2.1 Blocker 1: Funding Provenance Fail-Closed & Zero Mutation
- **Vấn đề cũ:** Tại `BacktestEngine.run()`, dòng lệnh `bool(row_15m["funding_readiness"])` đã biến các giá trị sai như chuỗi `"False"`, số `1`, hoặc `NaN` thành `True`, làm lách qua tầng kiểm soát của `PaperBroker`.
- **Khắc phục:**
  - Loại bỏ hoàn toàn `bool(...)` ép kiểu lỏng lẻo.
  - Phân lập kiểu dữ liệu:
    - Nếu là `numpy.bool_` thì chuyển về `bool` chuẩn Python.
    - Nếu là chuỗi, số, `NaN` hoặc object: giữ nguyên giá trị thô để `PaperBroker` kiểm tra `type(...) is bool` và fail-closed với `TypeError` hoặc `ValueError`.
  - Bổ sung kiểm thử tích hợp (`test_funding_metadata_fail_closed_and_zero_mutation`) cho 7 trường hợp lỗi: `missing`, `bool_False`, `str_False`, `int_1`, `nan`, `future`, `stale`.
  - Khẳng định tính bất biến trạng thái: Trong mọi trường hợp lỗi, `broker.wallet_balance`, `broker.positions["BTCUSDT"].isolated_collateral`, `broker.reserved_collateral`, và `broker.trade_history` không bị biến đổi bất kỳ giá trị nào (Zero Mutation).
  - Bổ sung kiểm thử `test_funding_metadata_valid_zero_rate` kiểm chứng `funding_rate = 0.0` hợp lệ với đầy đủ provenance được thanh toán bình thường với dòng tiền bằng 0.

### 2.2 Blocker 2: Future-Perturbation Test Phi-Rỗng & Tái Tính Chỉ Báo
- **Vấn đề cũ:** Test cũ tạo danh sách `trades_before_T_1` và `trades_before_T_2` nhưng không assert, đồng thời giữ nguyên các cột chỉ báo đã tính sẵn sau khi sửa dữ liệu OHLC.
- **Khắc phục (`test_future_perturbation_invariance`):**
  - Xây dựng kịch bản dữ liệu thực tế tạo ra setup ARMED, lệnh chờ và giao dịch đã khớp/đóng hoàn tất trước thời điểm $T$.
  - Khẳng định tính phi-rỗng (non-vacuous): `len(orders_before_T_1) >= 1`, `len(trades_before_T_1) >= 1`, `len(snaps_before_T_1) > 0`.
  - Nhiễu toàn bộ dữ liệu OHLC 15m và 4h sau $T$ (nhân 2.5x).
  - Đưa dữ liệu 4h nhiễu qua pipeline tính toán chỉ báo thật (`add_all_features`) để các chỉ báo sau $T$ thay đổi thực sự theo dữ liệu mới.
  - Kiểm chứng bất biến: Toàn bộ orders, trades và account snapshots trước hoặc tại $T$ giữa 2 lần chạy giống hệt nhau 100%.

### 2.3 Blocker 3: Test CWD Independence với Strategy Thật
- **Vấn đề cũ:** Test cũ gọi `--strategy breakout_retest` khiến CLI thoát trước khi thẩm định đường dẫn config và cache.
- **Khắc phục (`test_cli_cwd_independence`):**
  - Chạy chiến lược `trend_following` thật từ thư mục tạm ngoài project (`cwd=str(tmp_path)`).
  - Truyền đầy đủ các cờ: `--config config/default_config.yaml`, `--strategy trend_following`, `--start 2021-01-01`, `--end 2021-01-03`, `--no-fetch`.
  - Khẳng định lệnh thực thi thành công (exit code 0), xuất báo cáo hoàn chỉnh và vượt qua đối soát kế toán.

### 2.4 Blocker 4: Khớp Test Evidence với Cây Git Thực Tế
- Danh mục tệp kiểm thử trong báo cáo được đối chiếu chính xác từng tệp có trong Git commit, loại bỏ các tên tệp không tồn tại.
- Toàn bộ các probe test Giai đoạn 4 (`test_stage_04_review_06_coverage.py`, `test_stage_04_review_07_coverage.py`...) được giữ nguyên vẹn 100%, không né tránh assertion.

---

## 3. KẾT QUẢ KIỂM THỬ TỰ ĐỘNG (PYTEST SUITE)

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

================ 235 passed, 5 deselected, 1 warning in 7.74s =================
```

### 3.3 Bộ kiểm thử Network (5/5 tests PASSED)
Lệnh thực thi: `python -m pytest -m "network" -q`
```text
tests\test_data_layer.py .....                                           [100%]
================ 5 passed, 235 deselected, 1 warning in 12.39s ================
```

**Tổng cộng:** **240/240 tests PASSED (100% Xanh)**.

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
Git Commit SHA       : [Ghi nhận commit mới tại thời điểm push]
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

- `PROJECT_STATE.md`: Đã khôi phục dòng Giai đoạn 4 trong checklist; cập nhật Giai đoạn 5 ở trạng thái chờ nghiệm thu.
- `PLANNER_HANDOVER.md`: Đã ghi rõ Giai đoạn 5 do tác giả triển khai nhưng chưa được nghiệm thu, đang chờ GPT Review 10.
- `ADR 0008`: Đã chuyển trạng thái sang `PENDING REVIEW`.
- `docs/reviews/GPT_STAGE_04_REVIEW_07.md`: Đã bổ sung ghi chú superseded trỏ tới Review 08 và Review 09.

---

## 7. KẾT LUẬN VÀ DỪNG CHỜ REVIEW

Tác giả đã hoàn thành việc sửa đổi toàn bộ 8 blocker theo góp ý của GPT Review 10 sơ bộ:
- Không bắt đầu Giai đoạn 6.
- Không triển khai các chiến lược khác.
- Không kết nối testnet hay tiền thật.
- **DỪNG CHỜ GPT REVIEW 10 ĐÁNH GIÁ VÀ NGHIỆM THU CHÍNH THỨC.**
