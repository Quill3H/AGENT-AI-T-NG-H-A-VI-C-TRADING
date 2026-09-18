# GPT Review 05 — Giai đoạn 4 chưa đạt nghiệm thu

## 1. Kết luận và phạm vi

**CHƯA NGHIỆM THU GIAI ĐOẠN 4.** Không bắt đầu Giai đoạn 5. Có nền tảng hoạt động và oracle kế toán đúng, nhưng các đường funding, breaker, admission và validation chưa đáp ứng task đã giao.

- Repository: Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING, main.
- Commit code được review: `e4cb87b975d3404fbe73b31281d1d9697522cce0`.
- Tài liệu chuẩn nghiệm thu: `docs/planning/ANTIGRAVITY_STAGE_04_TASK.md`.
- Reviewer đọc các file đổi tại commit, models/broker/tests/demo, ADR 0007, báo cáo tác giả và hồ sơ trạng thái. Không sửa source triển khai.
- Môi trường độc lập: Linux/Python 3.12.14/pytest 9.1.1, pandas-ta chưa có.
- Tám nhóm E1–E8 dưới đây là **lỗi và thiếu sót theo yêu cầu Giai đoạn 4 đã giao**, không phải yêu cầu thêm strategy hoặc live trading.

## 2. Bằng chứng thực thi

```text
python -m pytest -m 'not network' -q
168 passed, 2 skipped, 5 deselected in 1.57s

python -m pytest docs/reviews/test_stage_04_review_05.py -q --tb=no
26 collected
24 failed, 2 passed in 0.51s

python scripts/simulate_paper_execution.py
Phần A: wallet cuối 9.440,94 USD, 8 trade, flat; đối soát đạt.
Phần B: LỖI Không tìm thấy cache .../15m/ohlcv.parquet
Script vẫn exit code 0.
```

Hai skip là kiểm tra phụ thuộc pandas-ta; năm network tests không được reviewer chạy lại. Tác giả báo 170 offline + 5 network =175 pass trên máy riêng: **không phải** kết quả 175 bài reviewer xác minh.

Oracle LONG hiện có đạt 10.038,88 USD, nhưng chỉ chứng minh đường đi cụ thể; không chứng minh các nhánh an toàn còn lại. Bộ mới của tác giả gồm 17 test, chưa đủ phủ các mục bắt buộc trong task.

Bộ tái hiện độc lập được lưu tại `docs/reviews/test_stage_04_review_05.py`, chạy tường minh bằng lệnh trên từ PROJECT_ROOT. Nó nằm ngoài pytest testpaths mặc định; các failure được cố ý giữ để thể hiện lỗi code hiện tại, không che chúng bằng cách chỉ chạy tests/.

## 3. Bảng phát hiện

| Mã | Ưu tiên | Vấn đề chính | Kiểm thử tái hiện |
|---|---|---|---|
| E1 | P1 | Funding thiếu/NaN bị bỏ qua, không đọc settlement hours config, khoảng thiếu nến đi qua settlement không bị chặn | 4 failed |
| E2 | P1 | Funding thay đổi collateral nhưng liquidation_price vẫn cố định | 1 failed |
| E3 | P1 | Daily loss bỏ qua fee/funding khi trade còn mở; lock không cưỡng chế đóng vị thế khác | 2 failed |
| E4 | P1 | Breaker nhận equity còn cộng unrealized của vị thế vừa đóng | 1 failed |
| E5 | P1 | Helper lỗi làm pending kẹt/crash; TP sai phía actual fill vẫn mở; loại lệnh/risk khai báo bị bỏ qua | 4 failed |
| E6 | P1 | Timestamp/duration lỗi được phát hiện sau mutation, hoặc được chấp nhận/fallback âm thầm | 4 failed |
| E7 | P2 | Các đường exit/SL update chưa giữ hợp đồng thực thi nhất quán | 3 failed |
| E8 | P1 | Broker nhận cấu hình số không hữu hạn, balance âm và slippage ngoài miền | 5 failed |

P1 phải sửa trước nghiệm thu. P2 cũng thuộc yêu cầu task đã giao, phải hoàn thiện trong đợt sửa này. Hai control pass xác nhận TP accounting cơ bản và từ chối nới SL đang hoạt động.

## 4. Yêu cầu sửa chi tiết

### E1 — Funding readiness, schedule và thời gian

**Code:** PaperBroker.__init__, process_candle pha 2.
- `funding_hours or {0,8,16}` không đọc `config.funding_rate.settlement_hours_utc`, còn biến explicit empty set thành lịch mặc định.
- Funding None/NaN tại kỳ cần thanh toán bị bỏ qua, broker vẫn tiến đồng hồ/snapshot. Không phân biệt “không có phí” với “không có dữ liệu”.
- Từ open 07:59 → 08:01, bỏ mất settlement 08:00 mà không báo lỗi.
- Điều kiện hour/minute không kiểm tra second/microsecond; chưa có khóa settlement event để bảo đảm exactly-once.
- Contract input hiện chưa chứa thời điểm rate available/source nên không kiểm soát stale/future rate như task yêu cầu.

