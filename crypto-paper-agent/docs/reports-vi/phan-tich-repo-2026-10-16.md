# Phân tích repo AGENT-AI-T-NG-H-A-VI-C-TRADING

Ngày: 2026-10-16 · Commit được đọc: `fe1c133` (`main`, "feat(web): add paper research preview console") · Chỉ đọc, không sửa repo.

**Về skill "book":** tôi không tìm thấy skill nào tên "book" (hay gần giống) trong danh sách skill của phiên này hay trong skill tài khoản. Thứ duy nhất có chữ "book" là skill mẫu `call-to-book` (gọi điện đặt lịch hẹn), không liên quan. Vì vậy tôi dùng skill **code-quality** (tiêu chuẩn review code) làm khung đánh giá. Nếu skill "book" có tên khác, bạn cho tôi tên để chạy lại theo đúng skill đó.

---

## 1. Tóm tắt một đoạn

Đây là một **hệ thống nghiên cứu giao dịch giấy (paper trading) cho BTCUSDT futures trên Binance**, không đặt lệnh thật. Phần kỹ thuật đã khá đầy đủ và rất kỹ về chống nhìn trước (lookahead), hạch toán và quản trị rủi ro: 4 chiến lược luật cố định, một tác tử PPO, broker mô phỏng, risk manager, báo cáo, và một web preview tĩnh. **Điểm yếu lớn nhất không nằm ở code mà ở bằng chứng:** chưa có lần backtest nào trên dữ liệu đầy đủ 2021–2026, chưa có reviewer độc lập nào xác nhận, và các mẫu thử ngắn hiện có cho kết quả 0 lệnh hoặc lỗ. Nói cách khác, bot hiện chưa "tìm ra giải pháp trade tốt nhất"; nó mới là một phòng thí nghiệm sẵn sàng để thử.

## 2. Bot hiện làm gì

| Thành phần | File chính | Chức năng |
| --- | --- | --- |
| Data layer | `src/data_layer/fetcher.py`, `binance_vision_downloader.py`, `cache_manager.py` | Lấy OHLCV, Open Interest, funding từ API công khai Binance (ccxt, không API key) và kho Binance Vision; cache Parquet, kiểm tra checksum. |
| Features | `src/features/` | EMA, RSI, MACD, ATR, CVD, OI delta, đặc trưng SMC (swing, FVG), bộ lọc lịch tin tức (mặc định tắt). |
| 4 chiến lược | `src/strategies/` | Trend Following (4h/15m, EMA20/50/200 + RSI), Breakout & Retest, SMC Liquidity Sweep (5m/1m, chốt lời từng phần 40/30/30), Funding Arbitrage (spot/perp). |
| Risk | `src/risk/` | Sizing theo % rủi ro, đòn bẩy tối đa 5x, khoảng đệm thanh lý ≥30%, circuit breaker (lỗ 5%/24h thì khoá 24h, thua 3 lệnh giảm 50% rủi ro, thắng 3 lệnh thì phục hồi). |
| Broker giấy | `src/execution/paper_broker.py` | Mô phỏng isolated futures theo 5 pha mỗi nến: gap → funding → khớp lệnh chờ + risk gate → thanh lý/SL/TP trong nến → mark-to-market. |
| Backtest | `src/backtest/engine.py`, `run_backtest.py` | Duyệt từng nến 15m, chỉ dùng nến 4h đã đóng để ra tín hiệu, khớp ở open nến kế tiếp. Mặc định offline. |
| Research / RL | `src/research/` | Walk-forward 4 tài khoản độc lập, môi trường Gymnasium + PPO (stable-baselines3), reward = lãi thực hiện − 0.5×drawdown − vi phạm. |
| Báo cáo | `src/report/`, `src/logging/trade_logger.py` | Win rate, expectancy, SQN, Sharpe, Max DD, đường equity, SQLite/CSV/PNG. |
| Web preview | `web-preview/` (React + Vite) | Trang tĩnh hiển thị số liệu bằng chứng được gõ tay trong `src/data/evidence.js`. |

Quy mô: khoảng 13.300 dòng Python (src + scripts), 9.500 dòng test (35 file), 5.000 dòng tài liệu Markdown, 12 ADR.

## 3. Kiến trúc

```
Binance public (REST / Vision ZIP)
        │  checksum, manifest, readiness funding
        ▼
   Cache Parquet ──► Features (causal) ──► Strategy.on_candle_close(nến đã đóng)
                                                │ OrderRequest
                                                ▼
                         Risk gate (invariant_checks + circuit_breakers)
                                                │
                                                ▼
                     PaperBroker (5 pha / nến) ──► TradeLogger (SQLite)
                                                │
                                                ▼
                                Report (metrics, lifecycle, PNG/JSON)
PPO env bọc cùng PaperBroker, nên tác tử không thể bỏ qua stop/breaker.
```

