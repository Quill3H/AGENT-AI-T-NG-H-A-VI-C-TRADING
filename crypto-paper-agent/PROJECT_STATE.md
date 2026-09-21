# PROJECT_STATE.md - Trạng thái Sống của Dự án

## Current repair checkpoint — 2026-09-21

**IMPLEMENTED AND AUTHOR_TESTED — PENDING INDEPENDENT REVIEW.** No acceptance is claimed.

- Active branch: `codex/stage-06-to-11-completion`; final code/test/script A: `23f94376215a7fca69c8a7606e34139bc21d090c`.
- Baseline: `2236e839529cbcfb31cfd399107617f0b541e907`; main preserved at `e970337d504563e5987a4db6b5c06c635bf7244b`.
- User has authorized continuous implementation through Stage 11 including actual PPO, isolated dependencies and branch push. Earlier stop-before-7 and optional-RL task instructions are **SUPERSEDED**. No main merge, force-push, live/testnet, credentials, money or paid resources.
- Stage6: parsed calendar semantic snapshot, portable config/report identity and exact byte checksums. Stage7: causal LONG/SHORT Breakout E2E. Stage8: funded atomic basket + existing risk/breaker + cash ledger. Stage9: real 5m/1m FVG limits and 40/30/30 partial/BE/trailing exits. Stage10: executable four-account OOS workflow. Stage11: actual Gymnasium/SB3 PPO train/evaluate/save/load through PaperBroker.
- Final A gates: offline **356 passed, 2 skipped, 5 deselected**; network **5 passed, 358 deselected**; Review05 **26**, Review06 **11**, Review07 **3** passed; clean detached A offline **356 passed, 2 skipped, 5 deselected**. Two existing skips require optional pandas-ta.
- Four external-CWD custom-config synthetic CLI runs have actual fills and closed realizations. Public three-day dataset, four-strategy OOS, real PPO256/save-load/holdout and evaluate-only CLI all ran. Artifact audit checked JSON/SQLite/hash/CSV/PNG consistency and found no absolute machine paths in report artifacts.
- Public directional OOS:0 trades; funding1 basket/-25.18825656 USDT. PPO holdout:-477.11246108 USDT. Short sample proves engineering paths, not economic quality. All performance is **AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED**. Full historical window/2021–2023 replay is **PARTIAL / NOT_VERIFIED**.
- SMC report rows are realization slices, not independent full-position samples. Funding uses sampled spot/perp quotes, not hidden intrabar paths. Four comparison accounts have independent capital. No shared portfolio or profitable learned policy is claimed.
- Documentation commit B is the documentation-only child of A. Obtain its actual full SHA from the final branch handoff; do not confuse B with the code commit tested above.

Current evidence: [repair report](docs/reviews/STAGE_06_11_REPAIR_REPORT.md), [matrix](docs/planning/STAGE_06_11_REPAIR_MATRIX.md), [ADR0010](docs/decisions/0010-research-strategies-and-rl-boundary.md), [ADR0011](docs/decisions/0011-funded-basket-and-research-execution.md), [ADR0012](docs/decisions/0012-causal-smc-limits-and-partial-accounting.md).


> [!IMPORTANT]
> **QUY TẮC SỐNG CỦA DỰ ÁN (BẮT BUỘC ĐỌC ĐẦU MỖI PHIÊN LÀM VIỆC):**
> 1. Trước khi viết bất kỳ dòng code nào, **BẮT BUỘC ĐỌC FILE NÀY** (`PROJECT_STATE.md`) kết hợp với `Project spec/CRYPTO_PAPER_TRADING_AGENT_MASTER_SPEC.md` trong repository. Tuyệt đối không dựa vào trí nhớ hội thoại để nhớ lại quyết định cũ.
> 2. **Chính sách PROJECT_ROOT portable:** PROJECT_ROOT là thư mục chứa repository Git đang được quản lý trong phiên hiện tại. Ưu tiên đường dẫn repo-relative trong tài liệu và config; không suy luận hoặc sửa một checkout khác bên ngoài repository hiện tại.
> 3. Sau khi hoàn thành một giai đoạn: Chạy toàn bộ pytest, cập nhật `PROJECT_STATE.md`, `CHANGELOG.md`, lưu báo cáo vào `BÁO CÁO TÓM TẮT/GIAI ĐOẠN X/` trước khi báo cáo hoàn thành.
> 4. Nếu cuộc trò chuyện kéo dài qua nhiều giờ/nhiều lượt, chủ động đề xuất người dùng mở phiên hội thoại mới để tránh trôi ngữ cảnh.

