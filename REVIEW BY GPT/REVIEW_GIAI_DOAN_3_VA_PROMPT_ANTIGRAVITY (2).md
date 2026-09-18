# Review giai đoạn 3 — Risk Manager và prompt sửa cho Antigravity

**Kết luận: FIX REQUIRED — cần sửa trước khi nghiệm thu và chuyển sang giai đoạn 4.**

Đây là review mã nguồn hiện có, không phải yêu cầu viết lại dự án. Antigravity tiếp tục là bên triển khai; GPT là planner/reviewer.

## 1. Bản được review và phạm vi kiểm chứng

- Repository: `Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING`.
- Commit: `6bdf5038a6d5bb5fc3d422d319662fd7e105519d` — “Upload toàn bộ Default Project”.
- Thư mục chương trình: `crypto-paper-agent/`.
- Đã đọc ba module `src/risk/position_sizing.py`, `invariant_checks.py`, `circuit_breakers.py`; bốn file test giai đoạn 3; script mô phỏng; cấu hình; ADR 0002; `PROJECT_STATE.md`, `CHANGELOG.md`, báo cáo giai đoạn 3; phần liên quan của master spec và giao diện news filter.
- Đã chạy lại bộ test không cần mạng, script mô phỏng và các tình huống kiểm tra độc lập. Không sửa mã nguồn chương trình hoặc đẩy thay đổi lên GitHub.

| Kiểm tra | Kết quả thực chạy |
|---|---|
| `python -m pytest -m "not network" -q` | **78 passed, 2 skipped, 5 deselected** |
| Riêng các test giai đoạn 3 trong lượt chạy trên | **32/32 passed**: sizing 10, liquidation 6, circuit breaker 5, invariants 11 |
| 2 test bỏ qua | So sánh EMA/RSI với `pandas-ta`, vì môi trường review chưa cài thư viện này |
| 5 test không chọn chạy | Test cần mạng/dữ liệu Binance, thuộc Data Layer; chưa xác nhận lại trong review này |
| Script mô phỏng 10 lệnh hiện có | Chạy thành công, in vốn cuối 9.320 USD và risk multiplier 1.0; có lỗi bằng chứng mô phỏng ở mục R6 |
| 15 test kiểm tra độc lập do reviewer tạo ngoài mã nguồn dự án | **13 failed, 2 passed**; các failure tái hiện lỗi được nêu dưới đây, hai ca đối chứng thanh lý cùng tier đạt |

Môi trường review: Linux, Python 3.12.14, pytest 9.1.1, pandas 2.2.3, numpy 2.3.5, PyYAML 6.0.3, loguru 0.7.3, ccxt 4.5.78, pyarrow 25.0.1. Đây không phải bản sao chính xác môi trường Windows/Python 3.13 của tác giả.

**Không kết luận báo cáo 85/85 trước đây là sai.** Bộ test cũ có thể đạt nhưng chưa kiểm tra đủ tình huống. Review này cũng không xác nhận lại toàn bộ 85 test.

## 2. Những phần đang làm đúng

- Công thức position sizing cơ bản đúng với các số liệu tính tay trong test.
- Có kiểm tra stop-loss, chiều stop-loss và giới hạn đòn bẩy trong các trường hợp thông thường.
- Chuỗi ba lệnh thua giảm risk, ba lệnh thắng phục hồi và lệnh thua xen giữa reset chuỗi thắng hoạt động trong các ca đã kiểm thử.
- Có gom nhiều lý do từ chối khi các trường đầu vào đều parse được.
- Công thức thanh lý LONG/SHORT với maintenance amount cho kết quả phù hợp khi tier không đổi giữa entry và liquidation.
- Cấu trúc module và tài liệu đủ để sửa tiếp trong phạm vi giai đoạn 3.

## 3. Các vấn đề cần sửa

