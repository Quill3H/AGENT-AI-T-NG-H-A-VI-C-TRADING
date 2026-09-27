# MASTER SPEC — Crypto Futures Paper-Trading Research Agent

> **Mục đích của file này:** Đây là bản đặc tả kỹ thuật đầy đủ để đưa trực tiếp cho **Google Antigravity** đọc và sinh mã nguồn. File này KHÔNG chứa hướng dẫn giao dịch thật, không kết nối ví thật, không đặt lệnh thật trên sàn — toàn bộ là **mô phỏng (paper trading / backtest)** trên dữ liệu thị trường thực.
>
> Vai trò phân chia: **Claude (tôi)** = người định hướng, thiết kế kiến trúc, review logic. **Antigravity** = công cụ viết code theo spec này. **Bạn** = người ra quyết định cuối cùng, review kết quả, quyết định có tiếp tục hay không.

---

## 0. GHI CHÚ REVIEW FILE GỐC (AGENT_SPEC.docx)

Trước khi đưa ra kế hoạch, dưới đây là các điểm cần lưu ý/sửa trong tài liệu nghiên cứu gốc bạn đã soạn. Tài liệu gốc rất tốt về mặt lý thuyết nhưng **thiếu một số chi tiết kỹ thuật bắt buộc phải có** để code được, và có vài chỗ cần làm rõ:

| # | Vấn đề trong file gốc | Vấn đề / rủi ro | Đề xuất chỉnh sửa |
|---|---|---|---|
| 1 | Công thức giá thanh lý chính xác (`P_liq = (OpeningValue - Margin) / (PositionSize × (1-MMR-Fee))`) | Công thức này là công thức **gần đúng tổng quát**, mỗi sàn (Binance, Bybit, OKX) có công thức thực tế hơi khác nhau và MMR còn phân theo bậc (tier) quy mô vị thế, không cố định | Trong code, để độ chính xác cao khi mô phỏng, nên **lấy bảng MMR tier thật từ API của sàn** (Binance có endpoint `leverageBracket`) thay vì hard-code MMR = 0.5% cho mọi quy mô |
| 2 | Circuit breaker "thua 3 lệnh liên tiếp → giảm 50% risk" | Không nói rõ **khi nào risk được phục hồi lại 100%** | Bổ sung rule: risk trở lại mức chuẩn sau 1 lệnh thắng liên tiếp, hoặc sau N ngày không vi phạm — cần Antigravity hỏi bạn chọn phương án khi code tới phần này |
| 3 | Bộ lọc tin tức (CPI, FOMC, NFP) | Không có nguồn dữ liệu lịch kinh tế được chỉ định | Cần chọn 1 nguồn: lịch kinh tế miễn phí (vd Trading Economics API free tier, hoặc file CSV lịch sử tự tạo thủ công cho các mốc lớn trong giai đoạn backtest) |
| 4 | Phân hệ 3 (SMC Liquidity Sweep) — định nghĩa FVG/Order Block | Mô tả đúng về lý thuyết nhưng **chưa đủ để code trực tiếp** (thế nào là "nến đảo chiều mạnh", ngưỡng % của BOS/CHoCH) | Cần định nghĩa ngưỡng số cụ thể (xem mục 4.3 bên dưới) trước khi Antigravity code phần này — đây là phân hệ rủi ro cao nhất về mặt "chủ quan hoá thành luật" |
| 5 | State Vector | Có OHLCV, OI, Funding, CVD nhưng chưa định nghĩa **tần suất cập nhật / độ trễ dữ liệu** khi backtest | Backtest phải dùng dữ liệu **đã đóng nến (closed candle)** tại mỗi bước, tuyệt đối không dùng dữ liệu tương lai (lookahead bias) — đây là lỗi phổ biến nhất khi build backtest, cần ghi rõ thành rule cứng |
| 6 | Reward function RL | Đầy đủ về mặt công thức nhưng **λ1, λ2 chưa có giá trị khởi tạo** | Đề xuất giá trị khởi tạo: λ1 = 0.5, λ2 = 1.0 (phạt vi phạm luật nặng hơn phạt drawdown) — sẽ tinh chỉnh bằng thực nghiệm |
| 7 | Toàn bộ tài liệu | Không có mục **Out of Scope** rõ ràng | Bổ sung ở mục 1.3 bên dưới — quan trọng để Antigravity không tự ý thêm tính năng kết nối API thật/đặt lệnh thật |
| 8 | Phí giao dịch | Nêu chung chung "0.05%-0.1%" | Cố định trong code: Taker fee = 0.05%, Maker fee = 0.02% (giá trị mặc định Binance Futures, có thể chỉnh trong config) |

