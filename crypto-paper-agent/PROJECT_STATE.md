# PROJECT_STATE.md - Trạng thái Sống của Dự án

> [!IMPORTANT]
> **QUY TẮC SỐNG CỦA DỰ ÁN (BẮT BUỘC ĐỌC ĐẦU MỖI PHIÊN LÀM VIỆC):**
> 1. Trước khi viết bất kỳ dòng code nào, **BẮT BUỘC ĐỌC FILE NÀY** (`PROJECT_STATE.md`) kết hợp với mục liên quan trong [CRYPTO_PAPER_TRADING_AGENT_MASTER_SPEC.md](file:///D:/Ta%CC%80i%20lie%CC%A3%CC%82u/Default%20Project/Project%20spec/CRYPTO_PAPER_TRADING_AGENT_MASTER_SPEC.md). Tuyệt đối không dựa vào trí nhớ hội thoại để nhớ lại quyết định cũ.
> 2. **Đường dẫn PROJECT_ROOT duy nhất và chính thức:**
>    `D:\Tài liệu\Default Project\crypto-paper-agent` (Unicode NFD: `Ta\u0300i lie\u0323\u0302u`).
>    Tuyệt đối không tự ý quét ổ đĩa, không suy luận hoặc tạo thêm thư mục ở đường dẫn khác. Nếu nghi ngờ có bản copy trùng, **DỪNG LẠI VÀ HỎI NGƯỜI DÙNG**.
> 3. Sau khi hoàn thành một giai đoạn: Chạy toàn bộ pytest, cập nhật `PROJECT_STATE.md`, `CHANGELOG.md`, lưu báo cáo vào `BÁO CÁO TÓM TẮT/GIAI ĐOẠN X/` trước khi báo cáo hoàn thành.
> 4. Nếu cuộc trò chuyện kéo dài qua nhiều giờ/nhiều lượt, chủ động đề xuất người dùng mở phiên hội thoại mới để tránh trôi ngữ cảnh.

---

## 1. CHECKLIST TIẾN ĐỘ CÁC GIAI ĐOẠN

- [x] **Giai đoạn 0 — Khởi tạo dự án & Cấu hình** (ĐÃ ĐÓNG & DUYỆT)
- [x] **Giai đoạn 1 — Data Layer** (ĐÃ ĐÓNG & DUYỆT — 28/28 tests passed)
- [x] **Giai đoạn 2 — Feature Engine** (ĐÃ ĐÓNG & DUYỆT — 53/53 tests passed)
- [x] **Giai đoạn 3 — Risk Manager** (ĐÃ NGHIỆM THU THEO GPT REVIEW 04; người dùng đã cho phép chuyển Giai đoạn 4)
- [ ] **Giai đoạn 4 — Paper Execution Engine** (GPT REVIEW 06: CHƯA ĐẠT. Commit `60f6930`: probes Review 05 đạt 26/26, nhưng probes Review 06 còn 10 failed/1 passed; cần sửa H1–H6 rồi chờ Review 07. Bộ reviewer offline: 168 passed, 2 skipped, 5 deselected. Chưa bắt đầu Giai đoạn 5.)
- [ ] **Giai đoạn 5 — Phân hệ 1: Trend Following** (Backtest 2-3 năm BTC)
- [ ] **Giai đoạn 6 — Trade Logger & Report Metrics** (`trade_logger.py`, `metrics.py`)
- [ ] **Giai đoạn 7 — Phân hệ 2: Breakout & Retest**
- [ ] **Giai đoạn 8 — Phân hệ 4: Funding Arbitrage** (Delta-neutral)
- [ ] **Giai đoạn 9 — Phân hệ 3: SMC Liquidity Sweep** (`smc_features.py`, Order Block, FVG)
- [ ] **Giai đoạn 10 — Tổng hợp & So sánh đa chiến lược** (Walk-forward testing)
- [ ] **Giai đoạn 11 — Reinforcement Learning (Optional, nâng cao)**

---

## 2. DANH SÁCH TOÀN BỘ QUYẾT ĐỊNH ĐÃ CHỐT

1. **News Filter (`news_filter`):** Mặc định `enabled: false`. Không chặn lệnh cho đến khi người dùng nạp file lịch CSV thực tế (Tham chiếu: Mục 10.1 Spec).
2. **Khoảng thời gian Backtest (`data.start_date`):** Bắt đầu từ `"2021-01-01"` đến `"2026-09-01"` (~5.5 năm), bao phủ đầy đủ chu kỳ bull 2021, bear 2022 (LUNA/FTX), hồi phục 2023-2024 và hiện tại (Tham chiếu: Mục 10.3 Spec).
3. **Phục hồi Risk sau chuỗi thua (`circuit_breakers.recovery_mode`):** Chọn `"after_3_wins"`. Cần đúng **3 lệnh thắng liên tiếp** để khôi phục risk về 100% mức chuẩn (Tham chiếu: Mục 10.2 Spec, ADR 0002).
4. **Loại bỏ phần thừa Reinforcement Learning:** Không đưa tham số RL vào `default_config.yaml` của giai đoạn 0-10; toàn bộ logic RL để dành riêng cho Giai đoạn 11 (Tham chiếu: Mục 10.4 Spec).
5. **Môi trường Python 3.13 & Thư viện:** Nâng cấp `requirements.txt` lên `numpy>=2.1.0` và `pandas>=2.2.3` để tương thích chính thức Python 3.13 (Tham chiếu: ADR 0004).
6. **Cơ chế Hybrid Open Interest:** Dùng Binance Data Vision (`binance_vision_downloader.py`) cho lịch sử xa >28 ngày; dùng Binance REST API cho 2 ngày gần nhất. Không để trống dữ liệu ở phần đuôi (Tham chiếu: ADR 0001).
7. **Cơ chế OI Confluence & Fallback:** Cấu hình `oi_confluence.mode: "optional"`, `fallback_when_nan: true`. Khi OI là NaN, `oi_delta_pct` tự động lan truyền NaN và chiến lược tự động fallback bỏ qua điều kiện OI, không ném exception (Tham chiếu: ADR 0005).
8. **Đóng gói hàm Cache Manager:** Chuẩn hóa các hàm public `ensure_utc_index` và `timeframe_to_timedelta` trong `cache_manager.py`, giữ alias tương thích ngược.
9. **Chống Lookahead Bias tuyệt đối cho CVD Divergence:** Nến $i$ là Swing Point được xác nhận tại nến $t = i + k$ ($k = 3$). Tín hiệu phân kỳ chỉ ghi nhận tại nến $t$, **tuyệt đối không gán ngược** về nến $i$ (Tham chiếu: ADR 0003).
10. **Tầng Fallback cho Chỉ báo Kỹ thuật:** Ưu tiên `pandas-ta`, nhưng luôn có tầng Fallback bằng pure pandas (`_ema_presma`, Wilder RMA) theo đúng chuẩn TA-Lib với log cảnh báo rõ ràng (Tham chiếu: ADR 0004).
11. **Chuẩn hóa Refinements cho Risk Manager theo Independent GPT Review (ADR 0006):** Khắc phục toàn diện 6 vấn đề R1–R6: Loại trừ bool/NaN/Inf khỏi sizing, đối soát rủi ro thực tế $Q \times |Entry - Stop|$ với ngân sách rủi ro và available margin, loại bỏ fallback wall-clock `datetime.now()` (bắt buộc timestamp UTC mô phỏng), làm sạch Circuit Breaker (sliding window $(T-24h, T]$, monotonic time, breakeven streak reset, lockout non-extension), giải giá thanh lý nhất quán theo Tier (Tier-Consistent Solver), kịch bản mô phỏng 100% minh bạch (Tham chiếu: ADR 0006).
12. **Chuẩn hóa Toàn diện Giai đoạn 3 theo GPT Review Lần 2 (F1 – F5):**
    - **F1:** Đối soát rủi ro thực tế với ngân sách khai báo của lệnh (`order_declared_budget_usd`), chống double reduction giữa `base_risk_percent` và `risk_percent`.
    - **F2:** Bắt buộc `available_margin` hữu hạn $\ge 0$, kiểm tra ký quỹ bao gồm phí vào lệnh ước tính, loại bỏ hoàn toàn crash `TypeError` (unhashable types), `AttributeError` (non-callable breaker) và `OverflowError` (timestamp).
    - **F3:** Phân lập `account_state['current_time']` (Admission Time) làm thẩm quyền duyệt lệnh duy nhất; chặn lách tin tức bằng signal cũ; phát hiện lệch cấu hình news filter.
    - **F4:** Thống nhất đồng hồ đơn nhất `advance_time` cho Circuit Breaker; giải quyết triệt để Scenario A và Scenario B; chuyển trạng thái `is_halted = True` khi cháy vốn; kiểm soát danh mục `recovery_mode`.
    - **F5:** Giải thuật thanh lý nghiêm ngặt: kiểm tra tính liên tục của bracket, từ chối vượt trần bracket tối đa (không ngoại suy), từ chối vị thế vi phạm ngay tại entry, ràng buộc phương hướng nghiệm, loại bỏ fallback tier cuối, kiểm chứng độc lập phương trình cân bằng ký quỹ (Tham chiếu: Phụ lục ADR 0006).
13. **Chuẩn hóa Tinh chỉnh Giai đoạn 3 theo GPT Review Lần 3 (G1 – G3):**
    - **G1:** Validate nghiêm ngặt `math.isfinite` và kiểu dữ liệu cho `config.risk` (`max_leverage`, `min_liquidation_buffer_pct`, `conviction_tiers`), `fees.taker_pct` và trạng thái `cb_state.risk_multiplier` (trong $(0, 1.0]$ và khớp trạng thái hợp lệ). Chặn đứng việc vô hiệu hóa so sánh buffer do `NaN` hoặc ngầm fallback 1.0 nhận full rủi ro.
    - **G2:** Phát hiện và chặn lùi thời gian tại cổng (`admission_time < cb_state.current_timestamp`) bằng mã lỗi `INVARIANT_FAIL_TIME_REVERSAL`, không gọi component gây unhandled exception, bảo toàn nguyên vẹn đồng hồ và trạng thái Breaker.
    - **G3:** Kiểm soát trạng thái sẵn sàng (`is_ready: bool`, `load_error`) của `NewsCalendarFilter` khi `enabled = True`. Từ chối lệnh nếu thiếu file hoặc lịch bị hỏng schema/timestamp; phân biệt rõ với lịch rỗng hợp lệ (Tham chiếu: Phụ lục 2 ADR 0006).
14. **Kiến trúc Paper Execution Engine & Quy trình 5 Pha Chống Nhìn Trước (ADR 0007):**
    - Mô hình Linear USDT-Margined Isolated Futures.
    - 5 pha bất biến: Open Time & Gap Exits -> Funding Settlement -> Pending Market Entry & Risk Gate -> Intrabar Protection (Liquidation > SL > TP) -> Close Time & Mark-to-Market.
    - Hạch toán kế toán chuẩn xác từng bit (Oracle test pass 100%), đối soát tự động sau mỗi nến.
    - Tích hợp 2 chiều với Circuit Breaker (khóa 24h khi lỗ ngày 5%, giảm 50% risk sau 3 thua, phục hồi sau 3 thắng).
    - Ràng buộc tối đa 1 vị thế/symbol, thắt chặt SL một chiều (tightening only) (Tham chiếu: ADR 0007).
15. **Chuẩn hóa Paper Execution Engine theo GPT Review 05 (E1–E8):**
    - **E1:** Đọc `settlement_hours_utc` linh hoạt, khóa trùng funding theo `(symbol, open_time)`, kiểm tra `math.isfinite` trên funding rate trước đột biến, phát hiện và từ chối gap nến bỏ qua mốc thanh toán funding khi đang mở vị thế.
    - **E2:** Tự động tính toán lại `liquidation_price` theo ký quỹ cô lập thực tế sau khi điều chỉnh dòng tiền funding với MMR tier động (`get_mmr_tier`).
    - **E3:** Bổ sung `record_cashflow` độc lập cho Breaker (theo dõi lỗ 24h từ funding/fees mà không ảnh hưởng win/loss streak); tự động kích hoạt `_handle_circuit_breaker_lock` hủy lệnh chờ và đóng cưỡng chế toàn bộ vị thế còn lại kèm slippage khi Breaker bị khóa.
    - **E4:** Gỡ bỏ vị thế khỏi `self.positions` trước khi tính `post_close_equity` gửi về Breaker, loại bỏ hoàn toàn double counting unrealized PnL cũ.
    - **E5:** Tái kiểm tra khoảng cách SL/TP sau trượt giá (`fill_price`); bắt ngoại lệ `ValueError` từ sizing/solver chuyển thành `OrderStatus.REJECTED`; kiểm tra khớp đúng `order_declared_budget_usd`.
    - **E6:** Giao dịch nguyên khối (Transactional Preflight) trong `process_candle` (kiểm tra OHLC, timeframe regex, duration, thời gian mở/đóng đơn điệu và funding rate trước mọi đột biến tài chính).
    - **E7:** Áp dụng trượt giá thoát lệnh khi force close, chặn dời SL vượt qua Mark Price, ưu tiên Gap TP tại Pha 1 trước khi settlement funding ở Pha 2.
    - **E8:** Xác thực miền cấu hình ban đầu (`initial_equity_usd > 0`, `fees in [0, 1]`, `settlement_hours in [0, 23]`) và gia cố `math.isfinite` trên toàn bộ tài khoản trong `verify_accounting_invariants` (Tham chiếu: Phụ lục ADR 0007, Báo cáo sửa đổi Review 05).
16. **Kết luận độc lập GPT Review 06 — Giai đoạn 4 chưa nghiệm thu:**
    - 26/26 probes Review 05 đã đạt, nhưng kiểm tra sâu hơn còn H1–H6: cashflow ledger chưa exactly-once, solver collateral chọn sai tier/fallback, clock chưa hỗ trợ multi-symbol cùng timestamp, một số đường public/config chưa transactional fail-closed, thiếu finalize/end-of-data, funding provenance và hồ sơ tái hiện còn thiếu.
    - Bằng chứng reviewer: 168 passed, 2 skipped, 5 deselected ở bộ offline; Review 06 probes 10 failed/1 passed. Chi tiết tại `docs/reviews/GPT_STAGE_04_REVIEW_06.md`. Không bắt đầu Giai đoạn 5 trước Review 07 và quyết định người dùng.

---

## 3. BẢN ĐỒ CÁC FILE QUAN TRỌNG VAI TRÒ

| Đường dẫn File | Vai trò chính |
| :--- | :--- |
| `PROJECT_STATE.md` | Bảng trạng thái sống của dự án, đọc đầu tiên ở mỗi phiên làm việc. |
| `CHANGELOG.md` | Nhật ký ghi nhận các thay đổi và kết quả test qua từng giai đoạn. |
| `config/default_config.yaml` | Toàn bộ tham số hệ thống: vốn, risk tiers, circuit breakers, phí, periods chỉ báo. |
| `config/strategies/` | File cấu hình riêng cho từng chiến lược (`trend_following.yaml`, `smc_liquidity_sweep.yaml`). |
| `src/data_layer/fetcher.py` | Kéo dữ liệu OHLCV, funding rate và hybrid OI từ Binance, merge không lookahead. |
| `src/data_layer/binance_vision_downloader.py` | Tải dữ liệu OI lịch sử sâu từ Binance Data Vision, giải nén và downsample. |
| `src/data_layer/cache_manager.py` | Quản lý đọc/ghi cache Parquet local, kiểm tra gap dữ liệu. |
| `src/features/indicators.py` | Tính EMA (20/50/200), RSI (14), MACD (12/26/9), ATR (14) từ config + fallback. |
| `src/features/oi_features.py` | Tính `oi_delta_pct` với cơ chế lan truyền NaN và tương thích OI confluence. |
| `src/features/cvd.py` | Tính Cumulative Volume Delta và phát hiện CVD Divergence chống lookahead 100%. |
| `src/features/news_calendar.py` | Quản lý lịch sự kiện vĩ mô, blackout window ±15m, quản lý trạng thái readiness và load_error. |
| `src/features/__init__.py` | Export module và cung cấp hàm pipeline tổng hợp `add_all_features`. |
| `src/risk/position_sizing.py` | Tính position size, required margin, stop distance, bắt lỗi chia 0 và sanitization chặt chẽ. |
| `src/risk/invariant_checks.py` | Tra MMR tier từ brackets, giải P_liq nhất quán theo Tier, kiểm tra Hard Invariants và đối soát margin. |
| `src/risk/circuit_breakers.py` | Quản lý Circuit Breaker, khóa 24h khi lỗ 5%, giảm 50% risk, phục hồi after_3_wins, làm sạch đầu vào. |
| `src/risk/__init__.py` | Export module và các hàm tiện ích của Risk Manager. |
| `src/execution/order_models.py` | Enums và dataclasses cho Paper Execution (OrderRequest, Position, TradeRecord, Snapshot). |
| `src/execution/paper_broker.py` | Paper Broker 5 pha chống nhìn trước, khớp lệnh isolated futures, funding, gap exit. |
| `src/execution/__init__.py` | Export module và các lớp thực thi cốt lõi của Giai đoạn 4. |
| `scripts/simulate_risk_manager_10_trades.py` | Kịch bản mô phỏng 10 lệnh minh bạch 100% (2 Phase độc lập, đối soát vốn tự động). |
| `scripts/simulate_paper_execution.py` | Kịch bản mô phỏng khớp lệnh Paper Execution (Phần A Synthetic + Phần B Real Cached Data). |
| `tests/test_data_layer.py` | 25 unit/integration tests cho Data Layer, cache và hybrid OI. |
| `tests/test_indicators.py` | 9 unit tests cho các chỉ báo kỹ thuật, so sánh chéo fallback và TA-Lib. |
| `tests/test_oi_features.py` | 6 unit tests cho OI delta và cơ chế lan truyền NaN. |
| `tests/test_cvd.py` | 4 unit tests cho CVD và nhận diện phân kỳ Bullish/Bearish. |
| `tests/test_no_lookahead.py` | 6 unit tests xáo trộn tương lai, chứng minh tính bất biến nhân quả quá khứ. |
| `tests/test_position_sizing.py` | 21 unit tests cho Position Sizing, so khớp số liệu tính tay, sanitization, biên số học. |
| `tests/test_liquidation_calc.py` | 15 unit tests cho Tier-Consistent Solver, benchmark GPT review, bracket validation & F5. |
| `tests/test_circuit_breakers.py` | 16 unit tests cho các kịch bản ngắt mạch, chuỗi thua/thắng/hòa, sliding window pruning & F4. |
| `tests/test_invariant_checks.py` | 41 unit tests kiểm tra invariant, gates từ chối, actual risk đối soát, margin check, F1-F3, G1-G3. |
| `tests/test_news_calendar.py` | 9 unit tests cho News Calendar Filter, blackout window, readiness, corrupted rows & reload. |
| `tests/test_execution_models.py` | 4 unit tests cho dataclasses, validation, deterministic IDs, immutability của order models. |
| `tests/test_execution_accounting.py` | 3 unit tests cho bài toán Oracle bắt buộc và kiểm tra bất biến kế toán sau mỗi sự kiện. |
| `tests/test_paper_broker.py` | 7 unit tests cho Paper Broker: 1 position/symbol, SL over TP, gap exit, trailing tightening, CB streak, Liq priority, replay determinism. |
| `tests/test_execution_no_lookahead.py` | 3 unit tests chứng minh chống nhìn trước: next-open entry, sizing độc lập High/Low/Close, future perturbation bất biến. |
| `docs/decisions/` | Thư mục lưu trữ các Architecture Decision Records (ADR 0001 → 0007). |
| `BÁO CÁO TÓM TẮT/` | Thư mục chứa báo cáo tổng hợp và code backup theo từng giai đoạn (Giai đoạn 0 → 4). |

---

## 4. CÁC VẤN ĐỀ ĐÃ BIẾT NHƯNG CỐ Ý ĐỂ LẠI (KNOWN LIMITATIONS)

1. **Giới hạn Binance REST API cho OI:** Endpoint `/fapi/v1/openInterestHist` chỉ trả về tối đa 30 ngày. Đã giải quyết bằng cơ chế Hybrid kết hợp Binance Data Vision cho dữ liệu sâu.
2. **Warm-up Period 199 nến đầu của EMA 200 là NaN:** Đây là tính chất toán học chuẩn mực của TA-Lib (`presma=True`), không phải bug. Các chiến lược khi chạy backtest sẽ bắt đầu quét lệnh sau khi đã đủ 200 nến.
3. **CVD Flatline khi thiếu Taker Buy Volume:** Nếu klines API không có cột `taker_buy_base_volume` (hoặc có giá trị `NaN`), hệ thống ước tính bằng 50% volume $\to \text{delta} = 0$, khiến đường CVD đi ngang (flatline) thay vì ném ngoại lệ làm crash engine. Đã thêm log cảnh báo chi tiết trong `cvd.py`. **LƯU Ý NGHIỆP VỤ:** Nếu sau này thấy `cvd_divergence` có vẻ bất thường ở một giai đoạn cụ thể, đây là nghi phạm đầu tiên cần kiểm tra xem dữ liệu sàn trong giai đoạn đó có bị khuyết taker buy volume hay không.