P1 = cần sửa trước giai đoạn 4 vì có thể làm lọt lệnh hoặc vô hiệu hóa bảo vệ. P2 = sai số/bằng chứng/khả năng tái lập cần sửa trước nghiệm thu. Số dòng bên dưới thuộc commit đã ghi, tính từ thư mục `crypto-paper-agent/`.

### R1 — P1: Dữ liệu lỗi vẫn được duyệt, hoặc làm văng hàm kiểm tra

**Vị trí:** `src/risk/invariant_checks.py:163–168, 173–188, 205–216, 260–266`; `src/risk/position_sizing.py:44–64`.

Lấy lệnh hợp lệ làm gốc, thay riêng từng trường, `check_all_invariants` vẫn trả `(True, [])` với:

- `direction="INVALID"`.
- `leverage=0`.
- `entry_price=NaN`, `stop_loss_price=NaN`, `risk_percent=NaN` hoặc `position_size_usd=NaN`.
- `risk_percent=-0.01`.
- Account có `equity=0`; thậm chí truyền account `{}` cũng được duyệt do tự mặc định vốn 10.000 USD và bỏ qua circuit breaker.

`NaN` là giá trị “không phải số”, thường xuất hiện khi dữ liệu khuyết. So sánh `NaN > ngưỡng` hoặc `NaN <= 0` không hoạt động như kiểm tra hợp lệ thông thường; cần kiểm tra hữu hạn riêng.

Với `entry_price="bad"`, hàm ném `ValueError` trước khi thu thập các lỗi khác. Ngoài ra, `calculate_position_size` nhận NaN ở từng tham số và trả kết quả chứa NaN thay vì từ chối.

**Tier:** `conviction_tier="normla"` hoặc `None` được nâng ngầm lên trần cao nhất 10%; lệnh khai risk 5% được duyệt. Không được biến lỗi nhập tên tier thành quyền chịu rủi ro cao hơn.

**Sửa:** xác thực kiểu dữ liệu, miền giá trị, số hữu hạn, direction, tier và account bắt buộc trước tính toán. Đầu vào order/account sai phải trả lý do từ chối ổn định; các hàm toán học trực tiếp phải ném lỗi rõ ràng. Không thay dữ liệu thiếu bằng vốn giả định hoặc tier cao nhất.

### R2 — P1: Chưa đối soát rủi ro thực, khả năng ký quỹ và mức giảm risk

**Vị trí:** `src/risk/invariant_checks.py:203–216, 260–266`; `circuit_breakers.py:148–152`.

Hai ví dụ thực chạy đều được duyệt trên account 10.000 USD:

| Trường | Ca A: khai ít nhưng chịu rủi ro nhiều | Ca B: không đủ tiền ký quỹ |
|---|---:|---:|
| Entry | 50.000 | 50.000 |
| Stop-loss | 49.000 | 49.900 |
| Leverage | 3x | 3x |
| Risk khai báo | 2% = 200 USD | 2% = 200 USD |
| Position notional truyền vào | 100.000 USD | 100.000 USD |
| Quantity | 2 BTC | 2 BTC |
| Lỗ do biến động giá tới stop, chưa phí | **2.000 USD = 20% vốn** | 200 USD |
| Ký quỹ cần | 33.333,33 USD | **33.333,33 USD > vốn 10.000 USD** |

Ca B chứng minh thiếu kiểm tra ký quỹ độc lập với sai khai báo risk. Ngoài ra, sau ba lệnh thua nhỏ khiến `risk_multiplier=0.5`, lệnh normal vẫn khai 2% và giữ size đầy đủ vẫn được cổng duyệt chấp nhận. Việc giảm risk hiện phụ thuộc hoàn toàn bên gọi có nhớ dùng helper hay không.

**Sửa:** cổng risk phải tính/đối soát `quantity × abs(entry − stop)` với ngân sách risk hiệu lực, kiểm tra margin khả dụng, và đảm bảo trạng thái giảm risk được thực thi ở một đường duyệt thống nhất. Chốt rõ base risk và effective risk để không nhân 0.5 hai lần. Không chỉ tin `risk_percent` do lệnh tự khai.