➡️ **Kết luận review:** File gốc đủ tốt để làm **tài liệu tham chiếu lý thuyết**, nhưng bản thân nó KHÔNG phải là spec kỹ thuật thi công được. File MASTER SPEC này (bạn đang đọc) là bản dịch từ lý thuyết đó sang **spec kỹ thuật có thể code**, đã bổ sung toàn bộ các khoảng trống ở trên.

---

## 1. TỔNG QUAN DỰ ÁN

### 1.1 Mục tiêu
Xây dựng một hệ thống chạy **local trên máy cá nhân** có khả năng:
1. Lấy dữ liệu thị trường thực tế (BTC/USDT Futures) từ sàn Binance (public API, không cần API key).
2. Áp dụng một hoặc nhiều chiến lược giao dịch **cố định, có luật rõ ràng** (rule-based).
3. Mô phỏng việc mở/đóng lệnh futures (paper trading) bao gồm phí, funding rate, đòn bẩy, thanh lý.
4. Tự động tuân thủ các nguyên tắc quản trị rủi ro cứng (risk management hard rules).
5. Ghi log toàn bộ giao dịch giả lập theo chuẩn JSON.
6. Sinh báo cáo thống kê: win rate, expectancy, drawdown, Sharpe ratio... sau một khoảng thời gian backtest.
7. (Giai đoạn sau, optional) Huấn luyện một agent bằng Reinforcement Learning trên chính engine mô phỏng này.

### 1.2 Nguyên tắc thiết kế cốt lõi
- **Không có lookahead bias**: tại mỗi thời điểm t, agent chỉ được thấy dữ liệu đã đóng nến tính đến t, không được nhìn thấy tương lai.
- **Risk-first**: không có lệnh nào được mở mà không tính position size theo % rủi ro cố định và không có stop-loss.
- **Reproducible**: mọi backtest phải chạy lại được ra kết quả giống hệt (cố định random seed, dữ liệu cache local).
- **Config-driven**: toàn bộ tham số (risk %, leverage cap, ngưỡng RSI...) nằm trong file config, không hard-code trong logic, để dễ thử nghiệm nhiều bộ tham số.

### 1.3 OUT OF SCOPE (Antigravity KHÔNG được làm những việc sau)
- ❌ Không kết nối API key thật, không đặt lệnh thật lên bất kỳ sàn nào.
- ❌ Không lưu trữ hoặc yêu cầu nhập private key / seed phrase ví.
- ❌ Không tự động gửi lệnh ra sàn kể cả ở chế độ "testnet" trừ khi người dùng yêu cầu rõ ràng ở giai đoạn sau.
- ❌ Không đưa ra khuyến nghị đầu tư — đây thuần túy là công cụ nghiên cứu/kiểm thử ý tưởng (research tool).

---

## 2. TECH STACK

