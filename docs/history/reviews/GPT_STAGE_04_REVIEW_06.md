# GPT Review 06 — Giai đoạn 4 chưa đạt nghiệm thu

## 1. Kết luận

**CHƯA NGHIỆM THU GIAI ĐOẠN 4. KHÔNG BẮT ĐẦU GIAI ĐOẠN 5.**

Antigravity đã sửa được toàn bộ 26 tình huống tái hiện trực tiếp của Review 05 và không làm hỏng bộ test hiện có. Tuy nhiên, kiểm tra độc lập sâu hơn cho thấy một số tiêu chí đã ghi rõ trong task Giai đoạn 4 và Review 05 vẫn chưa được hoàn tất. Đây không phải yêu cầu mở rộng mới.

- Repository: `Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING`, nhánh `main`.
- Commit code được review: `60f693016160f6c44bd7e9ff3569540324708bfc`.
- Commit tác giả khai báo: `fix(execution): Resolve E1-E8 Review 05 findings for Paper Execution Engine`.
- Chuẩn đối chiếu: `docs/planning/ANTIGRAVITY_STAGE_04_TASK.md` và `docs/reviews/GPT_STAGE_04_REVIEW_05.md`.
- Reviewer không sửa source triển khai; chỉ thêm báo cáo và probe độc lập.

## 2. Bằng chứng thực thi độc lập

```text
python -m pytest -m 'not network' -q
168 passed, 2 skipped, 5 deselected in 1.47s

python -m pytest docs/reviews/test_stage_04_review_05.py -q --tb=short
26 passed in 0.52s

python -m pytest docs/reviews/test_stage_04_review_06.py -q --tb=short
11 collected: 10 failed, 1 passed in 0.48s

python scripts/simulate_paper_execution.py
Phần A: exit code 0; wallet cuối 9.440,94 USD; 8 trades; flat; đối soát nội bộ đạt.
Phần B: SKIPPED / NOT_VERIFIED vì thiếu cache; exit code 0.
```

Hai skip offline là do môi trường reviewer không có `pandas-ta`; năm network tests được deselect và chưa được reviewer xác minh. Vì vậy dòng “175/175 tests PASSED” trong tài liệu tác giả là kết quả tác giả báo cáo, không phải kết quả reviewer xác minh trong môi trường này.

Bộ probe Review 06 được lưu tại `docs/reviews/test_stage_04_review_06.py`. Nó cố ý nằm ngoài `testpaths=tests` mặc định và phải được chạy tường minh.

## 3. Bảng phát hiện

| Mã | Ưu tiên | Phát hiện còn lại | Bằng chứng |
|---|---|---|---|
| H1 | P1 | Ledger daily loss chưa ghi entry fee đúng thời điểm và cộng trùng funding khi trade đóng | 3 probes failed; demo lệch khoảng đúng một funding event |
| H2 | P1 | Liquidation collateral-aware chọn tier bằng entry notional và âm thầm fallback tier hard-code | 2 probes failed |
| H3 | P1 | Đồng hồ toàn cục chặn hai symbol có cùng timestamp, nên chưa xử lý được danh mục multi-symbol | 2 probes failed |
| H4 | P1 | Một số public operation/config validation chưa transactional hoặc fail-closed | 2 failed, 1 control passed |
| H5 | P1 | Chưa có lifecycle `finalize/end-of-data` và chặn callback/entry sau kết thúc | 1 probe failed |
| H6 | P2 | Funding source-time và hồ sơ tái hiện/demo vẫn thiếu; tài liệu có file/lệnh không tồn tại | code/docs inspection |

## 4. Chi tiết và yêu cầu sửa

### H1 — Cashflow ledger phải ghi đúng một lần, đúng timestamp

Review 05 E3 đã yêu cầu: entry fee, funding, realized price PnL và exit fee đi vào rolling cashflow ngay khi phát sinh; kết quả trade đã đóng chỉ cập nhật streak, không cộng lại `trade_net_pnl`.

Hiện tại:

- Lúc entry, broker trừ entry fee khỏi wallet nhưng không gọi `record_cashflow`.
- Funding được gọi `record_cashflow` ngay, nhưng khi đóng lệnh `_execute_exit` vẫn gọi `record_trade_result(net_trade_pnl)`. Vì `net_trade_pnl` đã chứa entry fee, exit fee và cumulative funding, các thành phần đã ghi trước sẽ bị cộng lại.
- Demo tự chứng minh sai lệch: tại lúc lock, wallet từ 10.000 còn 9.312,91 (delta -687,09), nhưng rolling loss log là -687,59; chênh khoảng -0,498 đúng bằng funding đã bị tính lại trong net trade.

**Sửa bắt buộc:**

1. Entry fill: ghi `-entry_fee` vào cashflow ledger ngay sau khi fill được commit.
2. Funding: ghi signed funding đúng một lần tại settlement.
3. Close: ghi `gross_realized_price_pnl` và `-exit_fee` đúng timestamp; sau đó chỉ gọi `record_trade_outcome(net_trade_pnl, timestamp)` cho streak.
4. Forced close do breaker vẫn phải ghi cashflows thật, nhưng không được đệ quy/double close hoặc kéo dài lock.
5. Bổ sung đối soát độc lập giữa wallet delta và tổng cashflow ledger theo cửa sổ thời gian.

**Đạt khi:** ba probe H1 pass; test thêm LONG/SHORT fee/funding/close, rolling cutoff và breaker kích hoạt chỉ từ entry fee mà streak vẫn không tăng.

### H2 — Solver liquidation phải nhất quán theo tier tại nghiệm

Review 05 E2 yêu cầu solver collateral-aware vẫn giữ quy tắc Giai đoạn 3: tier được chọn theo `quantity × liquidation_price`, không theo `quantity × entry_price`.

Hiện tại `_calculate_collateral_aware_liquidation_price`:

- Tra `get_mmr_tier()` bằng entry notional.
- `except Exception` rồi âm thầm dùng `mmr=0.004, cum=0.0`, trái với nguyên tắc fail-closed/no-last-tier-fallback.

Probe q=600, entry=100 sau funding có nghiệm nằm dưới ngưỡng 50.000 USDT. Giá đúng theo tier 1 là khoảng `50.3012048193`, broker trả `50.2680067002` do lấy tier từ entry notional 60.000.

**Sửa bắt buộc:** tái sử dụng hoặc mở rộng solver tier-consistent đã nghiệm thu ở Giai đoạn 3 với collateral thực tế; xác minh phương trình độc lập; bracket sai/không có nghiệm phải lỗi tường minh trước mutation, không fallback hard-code.

### H3 — Event clock phải hỗ trợ multi-symbol cùng biên thời gian

Task gốc cho phép tối đa một vị thế trên mỗi symbol, không phải một symbol cho toàn broker. Review 05 E4 cũng yêu cầu test multi-position price snapshot và timestamp cùng biên.

Hiện tại `last_candle_open_time` là một timestamp toàn cục và từ chối mọi `open_time <= last_candle_open_time`. Do đó, BTC 07:58 được xử lý xong thì ETH 07:58 bị xem là duplicate/time reversal. Hệ quả: không thể mở/fund/mark nhiều symbol tại cùng market timestamp.

**Sửa bắt buộc:** thiết kế clock theo event batch hoặc per-symbol sequence kết hợp một global watermark rõ ràng. Cho phép mỗi symbol xuất hiện đúng một lần tại cùng timestamp; vẫn từ chối duplicate của chính symbol và time reversal thật. Equity/admission tại cùng biên phải dùng snapshot giá có `as-of` rõ ràng, không phụ thuộc thứ tự symbol.

### H4 — Transactional public paths và config fail-closed

- `close_all_positions` bắt đầu đóng/xóa position và thêm trade trước khi breaker phát hiện timestamp lùi; sau exception, state đã bị partial mutation.
- `_validate_config` chỉ validate `funding_rate` nếu nó là dict; nếu người dùng cung cấp `funding_rate: "bad"`, constructor âm thầm bỏ qua và dùng mặc định.
- Control probe request pending bị mutate sau submit hiện được từ chối sạch; phần này đạt và phải giữ nguyên.

**Sửa bắt buộc:** prevalidate toàn bộ price, timestamp, reason và dữ liệu cho tất cả symbol trước lần mutation đầu tiên trong `close_all_positions`; malformed subconfig được cung cấp phải bị reject, default chỉ áp dụng khi section/key thực sự vắng mặt.