---

## 1. CHECKLIST TIẾN ĐỘ CÁC GIAI ĐOẠN

- [x] **Giai đoạn 0 — Khởi tạo dự án & Cấu hình** (ĐÃ ĐÓNG & DUYỆT)
- [x] **Giai đoạn 1 — Data Layer** (ĐÃ ĐÓNG & DUYỆT — 28/28 tests passed)
- [x] **Giai đoạn 2 — Feature Engine** (ĐÃ ĐÓNG & DUYỆT — 53/53 tests passed)
- [x] **Giai đoạn 3 — Risk Manager** (ĐÃ NGHIỆM THU THEO GPT REVIEW 04; người dùng đã cho phép chuyển Giai đoạn 4)
- [x] **Giai đoạn 4 — Paper Execution Engine** (ĐÃ NGHIỆM THU THEO GPT REVIEW 09 — Code commit: `b16fa1e0...`)
- [x] **Giai đoạn 5 — Phân hệ 1: Trend Following** (ĐÃ NGHIỆM THU THEO GPT REVIEW 10 — Code commit: `060f8a8d...`, Docs commit: `dc0ab9be...`)
- [ ] **Giai đoạn 6 — Trade Logger & Performance Report** (IMPLEMENTED AND AUTHOR_TESTED — PENDING INDEPENDENT REVIEW; code A `23f94376215a7fca69c8a7606e34139bc21d090c`; xem giới hạn dữ liệu ở checkpoint)
- [ ] **Giai đoạn 7 — Phân hệ 2: Breakout & Retest** (IMPLEMENTED AND AUTHOR_TESTED — PENDING INDEPENDENT REVIEW; code A `23f94376215a7fca69c8a7606e34139bc21d090c`; xem giới hạn dữ liệu ở checkpoint)
- [ ] **Giai đoạn 8 — Phân hệ 4: Funding Arbitrage** (IMPLEMENTED AND AUTHOR_TESTED — PENDING INDEPENDENT REVIEW; code A `23f94376215a7fca69c8a7606e34139bc21d090c`; xem giới hạn dữ liệu ở checkpoint)
- [ ] **Giai đoạn 9 — Phân hệ 3: SMC Liquidity Sweep** (IMPLEMENTED AND AUTHOR_TESTED — PENDING INDEPENDENT REVIEW; code A `23f94376215a7fca69c8a7606e34139bc21d090c`; xem giới hạn dữ liệu ở checkpoint)
- [ ] **Giai đoạn 10 — Tổng hợp & So sánh đa chiến lược** (IMPLEMENTED AND AUTHOR_TESTED — PENDING INDEPENDENT REVIEW; code A `23f94376215a7fca69c8a7606e34139bc21d090c`; xem giới hạn dữ liệu ở checkpoint)
- [ ] **Giai đoạn 11 — Reinforcement Learning — PPO/Gymnasium thực** (IMPLEMENTED AND AUTHOR_TESTED — PENDING INDEPENDENT REVIEW; code A `23f94376215a7fca69c8a7606e34139bc21d090c`; xem giới hạn dữ liệu ở checkpoint)

---

## 2. QUYẾT ĐỊNH LỊCH SỬ VÀ INVARIANT ĐƯỢC GIỮ