| Thành phần | Lựa chọn | Lý do |
|---|---|---|
| Ngôn ngữ | Python 3.11+ | Hệ sinh thái quant mạnh nhất |
| Lấy dữ liệu | `ccxt` | Hỗ trợ sẵn Binance Futures public endpoints, không cần API key cho dữ liệu public |
| Xử lý dữ liệu | `pandas`, `numpy` | Chuẩn ngành |
| Indicator kỹ thuật | `pandas-ta` | Có sẵn EMA/RSI/MACD/ATR, dễ dùng hơn TA-Lib (không cần compile C) |
| Lưu trữ cache dữ liệu | Parquet (`pyarrow`) | Nhanh, nhẹ hơn CSV nhiều lần |
| Lưu trữ log giao dịch | SQLite (`sqlite3`) + xuất JSON | Truy vấn dễ, vẫn giữ được format JSON theo yêu cầu |
| Config | YAML (`pyyaml`) | Dễ đọc, dễ Antigravity sinh/sửa |
| Dashboard kết quả (optional) | `streamlit` | Dựng nhanh, không cần biết frontend |
| Testing | `pytest` | Bắt buộc có unit test cho risk manager (phần quan trọng nhất) |
| Quản lý môi trường | `venv` + `requirements.txt` | Đơn giản, không cần Docker cho giai đoạn nghiên cứu cá nhân |

---

## 3. CẤU TRÚC THƯ MỤC DỰ ÁN (đưa nguyên vào Antigravity)

```
crypto-paper-agent/
├── README.md
├── requirements.txt
├── config/
│   ├── default_config.yaml          # toàn bộ tham số hệ thống
│   └── strategies/
│       ├── trend_following.yaml
│       ├── breakout_retest.yaml
│       ├── smc_liquidity_sweep.yaml
│       └── funding_arbitrage.yaml
├── data/
│   ├── raw/                         # cache dữ liệu thô (parquet)
│   └── processed/                   # dữ liệu đã tính indicator
├── src/
│   ├── data_layer/
│   │   ├── fetcher.py               # kéo OHLCV, OI, funding rate qua ccxt
│   │   └── cache_manager.py
│   ├── features/
│   │   ├── indicators.py            # EMA, RSI, MACD, ATR
│   │   ├── oi_features.py           # delta OI, phân kỳ giá-OI
│   │   ├── cvd.py                   # cumulative volume delta
│   │   └── smc_features.py          # FVG, Order Block, BOS/CHoCH detection
│   ├── strategies/
│   │   ├── base_strategy.py         # abstract class chung
│   │   ├── trend_following.py
│   │   ├── breakout_retest.py
│   │   ├── smc_liquidity_sweep.py
│   │   └── funding_arbitrage.py
│   ├── risk/
│   │   ├── position_sizing.py
│   │   ├── circuit_breakers.py
│   │   └── invariant_checks.py      # các hard rule bắt buộc
│   ├── execution/
│   │   ├── paper_broker.py          # engine mô phỏng khớp lệnh, funding, liquidation
│   │   └── order_models.py
│   ├── logging/
│   │   └── trade_logger.py          # xuất JSON theo schema chuẩn
│   ├── backtest/
│   │   └── engine.py                # vòng lặp event-driven chính
│   └── report/
│       └── metrics.py               # win rate, expectancy, drawdown, Sharpe
├── tests/
│   ├── test_position_sizing.py
│   ├── test_circuit_breakers.py
│   ├── test_liquidation_calc.py
│   └── test_no_lookahead.py         # test QUAN TRỌNG chống lookahead bias
├── notebooks/
│   └── exploratory_analysis.ipynb
└── run_backtest.py                  # entrypoint chính
```

---

## 4. ĐẶC TẢ CHI TIẾT TỪNG MODULE

### 4.1 Data Layer

**Input:** symbol (`BTC/USDT`), khung thời gian (`4h`, `15m`, `1m`), khoảng thời gian lịch sử.

**Output:** DataFrame với các cột tối thiểu:
```
timestamp, open, high, low, close, volume,
taker_buy_base_volume, open_interest, funding_rate
```

