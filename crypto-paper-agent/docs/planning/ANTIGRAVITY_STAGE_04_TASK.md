# Nhiệm vụ Antigravity Giai đoạn 4 Paper Execution Engine

## Quyền triển khai và mục tiêu

Người dùng đã yêu cầu tiếp tục giai đoạn tiếp theo sau kết luận GPT Review 04. **Được phép triển khai riêng Giai đoạn 4**, không được chuyển sang Giai đoạn 5.

Giai đoạn 3 được nghiệm thu theo phạm vi kiểm tra kỹ thuật ghi trong `docs/reviews/GPT_STAGE_03_REVIEW_04.md`, trên code `44014393a2ed6dba7188096a6d1de600daa972d0`. Không chuyển số test tác giả thành kết quả reviewer: reviewer chạy 151 pass, 2 skip, 5 network deselected, thêm 9 kiểm thử độc lập đạt.

Mục tiêu đúng roadmap ban đầu: xây dựng engine mô phỏng futures event-driven, mở/đóng LONG và SHORT, SL/TP/thanh lý, phí, slippage, funding, vốn/margin và tích hợp Risk Manager. Chưa xây strategy kiếm lợi nhuận, dashboard, RL hay tầng đặt lệnh sàn.

Nội dung sau là prompt thi công đầy đủ. Các quy ước mới về khớp lệnh là **mô hình nghiên cứu do planner bổ sung để đặc tả có thể kiểm thử**, không được tuyên bố giống hoàn toàn cơ chế Binance thật.

## 1. Đọc trước khi làm và đồng bộ an toàn

1. Làm việc tại PROJECT_ROOT chính thức trong PROJECT_STATE; không quét ổ đĩa hay tạo project trùng.
2. Kiểm tra worktree. Nếu có thay đổi chưa commit, giữ nguyên; không reset/overwrite. Đồng bộ main an toàn để có tài liệu mới; nếu xung đột thì dừng báo.
3. Đọc theo đường dẫn tính từ gốc repo:
   - `PLANNER_HANDOVER.md`.
   - `crypto-paper-agent/PROJECT_STATE.md`.
   - `Project spec/CRYPTO_PAPER_TRADING_AGENT_MASTER_SPEC.md`: mục 1.3, 3, 4.4, 4.5, 4.6, 5, Giai đoạn 4 trong mục 6 và Definition of Done mục 8.
   - ADR 0001–0006 và các phụ lục; GPT Review 04.
   - Code/tests risk hiện tại và config thực tế.
4. PROJECT_STATE/ADR mới hơn thắng mặc định cũ trong spec: after_3_wins, news disabled, data 2021-01-01 → 2026-09-01; giữ nguyên giới hạn 5x và buffer 30%.
5. Trước khi code, viết ADR tiếp theo đúng số chưa dùng, mô tả model tài khoản, thời gian, funding, SL/TP cùng nến và event order dưới đây. Có thể chọn cấu trúc API nội bộ nhưng không tự thay các quy tắc bắt buộc. Nếu yêu cầu mâu thuẫn không thể giải quyết mà vẫn giữ scope, dừng hỏi.

## 2. Phạm vi và file bàn giao

Bắt buộc:
- `src/execution/order_models.py`.
- `src/execution/paper_broker.py`.
- `src/execution/__init__.py` xuất public API.
- Tests cho models, broker, accounting, funding, risk integration và execution no-lookahead.
- `scripts/simulate_paper_execution.py`: kịch bản dễ đọc với bảng đối soát.
- ADR về execution; báo cáo Giai đoạn 4; cập nhật README/PROJECT_STATE/CHANGELOG/PLANNER_HANDOVER.

Tối thiểu hỗ trợ:
- Linear USDT-margined futures, isolated-margin simulation.
- Một vị thế tại một thời điểm cho mỗi symbol. Không pyramiding, không hedge LONG+SHORT, không đảo chiều tự động. Lệnh mới khi đã có vị thế cùng symbol bị từ chối rõ lý do.
- Market entry ở open nến kế tiếp; stop-market SL và TP đóng toàn bộ với taker fee.
- Pending → filled/rejected/cancelled; vị thế open → closed; mỗi giao dịch có ID xác định, không dùng wall-clock/random UUID gây khác kết quả giữa hai lần chạy.
- Signal/trade/position/fill/account snapshot/event có dữ liệu đủ audit: symbol, direction, timestamp, giá signal và fill, stop, TP, quantity, leverage, conviction tier, base/effective risk, margin, phí, funding và lý do trạng thái.

