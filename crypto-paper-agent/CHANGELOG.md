# CHANGELOG - Crypto Paper-Trading Research Agent

Toàn bộ lịch sử cập nhật và hoàn thành các giai đoạn theo [CRYPTO_PAPER_TRADING_AGENT_MASTER_SPEC.md](file:///D:/Ta%CC%80i%20lie%CC%A3%CC%82u/Default%20Project/Project%20spec/CRYPTO_PAPER_TRADING_AGENT_MASTER_SPEC.md).

---

## [Giai đoạn 3] - Risk Manager (2026-09-18)
### Đã triển khai
- `src/risk/position_sizing.py`: Tính toán Position Size, Required Margin, Stop Distance, Quantity; xử lý ngoại lệ chia cho 0 khi stop == entry và validation input.
- `src/risk/invariant_checks.py`:
  - Tra cứu MMR tier và `cumulative_maintenance_amount` theo `leverage_brackets` cho BTCUSDT.
  - Tính toán giá thanh lý `estimated_liquidation_price` theo chuẩn Binance Futures Isolated Margin (LONG & SHORT).
  - Kiểm tra toàn diện 6 Hard Invariants (Stop-Loss, Leverage Cap, Min Liquidation Buffer 30%, Conviction Tier Limits, Circuit Breaker Lock, News Blackout Window); LUÔN trả về toàn bộ danh sách lỗi vi phạm (không dừng ở lỗi đầu tiên).
- `src/risk/circuit_breakers.py`:
  - Quản lý trạng thái `CircuitBreakerState` với cửa sổ trượt rolling 24h PnL.
  - Tự động kích hoạt khóa 24h khi lỗ rolling 24h $\ge 5\%$ vốn hiện tại.
  - Tự động giảm risk xuống 50% (`risk_multiplier = 0.5`) khi thua liên tiếp $\ge 3$ lệnh.
  - Phục hồi 100% risk sau đúng 3 lệnh thắng liên tiếp (`recovery_mode: "after_3_wins"`, ADR 0002).
  - Xử lý reset chuỗi thắng về 0 nếu có lệnh thua xen ngang trong giai đoạn phục hồi.
  - Tự động mở khóa khi thời gian khóa 24h kết thúc.
- `src/risk/__init__.py`: Export subsystem Risk Manager.
- `tests/test_position_sizing.py`: 10 unit tests cho công thức tính tay, biên số học và bắt ngoại lệ.
- `tests/test_liquidation_calc.py`: 6 unit tests tra cứu qua 4 MMR tiers và công thức giá thanh lý Long/Short.
- `tests/test_circuit_breakers.py`: 5 unit tests cho 5 kịch bản ngắt mạch, chuỗi thua/thắng và khóa 24h.
- `tests/test_invariant_checks.py`: 11 unit tests cho 6 invariants riêng biệt, all-pass và multiple-fails.
- Script mô phỏng trực quan `scripts/simulate_risk_manager_10_trades.py` chạy qua 10 lệnh giả lập liên tiếp, in bảng ASCII chi tiết.
- Báo cáo chi tiết `BÁO CÁO TÓM TẮT/GIAI ĐOẠN 3/BAO_CAO_GIAI_DOAN_3.md`.
### Kết quả kiểm thử
- **Pytest:** 85/85 tests PASSED (100% xanh) trong 25.17s (32 test mới của Giai đoạn 3).
- **Mô phỏng 10 lệnh:** Chạy thông suốt qua đầy đủ các trạng thái (duyệt lệnh, từ chối lệnh do vi phạm invariant, giảm 50% risk sau 3 loss, khóa 24h khi lỗ 5%, từ chối do khóa, mở khóa và phục hồi 100% risk sau 3 win).

---

## [Giai đoạn 2] - Feature Engine (2026-09-18)
### Đã triển khai
- `src/features/indicators.py`: Tính toán EMA (20/50/200), RSI (14), MACD (12/26/9), ATR (14) từ cấu hình động; hỗ trợ 2 tầng (pandas-ta + pure pandas fallback theo chuẩn TA-Lib).
- `src/features/oi_features.py`: Tính `% thay đổi Open Interest (oi_delta_pct)` với cơ chế lan truyền NaN và tương thích `oi_confluence`.
- `src/features/cvd.py`: Tính Cumulative Volume Delta (`cvd`) và phát hiện phân kỳ CVD (`cvd_divergence`) với cơ chế chống Lookahead Bias 100% (xác nhận trễ $k=3$ nến, không backfill).
- `src/features/__init__.py`: Export toàn bộ hàm và pipeline tích hợp `add_all_features`.
- Nâng cấp `src/data_layer/fetcher.py`: Trích xuất trực tiếp `taker_buy_base_volume` thực từ Binance Futures klines endpoint.
- `tests/test_indicators.py`: Kiểm thử toán học EMA, RSI, MACD, ATR và so sánh chéo fallback.
- `tests/test_oi_features.py`: Kiểm thử công thức và lan truyền NaN.
- `tests/test_cvd.py`: Kiểm thử cộng dồn CVD và nhận diện 2 kịch bản phân kỳ Bullish/Bearish mẫu.
- `tests/test_no_lookahead.py`: Kiểm thử xáo trộn dữ liệu tương lai sau điểm $T$, chứng minh tính bất biến nhân quả.
- Script thực nghiệm `scripts/verify_stage2_real_data.py` và báo cáo `BÁO CÁO TÓM TẮT/GIAI ĐOẠN 2/BAO_CAO_CLAUDE_REVIEW_GIAI_DOAN_2.md`.
### Kết quả kiểm thử
- **Pytest:** 53/53 tests PASSED (100%) trong 11.90s.
- **Thực nghiệm dữ liệu thật Binance (70 ngày BTC/USDT):** Khung 4H (420 nến, 52.6% đầy đủ sau warm-up EMA200); Khung 15M (6,720 nến, 97.0% đầy đủ). Phân kỳ CVD hoạt động chuẩn xác.

---

## [Giai đoạn 1] - Data Layer (2026-09-18)
### Đã triển khai
- `src/data_layer/fetcher.py`: Kéo dữ liệu OHLCV, Funding Rate và cơ chế Hybrid Open Interest từ Binance Futures API qua `ccxt`.
- `src/data_layer/binance_vision_downloader.py`: Tải dữ liệu OI lịch sử sâu từ Binance Data Vision (`data.binance.vision`), giải nén, parse và downsample về 4h/15m/1m bằng forward-fill.
- `src/data_layer/cache_manager.py`: Quản lý lưu trữ/đọc cache Parquet local, kiểm tra khoảng trống dữ liệu (`detect_gaps`), hàm public `ensure_utc_index` và `timeframe_to_timedelta`.
- `src/features/news_calendar.py`: Quản lý lịch kinh tế CSV với log warning chi tiết (không nuốt lỗi).
- Cấu hình `oi_confluence` mode `optional` và `fallback_when_nan: true`.
### Kết quả kiểm thử
- **Pytest:** 28/28 tests PASSED (100%) trong 14.06s.
- **Thực nghiệm dữ liệu thật Binance:** Tải trơn tru 60 ngày dữ liệu không còn NaN ở đuôi.

---

## [Giai đoạn 0] - Khởi tạo dự án & Cấu hình (2026-09-18)
### Đã triển khai
- Thiết lập cấu trúc thư mục module hóa: `src/data_layer`, `src/features`, `src/risk_manager`, `src/execution`, `src/strategies`, `src/analytics`, `config/`, `tests/`, `data/`.
- File cấu hình trung tâm `config/default_config.yaml` và các config chiến lược mẫu (`trend_following.yaml`, `smc_liquidity_sweep.yaml`).
- Chốt 4 quyết định kỹ thuật: `news_filter.enabled: false`, `start_date: "2021-01-01"`, `recovery_mode: "after_3_wins"`, loại bỏ hoàn toàn phần thừa RL.
- Cập nhật `requirements.txt` tương thích Python 3.13 (`numpy>=2.1.0`).