**Yêu cầu bắt buộc:**
- Cache dữ liệu về local (Parquet), không gọi lại API nếu đã có sẵn trong khoảng thời gian yêu cầu.
- Xử lý rate limit của Binance API (retry với backoff).
- Đồng bộ timestamp giữa 3 khung thời gian (4H/15M/1M) và dữ liệu OI/funding (funding chỉ có mỗi 8h, cần forward-fill hợp lý mà **không** leak dữ liệu tương lai).
- Ghi log rõ ràng nếu có khoảng trống dữ liệu (missing candles).

### 4.2 Feature Engine

Tính các chỉ báo sau, mỗi hàm nhận vào DataFrame OHLCV, trả về thêm cột:
- `ema_20`, `ema_50`, `ema_200`
- `rsi_14`
- `macd`, `macd_signal`
- `atr_14`
- `oi_delta_pct` (% thay đổi OI so với N nến trước, N cấu hình được)
- `cvd` (cumulative: `taker_buy_volume - taker_sell_volume`, cộng dồn)
- `cvd_divergence` (bullish/bearish/none) — so sánh đỉnh/đáy giá gần nhất với đỉnh/đáy CVD tương ứng trong cùng cửa sổ N nến

### 4.3 Định nghĩa cụ thể cho SMC (bổ sung phần thiếu trong file gốc)

Vì đây là phần "mơ hồ nhất" trong tài liệu gốc, cần chốt luật cụ thể trước khi code:

- **Swing High/Low:** một nến được coi là swing high nếu giá cao (high) của nó lớn hơn N nến liền trước và N nến liền sau (N mặc định = 3).
- **Liquidity Sweep:** giá (bằng bóng nến) vượt qua một swing high/low đã xác nhận trước đó, sau đó đóng nến quay trở lại bên trong vùng giá cũ.
- **BOS (Break of Structure):** giá đóng nến vượt qua swing high/low **cùng chiều xu hướng hiện tại**.
- **CHoCH (Change of Character):** giá đóng nến vượt qua swing high/low **ngược chiều xu hướng hiện tại** — tín hiệu đảo chiều tiềm năng.
- **Order Block:** nến ngược chiều cuối cùng (thân nến, không tính bóng) trước cụm nến tạo ra BOS/CHoCH.
- **FVG (Fair Value Gap):** mô hình 3 nến trong đó `low` của nến 1 > `high` của nến 3 (cho FVG giảm) hoặc `high` của nến 1 < `low` của nến 3 (cho FVG tăng).
- **Entry tại 50% FVG:** giá trung bình giữa mép trên và mép dưới của khoảng trống.

> Antigravity nên implement module `smc_features.py` theo đúng các định nghĩa số học ở trên — đây là phần cần unit test kỹ nhất vì dễ sai lệch logic.

### 4.4 Risk Manager (module quan trọng nhất — code trước tiên)

**Position sizing** (`position_sizing.py`):
```
risk_usd = account_equity * risk_percent
stop_distance = abs(entry_price - stop_price)
position_size_usd = risk_usd / (stop_distance / entry_price)
quantity = risk_usd / stop_distance
required_margin = position_size_usd / leverage
```

**Hard invariants** (`invariant_checks.py`) — mỗi lệnh trước khi được engine chấp nhận PHẢI pass toàn bộ các check sau, nếu fail thì **từ chối lệnh và ghi log lý do**:
1. `stop_loss_price is not None` — không có lệnh nào thiếu SL.
2. `leverage <= config.max_leverage` (mặc định 5x).
3. `abs(liquidation_price - stop_price) / entry_price >= 0.30` — khoảng cách thanh lý tối thiểu 30%.
4. `risk_percent <= tier_limit` theo conviction tier (1% / 2% / 5% / 10%).
5. Không mở lệnh mới nếu đang trong thời gian "khóa" do circuit breaker.
6. Không mở lệnh mới trong cửa sổ ±15 phút quanh sự kiện tin tức lớn (nếu module news filter được bật).