Ngoài phạm vi lần này:
- Spot/perp hai chân, funding arbitrage, đa chiến lược, limit/maker matching, orderbook, nhiều TP/partial close tự động, chiến lược trailing stop, metrics đầy đủ/SQLite/dashboard/RL.
- Đầu vào chưa hỗ trợ phải bị từ chối, không âm thầm bỏ qua rồi coi như đã thực thi. Thiết kế model đủ mở rộng cho giai đoạn sau.
- Event log in-memory/JSON và báo cáo đơn giản được phép; không triển khai toàn bộ Trade Logger/Report Giai đoạn 6.

## 3. Đồng hồ và thứ tự sự kiện chống nhìn trước

Quy định timestamp nến là **open_time UTC**, có timeframe/duration để tính close_time. Signal dựa trên nến đã đóng. Ở biên close_time cũng là next_open_time, signal vừa được xác nhận có thể vào hàng đợi cho open kế tiếp, tuyệt đối không được khớp ở giá close của nến tạo signal.

Tách pha xử lý thay vì cho gate thấy cả OHLC trước khi vào lệnh:
1. Tại open_time: tiến đồng hồ; xử lý gap và các mức bảo vệ đã có hiệu lực của vị thế mang từ nến trước.
2. Funding nếu có settlement đúng biên này: sau gap exits, trước mở entry mới. Chỉ vị thế còn mở và đã tồn tại trước biên settlement chịu funding. Vị thế bị gap-exit ngay biên không chịu funding; entry mới ngay biên không chịu kỳ đó. Đây là quy ước mô phỏng phải ghi ADR.
3. Xử lý pending market entry bằng **open hiện tại**, áp dụng slippage, tính size/margin và chạy gate với snapshot tại thời điểm này. Không dùng close/high/low của nến sắp diễn ra để sizing hoặc duyệt lệnh.
4. Trong nến: dùng high/low kiểm tra bảo vệ vị thế còn tồn tại hoặc mới mở ở open. Vì không biết đường đi intrabar, áp dụng quy tắc bảo thủ ở mục 5; event intrabar được gắn close_time kèm flag `intrabar_time_estimated`, không giả vờ biết giây khớp chính xác.
5. Tại close_time: mark giá close, cập nhật unrealized/equity và tạo signal mới từ dữ liệu đã đóng. Signal này chỉ được dùng tại next_open. Không thực thi cùng giá close vừa tạo signal.

Khi khoảng thiếu nến đi qua settlement: không suy đoán giá/rate và tiếp tục âm thầm. Chặn xử lý đoạn thiếu dữ liệu cần thiết, báo lỗi/gap rõ ràng; chỉ chạy được nếu có dữ liệu settlement hợp lệ độc lập theo contract đã ghi.
- Reject timestamp lùi, trùng candle hoặc duplicate event; không ghi phí/funding/outcome hai lần. Replay toàn lượt chạy phải cho kết quả giống nhau.
- Validation nến đầy đủ trước commit state: finite positive OHLC, high >= max(open,close), low <= min(open,close), high >= low; timeframe/timestamp hợp lệ.
- Mỗi API phải nói rõ validation error vs order rejection. Dữ liệu malformed không được mutate tài khoản/vị thế/ledger; reject order có thể thêm audit event, và tiến đồng hồ hợp lệ của gate theo contract Giai đoạn 3, nhưng không trừ tiền hoặc tạo vị thế.

## 4. Sizing, slippage và cổng Risk Manager

- Slippage mặc định lấy `fees.slippage_pct = 0.0003`, không hard-code; cho phép 0 trong fixture đối chiếu bằng tay.
- Fill bất lợi: BUY = reference × (1+s), SELL = reference × (1-s).
  LONG entry BUY / exit SELL; SHORT entry SELL / exit BUY.