Công thức sizing hiện tại chỉ mô tả rủi ro do biến động giá tới stop. Chi phí phí/slippage/funding phải được ghi rõ trong giao diện giai đoạn 4; không tuyên bố đây là mức lỗ tối đa tuyệt đối sau mọi chi phí/gap.

### R3 — P1: Thiếu thành phần bảo vệ hoặc sai đồng hồ vẫn có thể mở lệnh

**Vị trí:** `src/risk/invariant_checks.py:276–301`.

Các tình huống đã tái hiện:

1. Thiếu `circuit_breaker_state` vẫn được duyệt; object sai giao diện cũng có nhánh bỏ qua.
2. Cấu hình `news_filter.enabled=true`, nhưng account không có news filter: vẫn được duyệt.
3. News filter bật và có sự kiện, `timestamp` là Unix seconds như docstring cho phép: văng `AttributeError: 'float' object has no attribute 'tzinfo'`.
4. Khi cả thời gian order/account thiếu, code dùng `datetime.now()`. Trong review, một khóa lịch sử đến 02/09/2026 được mở bằng đồng hồ thực, dù không có thời điểm mô phỏng để xác định lệnh đã hết khóa hay chưa.

**Sửa:** cổng duyệt cần trạng thái circuit breaker hợp lệ và thời gian mô phỏng rõ ràng. Chuẩn hóa UTC một lần cho cả circuit breaker và news filter; không fallback đồng hồ thật. Cấu hình news là nguồn quyết định bật/tắt; khi bật mà thiếu bộ lọc hợp lệ thì từ chối có lý do. Khi tắt thì bỏ qua tin tức đúng chủ đích. Kiểm tra tính nhất quán giữa thời gian tín hiệu và thời gian duyệt; không cho một timestamp tương lai tùy ý mở khóa trạng thái hiện tại.

### R4 — P1: Circuit breaker có thể nhiễm NaN và nhận dữ liệu tương lai vào quá khứ

**Vị trí:** `src/risk/circuit_breakers.py:90–108, 154–176`.

- Ghi một kết quả `pnl=NaN`, rồi ghi lỗ 1.000 USD trên vốn 9.000 USD: `rolling_24h_pnl=NaN`, `is_locked=False`. Tổng lỗ bị nhiễm NaN khiến điều kiện khóa không còn hoạt động.
- Ghi -600 USD tại 03/09, sau đó ghi +1 USD tại 01/09: hệ thống chấp nhận, tính rolling -599 tại thời điểm quá khứ và còn dời `locked_until` về sớm hơn. Code chỉ lọc cận dưới cửa sổ, không bảo vệ thứ tự thời gian.
- Gọi kiểm tra quyền giao dịch sau 25 giờ mở khóa nhưng `rolling_24h_pnl` vẫn giữ -600 cho tới lần ghi trade tiếp theo. Đây là trạng thái rolling đã cũ, cần đồng bộ khi thời gian tiến lên.

**Sửa:** validate PnL/equity/time/config trước khi thay đổi state; reject event lùi thời gian; có một cơ chế cập nhật cửa sổ theo thời gian; invalid input không được làm thay đổi state. `recovery_mode` hiện được lưu nhưng không điều khiển logic: kiểm tra cấu hình để không âm thầm chấp nhận mode/threshold mâu thuẫn.

Các quy ước chưa đủ rõ cần được ghi bằng ADR và test biên trong đợt sửa, xem phần prompt: cận cửa sổ 24h, lệnh hòa, vốn dùng làm mẫu số, và việc có gia hạn khóa khi ghi thêm kết quả hay không.

### R5 — P2: Tier thanh lý chỉ lấy ở giá vào, sai khi notional vượt ranh giới tier