**Sửa:** xác thực funding inputs và các settlement bắt buộc trước mutation; đọc schedule config và precedence override rõ ràng; kiểm tra độ mới/thời điểm source, finite không nhận bool; không backfill tương lai. Khoảng dữ liệu thiếu đi qua settlement phải lỗi tường minh nếu không có dữ liệu settlement độc lập hợp lệ. Rate 0 hợp lệ phải khác rate thiếu. Có khóa idempotency theo symbol/position/settlement và test duplicate.

**Đạt khi:** bốn tái hiện E1 đạt và bổ sung test exactly-once, source stale/future, seconds, rate +/-/0 cho hai chiều. Không tự đặt missing=0 để qua test.

### E2 — Solver thanh lý phản ánh collateral thực tế

**Code:** _apply_funding_settlement chỉ đổi wallet/collateral/cumulative_funding, không cập nhật liquidation_price.

**Tái hiện:** LONG q=10, entry100, margin500; funding -.01×10×100 = -10, collateral490. Tier đầu mmr=.004, cum=0:
```text
P đúng = (q×entry - collateral)/(q×(1-mmr)) = 51,2048192771
P broker giữ = 50,2008032129
```

**Sửa:** helper collateral-aware, solver nhất quán tier tại q×P, phương trình margin độc lập; giữ public API và tests Giai đoạn 3. Recalculate sau funding/collateral change, xử lý ngay insufficient collateral/không có nghiệm hợp lệ theo dữ liệu hiện tại; không giữ giá cũ khi helper lỗi. Kiểm thử cả funding debit/credit LONG/SHORT, tier boundaries, collateral cạn.

### E3 — Daily cashflows, trade outcomes và đóng toàn bộ

**Code:** chỉ gọi record_trade_result(net_trade_pnl) lúc exit; entry fee/funding không ghi rolling loss ngay. _execute_exit khi lock chỉ cancel pending, không đóng các position khác. close_all_positions có nhưng không được trigger tự động.

**Tái hiện A:** q100 entry100, funding +.06 => LONG trả600 USD, wallet9.395 USD sau entry fee. Vượt ngưỡng 5% equity nhưng breaker vẫn unlocked, vị thế vẫn mở. Rate fixture là stress test thuật toán, không phải dự báo/rate Binance thực tế.

**Tái hiện B:** mở ETH q50 và BTC q49 tại các nến tuần tự không trùng funding; BTC SL90 gây net -494,655 USD, breaker lock với ngưỡng khoảng475,142 USD, **ETH vẫn OPEN**.

**Sửa:** tách cashflow ledger có timestamp khỏi completed-trade net outcome/streak như task gốc; entry fee/funding/realized price PnL cập nhật rolling ngay và đúng một lần. Outcome khi close chỉ cập nhật streak, không cộng net trade lần nữa vào cashflow ledger. API record_trade_result cũ vẫn giữ tương thích.

Khi daily guard kích hoạt: cưỡng chế đóng mọi vị thế còn mở, cancel pending, giữ locked_until không kéo dài. Dùng price khả dụng riêng từng symbol/pha, không lấy cùng một current_price cho các tài sản giá khác nhau; nếu thiếu price phải báo dữ liệu thiếu, không bịa giá. Không cho guard gọi đệ quy dẫn tới double close.

**Đạt khi:** E3 probes pass; thêm tests fee/funding không đếm như một trade thua, close không doublecount cashflows, losses hai bên rolling cutoff, expiry/relock, lock không kéo dài khi forced exits. Streak after_3_wins không đổi.

### E4 — Equity đúng pha và hậu tất toán

**Code:** _execute_exit cộng realized PnL vào wallet, gọi breaker với self.equity **trước khi xóa position**. _last_unrealized_pnl còn giữ mark close nến trước. Admission pha open cũng chưa cập nhật mark của vị thế khác sang price khả dụng tại open.

**Tái hiện:** q100 entry100; close nến trước101 => UPNL+100. Exit SL98: wallet flat9.790,10 USD; breaker được truyền **9.890,10 USD**. Threshold và halted có thể sai vì vốn bị cộng lãi/lỗ cũ.

**Sửa:** settle/remove position và cập nhật mark snapshot đúng pha trước tính equity/guard; không doublecount realized+unrealized của cùng vị thế. Broker multi-symbol phải có contract mark/as-of và batch/time handling rõ ràng; không mark current close tương lai trước admission, không giả định equity dùng stale mark là “vốn hiện tại”.