Các lệnh dừng/chuyển giai đoạn và số lượng test cũ dưới đây thuộc mốc lịch sử; quyền hiện tại và gates trên A ở đầu file. Nội dung risk không bị nới lỏng. ADR0010–0012 cập nhật semantics Stage8–11.

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
17. **Chuẩn hóa Toàn diện Paper Execution Engine theo GPT Review 06 (H1–H6):**
    - **H1:** Ghi nhận entry fee vào cashflow ledger ngay sau khi fill được commit; ghi nhận signed funding đúng một lần tại settlement; khi đóng lệnh, ghi nhận `gross_pnl - exit_fee` vào cashflow ledger và cập nhật net trade pnl vào win/loss streak; loại bỏ hoàn toàn double-counting funding/fees trong rolling cashflows; khi CB lock do entry fee thì không tính vào streak thua.
    - **H2:** Tái cấu trúc `_calculate_collateral_aware_liquidation_price` bằng solver tự nhất quán theo tier của quy mô tại chính giá thanh lý ($Q \times P_{liq}$); loại bỏ hoàn toàn hardcoded fallback `mmr=0.004, cum=0.0`, ném ngoại lệ rõ ràng khi cấu hình bracket không hợp lệ hoặc không có nghiệm.
    - **H3:** Nâng cấp đồng hồ Paper Broker hỗ trợ multi-symbol cùng market timestamp: theo dõi `last_candle_open_time_per_symbol` và batch sequence watermark `current_batch_open_time` cùng `symbols_in_current_batch`; cho phép nhiều symbol cùng open_time nhưng từ chối duplicate của chính symbol; gỡ bỏ advance time sớm tại Phase 5 để bảo toàn tính độc lập thứ tự nến trong batch.
    - **H4:** Transactional fail-closed: kiểm tra price, timestamp (chống time reversal) và enum reason trước khi thực hiện bất kỳ mutation nào trong `close_all_positions`; cấu hình `funding_rate` và các sub-configs khác bắt buộc phải là `dict` (ném `TypeError` nếu truyền chuỗi/sai kiểu).
    - **H5:** Bổ sung lifecycle `finalize(timestamp, force_close=False)`: idempotent, trả về tóm tắt phiên; force mode đóng mọi vị thế mở với `ExitReason.END_OF_DATA` kèm slippage/phí; chặn mọi nến và lệnh mới sau khi finalize.
    - **H6:** Kiểm soát funding provenance (chặn lookahead bias nếu `funding_time > open_time`, chặn dữ liệu cũ >24h, chặn funding unready tại settlement); cung cấp `scripts/fetch_market_data.py`; phục hồi dòng trạng thái Giai đoạn 3 trong checklist `PROJECT_STATE.md`; phân định minh bạch kết quả author vs reviewer (Tham chiếu: Phụ lục 2 ADR 0007, Báo cáo sửa đổi Review 06).
18. **Chuẩn hóa Toàn diện Paper Execution Engine theo GPT Review 07 (J1–J3):**
    - **J1:** Bắt buộc `funding_readiness is True` (kiểu boolean) và source timestamp hợp lệ (`funding_time`) tại settlement boundary khi vị thế sống qua Pha 1. Thiếu key, None, sai kiểu, future hoặc stale (>24h) đều fail-closed trước mọi đột biến tài khoản. Cho phép rate 0.0 hữu hạn khi metadata hợp lệ.
    - **J2:** Tách `_calculate_liquidation_price_for_collateral` độc lập; precompute candidate cashflow, candidate collateral và pre-run solver ngay tại Preflight trước mọi mutation. Toàn bộ state (wallet, collateral, cumulative funding, history, breaker, settled keys, clocks) bất biến 100% nếu solver thất bại do leverage brackets hỏng hoặc vô nghiệm.
    - **J3:** Finalize force_close và close_all_positions duyệt vị thế an toàn (`symbol not in self.positions`), không văng KeyError khi Circuit Breaker lock kích hoạt lồng nhau và tự đóng các vị thế còn lại. Broker chuyển terminal state nhất quán (`is_finalized = True`), lưu `_finalized_summary` và đảm bảo tính idempotent tuyệt đối khi gọi lại (Tham chiếu: Mục 5.7–5.9 ADR 0007, Báo cáo sửa đổi Review 07).
19. **Khắc phục Dứt điểm Phát hiện K1 theo GPT Review 08 (Loại bỏ Caller Inspection & Thực thi Funding Invariant Vô Điều Kiện):**
    - **Loại bỏ triệt để inspect / frame inspection:** Xóa bỏ hoàn toàn `import inspect`, `_is_legacy_probe_caller()` và mọi logic nhận diện tên test/caller/stack trong `src/execution/paper_broker.py`. `PaperBroker` xử lý đồng nhất 100% giữa môi trường test và production đối với cùng một input.
    - **Fail-closed vô điều kiện tại settlement:** Mọi lệnh gọi vào mốc thanh toán funding (00, 08, 16 UTC) cho vị thế mở bắt buộc phải có `funding_readiness` là kiểu `bool` và mang giá trị `True`; timestamp nguồn phải hợp lệ, không future và không stale (>24h); `funding_rate` hữu hạn (`0.0` được phép). Tuyệt đối không cho phép bất kỳ cờ cấu hình nào (như `strict_provenance`) hay tên caller nào nới lỏng bất biến này.
    - **Bổ sung metadata hợp lệ vào test cũ:** Trong `docs/reviews/test_stage_04_review_05.py` và `docs/reviews/test_stage_04_review_06.py`, bổ sung `funding_time` và `funding_readiness=True` vào helper `candle()` khi có `funding_rate`, tuyệt đối không sửa hay làm yếu bất kỳ assertion nào.
    - **Bổ sung 3 regression tests K1:** Kiểm tra AST (chặn `inspect`/caller frame inspection), kiểm tra tính bất biến trước tên caller stack (`test_stage_04_review_05_probe_caller` vs `production_live_caller`), và kiểm tra cấu hình `strict_provenance=False` không thể nới lỏng fail-closed (Tham chiếu: Mục 5.7 ADR 0007, Báo cáo sửa đổi Review 08).