**Vị trí:** `src/risk/invariant_checks.py:105–124`; `tests/test_liquidation_calc.py`.

Đây là sai lệch toán học trong chính mô hình isolated của dự án, không phải đối chiếu với một tài khoản giao dịch thật. Đặt `q = notional_entry / entry`, `M = notional_entry / leverage`. Tại giá thanh lý P, mô hình cần thỏa:

```text
LONG:  M + q × (P − entry) = q × P × mmr − cum
SHORT: M + q × (entry − P) = q × P × mmr − cum
```

Tier ở vế phải phải nhất quán với notional `q × P`. Hàm hiện tại cố định tier từ `q × entry`.

| Ca, entry 50.000 và leverage 3x | Giá hàm hiện trả | Giá nghiệm nhất quán với bảng hiện có |
|---|---:|---:|
| LONG, notional entry 60.000 | 33.458,961474 | 33.467,202142 |
| SHORT, notional entry 45.000 | 66.401,062417 | 66.390,270868 |

Ở giá hiện trả, chênh lệch giữa margin balance và maintenance lần lượt khoảng -9,849246 USD và -9,760956 USD. Hai ca đối chứng notional entry 30.000, không đổi tier, đạt phương trình đến sai số số thực.

**Sửa:** giải theo từng tier và chỉ chọn nghiệm nằm trong miền notional của tier đó; hoặc dùng cách giải tương đương có kiểm chứng. Thêm test đi xuống tier, đi lên tier, đúng ranh giới và nhiều tier. Không chỉ chép lại công thức triển khai làm expected value.

Kiểm tra bảng cấu hình hợp lệ; symbol ngoài phạm vi không được lặng lẽ dùng bảng BTC; alias BTC phải chuẩn hóa rõ. Không gọi bảng tĩnh này là bảng chính xác cho toàn bộ lịch sử 2021–2026 nếu chưa có chứng cứ nguồn/ngày hiệu lực.