- Fill entry thực tế là cơ sở tính stop distance, quantity, notional, margin và liquidation — không dùng giá signal cũ.
- Áp dụng multiplier risk **đúng một lần** bằng API Giai đoạn 3; giữ base_risk_percent và effective_risk_percent để audit.
- Gọi sizing hiện có, rồi `check_all_invariants` trước mọi mở vị thế. Snapshot account lấy từ broker thật, không nhận equity/available_margin do caller tự khai để bypass.
- `account_state.current_time` là admission time, breaker/news instance do broker quản lý. News enabled unready phải chặn; không dùng stub thiếu readiness để bypass.
- Gate fail: không tạo vị thế, không charge entry fee, log đầy đủ reasons. Không có public helper “mở trực tiếp” bỏ gate.
- Initial margin = fill_notional / leverage; gate phải kiểm tra available_margin và entry fee cùng lúc.
- Nếu fill làm SL sai phía, TP sai phía hoặc rủi ro/margin vi phạm thì từ chối. Không tự nới stop, tăng leverage hoặc bỏ liquidation buffer để lệnh được duyệt.
- Lệnh pending phải được duyệt lại tại lúc fill; approval cũ không cấp quyền vĩnh viễn.
- Cho phép API cập nhật SL của vị thế để phục vụ giai đoạn sau: LONG chỉ nâng SL, SHORT chỉ hạ SL; finite và đúng phía mark tại thời điểm cập nhật. Thay đổi dựa trên close chỉ có hiệu lực từ biên/nến tiếp theo, không sửa kết quả intrabar đã đi qua. Chưa code strategy trailing.

## 5. SL, TP, gap và thanh lý

- LONG: low chạm SL/liquidation, high chạm TP; SHORT ngược lại; touch inclusive.
- Nếu nhiều mức cùng có thể chạm trong một nến và không có dữ liệu finer chứng minh thứ tự: **liquidation > SL > TP**, theo mô hình bảo thủ của spec; không suy diễn đây là thứ tự diễn ra thật trên sàn.
- Với vị thế mang sang nến sau, kiểm tra gap tại open trước range cả nến. SL/liquidation vượt qua bởi gap dùng open làm reference exit, không khớp “đẹp” ở mức stop cũ. TP full-close dùng target làm reference bảo thủ, không thưởng gap có lợi.
- Exit áp dụng slippage/fee theo contract; liquidation có liquidation flag, giá/margin còn lại/deficit phải audit. Không khấu trừ đồng thời “mất hết margin” rồi lại khấu trừ full price PnL cho cùng sự kiện.
- Ước tính liquidation dùng solver tier-consistent đã được duyệt với snapshot bracket trong config, không gọi endpoint cần key, không dùng last-tier fallback.
- Isolated collateral có thể thay đổi do funding; khi đó liquidation phải phản ánh collateral hiện tại, không đóng băng giá entry nếu margin đã đổi. Nếu cần helper collateral-aware, mở rộng tối thiểu công thức/helper, giữ API cũ và toàn bộ tests Giai đoạn 3; thêm kiểm chứng phương trình độc lập.
- Đây không phải simulator liquidation chính xác của Binance: nến OHLC làm proxy price, không có riêng intrabar mark price/orderbook/liquidation penalty thực tế. Ghi rõ giới hạn. Mọi khoản liquidation fee bổ sung nếu mô phỏng phải config, ghi ledger và test, không tự bịa phí sàn.
- Cuối dataset: mặc định không giả định đã đóng vị thế. Báo cash/unrealized/open position. Chỉ force-close ở last close nếu mode tường minh, log END_OF_DATA, áp dụng phí/slippage và không cho callback mở lệnh sau đó.

## 6. Hạch toán tài khoản và đối soát

Phân biệt rõ wallet balance, reserved isolated collateral, unrealized PnL, equity và available margin. Wallet balance gồm cả tiền đang ký quỹ; reserve/release không phải phí hoặc lãi.

Bất biến tổng tài khoản:
```text
wallet_balance = initial_balance + Σ realized_price_pnl - Σ trading_fees + Σ signed_funding_cashflows
equity = wallet_balance + Σ unrealized_price_pnl
available_margin = wallet_balance - Σ reserved_collateral
LONG price_pnl = quantity × (exit - entry)
SHORT price_pnl = quantity × (entry - exit)
trade_net_pnl = realized_price_pnl - entry_fee - exit_fee + signed_funding_cashflows
```

- Entry/exit fee = abs(quantity × actual_fill_price) × fee_rate; không nhân leverage thêm lần nữa.
- Unrealized mark theo close trong pha close, theo open trong snapshot pha open; không mark close tương lai trước admission.
- Entry fee trả từ free wallet; initial margin được reserve riêng.
- Funding vào isolated collateral: cập nhật wallet và collateral cùng signed cashflow; không charge free cash hai lần. Margin release khi đóng trả lại reservation, không cộng margin như lợi nhuận.
- PnL của trade dùng cho streak là net sau phí và funding; không trừ entry fee/funding lần nữa ở wallet khi đã ghi trước đó.
- Trường hợp deficit/insolvency phải thể hiện số thô và cảnh báo, không âm thầm clamp equity thành 0 rồi báo đối soát đúng. Nếu breaker chỉ nhận equity >= 0, adapter có thể truyền 0 cho trạng thái halted nhưng phải lưu raw equity/deficit và dừng mở lệnh; không tuyên bố isolated của sàn bảo đảm đúng mức loss trong mô hình gap/slippage này.
- Các phương trình đối soát phải kiểm tra tự động sau mỗi event, với tolerance số học rõ ràng.