**Đạt khi:** spy capture đúng post-close equity, thêm stale UPNL dương/âm, actual next-open thay đổi, multi-position price snapshot và timestamp cùng biên. Không sửa threshold sang initial balance.

### E5 — Admission và vòng đời lệnh

**Code:** pending bị remove trước sizing/liquidation helpers; ValueError không chuyển thành rejection. Gate không nhận TP/order_type/risk_percent do request khai nên các field đó bị bỏ qua.

**Tái hiện:**
- Signal100/SL98, next-open98 => sizing ném ValueError; order record còn PENDING nhưng không còn trong queue.
- Signal100/TP104, next-open105 với q1 vẫn được FILLED rồi TP104 như một exit lỗ thay vì reject TP sai phía.
- OrderType.STOP_MARKET gửi vào entry queue vẫn khớp như MARKET_ENTRY.
- risk_percent=.0001, base=.002, q10: risk khai1 USD nhưng broker tự thay bằng20 USD mà không báo mismatch.

**Sửa:** validation/preflight tại actual fill; SL/TP direction; chỉ loại entry hỗ trợ được nhận. Risk authority rõ ràng: request risk_percent nếu supplied phải khớp giá trị derived hoặc bị reject, không âm thầm bỏ qua; không nhân multiplier hai lần. Bắt lỗi sizing/solver được dự kiến và chuyển REJECTED với reason, không swallowing programming errors. Lifecycle terminal, ID lookup ổn định; không remove rồi để record pending kẹt. Revalidate request ở broker vì dataclass mutable; giữ quantity/risk audit đầy đủ.

**Đạt khi:** bốn probes E5 pass; thêm cap/bracket lỗi, leverage/margin, pending future/current time, cancel/reject không charge, không có đường bỏ gate.

### E6 — Preflight thời gian và transactional state

**Code:** last_candle_open_time được mutate trước parse timeframe và close_time; current_time/entry/fee mutate trước xác nhận close_time không lùi. Parse duration nhận0m, -1m và trả mặc định1m cho string không hỗ trợ.

**Tái hiện:** nến close_time=open-1s vẫn fill q10 và charge fee trước khi advance_time phát hiện lỗi.0m được nhận; -1m bị lỗi sau financial mutation; “nonsense” được mặc định1m.

**Sửa:** kiểm tra timeframe enum/parser hữu hạn duration>0; close_time > open và khớp timeframe; candle không overlap với phần thời gian đã xử lý; duplicates và timestamp lùi được từ chối trước mutation. Preflight bao gồm funding/required-price dữ liệu trước event commits; validation failure giữ nguyên wallet/positions/queue/ledger/clock và ID counters. Không cần rollback hợp lệ cho một order rejection, nhưng malformed candle/invalid API inputs phải không partial-commit.

**Đạt khi:** E6 pass; bổ sung tests overlap, duplicate valid candle, bad close_time type và parse failure, duplicate zero-duration không double funding vì phải reject0m trước.

### E7 — Exit, stop update và trạng thái kết thúc

**Tái hiện:**
- close_all_positions(current_price100) LONG với slippage .0003 exit100 thay vì99,97.
- update_stop_loss LONG mark100 SL98 chấp nhận newSL110, dù stop đã vượt mark hiện tại.
- Gap next-open105 qua TP104 ngay08:00: broker charge funding rồi mới TP ở close08:01; phải thoát pha open trước funding theo thứ tự task.

**Code inspection bổ sung:** liquidation exits bỏ slippage; _execute_exit không chuyển Position.status/closed_at/exit_price/exit_reason; close_all_positions không prevalidate price/time, dùng cùng một price cho mọi symbol; không có finalized/end-of-data guard ngăn nhận signal sau force-finalize.

**Sửa:** tập trung fill exit qua side-aware fee/slippage contract, cả force-close/liquidation; TP gap reference target bảo thủ ở pha open. Mark-aware tightening update SL có effective_time ở biên tiếp theo, không thay quá khứ. Set terminal fields và event copies/snapshots để history không bị sửa ngược. Có finish/finalize API default giữ vị thế mở; force mode explícit END_OF_DATA, không mở entry sau finish. Có cancel public API/terminal reasons cho pending. Prevalidate timestamp và prices trước close mutation.

**Đạt khi:** ba probes E7 và tests status, finalize open/force, future submit rejected, stop effective_time, liquidation slippage, price-per-symbol pass.

### E8 — Cấu hình engine và kiểm tra finite

**Code:** config.initial_equity, fees.slippage/taker/maker cast float trực tiếp, chưa validate domain. Constructor nhận balance NaN/âm khi lấy từ config; slippage NaN/âm/>1.