Tài liệu [Binance về leverage brackets](https://developers.binance.com/docs/derivatives/usds-margined-futures/account/rest-api/Notional-and-Leverage-Brackets) mô tả các trường cap/floor, maintenance ratio, cum và yêu cầu API key/chữ ký của endpoint. Vì phạm vi dự án không dùng API key, đợt sửa nên dùng snapshot cấu hình có nguồn và giả định được ghi rõ; không yêu cầu người dùng cung cấp key. Phương trình và phép kiểm tra nghiệm ở trên là phân tích toán học của reviewer trong mô hình hiện có, không phải xác nhận giá thanh lý thực tế trên sàn.

### R6 — P2: Mô phỏng thêm hai lệnh thắng không hiện trên bảng và không cộng vào vốn

**Vị trí:** `scripts/simulate_risk_manager_10_trades.py:218–221, 241–243`; báo cáo giai đoạn 3 phần mô phỏng.

Sau lệnh số 10, script gọi thêm `record_trade_result(+100)` hai lần. Hai lần này không đi qua sizing/invariants, không có dòng riêng, không cộng 200 USD vào equity. Bảng vì thế in vốn 9.320 USD nhưng circuit breaker đã nhận thêm hai khoản thắng; risk được phục hồi bằng các sự kiện ẩn này. Câu “Đã phục hồi 100%” ở cuối cũng được in cố định.

**Sửa:** mỗi trade được ghi nhận phải có dòng riêng, phải qua đường duyệt như các trade khác và cập nhật equity đúng một lần. Với 10 tình huống gốc, sau lệnh 10 chỉ có một thắng trong chuỗi phục hồi nên multiplier phải còn 0.5. Nếu thêm hai thắng +100 sau đó, phải hiển thị thành dòng 11/12 và vốn cuối thành 9.520 USD theo cùng PnL giả định. Có thể giữ đúng 10 dòng ở kịch bản chính và làm kịch bản phục hồi riêng; không ép tất cả trạng thái bằng cách thêm sự kiện ẩn.

Đây vẫn là mô phỏng trạng thái với PnL đặt trước, chưa phải engine khớp lệnh. Cú lỗ lớn hơn ngân sách trong kịch bản cần ghi là tình huống stress, không trình bày như giá khớp đã được mô phỏng.

## 4. Những điểm thiết kế không tự ý đổi

- Giữ paper trading/backtest; chưa triển khai lệnh thật, strategy, RL hoặc giai đoạn 4.
- Giữ phục hồi sau **3 thắng liên tiếp**, giảm risk 50%, giới hạn leverage 5x, buffer thanh lý 30%, news filter mặc định tắt.
- Buffer 30% có thể khiến nhiều lệnh ở leverage 4–5x bị từ chối. Đó là hệ quả của quy tắc đang chốt, không phải lý do tự giảm buffer để làm test xanh.
- Daily loss hiện được code/báo cáo hiểu là tỷ lệ của equity hiện tại. Bộ test cũ lại giữ equity cố định qua các trade. Cần thống nhất và test cả tài khoản biến động; không tự gọi đây là “5% vốn đầu cửa sổ”.
- Lệnh hòa không làm thay đổi chuỗi theo code hiện tại, nhưng “3 thắng liên tiếp” chưa có ADR rõ cho lệnh hòa. Cần quyết định rõ, không đánh đồng với lỗi đã chứng minh.
- Đóng toàn bộ vị thế, lỗ chưa chốt, phí và funding theo diễn biến thị trường cần được tích hợp khi xây engine giai đoạn 4. Giai đoạn 3 phải công bố tín hiệu khóa/đóng vị thế và hợp đồng dữ liệu; không nghiệm thu tính năng đóng vị thế khi engine chưa tồn tại.

## 5. Prompt đầy đủ — sao chép từ dòng bắt đầu đến dòng kết thúc cho Antigravity

--- BẮT ĐẦU PROMPT ---

Bạn tiếp tục dự án Crypto Paper-Trading Research Agent với vai trò implementer. GPT planner đã review giai đoạn 3 và kết luận FIX REQUIRED. Chỉ sửa giai đoạn 3 theo yêu cầu dưới đây, chạy kiểm chứng, báo cáo và dừng chờ review. Chưa bắt đầu giai đoạn 4.

### A. Nạp đúng bối cảnh

1. Làm việc trong project root đã khai báo trong PROJECT_STATE.md trên máy người dùng. Đọc PROJECT_STATE.md, CHANGELOG.md, master spec mục 4.4/5/6/10.2, ADR 0002 và báo cáo review này.
2. Bản review dựa trên commit 6bdf5038a6d5bb5fc3d422d319662fd7e105519d, chương trình nằm trong crypto-paper-agent/. Nếu local có thay đổi mới hơn, kiểm tra diff và bảo toàn công việc hiện có, xác minh lỗi còn tái hiện trước khi sửa.
3. Đọc các file thực tế: src/risk/*.py, tests/test_position_sizing.py, test_liquidation_calc.py, test_circuit_breakers.py, test_invariant_checks.py, config/default_config.yaml, scripts/simulate_risk_manager_10_trades.py và giao diện NewsCalendarFilter.
4. Chạy baseline, lưu output thật và phiên bản môi trường. Không dùng lại số 85/85 từ báo cáo cũ như kết quả mới.

### B. Sửa dữ liệu đầu vào và cổng duyệt lệnh — ưu tiên P1

1. calculate_position_size và calculate_estimated_liquidation_price phải từ chối NaN, +/-Inf, giá trị sai miền và kiểu không phù hợp; kiểm tra cả kết quả trung gian bị overflow. Equity/entry/stop/notional/risk phải dương hữu hạn; leverage hữu hạn >=1. Không coi bool là số hợp lệ. Giữ công thức sizing cơ bản của spec.
2. check_all_invariants phải trả (False, rejection_reasons) có mã lỗi ổn định cho order/account không hợp lệ. Không để float('bad') hoặc None làm văng hàm trước khi kiểm tra các lỗi độc lập khác. Nếu một phép kiểm tra phụ thuộc đầu vào sai thì ghi rõ không đánh giá được, không coi là pass.
3. Direction phải được chuẩn hóa và xác thực; tier phải tồn tại trong config. Thiếu/sai tier thì từ chối, không fallback trần 10%. Không tự tạo equity=10000 khi account thiếu vốn. Position size đã được truyền nhưng không hợp lệ phải bị từ chối; không âm thầm tính lại để che lỗi.
4. Tính lại quantity và rủi ro do biến động tới stop từ notional/entry/stop. Chặn trường hợp khai risk 2% nhưng size làm rủi ro thật 20%. Nếu order thiếu size và API cho phép tính hộ thì tính bằng một nguồn logic sizing thống nhất, rồi kiểm tra cùng bộ điều kiện.
5. Thêm kiểm tra required margin so với available/free margin. Ghi rõ trường dữ liệu mới nếu cần; equity và tiền ký quỹ khả dụng không phải luôn bằng nhau. Với fixture chưa có vị thế, đặt available margin bằng equity một cách tường minh. Không nhận lệnh cần 33.333,33 USD khi chỉ có 10.000 USD khả dụng. Với phí entry, ghi rõ khoản dự phòng/chi phí nào được tính trong admission và hợp đồng tích hợp giai đoạn 4, tránh tính hai lần.
6. Phân biệt base risk và effective risk bằng contract rõ ràng. Áp dụng trạng thái CircuitBreakerState tại cổng duyệt; không để bỏ quên helper là vượt giảm risk. Normal base=2%, multiplier=0.5 phải có ngân sách hiệu lực tối đa 1%; lệnh vẫn dùng full 2% phải bị từ chối hoặc được sizing lại trước khi tạo order đã duyệt. Không nhân 0.5 lần thứ hai vào risk đã giảm.
7. Account phải có circuit breaker hợp lệ. Missing hoặc sai giao diện phải từ chối rõ ràng. News enabled=false thì bypass; enabled=true mà thiếu/sai filter thì từ chối. Không để flag trên object bất nhất âm thầm ghi đè config. Chỉ sửa news_calendar.py nếu thật sự cần cho giao diện này, không mở rộng sang dịch vụ lịch mới.
8. Dùng thời gian mô phỏng UTC tường minh. Chuẩn hóa datetime/ISO/Unix seconds/milliseconds nếu tiếp tục hỗ trợ như API hiện tại. Không dùng datetime.now() làm fallback. Phân biệt timestamp bằng 0 với thiếu dữ liệu. Chốt thời điểm admission là nguồn quyết định, không để timestamp tùy ý trong order mở khóa sớm; ghi rõ quan hệ giữa signal time và admission time.

### C. Sửa CircuitBreakerState

1. Validate pnl/equity/timestamp và config trước khi mutate state. pnl=NaN phải bị từ chối, state không đổi; lần ghi lỗ hợp lệ sau đó vẫn có thể kích hoạt khóa. Không nhận equity âm/không hữu hạn; xử lý equity=0 bằng trạng thái dừng rõ ràng nếu tài khoản cạn vốn, không chia cho 0 hoặc cho phép giao dịch.
2. Đảm bảo thời gian xử lý không đi lùi; timestamp bằng nhau có thể hợp lệ cho nhiều sự kiện khác nhau. Event quá khứ sau event tương lai phải bị từ chối trước khi sửa history/lock/counters. Sau reset có thể bắt đầu một backtest mới.
3. Tạo một cơ chế cập nhật cửa sổ khi thời gian tiến lên, dùng nhất quán trong ghi trade và kiểm tra quyền giao dịch. Rolling PnL không được còn dữ liệu hết hạn khi đã hỏi trạng thái ở thời điểm mới.
4. Đề xuất planner cho những chỗ chưa được định nghĩa đầy đủ: cửa sổ (T-24h, T]; khóa 24h kể từ lần kích hoạt, không gia hạn vô tình do xử lý thêm các kết quả đóng vị thế trong cùng đợt khóa; thời điểm đúng locked_until thì hết khóa. Ghi quyết định vào ADR mới và test trước/đúng/sau mốc biên. Không sửa hồi tố ADR cũ để giả vờ các lựa chọn này đã được chốt trước đây.
5. Giữ cách hiểu hiện đang được code/báo cáo sử dụng: equity truyền vào record_trade_result là equity sau khi ghi nhận PnL ròng hiện tại; ngưỡng là daily_loss_limit_pct nhân equity này. Ghi rõ đây là tỷ lệ trên equity hiện tại, không phải vốn đầu ngày. Chạy test vốn thay đổi qua từng lệnh và test đúng ngưỡng; không dùng vốn cố định trong tất cả test. Nếu nhận thấy cần đổi sang vốn đầu cửa sổ, nêu đề xuất riêng, không tự đổi trong bản sửa.
6. Giữ after_3_wins. Validate recovery_mode và consecutive_wins_to_recover để config mâu thuẫn không bị bỏ qua. Với yêu cầu “thắng liên tiếp”, đề xuất bổ sung: pnl=0 sau mọi chi phí cắt chuỗi thắng/thua nhưng không tự đổi multiplier. Đây là quyết định planner mới cho trường hợp chưa có ADR, cần ghi rõ và test; không gọi là lỗi của yêu cầu cũ.
7. Công bố tín hiệu/state rõ để engine giai đoạn 4 biết khi nào cần đóng toàn bộ vị thế. Không code paper broker trong đợt sửa này; ghi rõ kiểm tra lỗ đang mở và xử lý fee/funding sẽ cần dữ liệu từ engine.

### D. Sửa liquidation — giải nhất quán với tier tại giá cần tìm

1. Trong mô hình isolated hiện tại: q=N_entry/entry, M=N_entry/leverage. LONG thỏa M+q(P-entry)=qP*mmr-cum; SHORT thỏa M+q(entry-P)=qP*mmr-cum.
2. Tìm nghiệm trên các tier và kiểm tra qP nằm trong miền của tier tương ứng. Không cố định tier theo N_entry khi P đã đi sang tier khác.
3. Đối chiếu tối thiểu hai ca dùng bảng hiện tại: entry=50000, leverage=3; LONG N_entry=60000 phải ra khoảng 33467.20214190094; SHORT N_entry=45000 phải ra khoảng 66390.2708678828. Thêm ca cùng tier, nhiều tier, ranh giới, long 1x và tình huống ngoài miền mô hình. Kiểm tra phương trình balance=maintenance độc lập với công thức triển khai.
4. Validate bảng bracket: cap tăng dần, số hữu hạn, MMR hợp lệ, cum hợp lệ và miền bao phủ rõ; không lặng lẽ dùng tier cuối cho dữ liệu ngoài miền chưa hỗ trợ. Chuẩn hóa BTCUSDT/BTC/USDT; symbol chưa hỗ trợ phải lỗi rõ, không mượn bảng BTC.
5. Ghi rõ đây là estimated liquidation theo snapshot cấu hình và giả định isolated, chưa bao gồm toàn bộ điều chỉnh margin/phí/funding của engine. Không tuyên bố đúng tuyệt đối lịch sử hoặc hiện tại của Binance. Không thêm API key/private endpoints.

### E. Sửa mô phỏng và báo cáo

1. Bỏ hai record_trade_result(+100) ẩn sau dòng 10. Mỗi trade phải được duyệt, hiện thành dòng, cập nhật equity một lần, ghi vào breaker một lần.
2. Giữ 10 dòng gốc thì cuối dòng 10 risk vẫn là 0.5. Muốn minh họa phục hồi sau ba thắng, thêm kịch bản riêng với ba dòng rõ ràng, hoặc mở rộng số dòng và sửa tên/mô tả tương ứng. Không chèn dữ liệu không hiển thị để ép kết quả mong muốn.
3. Có đủ ca giảm risk, thua xen giữa reset, khóa, từ chối trong khóa, mở khóa, và phục hồi. Có thể chia thành nhiều kịch bản độc lập, mỗi kịch bản reset state rõ ràng.
4. In equity trước/sau, PnL, risk trước/sau, lock status và đầy đủ rejection reasons. Lệnh bị từ chối không có PnL và không làm đổi streak. Nội dung “đã phục hồi” phải phụ thuộc state thực.
5. Có assertion đối soát equity cuối = equity đầu + tổng PnL của trade được chấp nhận; không tính trade bị từ chối. Ghi đây là mô phỏng state với PnL giả định, chưa là backtest execution; cú lỗ stress phải được gắn nhãn rõ.

### F. Bộ kiểm tra bắt buộc và điều kiện trả bài

- Bổ sung regression tests cho tất cả lỗi R1–R6. Test phải bắt được bug trên bản cũ và đạt sau sửa. Không bỏ/skip test quan trọng để lấy kết quả xanh; nếu contract đổi, sửa fixture/test có giải thích.
- Test numeric validation với NaN/Inf/None/bool/chuỗi sai, thiếu account, direction/tier sai và nhiều lỗi đồng thời.
- Test đối soát risk thật, thiếu margin, giảm risk không thể bypass và không nhân hai lần.
- Test missing circuit breaker; news bật/tắt/thiếu object; timestamp tương đương giữa các format; không có wall-clock fallback.
- Test NaN PnL không nhiễm state, timestamp đi lùi, rolling 24h tại biên, lock tại biên, recovery đúng ba thắng, hòa và thua xen giữa, config mâu thuẫn.
- Test liquidation qua tier bằng phương trình độc lập, không chỉ so với biểu thức chép từ production.
- Test kịch bản mô phỏng không có trade ẩn, equity và counters khớp từng dòng.
- Chạy toàn bộ test offline: python -m pytest -m "not network" -q. Chạy riêng nhóm network nếu môi trường hỗ trợ: python -m pytest -m network -q. Ghi rõ pass/fail/skip/deselected và lý do; network bị chặn không được báo PASS.
- Chạy script mô phỏng, lưu stdout/stderr thật; ghi phiên bản Python/thư viện. Các test cần pandas-ta phải ghi rõ đã chạy hay bị skip.
- Cập nhật PROJECT_STATE.md thành “Giai đoạn 3: đã sửa theo review, chờ nghiệm thu”; cập nhật CHANGELOG.md, ADR cho quy ước mới và báo cáo sửa dưới BÁO CÁO TÓM TẮT/GIAI ĐOẠN 3/. Giữ lịch sử báo cáo cũ và ghi phần đính chính thay vì làm mất dấu kết quả trước.
- Trả bảng: mã lỗi R1–R6 → file/hàm sửa → test chứng minh → kết quả thực chạy; kèm diff, thay đổi contract cho giai đoạn 4 và hạn chế còn lại. Commit các thay đổi dự án theo quy trình hiện có; không tự bắt đầu giai đoạn 4.

--- KẾT THÚC PROMPT ---

## 6. Cách dùng cho chủ dự án

Bạn có thể gửi toàn bộ file này cho Antigravity, hoặc sao chép phần nằm giữa “BẮT ĐẦU PROMPT” và “KẾT THÚC PROMPT”. Sau khi Antigravity sửa và cập nhật GitHub, GPT review lại diff, log test và mô phỏng để quyết định giai đoạn 3 đã đủ điều kiện nghiệm thu chưa.