## 7. Funding và circuit breaker

Funding:
- Đọc hours từ config hiện có (mặc định 00/08/16 UTC), xử lý đúng một lần cho mỗi settlement/position.
- Cashflow = -direction_sign × quantity × settlement_mark × funding_rate, LONG sign +1, SHORT sign -1. Rate dương LONG trả/SHORT nhận, rate âm ngược lại.
- Settlement mark/rate phải đã khả dụng tại settlement; không dùng close của nến kết thúc sau settlement. Với settlement trùng open, open là price proxy đã biết, ghi ADR.
- NaN/missing/stale rate không tự biến thành 0. Event cần funding mà thiếu dữ liệu phải báo lỗi trước mutation hoặc có policy explicit được planner chấp thuận. Rate 0 được cung cấp hợp lệ khác với thiếu rate.
- Không lấy hàng funding timestamp > settlement. Ffill có giới hạn hiện có, không backfill tương lai, không dùng rate cũ như sự kiện mới.
- Không dùng dữ liệu funding để phát signal chiến lược ở giai đoạn này.

Breaker:
- Dùng chung đồng hồ UTC và state Giai đoạn 3. Locked/halted chặn entry nhưng vẫn xử lý exits/funding của vị thế mở.
- Khi chạm ngưỡng daily loss: đóng tất cả vị thế còn mở theo price khả dụng ở pha hiện tại với fee/slippage; hủy pending entry; khóa 24h; không gia hạn khóa do các close phát sinh trong lúc khóa.
- Phải phân biệt **cashflow đã thực sự phát sinh tại timestamp** (phí, funding, realized price PnL) và **kết quả một trade đã hoàn tất** (net PnL để đếm streak). Daily rolling loss không được bỏ qua funding/entry fee chỉ vì trade chưa đóng; streak không được đếm mỗi funding hoặc fee như một trade thua.
- Không vừa đưa cashflows vào rolling ledger vừa cộng lại trade_net_pnl của cùng trade gây double count.
- Cho phép bổ sung API/adapter tối thiểu để tách cashflow update và completed-trade outcome, nhưng giữ hợp đồng/public API và kết quả test Giai đoạn 3; API `record_trade_result` cũ phải vẫn hoạt động như trước cho caller cũ. Broker dùng một đường ghi nhận nhất quán, ADR phải chỉ rõ nguồn rolling ledger.
- Mức so sánh daily loss giữ semantics Giai đoạn 3 là 5% equity hiện tại; không tự đổi sang initial equity hoặc day-start equity.
- Khi net close cập nhật multiplier, lệnh tiếp theo mới dùng multiplier mới, không resize vị thế đang mở.
- Không đưa unrealized fluctuation như realized cashflow. Nếu muốn thêm equity drawdown guard ngoài rule đã chốt thì phải xin phép riêng, chưa làm trong task này.

## 8. Kiểm thử và tiêu chí nghiệm thu

Không dùng solver/sizing của chính engine làm “kết quả kỳ vọng” duy nhất. Có oracle bằng tay cho các phép hạch toán, fee/funding và liquidation margin equation.

Bắt buộc có tests:
1. LONG lời/lỗ, SHORT lời/lỗ; SL/TP; một LONG qua vài trăm nến như roadmap.
2. Entry next-open; signal trên close không fill cùng nến; thay close/high/low của nến fill không ảnh hưởng admission/sizing tại open, mặc dù có thể thay exit cuối nến.
3. Future perturbation: sửa/shuffle phần dữ liệu sau cutoff, fills/rejections/ledger/snapshots tính đến cutoff giữ nguyên.
4. Slippage BUY/SELL cả entry/exit; reference signal khác next-open; sizing/risk theo fill thật.
5. Gap qua SL/liquidation, SL+TP cùng nến, liquidation+SL+TP cùng nến, exact touch.
6. Fee entry/exit đúng actual notional; leverage không nhân PnL hai lần; reserve/release và available margin khớp.
7. Funding rate +/-/0 cho LONG/SHORT, settlement boundaries, duplicate event, missing rate, nhiều kỳ, collateral và liquidation thay đổi.
8. Gate từ chối thiếu stop, leverage >5, buffer thiếu, margin thiếu, declared risk mismatch; news enabled unready, breaker lock, multiplier giảm đúng một lần.
9. Daily loss đóng vị thế và khóa; funding/fee cashflow không đếm trade streak; net outcome không doublecount rolling; ba thua giảm risk, đúng ba thắng phục hồi; breakeven reset và expiry/relock.
10. Một position/symbol, pending rejection/cancel, không mở ngược chiều tự động; unsupported order/features bị từ chối.
11. Invalid input/time reversal/OHLC malformed: state không bị charge/mutate tài chính; replay duplicate không charge lại.
12. End-of-data còn open vs force-close explicit; insolvency raw deficit và halted.
13. Hai lần chạy cùng data/config ra cùng IDs/ledger/account/trade results.
14. Toàn bộ test cũ Giai đoạn 0–3 giữ nguyên ý nghĩa và pass. Không sửa assertion cũ chỉ để che regression.