Điểm mạnh kiến trúc:
- **Chống lookahead nghiêm túc:** tín hiệu chỉ từ nến đã đóng, khớp ở nến sau (`engine.py:233-262`); swing CVD chỉ ghi nhận tại nến xác nhận (ADR 0003); có test riêng (`test_no_lookahead.py`, `test_execution_no_lookahead.py`).
- **Fail-closed:** thiếu dữ liệu, funding không khớp nguồn, cấu hình NaN đều bị từ chối thay vì đoán.
- **PPO bị nhốt trong broker:** RL không thể "học" cách vượt rủi ro.
- **Không có đường đặt lệnh thật:** `fetcher.py:57-67` khởi tạo ccxt không key; tôi không thấy `create_order` hay key nào trong `src/` và `scripts/`.

## 4. Kết quả kiểm tra tôi tự chạy

Môi trường sạch Python 3.13, cài tay các gói lõi (bỏ jupyter/streamlit/plotly/mypy, không cài torch):

- `pytest -m "not network"`: **dừng ngay khi thu thập test**, vì `tests/test_rl_env.py` import `gymnasium`, mà `requirements.txt` không có gói này (nó nằm trong `requirements-rl.txt`).
- Bỏ file đó ra: **406 passed, 2 skipped, 1 failed, 5 deselected** (49 giây). Test fail là `test_quickstart.py`, cũng vì thiếu `gymnasium`. 2 test skip cần `pandas-ta`.
- `pip install -r requirements.txt` vào Python hệ thống thất bại (xung đột PyYAML do Debian cài). Repo cũng tự ghi nhận cài môi trường sạch bị **BLOCKED** do `coincurve`/cffi.

Kết luận: lõi tính toán ổn định, nhưng **người mới làm theo README sẽ không chạy được quickstart**. Tôi không chạy test mạng và không chạy PPO.

## 5. Điểm thiếu và rủi ro (xếp theo mức ảnh hưởng)

### Critical / quan trọng nhất

1. **Chưa có bằng chứng bot có lợi thế (edge).** Mọi kết quả đều là `AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED`. Mẫu 7 ngày: Trend và Breakout 0 lệnh, SMC fail-closed; Funding Arbitrage 1 basket lỗ −25,19 USDT; PPO holdout lỗ −477,11 USDT. Chưa từng chạy cửa sổ chuẩn 2021-01-01 → 2026-09-01 (`PROJECT_STATE.md`, mục G2 và Functional candidate).
2. **Funding replay bị chặn bởi sai lệch vài mili giây.** Trên mẫu 2026-08-20..26, chỉ 11/21 mốc funding "sẵn sàng chính xác", 10 mốc đến muộn 1–6 ms, nên toàn bộ funded replay FAIL_CLOSED. Đây là quyết định chính sách đang chờ bạn (ADR 0011): chừng nào chưa quyết, mọi backtest có funding trên dữ liệu thật đều không chạy được.
3. **Toàn bộ gate G0, G1, G2 đang chờ Tester và Independent Reviewer** từ ngày 22/09, gần một tháng chưa có ai làm. Quy trình cấm tự nghiệm thu, nên dự án đang đứng yên chủ yếu vì khâu này.

### Required (nên sửa)

4. **Mức rủi ro mặc định mâu thuẫn với breaker.** SMC mặc định `default_conviction: "high"` = 5% vốn mỗi lệnh (`config/strategies/smc_liquidity_sweep.yaml:11`), bằng đúng ngưỡng khoá 5%/24h (`default_config.yaml:24`): một lệnh SMC thua là khoá cả ngày. Tier `ultra_high` 10% (`default_config.yaml:16`) còn vượt mục tiêu drawdown dưới 10% của ý tưởng ban đầu chỉ với một lệnh. Đây là paper nên không mất tiền thật, nhưng nó làm méo thống kê (breaker kích hoạt liên tục) và sẽ nguy hiểm nếu sau này mang ra dùng thật. Đề xuất: SMC về `normal` (2%) hoặc thấp hơn, cân nhắc bỏ `ultra_high`. Việc này đổi ngữ nghĩa rủi ro nên cần bạn duyệt theo ADR.
5. **Cài đặt không khớp hướng dẫn.** `requirements.txt` thiếu `gymnasium`/`stable-baselines3`/`torch` nhưng test lõi và quickstart lại cần; ngược lại nó kéo theo jupyterlab, streamlit, plotly, mypy không dùng trong luồng chính. Phiên bản để `>=` nên mỗi lần cài ra môi trường khác nhau. README ghi Python 3.11–3.13, còn QA thực tế dùng 3.12 với lock riêng. Đề xuất: tách `requirements-core.txt` (đã pin), cho test RL tự skip khi thiếu gymnasium (`pytest.importorskip`), cập nhật README.
6. **File quá lớn, ôm nhiều trách nhiệm** (theo quy tắc "một file một lý do thay đổi"): `paper_broker.py` 1.586 dòng (khớp lệnh, funding, thanh lý, breaker, finalize), `trade_logger.py` 904, `invariant_checks.py` 896, `fetcher.py` 818. Hiện tests bảo vệ tốt nên chưa gấp, nhưng mỗi lần sửa broker đều rủi ro cao. Nên tách sau khi các gate hiện tại được nghiệm thu, không làm ngay.
7. **Web preview gõ số tay.** `web-preview/src/data/evidence.js` chép cứng số liệu và commit `23f9437…` cũ, không sinh từ artifact. Số trên web sẽ lệch dần với kết quả thật. Nên có một script xuất `evidence.json` từ report.