20. **Nghiệm thu Giai đoạn 4 theo GPT Review 09:** Giai đoạn 4 được đóng tại commit `b16fa1e0b7f064f764cea12fc97ae5c0677a40d2`. Kết luận chi tiết tại `docs/reviews/GPT_STAGE_04_REVIEW_09.md`. Mọi thay đổi sau commit này phải tự chứng minh không hồi quy các bất biến E1–E8, H1–H6, J1–J3 và K1.
21. **Phạm vi Giai đoạn 5 — Trend Following:** Triển khai rulebook EMA20/EMA50 crossover → pullback vùng EMA20/50, regime EMA200, RSI và OI confluence; stop swing causal và trailing EMA50; LONG cùng SHORT đối xứng; tín hiệu 4h, thực thi next-open 15m. Giai đoạn 5 bao gồm `BacktestEngine` tối thiểu và cầu nối funding provenance vì đây là dependency cần thiết để chạy backtest, nhưng không bao gồm Trade Logger/metrics/dashboard Giai đoạn 6 hoặc chiến lược/RL Giai đoạn 7–11. Benchmark win rate 35–45% chỉ để đối chiếu, không phải mục tiêu được phép overfit. Antigravity phải dừng sau Giai đoạn 5 theo `docs/planning/ANTIGRAVITY_STAGE_05_TASK.md`.
22. **Kiến trúc Trend Following & Backtest Engine Đa Khung Thời Gian (ADR 0008):**
    - Hợp đồng `BaseStrategy` với `on_candle_close` và `update_trailing_stop`.
    - State machine bám xu hướng (IDLE -> ARMED -> Pullback/Retest -> Executed / Invalidation / Expiry), one-shot per crossover.
    - Cắt lỗ ban đầu causal theo swing low/high 5 nến 4h đóng gần nhất; Trailing stop bám EMA50 nến 4h đóng siết chặt một chiều (tightening-only) qua `broker.update_stop_loss`.
    - `BacktestEngine` đồng bộ nhân quả: nến 15m dẫn dắt event loop, chỉ đánh giá chiến lược khi nến 4h đóng hoàn toàn (`close_time_15m == close_time_4h`), lệnh khớp tại open nến 15m kế tiếp (+ slippage), chống lookahead bias tuyệt đối (`test_future_perturbation_invariance`).
    - Đóng mắt xích funding provenance trong `fetcher.py`: bảo toàn `funding_time` và cờ boolean `funding_readiness`, fail-closed khi thiếu/future/stale dữ liệu tại settlement.
    - CLI `run_backtest.py` hoàn chỉnh: hỗ trợ `--config`, `--strategy`, `--start`, `--end`, `--no-fetch`; độc lập CWD và fail-closed rõ ràng khi strategy chưa triển khai.
    - Nghiệm thu benchmark 3 năm BTCUSDT (2021-2023): Win rate 50.00%, Total return +21.01%, Max Drawdown -16.15%, đối soát sổ cái kế toán khớp từng cent (Tham chiếu: ADR 0008).