**Circuit breakers** (`circuit_breakers.py`):
- Theo dõi PnL ròng trong rolling 24h. Nếu lỗ ≥ 5% vốn → đóng toàn bộ vị thế mở, khóa trading 24h.
- Đếm chuỗi lệnh thua liên tiếp. Nếu ≥ 3 → giảm 50% risk_percent cho các lệnh tiếp theo.
- **[Điểm cần bạn quyết định]** Điều kiện phục hồi risk về mức chuẩn: đề xuất mặc định = sau 1 lệnh thắng liên tiếp. Antigravity nên implement dưới dạng tham số config `recovery_mode: "after_1_win"` để dễ đổi sau.

### 4.5 Paper Execution Engine (`paper_broker.py`)

Chạy theo kiểu **event-driven** (lặp qua từng nến theo thời gian, không vectorized), tại mỗi bước:
1. Cập nhật mark price = giá close của nến hiện tại.
2. Với các vị thế đang mở: kiểm tra có chạm SL/TP/liquidation không (theo thứ tự ưu tiên: liquidation > SL > TP, vì liquidation luôn được sàn ưu tiên xử lý trước).
3. Nếu tới mốc funding time (00:00, 08:00, 16:00 UTC theo chuẩn Binance): tính phí funding = position_notional × funding_rate, cộng/trừ vào equity.
4. Gọi strategy rulebook để kiểm tra tín hiệu mở lệnh mới (chỉ nếu không có vị thế đang mở theo hướng xung đột).
5. Nếu có tín hiệu: gọi risk manager để tính size và kiểm tra invariants, nếu pass thì mở lệnh giả lập (trừ phí taker/maker).
6. Ghi lại mọi hành động vào trade logger.

**Mô hình trượt giá (slippage):** áp dụng slippage cố định 0.02%-0.05% trên giá entry/exit (cấu hình được), để backtest không quá lạc quan.

### 4.6 Trade Logger

Xuất đúng theo JSON schema đã có trong file gốc của bạn (giữ nguyên, đã đúng chuẩn):
```json
{
  "trade_id": "SIM_BTC_20260918_001",
  "timestamp": 1789689600,
  "asset": "BTCUSDT",
  "direction": "LONG",
  "strategy_used": "SMC_LIQUIDITY_SWEEP",
  "conviction_tier": "HIGH_5_PERCENT",
  "entry_price": 70000.0,
  "stop_loss_price": 68600.0,
  "take_profit_levels": [72100.0, 74200.0],
  "nominal_position_size_usd": 25000.0,
  "leverage": 3.0,
  "margin_used_usd": 8333.33,
  "risk_amount_usd": 500.0,
  "risk_ratio_percent": 5.0,
  "estimated_liquidation_price": 47016.6,
  "market_context": {
    "oi_trend_4h": "RISING",
    "funding_rate_8h": 0.0001,
    "cvd_divergence": "BULLISH",
    "fvg_consequent_encroachment": true
  },
  "outcome": {
    "exit_price": 73500.0,
    "pnl_usd": 1250.0,
    "fees_paid_usd": 25.0,
    "net_return_percent": 14.7,
    "max_adverse_excursion_mae": 0.003,
    "max_favorable_excursion_mfe": 0.052,
    "rule_compliance": true
  }
}
```

### 4.7 Report & Metrics

Sau mỗi lần backtest, sinh báo cáo gồm:
- Tổng số lệnh, win rate, loss rate
- RRR trung bình thực tế
- Expectancy `E = W×R - L`
- Max Drawdown (%)
- Sharpe ratio (annualized)
- Số lần vi phạm circuit breaker
- Biểu đồ equity curve (matplotlib/plotly)
- So sánh kết quả với benchmark kỳ vọng trong bảng ma trận của tài liệu gốc (VD Trend Following kỳ vọng win rate 35-45%)

---

## 5. YÊU CẦU CHỐNG LOOKAHEAD BIAS (rất quan trọng — nguyên nhân #1 khiến backtest "ảo")

