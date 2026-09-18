# Crypto Futures Paper-Trading Research Agent

> ⚠️ **Mục đích thuần túy nghiên cứu**: Hệ thống này chỉ mô phỏng giao dịch (paper trading / backtest) trên dữ liệu thị trường thực.
> KHÔNG kết nối API key thật, KHÔNG đặt lệnh thật lên bất kỳ sàn nào, KHÔNG lưu private key/seed phrase.

## Tổng quan

Hệ thống backtest chiến lược giao dịch BTC/USDT Futures trên Binance, bao gồm:
- **Data Layer**: Fetch OHLCV + OI + Funding Rate từ Binance public API (không cần API key)
- **Feature Engine**: EMA, RSI, MACD, ATR, CVD, OI Delta, SMC features
- **Risk Manager**: Position sizing, circuit breakers, hard invariants
- **Paper Execution Engine**: Mô phỏng khớp lệnh, funding, liquidation
- **4 Chiến lược**: Trend Following, Breakout & Retest, SMC Liquidity Sweep, Funding Arbitrage
- **Report**: Win rate, expectancy, Sharpe ratio, Max Drawdown, equity curve

## Cấu trúc thư mục

```
crypto-paper-agent/
├── README.md
├── requirements.txt
├── run_backtest.py              # Entrypoint
├── config/
│   ├── default_config.yaml     # Toàn bộ tham số hệ thống
│   └── strategies/
│       ├── trend_following.yaml
│       ├── breakout_retest.yaml
│       ├── smc_liquidity_sweep.yaml
│       └── funding_arbitrage.yaml
├── data/
│   ├── raw/                    # Cache dữ liệu thô (Parquet)
│   └── processed/              # Dữ liệu đã tính indicator
├── src/
│   ├── data_layer/             # fetcher.py, cache_manager.py
│   ├── features/               # indicators.py, oi_features.py, cvd.py, smc_features.py
│   ├── strategies/             # base_strategy.py + 4 strategies
│   ├── risk/                   # position_sizing.py, invariant_checks.py, circuit_breakers.py
│   ├── execution/              # paper_broker.py, order_models.py
│   ├── logging/                # trade_logger.py
│   ├── backtest/               # engine.py
│   └── report/                 # metrics.py
├── tests/
│   ├── test_position_sizing.py
│   ├── test_circuit_breakers.py
│   ├── test_liquidation_calc.py
│   └── test_no_lookahead.py    # CRITICAL: chống lookahead bias
└── notebooks/
    └── exploratory_analysis.ipynb
```

## Setup

```bash
# Tạo virtualenv
python -m venv venv

# Kích hoạt (Windows)
venv\Scripts\activate

# Cài dependencies
pip install -r requirements.txt

# Chạy tests
pytest tests/ -v

# Chạy backtest (sau Giai đoạn 4)
python run_backtest.py --strategy trend_following
```

## Khoảng thời gian backtest

- **Mặc định**: 2021-01-01 → 2026-09-01 (~5.5 năm)
- Bao phủ: bull run 2021, bear market 2022 (LUNA/FTX collapse), hồi phục 2023-2024, 2025-2026

## Nguyên tắc chống Lookahead Bias

- Tại bước thời gian `t`, mọi feature chỉ được tính từ dữ liệu có timestamp `<= t`
- Quyết định vào lệnh dựa trên **nến đã đóng**, thực thi ở **open nến kế tiếp**
- Funding rate được forward-fill tối đa 480 nến 1M (= 8h, 1 chu kỳ funding)
- Test tự động: `tests/test_no_lookahead.py` shuffle dữ liệu tương lai để verify

## Roadmap thực hiện

| Giai đoạn | Nội dung | Status |
|-----------|----------|--------|
| 0 | Khởi tạo dự án | ✅ Done |
| 1 | Data Layer (fetcher + cache) | ⬜ Todo |
| 2 | Feature Engine | ⬜ Todo |
| 3 | Risk Manager | ⬜ Todo |
| 4 | Paper Execution Engine | ⬜ Todo |
| 5 | Strategy: Trend Following | ⬜ Todo |
| 6 | Trade Logger + Report | ⬜ Todo |
| 7 | Strategy: Breakout & Retest | ⬜ Todo |
| 8 | Strategy: Funding Arbitrage | ⬜ Todo |
| 9 | Strategy: SMC Liquidity Sweep | ⬜ Todo |
| 10 | Tổng hợp & So sánh đa chiến lược | ⬜ Todo |
| 11 | Reinforcement Learning (Optional) | ⬜ Todo |

## Các quyết định đã chốt

| # | Quyết định | Giá trị đã chọn |
|---|-----------|----------------|
| 1 | News filter | Placeholder CSV, `enabled: false` cho giai đoạn đầu |
| 2 | Khoảng backtest | 2021-01-01 → 2026-09-01 |
| 3 | Circuit breaker recovery | `after_3_wins` (3 lệnh thắng liên tiếp) |
| 4 | Reinforcement Learning | Chưa ưu tiên, tập trung rule-based |
