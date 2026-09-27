# Nhiệm vụ Antigravity Giai đoạn 5 Trend Following

## 1. Thẩm quyền và điểm xuất phát

- Repository: `Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING`, nhánh `main`.
- Baseline bắt buộc: commit nghiệm thu Giai đoạn 4 `b16fa1e0b7f064f764cea12fc97ae5c0677a40d2` hoặc descendant chỉ chứa tài liệu giao Giai đoạn 5 của GPT Planner.
- Trước khi sửa code, đọc đầy đủ:
  1. `PLANNER_HANDOVER.md`.
  2. `crypto-paper-agent/PROJECT_STATE.md`.
  3. `Project spec/CRYPTO_PAPER_TRADING_AGENT_MASTER_SPEC.md`, đặc biệt Mục 1.2, 1.3, 4.2, 4.4, 4.5, 5, 6 Giai đoạn 5 và 8.
  4. `Initial idea/AGENT_SPEC.docx`, phần Strategy Rulebook — Phân hệ 1.
  5. ADR 0003, 0005, 0006, 0007 và `crypto-paper-agent/docs/reviews/GPT_STAGE_04_REVIEW_09.md`.
- Xác nhận `git rev-parse HEAD` trước khi làm. Nếu baseline không phải descendant phù hợp hoặc worktree có thay đổi không rõ nguồn gốc, dừng và báo người dùng; không tự reset, không tạo bản project khác.

## 2. Mục tiêu duy nhất của Giai đoạn 5

Xây dựng Phân hệ 1 Trend Following theo rulebook gốc, nối nó vào Data Layer, Feature Engine, Risk Manager và PaperBroker đã nghiệm thu, rồi chạy backtest BTCUSDT có thể tái lập trên dữ liệu thật 2–3 năm.

Giai đoạn này bao gồm lớp điều phối backtest tối thiểu vì repo hiện chưa có `src/backtest/` và `run_backtest.py` vẫn là placeholder. Đây là dependency bắt buộc để đạt Definition of Done của Giai đoạn 5, không phải mở sớm Giai đoạn 6.

## 3. Nguồn ưu tiên và xử lý mâu thuẫn hiện tại

Thứ tự ưu tiên: yêu cầu trong task này → quyết định/ADR mới → `PROJECT_STATE.md` → Master Spec và Strategy Rulebook gốc → config placeholder cũ.

`config/strategies/trend_following.yaml` hiện là placeholder Giai đoạn 0 và có các điểm lệch rulebook: EMA alignment thay cho chuỗi crossover rồi pullback; ATR stop; TP cố định/partial TP; CVD blocker. Không triển khai các điểm lệch đó như mặc định chỉ vì chúng đang có trong file. Hãy sửa config để phản ánh hợp đồng dưới đây và ghi thay đổi vào ADR Giai đoạn 5.

## 4. Phạm vi bắt buộc

### 4.1 Cấu trúc module

Tạo tối thiểu:

- `src/strategies/__init__.py`
- `src/strategies/base_strategy.py`
- `src/strategies/trend_following.py`
- `src/backtest/__init__.py`
- `src/backtest/engine.py`

Cập nhật:

- `config/strategies/trend_following.yaml`
- `run_backtest.py`
- seam dữ liệu funding trong `src/data_layer/fetcher.py` nếu cần theo Mục 4.5
- test, ADR, CHANGELOG, PROJECT_STATE và báo cáo Giai đoạn 5.

`BaseStrategy` chỉ cần hợp đồng nhỏ, ổn định cho Giai đoạn 5: nhận dữ liệu nến đã đóng/trạng thái hiện tại và trả về không tín hiệu hoặc `OrderRequest`; không thiết kế framework đa chiến lược quá mức và không code chiến lược Giai đoạn 7–9.

### 4.2 Hợp đồng tín hiệu Trend Following

Khung chuẩn:

- Signal/regime: `4h`.
- Execution: `15m`.
- Chỉ sử dụng nến đã đóng. Tín hiệu hình thành tại thời điểm đóng nến 4h; lệnh market được xếp hàng sau khi nến tín hiệu đóng và chỉ được PaperBroker khớp tại open nến 15m kế tiếp.
- Không dùng nến 1m trong Giai đoạn 5.

Thiết lập LONG bắt buộc:

1. Regime: close 4h > EMA200.
2. Trigger: EMA20 cắt từ dưới lên EMA50 trên hai nến 4h đã đóng liên tiếp: `ema20[t-1] <= ema50[t-1]` và `ema20[t] > ema50[t]`.
3. Sau trigger, setup được arm; không vào ngay tại nến crossover.
4. Pullback/retest hợp lệ chỉ ở một nến 4h đóng sau trigger: biên nến giao với vùng giữa EMA20 và EMA50, và close lấy lại phía thuận xu hướng (`close >= ema20` cho LONG).
5. Momentum tại nến xác nhận: RSI14 > 50.
6. OI confluence: `oi_delta_pct > 0` khi dữ liệu hữu hạn. Giữ nguyên ADR 0005: mode mặc định `optional`; nếu OI là NaN và `fallback_when_nan=true`, cho phép bỏ qua nhưng phải ghi metadata `OI_BYPASSED_HISTORICAL`. `strict` phải chặn; `disabled` bỏ điều kiện. Giá trị sai kiểu/Inf không được coi là NaN hợp lệ để bypass.
7. Không dùng MACD hoặc CVD divergence như điều kiện bắt buộc mặc định của benchmark Giai đoạn 5.

Thiết lập SHORT là ảnh gương xác định rõ:

1. close 4h < EMA200.
2. `ema20[t-1] >= ema50[t-1]` và `ema20[t] < ema50[t]`.
3. Chờ một nến 4h sau trigger retest vùng EMA20/EMA50; close phải `<= ema20`.
4. RSI14 < 50.
5. OI confluence áp dụng cùng chính sách: OI tăng xác nhận vốn mới vào xu hướng giảm.

State machine:

- Mỗi symbol/direction có trạng thái `IDLE` hoặc `ARMED` với `trigger_time` và tuổi setup.
- `max_setup_age_bars` phải nằm trong config, mặc định 12 nến 4h. Hết hạn, regime/crossover đảo chiều, dữ liệu bắt buộc không hợp lệ hoặc setup đã phát lệnh thì reset.
- Một crossover chỉ được phát tối đa một `OrderRequest`; không phát lặp mỗi nến pullback.
- Không pyramiding, không hedge, không tự đảo chiều; giữ chính sách một vị thế/pending order trên mỗi symbol của PaperBroker.

### 4.3 Stop loss, trailing và sizing

- Stop ban đầu là đáy swing gần nhất cho LONG hoặc đỉnh swing gần nhất cho SHORT, được tính hoàn toàn từ các nến 4h đã đóng trước hoặc tại nến xác nhận.
- Định nghĩa số học cho Giai đoạn 5: `swing_lookback_bars` trong config, mặc định 5; LONG dùng minimum `low`, SHORT dùng maximum `high` của cửa sổ causal đó. Không dùng future bars để “xác nhận” swing và không backfill kết quả về quá khứ.
- Nếu stop không nằm đúng phía giá tín hiệu, bằng giá tín hiệu, NaN/Inf hoặc không đủ warm-up thì không tạo lệnh; ghi reason code xác định.
- Lệnh dùng conviction mặc định `normal`, leverage cấu hình nhưng không vượt 5x, và risk multiplier hiện hành của CircuitBreaker. Không tự tính sizing theo một công thức khác: tạo `OrderRequest` đúng hợp đồng để PaperBroker/Risk Manager thực hiện cổng duyệt đã nghiệm thu.
- Không có take-profit cố định và không partial TP trong Giai đoạn 5. `take_profit_price=None`.
- Sau mỗi nến 4h đóng, với vị thế mở, trailing stop bám EMA50 của nến đã đóng. Chỉ gọi `PaperBroker.update_stop_loss` khi stop mới thắt chặt rủi ro và nằm đúng phía mark price; tuyệt đối không nới stop và không sửa trực tiếp Position.

### 4.4 BacktestEngine tối thiểu và CLI

`BacktestEngine` phải:

- Nhận config, dữ liệu 4h và 15m đã chuẩn hóa UTC, một strategy và PaperBroker qua dependency injection để test được.
- Validate schema, index UTC, thứ tự tăng đơn điệu, không duplicate timestamp và OHLC hữu hạn/hợp lệ trước khi mutate broker. Dữ liệu lỗi fail-closed với lỗi rõ ràng.
- Tính feature trên từng timeframe bằng pipeline hiện có; không tính lại bằng logic riêng gây lệch chuẩn.
- Hợp nhất đa khung theo quan hệ causal: tại thời điểm quyết định chỉ cho strategy thấy nến 4h có `close_time <= decision_time`. Cấm `bfill`, nearest merge hoặc resample gắn nhãn khiến nến 4h chưa đóng bị lộ.
- Với mỗi nến 15m: xử lý PaperBroker theo đúng event time; sau khi nến đóng mới đánh giá nến 4h vừa hoàn tất, cập nhật trailing và có thể submit signal để khớp ở open 15m kế tiếp.
- Không tự sao chép logic phí, slippage, funding, liquidation, risk gate hoặc accounting ra ngoài PaperBroker.
- Kết thúc dataset bằng `PaperBroker.finalize(...)` theo lựa chọn config được ghi rõ; mặc định cho báo cáo benchmark là `force_close=true` để mọi trade có outcome xác định, đồng thời phải test cả `force_close=false`.
- Cố định random seed dù strategy hiện không ngẫu nhiên; cùng input/config phải sinh cùng order/trade/equity history.

`run_backtest.py` phải chạy thật cho `--strategy trend_following`, tôn trọng `--config`, `--start`, `--end`, `--no-fetch`; path phải được resolve nhất quán từ project root, không phụ thuộc current working directory. Các lựa chọn chiến lược chưa triển khai phải fail rõ ràng, không giả vờ chạy thành công.

### 4.5 Cầu nối funding provenance bắt buộc

PaperBroker đã nghiệm thu yêu cầu `funding_rate`, `funding_time` và `funding_readiness is True` tại settlement khi có vị thế mở. Data Layer hiện chỉ giữ `funding_rate`, vì vậy Giai đoạn 5 phải đóng seam này:

- Khi merge funding backward/as-of, bảo toàn timestamp thật của bản ghi nguồn thành `funding_time`.
- `funding_readiness=True` chỉ khi rate hữu hạn và source timestamp hợp lệ, không future, nằm trong giới hạn stale được broker chấp nhận; không tự gán True chỉ vì đã forward-fill.
- Nếu không có nguồn hợp lệ, giữ readiness False và để pipeline fail-closed tại settlement; không thay NaN bằng `0.0`, không tạo timestamp giả, không dùng wall clock.
- Cột metadata phải sống qua cache/load/feature/backtest tới đúng candle dictionary đưa vào `PaperBroker.process_candle`.
- Thêm test data-layer và integration cho source time, readiness, future/stale/missing và funding rate bằng 0 hợp lệ.

## 5. Backtest nghiệm thu và benchmark

- Dataset chuẩn của dự án vẫn là `2021-01-01` đến `2026-09-01`; không sửa mốc này trong `default_config.yaml`.
- Chạy nghiệm thu chính trên một cửa sổ BTCUSDT liên tục đúng 3 năm nằm trong dataset trên. Mặc định dùng `2021-01-01T00:00:00Z` đến hết `2023-12-31T23:59:59Z` để bao phủ bull, bear và hồi phục. Nếu cache thực tế thiếu, tải/bổ sung theo Data Layer hiện có; không rút ngắn âm thầm.
- Dùng 4h signal và 15m execution, có OI/funding provenance thật từ cache. Network fetch và backtest cache phải báo riêng.
- Benchmark win rate 35–45% là mốc so sánh nghiên cứu, **không phải assertion để chỉnh luật cho đến khi đạt**. Kết quả ngoài dải không làm test fail nếu code đúng; phải báo trung thực, giải thích data window/trade count và tuyệt đối không overfit hoặc thay luật sau khi xem kết quả.
- Báo cáo Giai đoạn 5 tối thiểu phải nêu: commit, Python/library versions, config dùng, data source/cache provenance, exact UTC range, candle counts và gaps, số setup/candidate/submitted/filled/rejected, reason counts, số trade đóng, win/loss/breakeven và win rate (toàn bộ + LONG/SHORT), start/final equity, total return, max drawdown tối thiểu cho kiểm tra sanity, funding/fees, trạng thái finalize và đối soát accounting.
- Đây chỉ là báo cáo nghiệm thu chiến lược. Không tạo Trade Logger SQLite/JSON schema tổng quát, `metrics.py`, dashboard hoặc hệ thống báo cáo Giai đoạn 6.