Antigravity phải đảm bảo:
- Tại bước thời gian `t`, mọi feature (EMA, RSI, OI...) chỉ được tính từ dữ liệu có timestamp `<= t`.
- Không sử dụng giá `close` của nến hiện tại để ra quyết định vào lệnh trong chính nến đó — quyết định dựa trên nến đã đóng, thực thi ở nến kế tiếp (hoặc dùng giá open của nến kế tiếp làm entry giả lập nếu dùng tín hiệu market order).
- Bắt buộc có 1 unit test riêng (`tests/test_no_lookahead.py`) shuffle ngẫu nhiên dữ liệu tương lai để đảm bảo thay đổi dữ liệu tương lai không ảnh hưởng tới quyết định quá khứ.

---

## 6. ROADMAP TRIỂN KHAI (đưa nguyên phần này cho Antigravity làm theo thứ tự)

### Giai đoạn 0 — Khởi tạo dự án
- [ ] Tạo cấu trúc thư mục như mục 3.
- [ ] Setup `requirements.txt`, virtualenv.
- [ ] File `default_config.yaml` với toàn bộ tham số mặc định (risk %, leverage cap, fee, slippage...).

### Giai đoạn 1 — Data Layer
- [ ] Viết `fetcher.py` kéo OHLCV 3 khung + OI + funding rate qua `ccxt`.
- [ ] Viết `cache_manager.py` lưu/đọc Parquet.
- [ ] Test: kéo 6 tháng dữ liệu BTC/USDT, kiểm tra không có khoảng trống bất thường.

### Giai đoạn 2 — Feature Engine
- [ ] Viết `indicators.py`, `oi_features.py`, `cvd.py`.
- [ ] Test unit cho từng indicator so với giá trị tính tay/thư viện tham chiếu.

### Giai đoạn 3 — Risk Manager (làm TRƯỚC strategy, vì mọi chiến lược đều phụ thuộc vào nó)
- [ ] `position_sizing.py`
- [ ] `invariant_checks.py`
- [ ] `circuit_breakers.py`
- [ ] Viết đầy đủ unit test — đây là phần bắt buộc phải test kỹ nhất trước khi đi tiếp.

### Giai đoạn 4 — Paper Execution Engine
- [ ] `paper_broker.py`, `order_models.py`
- [ ] Test: mô phỏng 1 lệnh long đơn giản tay (entry/SL/TP cố định) chạy qua vài trăm nến, kiểm tra kết quả PnL đúng bằng tay tính.

### Giai đoạn 5 — Phân hệ 1: Trend Following
- [ ] Implement theo đúng luật ở mục "Strategy Rulebook" trong file gốc.
- [ ] Chạy backtest full trên dữ liệu 2-3 năm BTC.
- [ ] So sánh kết quả với kỳ vọng win rate 35-45% trong bảng benchmark.

### Giai đoạn 6 — Trade Logger + Report
- [ ] `trade_logger.py` xuất đúng JSON schema.
- [ ] `metrics.py` sinh báo cáo đầy đủ.
- [ ] (Optional) Dashboard Streamlit đơn giản để xem equity curve.

### Giai đoạn 7 — Phân hệ 2: Breakout & Retest
- [ ] Implement + backtest + so sánh benchmark.

### Giai đoạn 8 — Phân hệ 4: Funding Arbitrage
- [ ] Implement (đơn giản hơn về logic entry, nhưng cần mô phỏng 2 chân lệnh song song).
- [ ] Backtest riêng vì cơ chế hoàn toàn khác (delta-neutral).

### Giai đoạn 9 — Phân hệ 3: SMC Liquidity Sweep (làm sau cùng — phức tạp nhất)
- [ ] Implement `smc_features.py` theo định nghĩa cụ thể ở mục 4.3.
- [ ] Implement strategy logic.
- [ ] Backtest trên khung 1M/5M (dữ liệu nặng hơn nhiều, cần tối ưu tốc độ).

### Giai đoạn 10 — Tổng hợp & So sánh đa chiến lược
- [ ] Chạy song song 4 phân hệ trên cùng giai đoạn dữ liệu, so sánh hiệu suất.
- [ ] Walk-forward testing: chia dữ liệu thành nhiều giai đoạn train/test để tránh overfit tham số.