### H5 — Lifecycle kết thúc dữ liệu chưa tồn tại

Review 05 E7 và task gốc yêu cầu API finish/finalize:

- Mặc định cuối dataset giữ position mở và báo cash/unrealized/open positions.
- Force mode phải đóng với phí/slippage và reason `END_OF_DATA`.
- Sau finalize không nhận callback/nến/signal/entry mới.

Hiện `PaperBroker` không có `finalize`; vì vậy không có trạng thái terminal để ngăn thao tác sau kết thúc.

**Sửa bắt buộc:** thêm lifecycle public có semantics trên, idempotent, transactional và có tests cho default-open, force-close, gọi lại finalize và future submit/process rejection.

### H6 — Funding provenance và hồ sơ tái hiện

Các mục Review 05 chưa có bằng chứng hoàn tất:

1. Input funding vẫn chỉ có giá trị `funding_rate`, chưa có timestamp/source-time/readiness; chưa thể chặn rate đến từ tương lai hoặc quá cũ theo policy đã giao.
2. `walkthrough.md` tác giả nói đã cập nhật nhưng không tồn tại trong cây GitHub tại commit review.
3. Demo hướng dẫn `python scripts/fetch_market_data.py`, nhưng file này không tồn tại trong repository.
4. Real-cache demo vẫn `SKIPPED / NOT_VERIFIED`; báo cáo lại ghi chạy thông suốt trên 100 nến thật. Phải phân biệt kết quả tác giả từng chạy với artifact hiện có thể tái hiện.
5. `PROJECT_STATE.md` checklist nhảy từ Giai đoạn 2 sang Giai đoạn 4, làm mất dòng Giai đoạn 3 đã nghiệm thu.

**Sửa bắt buộc:** bổ sung contract source-time/readiness và tests future/stale/zero/missing; cung cấp đúng script/lệnh có thật hoặc sửa hướng dẫn; commit walkthrough nếu nó là deliverable; khôi phục dòng trạng thái Giai đoạn 3; không gọi real-data verified khi reviewer không thể tái hiện từ hướng dẫn trong repo.

## 5. Tiêu chí nghiệm thu Review 07

Antigravity phải:

1. Không sửa/xóa/né assertion trong `test_stage_04_review_05.py` và `test_stage_04_review_06.py`. Nếu bất đồng contract, dừng và nêu bằng chứng trước khi đổi test.
2. Làm 26/26 Review 05 tiếp tục pass và 11/11 Review 06 pass.
3. Thêm coverage còn thiếu nêu trong H1–H6, đặc biệt funding source-time, per-symbol duplicate, batch order-independence, finalize và transactional close-all.
4. Chạy bộ offline mặc định, hai bộ probes tường minh, demo synthetic và real-cache nếu có dữ liệu. Báo riêng pass/skip/deselected/network-not-run.
5. Không tuyên bố “175/175 reviewer verified” nếu môi trường reviewer chưa chạy năm test network và hai test optional đang skip.
6. Cập nhật ADR 0007, báo cáo sửa Review 06, PROJECT_STATE, CHANGELOG và PLANNER_HANDOVER. Không xóa lịch sử báo cáo cũ; ghi rõ Review 06 chưa đạt cho đến khi GPT Review 07 kết luận.
7. Commit/push `main`, trả full SHA và dừng. **Không bắt đầu Giai đoạn 5.**

## 6. Prompt thi công ngắn cho Antigravity

Đọc lần lượt `PLANNER_HANDOVER.md`, `crypto-paper-agent/docs/planning/ANTIGRAVITY_STAGE_04_TASK.md`, `crypto-paper-agent/docs/reviews/GPT_STAGE_04_REVIEW_05.md` và `crypto-paper-agent/docs/reviews/GPT_STAGE_04_REVIEW_06.md`. Sửa đúng H1–H6 và tiêu chí Review 07; không thay probes để che lỗi; không mở rộng sang strategy/live trading. Chạy đầy đủ lệnh test được nêu, cập nhật hồ sơ, commit/push `main`, báo full SHA rồi dừng chờ GPT Review 07. Không bắt đầu Giai đoạn 5.