**Sửa:** validate config shape và domain trước tạo state: balance finite>0, fee finite>=0 với upper bound mô hình được ghi ADR, slippage finite0<=s<1 (không nhận bool), hours integers0–23, timeframe hợp lệ; không default khi giá trị sai được cung cấp. Default chỉ khi bỏ trống có chủ đích. Verify_accounting_invariants phải kiểm tra finite trước so sánh — abs(NaN)>tol không phát hiện lỗi. Expected balances lấy ledger độc lập, không chỉ kiểm tra equality giữa property và công thức giống hệt property.

**Đạt khi:** năm probes E8 và tests bool/Inf/malformed subconfig, finite snapshots/collateral/ledger, equality tolerance rõ ràng.

## 5. Tài liệu, demo và các phần còn thiếu bằng chứng

Không được tiếp tục dùng các khẳng định “100% mục tiêu”, “chính xác từng bit”, “chạm5% lập tức đóng toàn bộ” khi code chưa thực hiện các đường trên.
- Label báo cáo/HANDOVER rõ “tác giả báo cáo175 pass”, không phải verified reviewer.
- Oracle test ghi300 nến nhưng thân test chỉ xử lý khoảng62 nến. Thực sự chạy đủ vài trăm nến như task và báo số đã xử lý.
- README không đổi tại commit; chưa có walkthrough.md trong danh sách file commit này. Nếu walkthrough là artifact riêng trên máy, nói rõ không nằm trên GitHub; không cần copy project để bù.
- Demo thật không tái hiện được ở reviewer vì cache không nằm repo; đây là **chưa xác minh**, không tự kết luận dữ liệu tác giả là giả. Cho phép cache không commit nặng, nhưng phải có CLI cache-path/source/range, metadata/hash nhỏ và hướng dẫn public fetch an toàn để tái hiện.
- Demo hiện tạo signal từ open chính nến fill. Với manual fixtures, điều này không chứng minh strategy lookahead, nhưng không minh họa pipeline signal_on_close đã yêu cầu. Tạo planned/manual request sau previous closed candle bằng previous close, thực thi next open và log hai thời điểm.
- Cache thiếu: report SKIPPED/NOT_VERIFIED và CLI result mode rõ ràng, không exit0 thành “toàn bộ demo đạt”.
- Demo synthetic đang nhảy25h. Sau khi E1 sửa, phải cung cấp chuỗi nến/settlement hợp lệ cho vị thế tồn tại hoặc dùng explicit clock advancement khi flat; không bypass validation để giữ demo cũ.

## 6. Prompt thi công cho Antigravity

Được phép **sửa trong phạm vi Giai đoạn 4**, chưa nghiệm thu, chưa Giai đoạn5.

1. Đồng bộ main an toàn, đọc PLANNER_HANDOVER, task gốc và toàn bộ Review05 này.
2. Tái hiện commit e4cb87b bằng bộ probes, đọc nguyên nhân từng fail. Không sửa assertion/cắt test để che lỗi; nếu bất đồng test contract, đưa bằng chứng và giải thích trước khi thay.
3. Sửa theo dependency: E8/E6 preflight → E5 admission → E4 snapshot → E1/E2 funding/solver → E3 rolling guard → E7 lifecycle/exit/finalize, rồi hoàn thiện demo/tài liệu.
4. Có thể thêm adapter/API risk tối thiểu như task cho phép, nhưng API hiện có và tests Giai đoạn3 phải giữ semantics. Không nới leverage/buffer/risk, không missing funding=0.
5. Chạy bộ repo offline, bộ probes explicit, thêm coverage bắt buộc chưa có. Probes bổ sung chỉ là mức tối thiểu, không thay 14 nhóm test trong task gốc.
6. Chạy demo synthetic và real-cache với nguồn/timestamp/cấu hình tường minh; ledger oracle độc lập và reconciliation sau từng event.
7. Cập nhật ADR0007 phụ lục, PROJECT_STATE/CHANGELOG/README, báo cáo sửa `BÁO CÁO TÓM TẮT/GIAI ĐOẠN 4/BAO_CAO_SUA_DOI_THEO_GPT_REVIEW_05.md` và PLANNER_HANDOVER. State phải ghi **đã sửa, chờ review**, không tự “nghiệm thu”.
8. Commit/push, trả fullSHA, raw pass/fail/skip/deselected/network status, mapping E1–E8 và known limitations.
9. **DỪNG CHỜ GPT REVIEW06. KHÔNG GIAI ĐOẠN5.**

Nếu thiếu giá/dữ liệu hoặc gặp mâu thuẫn API không thể giải quyết trong phạm vi, báo blocker, không giả định dữ liệu hoặc silently đổi quy tắc.