23. **Kiến trúc Trade Logger & Performance Reporting (ADR 0009 - Hoàn thiện toàn diện sau GPT Review 11):**
    - Kho lưu trữ SQLite Event Store (`src/logging/trade_logger.py`) với 6 bảng quan hệ có khóa ngoại (`PRAGMA foreign_keys = ON;`): `runs`, `orders`, `trades`, `funding_events`, `account_snapshots`, `run_metrics`.
    - Khóa chính phức hợp bảo vệ toàn vẹn dữ liệu: `PRIMARY KEY (run_id, order_id)`, `PRIMARY KEY (run_id, trade_id)`, `PRIMARY KEY (run_id, event_id)`, `PRIMARY KEY (run_id, timestamp)`.
    - Lưu trọn vẹn lý do từ chối lệnh (`rejection_reasons_json`) trong bảng `orders`; lan truyền metadata từ `OrderRequest` sang mọi `OrderExecutionRecord`.
    - Ánh xạ trực tiếp các trường của `AccountSnapshot`: `reserved_collateral`, `available_margin`, `open_positions_count`, `is_halted`.
    - Cơ chế kiểm soát luỹ thừa toàn diện bằng mã băm chuẩn tắc SHA-256 (`canonical_payload_hash`) bao phủ config, run metadata, orders, trades, funding events, snapshots, metrics. Cùng `run_id` + cùng hash là idempotent no-op; cùng `run_id` + sai lệch bất kỳ ném `ValueError` (fail-closed).
    - Hỗ trợ cả production nested config (`config["data"]["futures_symbol"]`, `config["strategy"]["name"]`) và flat config.
    - Xuất JSON trade chuẩn xác nguyên văn theo Master Spec Mục 4.6 (17 key gốc, nested `market_context` với 4 key null unmeasured, nested `outcome` với 7 key, `rule_compliance: true`, RFC 8259 `allow_nan=False`).
    - Chuẩn hoá nguồn chân lý tính toán metrics (`src/report/metrics.py`): Expectancy USD & R-multiple, Profit Factor (loss=0 xử lý là `None`/`null`), Max Drawdown USD & %, Daily Sharpe Ratio resampled 1D UTC $\sqrt{365}$ annualization (std=0 trả `0.0` hữu hạn và deterministic). Chặn đứng `bool`, `NaN`, `Inf` bằng fail-closed type validation.
    - Phân tách độc lập chỉ số Circuit Breaker (`status`, `multiplier`, `lock_count`, `rejections_count`) khỏi từ chối do thiếu ký quỹ riêng lẻ (`margin_rejections_count`).
    - Run ID tất định (Deterministic Run ID) sinh từ mã băm SHA-256 của `code_sha | strategy | symbol | start | end | config_hash` (loại bỏ wall-clock). Canonical config loại bỏ machine-specific absolute cache roots bằng placeholder ổn định; thay đổi `fees.taker_pct` làm thay đổi hash/run ID.
    - Phân giải đường dẫn chuẩn tắc (Hermetic Path Resolution): Mọi đường dẫn tương đối `--output-dir` và `--db-path` đều resolve từ `PROJECT_ROOT`, bảo đảm độc lập 100% với CWD ngoại vi; bảo toàn đường dẫn tuyệt đối.
    - Tự động sinh bộ 6 artifacts đa định dạng (`src/report/generator.py`) trong `reports/<run_id>/`: `summary.json` (đầy đủ provenance, candle counts, gaps, đối soát kế toán), `summary.md` (nhãn `AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED`, bảng đối soát, disclosures & caveats), `trades.json`, `equity_curve.csv`, `equity_curve.png`, `trades.sqlite`.
    - Thống nhất Benchmark Chuẩn Tắc 3 năm BTCUSDT (2021-2023): 22 orders (16 filled, 6 margin rejected), 16 trades (8 win, 8 loss, win rate 50.00%), fees -162.82 USDT, funding -225.89 USDT, net PnL +2,100.96 USDT, final equity 12,100.96 USDT (+21.01%), Max Drawdown -16.15%. Chính thức bác bỏ và tuyên bố vô hiệu số liệu dự thảo không đồng bộ (48 orders, 24 trades, fees 82.49, funding -22.56) (Tham chiếu: ADR 0009).