### Oracle LONG đơn giản bắt buộc

Dùng fixture riêng: balance 10.000 USD, leverage 2x, entry actual 100, SL 98, TP 104, base risk 0.002, tier low, quantity 10, slippage 0, taker 0.0005.
Signal trước nến entry, entry trước settlement, TP sau settlement. Có 300 nến 1 phút với OHLC hợp lệ, chỉ một settlement giữ vị thế và rate +0.0001, settlement mark 100.

```text
notional entry = 1.000 USD; initial reserved margin = 500
entry fee = 0,50
funding cashflow = -0,10; isolated collateral sau funding = 499,90
gross price PnL tại TP = 40,00
exit fee = 0,52
net trade PnL = 38,88
final wallet/equity sau khi flat = 10.038,88
reserved margin cuối = 0; available margin cuối = 10.038,88
```

Fixture không thay config mặc định production để làm test pass. Thêm case riêng dùng slippage mặc định và default risk config, kiểm tra entry được duyệt hoặc bị từ chối đúng lý do.

## 9. Demo trên dữ liệu thật và báo cáo

- Script offline synthetic trước: in bảng signal_time, admission/fill_time, fill_price, stop/TP/liquidation, quantity, margin, phí, funding, net PnL, wallet/equity/available margin và breaker state.
- Bắt buộc thêm demo trên đoạn OHLCV thật từ cache/Data Layer public đã có; signal fixture/manual deterministic được phép vì chưa làm strategy.
- Thực thi đúng risk config. Nếu signal thực không qua gate thì ghi rejection thật, không nới invariants hoặc bịa fill để báo đạt. Điều chỉnh fixture signal hợp lệ có giải thích để chứng minh đường opened → closed ít nhất một lần.
- Báo nguồn/cache path, symbol, timeframe, range, config và lệnh chạy. Không đẩy dữ liệu nặng, venv, secrets hoặc bản sao code toàn project.
- Nếu không có cache và public network thất bại, báo rõ demo thật chưa xác minh; không nói Definition of Done đạt toàn bộ. Không cần API key.
- pytest: ghi riêng passed/failed/skipped/deselected; network run riêng khi khả dụng. Kết quả skip/network chưa chạy không được gọi 100% pass.
- Báo cáo readable markdown/JSON nhỏ trong `BÁO CÁO TÓM TẮT/GIAI ĐOẠN 4/BAO_CAO_GIAI_DOAN_4.md`; gồm đối soát bằng tay, test raw output, known limitations và cách chạy.

## 10. Kết thúc và bàn giao

1. Cập nhật PROJECT_STATE: Giai đoạn 3 được duyệt theo Review 04; Giai đoạn 4 đã triển khai **chờ GPT review**, không tự đánh dấu được nghiệm thu.
2. Cập nhật CHANGELOG/ADR/README và PLANNER_HANDOVER: SHA/code đang chờ review, tests thực tế, blocker/limitation, next action là GPT review Giai đoạn 4.
3. Sửa ghi chú báo cáo Review 03 “15 tests mới” thành số đúng 23 nếu đối chiếu xác nhận; giữ lịch sử kết quả tác giả, không ghi đè bằng kết quả reviewer.
4. Commit/push đúng repo main theo workflow hiện có sau kiểm tra diff; không đè thay đổi của người dùng, không force-push.
5. Trả cho người dùng: commit SHA đầy đủ, file chính, raw test summary, kết quả demo/đối soát và giới hạn còn lại.
6. **DỪNG CHỜ GPT REVIEW. Không bắt đầu strategy Giai đoạn 5.**

Nếu phiên bị dài: cập nhật tài liệu trước khi đổi phiên và đọc lại task này ở phiên mới. Không tự nhớ từ hội thoại.