### Optional / Nit

8. `paper_broker.py:1414` và `:1423` dùng `datetime.now()` làm dự phòng khi finalize mà chưa xử lý nến nào. Không ảnh hưởng kết quả bình thường, nhưng trái với nguyên tắc "không dùng đồng hồ thật" của ADR 0006.
9. Hàm chuẩn hoá UTC bị viết lại ở nhiều nơi (`order_models._ensure_utc`, `circuit_breakers._ensure_utc_datetime`, `cache_manager.ensure_utc_index`). Nên gom về một chỗ.
10. Trend Following theo thiết kế ra rất ít lệnh. Charter đã cảnh báo: dù có dữ liệu 5,5 năm, số lệnh có thể không đủ cho thống kê; khi đó không được hạ ngưỡng sau khi đã xem OOS.

### Về quy trình và tài liệu

11. **Tài liệu nặng hơn tiến độ.** `PROJECT_STATE.md` và `PLANNER_HANDOVER.md` chồng nhiều checkpoint, mỗi cái kèm nhiều SHA và nhãn trạng thái. Người mới (hoặc chính bạn) khó trả lời nhanh câu "giờ bot đang ở đâu". Nên có một bảng trạng thái ngắn ở đầu file và chuyển lịch sử xuống `CHANGELOG`.
12. `AGENTS.md` có ghi chú workflow cho Codex (`wait_threads`, `$skill-name`). Với Claude thì phần đó không áp dụng được, nhưng không gây hại.

## 6. Đề xuất bước tiếp theo (theo thứ tự)

1. **Bạn quyết định chính sách funding đến muộn vài mili giây** (ví dụ: chấp nhận sai lệch ≤ 1 giây so với mốc 8h, hoặc giữ nguyên fail-closed). Đây là nút thắt chặn mọi replay có funding.
2. **Chạy review độc lập cho G0–G2.** Một phiên Claude riêng có thể làm Tester (chạy lại test và hash trên đúng commit) và một phiên khác làm Independent Reviewer (kiểm tra tính nhân quả và hạch toán), rồi bạn nghiệm thu.
3. **Sửa đường cài đặt** (mục 5) để quickstart chạy được trên máy sạch. Việc nhỏ, rủi ro thấp.
4. **Duyệt lại mức rủi ro mặc định** (mục 4) trước khi chạy dữ liệu dài, để kết quả không bị breaker làm méo.
5. **Tải dữ liệu chuẩn 2021–2026 và chạy Trend + Breakout** để có số lệnh thật theo năm và theo regime. Đây là lần đầu tiên dự án có câu trả lời thật về chiến lược.
6. **Chốt protocol đánh giá kinh tế trước khi mở OOS** (số lệnh tối thiểu, expectancy sau phí, drawdown tối đa). Charter có hai phương án đang chờ bạn chọn.
7. Sau đó mới đến G5: chạy paper trading với dữ liệu live và tối ưu hay tách code.

## 7. Mức độ tin cậy của báo cáo này

- Tôi đã đọc trực tiếp: `AGENTS.md`, `PROJECT_STATE.md`, `PLANNER_HANDOVER.md`, charter, capability matrix, config, engine, phần đầu fetcher và broker, web evidence. Tôi đã tự chạy bộ test offline (kết quả ở mục 4).
- Tôi **không** đọc hết từng dòng broker, risk và strategy, cũng không chạy PPO, test mạng hay backtest dữ liệu thật. Các con số hiệu suất ở mục 5.1 và 5.2 được trích từ tài liệu của repo, tôi chưa tự kiểm chứng.