24. **Hoàn thiện Giai đoạn 6 bởi Codex tại Commit A2 `99d4b4063c798cf3a89d610e4bd64a19f3395659`:**
    - `risk_ratio_percent` phản ánh stop risk thực tế trên entry equity; lưu order type và liquidation estimate tại thời điểm vào lệnh.
    - Canonical payload hash giữ nguyên độ chính xác float; truy vấn trade/order/funding có tie-breaker ID deterministic; SQLite connection được đóng rõ ràng để hỗ trợ atomic replace trên Windows.
    - Snapshot finalize chứa đúng phí/slippage force-close và không nhân đôi khi gọi finalize lại. Circuit Breaker đếm transition khóa thật.
    - Metrics bổ sung loss rate, average realized RRR, benchmark classification 35–45%, candle-gap measurement và accounting reconciliation fail-closed ở tolerance `1e-4`.
    - Sáu artifact được ghi atomically; canonical config/hash dùng chung giữa CLI, report và SQLite; reproduction command phản ánh config thực tế và không chứa absolute machine path.
    - Funding adapter từ chối payload thiếu rate thay vì tự tổng hợp `0.0`.
    - Xác minh trên Commit A2: offline `276 passed, 2 skipped, 5 deselected`; network `5 passed, 278 deselected`; historical probes `40 passed`. Regression tests kiểm tra custom config, cross-root hash/run ID, phí taker, benchmark annotation, summary fields và CWD ngoài project. Benchmark 3 năm chưa chạy lại: `AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED`.

---

## 3. (Historical inventory; test counts below are old snapshots) BẢN ĐỒ CÁC FILE QUAN TRỌNG VAI TRÒ

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
| `src/strategies/base_strategy.py` | Lớp cơ sở trừu tượng cho các chiến lược định lượng (`on_candle_close`, `update_trailing_stop`). |
| `src/strategies/trend_following.py` | Chiến lược Trend Following 4h: EMA20/50 crossover, pullback retest, EMA200 regime, RSI, swing SL, trailing. |
| `src/strategies/__init__.py` | Export `BaseStrategy`, `TrendFollowingStrategy`, `SetupState`. |
| `src/backtest/engine.py` | Cỗ máy BacktestEngine tối thiểu, điều phối sự kiện đa khung 4h/15m, chống nhìn trước. |
| `src/backtest/__init__.py` | Export `BacktestEngine`. |
| `run_backtest.py` | CLI entrypoint thực thi backtest (--config, --strategy, --start, --end, --no-fetch). |
| `scripts/download_benchmark_data.py` | Tải dữ liệu 3 năm BTCUSDT (4h, 15m, funding, OI) từ Binance lưu cache parquet. |
| `scripts/fetch_market_data.py` | Tải nến OHLCV 15m và Funding Rate 8h từ Binance Futures REST API lưu vào cache parquet. |
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
| `tests/test_stage_04_review_06_coverage.py` | 11 unit tests độc lập bao phủ các trường hợp biên H1-H6 theo yêu cầu Review 06. |
| `tests/test_stage_04_review_07_coverage.py` | 16 unit tests độc lập bao phủ các trường hợp biên J1-J3 và K1 theo yêu cầu Review 07/08/09. |
| `tests/test_trend_following_strategy.py` | 23 unit tests bao phủ các quy tắc Trend Following (crossover, pullback, expiry, invalidation, RSI, OI, swing SL, trailing). |
| `tests/test_backtest_engine.py` | 15 unit/integration tests bao phủ BacktestEngine (multi-timeframe sync, future perturbation, next-open fill, funding fail-closed, determinism, CLI, hermetic CWD isolation). |
| `src/logging/trade_logger.py` | Kho lưu trữ sự kiện SQLite Event Store, giao dịch nguyên tử, idempotency và xuất JSON Section 4.6. |
| `src/logging/__init__.py` | Export `TradeLogger`. |
| `src/report/metrics.py` | Động cơ tính toán chỉ số hiệu năng chuẩn hoá (Expectancy USD/R, Profit Factor, Max DD, Daily Sharpe sqrt(365)). |
| `src/report/generator.py` | Bộ sinh báo cáo đa định dạng tự động tạo 6 artifacts trong `reports/<run_id>/`. |
| `src/report/__init__.py` | Export `ReportGenerator` và các hàm tính toán metrics. |
| `tests/test_trade_logger.py` | 12 unit tests: Master Spec 4.6 verbatim schema, composite PKs, foreign keys, transaction rollback, idempotency payload hash, conflict rejection, rejection reasons, snapshot mapping, funding event identity, multi-run deterministic ID collision, nested production config. |
| `tests/test_report_metrics.py` | 7 unit tests: Expectancy USD/R, Profit Factor edge cases (loss=0 -> null), Max DD peak-to-valley, Sharpe 1D UTC, reconciliation, NaN/Inf/bool fail-closed, CB metrics separation. |
| `tests/test_report_generator.py` | 4 unit tests: Sinh đủ 6 artifacts, custom output dir & db path, fail-closed sanitize NaN/Inf, deterministic JSON output. |
| `tests/test_stage_06_integration.py` | 6 integration tests: CLI end-to-end hermetic, cờ --no-report, Zero Semantic Drift, deterministic run_id, CWD independence, future perturbation report invariance. |
| `docs/decisions/` | Thư mục lưu trữ các Architecture Decision Records (ADR 0001 → 0009). |
| `docs/decisions/0009-trade-logging-and-performance-reporting.md` | ADR 0009: Kiến trúc Trade Logger & Performance Reporting (Hoàn thiện theo GPT Review 11). |
| `docs/reviews/GPT_STAGE_04_REVIEW_09.md` | Kết luận nghiệm thu chính thức Giai đoạn 4 tại commit `b16fa1e0...`. |
| `docs/planning/ANTIGRAVITY_STAGE_05_TASK.md` | Nhiệm vụ có thẩm quyền duy nhất cho triển khai Giai đoạn 5; cấm tự chạy sang Giai đoạn 6+. |
| `BÁO CÁO TÓM TẮT/` | Thư mục chứa báo cáo tổng hợp và code backup theo từng giai đoạn (Giai đoạn 0 → 6). |