### Giai đoạn 11 (Optional, nâng cao) — Reinforcement Learning
- [ ] Wrap engine giai đoạn 4 thành custom Gym environment.
- [ ] Implement reward function theo công thức trong file gốc (λ1=0.5, λ2=1.0 khởi tạo).
- [ ] Train bằng `stable-baselines3` (PPO hoặc SAC).

---

## 7. ĐỊNH DẠNG CONFIG MẪU (`default_config.yaml`)

```yaml
account:
  initial_equity_usd: 10000
  base_currency: USDT

risk:
  conviction_tiers:
    low: 0.01
    normal: 0.02
    high: 0.05
    ultra_high: 0.10
  max_leverage: 5
  min_liquidation_buffer_pct: 0.30

circuit_breakers:
  daily_loss_limit_pct: 0.05
  consecutive_losses_threshold: 3
  risk_reduction_on_streak: 0.5
  recovery_mode: after_1_win

fees:
  taker_pct: 0.0005
  maker_pct: 0.0002
  slippage_pct: 0.0003

data:
  symbol: BTC/USDT
  timeframes: ["4h", "15m", "1m"]
  exchange: binance
  start_date: "2022-01-01"
  end_date: "2026-09-01"

news_filter:
  enabled: true
  blackout_minutes_before: 15
  blackout_minutes_after: 15
  calendar_source: "manual_csv"   # cần bạn chuẩn bị file CSV các mốc CPI/FOMC/NFP trong giai đoạn backtest
```

---

## 8. ĐỊNH NGHĨA "XONG" (Definition of Done) CHO MỖI GIAI ĐOẠN

Một giai đoạn chỉ coi là hoàn thành khi:
1. Toàn bộ unit test liên quan pass.
2. Chạy được end-to-end không lỗi trên dữ liệu thật (không phải dữ liệu giả lập test).
3. Có ít nhất 1 báo cáo kết quả (report) xuất ra được, đọc hiểu được bằng mắt thường.
4. Không có cảnh báo lookahead bias từ test ở mục 5.

---

## 9. GỢI Ý PROMPT ĐỂ ĐƯA CHO ANTIGRAVITY

Khi bắt đầu, bạn có thể đưa nguyên văn cho Antigravity:

> "Đọc file `CRYPTO_PAPER_TRADING_AGENT_MASTER_SPEC.md` này. Hãy khởi tạo cấu trúc dự án đúng như mục 3, sau đó thực hiện lần lượt Giai đoạn 0 → Giai đoạn 4 theo roadmap ở mục 6. Sau mỗi giai đoạn, dừng lại và tóm tắt kết quả để tôi review trước khi làm giai đoạn tiếp theo. Tuyệt đối tuân thủ phần 'Out of Scope' ở mục 1.3 — không kết nối API key thật, không đặt lệnh thật."

Nên làm **từng giai đoạn một**, review kỹ output của Antigravity sau mỗi giai đoạn (đặc biệt Giai đoạn 3 - Risk Manager) trước khi cho đi tiếp, tránh để nó code một mạch toàn bộ hệ thống rồi mới phát hiện lỗi logic ở phần lõi.

---

## 10. CÁC ĐIỂM BẠN CẦN QUYẾT ĐỊNH TRƯỚC KHI BẮT ĐẦU (không thể tự động hoá)

1. Nguồn dữ liệu lịch kinh tế (CPI/FOMC/NFP) — tự chuẩn bị CSV hay bỏ qua news filter ở giai đoạn đầu?
2. Khoảng thời gian backtest (đề xuất tối thiểu 2 năm để đủ đa dạng regime thị trường: uptrend/downtrend/sideway).
3. Điều kiện phục hồi risk sau circuit breaker (mục 4.4).
4. Có làm Reinforcement Learning (Giai đoạn 11) hay dừng ở rule-based backtest?