## 6. Kiểm thử bắt buộc

Tạo test riêng tối thiểu cho:

1. Crossover LONG/SHORT chỉ dùng hai nến đã đóng.
2. Không entry tại nến crossover; chỉ entry sau pullback/retest hợp lệ.
3. Setup expiry, invalidation và one-shot không phát tín hiệu lặp.
4. RSI biên 50 không pass (`>50` LONG, `<50` SHORT).
5. OI `strict`/`optional`/`disabled`, NaN fallback có note; None/string/Inf fail-closed.
6. Stop swing causal, warm-up, stop sai phía và trailing EMA50 tightening-only.
7. Warm-up EMA200 không phát tín hiệu.
8. Đồng bộ 4h/15m tại biên timestamp; nến 4h chưa đóng không được nhìn thấy.
9. Future perturbation: sửa mọi dữ liệu sau thời điểm T không làm thay đổi signal/order/trade/snapshot trước hoặc tại T.
10. Tín hiệu close → fill đúng next 15m open, kể cả gap/slippage vẫn do PaperBroker xử lý.
11. Funding metadata end-to-end và fail-closed không mutation khi missing/future/stale.
12. Replay determinism và accounting invariants.
13. CLI `--no-fetch`, override date, path độc lập CWD và strategy chưa hỗ trợ fail rõ ràng.

Chạy và lưu stdout/stderr thực tế:

```bash
python -m pytest -m "not network" -q
python -m pytest -m network -q
python run_backtest.py --config config/default_config.yaml --strategy trend_following --start 2021-01-01 --end 2023-12-31 --no-fetch
```

- Báo riêng passed/failed/skipped/deselected và thời gian; skipped/deselected không được gọi là passed.
- Network test chỉ gọi pass nếu đã chạy thật. Nếu môi trường không có network/cache, ghi rõ `NOT_RUN`/`SKIPPED` và lý do; không dựng log giả.
- Toàn bộ 237 offline tests và probes Review 05–07 phải tiếp tục không hồi quy. Không sửa/xóa/làm yếu assertion lịch sử để làm test pass.

## 7. Definition of Done

Giai đoạn 5 chỉ sẵn sàng cho GPT review khi:

- Mọi mục bắt buộc trong task hoàn tất; không có code Giai đoạn 6+.
- Unit/integration/no-lookahead tests mới pass và toàn bộ regression cũ pass.
- Backtest 3 năm trên dữ liệu thật/cache thật chạy end-to-end, report có thể tái hiện bằng đúng command và đối soát kế toán pass.
- Không có secret/API key giao dịch, testnet hoặc live-order path.
- Cập nhật `crypto-paper-agent/PROJECT_STATE.md`, `crypto-paper-agent/CHANGELOG.md`, ADR mới cho hợp đồng Trend Following/Backtest, và báo cáo `crypto-paper-agent/BÁO CÁO TÓM TẮT/GIAI ĐOẠN 5/BAO_CAO_GIAI_DOAN_5.md`.
- Commit/push toàn bộ lên `main`, báo full SHA và danh sách file thay đổi.

## 8. Ngoài phạm vi tuyệt đối

- Giai đoạn 6: Trade Logger, SQLite/JSON schema tổng quát, metrics/report framework đầy đủ, Streamlit.
- Giai đoạn 7–9: Breakout & Retest, Funding Arbitrage, SMC.
- Giai đoạn 10: multi-strategy comparison, walk-forward optimization.
- Giai đoạn 11: RL/Gym/PPO/SAC.
- Live trading, testnet, API key/private key/seed phrase, gửi lệnh ra sàn.
- Tối ưu tham số để ép win rate vào 35–45%, grid search, Bayesian optimization hoặc thay rulebook sau khi xem kết quả.

## 9. Quy tắc dừng

Sau khi hoàn tất, Antigravity phải commit/push, gửi full SHA cùng bằng chứng test/backtest rồi **DỪNG CHỜ GPT REVIEW GIAI ĐOẠN 5**. Không tự triển khai Giai đoạn 6 hoặc bất kỳ giai đoạn sau, kể cả khi mọi test đều xanh.