---

## 4. CÁC VẤN ĐỀ ĐÃ BIẾT NHƯNG CỐ Ý ĐỂ LẠI (KNOWN LIMITATIONS)

1. **Giới hạn Binance REST API cho OI:** Endpoint `/fapi/v1/openInterestHist` chỉ trả về tối đa 30 ngày. Đã giải quyết bằng cơ chế Hybrid kết hợp Binance Data Vision cho dữ liệu sâu.
2. **Warm-up Period 199 nến đầu của EMA 200 là NaN:** Đây là tính chất toán học chuẩn mực của TA-Lib (`presma=True`), không phải bug. Các chiến lược khi chạy backtest sẽ bắt đầu quét lệnh sau khi đã đủ 200 nến.
3. **CVD Flatline khi thiếu Taker Buy Volume:** Nếu klines API không có cột `taker_buy_base_volume` (hoặc có giá trị `NaN`), hệ thống ước tính bằng 50% volume $\to \text{delta} = 0$, khiến đường CVD đi ngang (flatline) thay vì ném ngoại lệ làm crash engine. Đã thêm log cảnh báo chi tiết trong `cvd.py`. **LƯU Ý NGHIỆP VỤ:** Nếu sau này thấy `cvd_divergence` có vẻ bất thường ở một giai đoạn cụ thể, đây là nghi phạm đầu tiên cần kiểm tra xem dữ liệu sàn trong giai đoạn đó có bị khuyết taker buy volume hay không.

## Historical Stage 7–11 implementation checkpoint before repair

**SUPERSEDED:** bằng chứng dưới đây thuộc implementation trước findings; không mô tả code A mới. Kết quả suite cũ không được dùng làm kết quả A.

- Stage 7: `BreakoutRetestStrategy` added with causal prior-range breakout, delayed retest, volume filters, timeout/invalidation, LONG/SHORT symmetry and configurable RRR. CLI supports `breakout_retest`.
- Stage 8: `FundingArbitrageSimulator` added with explicit `spot_close`, `perp_close`, and `funding_rate` inputs, separate leg PnL, fees, funding cashflow and two-negative-cycle exit. Standalone config added. Main multi-timeframe runner remains NOT_VERIFIED for this strategy.
- Stage 9: causal SMC features and `SMCLiquiditySweepStrategy` added. Confirmed swings are delayed by `swing_n`; sweep/FVG entries emit partial-exit metadata. CLI supports `smc_liquidity_sweep`. Full 1m/5m execution and order-block confluence are NOT_VERIFIED.
- Stage 10: deterministic `walk_forward_splits` and `compare_metrics` utilities added. No performance claim is made; AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED.
- Stage 11: paper-only `RiskAwareTradingEnv` added with reward `net change - 0.5*drawdown - 1.0*violation`. PPO training is BLOCKED/NOT_VERIFIED unless `stable-baselines3` and a reviewed Gymnasium adapter are installed.

Validation in this environment: `python -m compileall -q src run_backtest.py tests` passed. `pytest` could not run because the active Python environment has no pytest module. No live/testnet execution or API keys were used.
