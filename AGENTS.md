# AGENTS.md — AI Agent Operating Manual

Chào mừng AI Agent! Đây là cẩm nang vận hành chính thức giúp bạn nắm bắt dự án, tuân thủ các ranh giới an toàn và bắt tay vào công việc trong vòng 3 phút mà không cần đọc lại lịch sử hội thoại cũ.

---

## 1. Mục tiêu & Ranh giới Tuyệt đối (Project Mission & Boundaries)

- **Mục tiêu:** Hệ thống nghiên cứu định lượng và mô phỏng giao dịch hợp đồng tương lai tiền điện tử (Crypto Futures Paper Trading & Backtesting) trên dữ liệu sàn Binance.
- **Ranh giới an toàn tối cao (SAFETY BOUNDARY):**
  - **PAPER TRADING ONLY:** Hệ thống chỉ chạy mô phỏng trên bộ nhớ và database nội bộ.
  - **KHÔNG** kết nối API key thật, private key, seed phrase, chữ ký ví hay lệnh testnet/live.
  - **KHÔNG** merge nhánh `main`, không force-push, không rebase, không squash lịch sử Git.
  - **KHÔNG** thay đổi các nguyên tắc rủi ro hay logic giao dịch trừ khi có yêu cầu cụ thể từ chủ dự án.

---

## 2. Tài liệu Cốt lõi & Thứ bậc Ưu tiên (Source of Truth & Precedence)

Khi bắt đầu một phiên làm việc mới, hãy đọc theo thứ tự ưu tiên:
1. `AGENTS.md` (chính là file này — quy tắc vận hành tối cao).
2. [docs/PROJECT_STATE.md](docs/PROJECT_STATE.md) (trạng thái sống hiện hành của dự án).
3. [docs/INDEX.md](docs/INDEX.md) (bản đồ tài liệu toàn dự án).
4. [docs/architecture/SYSTEM_ARCHITECTURE.md](docs/architecture/SYSTEM_ARCHITECTURE.md) (kiến trúc tổng thể hệ thống).
5. [docs/specs/CRYPTO_PAPER_TRADING_AGENT_MASTER_SPEC.md](docs/specs/CRYPTO_PAPER_TRADING_AGENT_MASTER_SPEC.md) (đặc tả kỹ thuật chuẩn).
6. [docs/adr/](docs/adr/) (các quyết định kiến trúc từ ADR 0001 đến 0012).

### Thứ bậc Hiệu lực khi có mâu thuẫn tài liệu (Documentation Precedence):
- **Accepted ADR ([docs/adr/](docs/adr/))** có hiệu lực **ghi đè** Master Spec tại các điểm cụ thể mà ADR đó điều chỉnh.
  *(Ví dụ thực tế đã xảy ra: ADR 0002 định nghĩa `recovery_mode = after_3_wins` — cần đúng 3 lệnh thắng liên tiếp để phục hồi 100% risk budget, ghi đè đề xuất gốc `after_1_win` trong Master Spec).*
- **[docs/planning/PRODUCT_CHARTER_AND_GATE_SPEC.md](docs/planning/PRODUCT_CHARTER_AND_GATE_SPEC.md)** có hiệu lực cao nhất về acceptance criteria và gate pass/fail.
- **[docs/PROJECT_STATE.md](docs/PROJECT_STATE.md)** chỉ mô tả trạng thái hiện hành, **không thay thế hay override** spec/ADR.
- **Mã nguồn (`crypto-paper-agent/src/`) + Executable Tests (`crypto-paper-agent/tests/`)** là hiện thực hóa của các hợp đồng kỹ thuật.
- **Tài liệu trong [docs/history/](docs/history/)** chỉ là hồ sơ lịch sử, **tuyệt đối không dùng làm Source of Truth** hiện hành.

> **Lưu ý Token / Context:** Bạn **KHÔNG CẦN** đọc thư mục `docs/history/` (chứa các báo cáo và review cũ) để hiểu hệ thống hiện tại. Chỉ tra cứu `docs/history/` khi cần bằng chứng lịch sử cụ thể.

---

## 3. Bản đồ Điều phối Tác vụ (Agent Task Routing Map)

> **Hướng dẫn CWD đồng bộ:** Toàn bộ đường dẫn code và test dưới đây được chuẩn hóa theo **Repository Root** (tiền tố `crypto-paper-agent/`).  
> Khi thực thi: chạy từ repo root kèm tiền tố, hoặc `cd crypto-paper-agent` rồi chạy `tests/...`.

| Loại Tác vụ | 1. Đọc Tài liệu này trước | 2. Code tương ứng tại | 3. Chạy Tests tương ứng (từ repo root) |
| :--- | :--- | :--- | :--- |
| **Data Layer** | [ADR 0001](docs/adr/0001-oi-hybrid-fetch.md), [ADR 0005](docs/adr/0005-oi-confluence-optional-fallback.md) | `crypto-paper-agent/src/data_layer/` | `crypto-paper-agent/tests/test_data_layer.py`, `crypto-paper-agent/tests/test_public_data_pipeline.py` |
| **Features & Indicators**| [ADR 0003](docs/adr/0003-anti-lookahead-cvd-divergence.md), [ADR 0004](docs/adr/0004-python-313-numpy-compatibility.md) | `crypto-paper-agent/src/features/` | `crypto-paper-agent/tests/test_indicators.py`, `crypto-paper-agent/tests/test_cvd.py`, `crypto-paper-agent/tests/test_no_lookahead.py` |
| **Strategies** | [Master Spec §4](docs/specs/CRYPTO_PAPER_TRADING_AGENT_MASTER_SPEC.md), [ADR 0008](docs/adr/0008-trend-following-and-backtest-engine-architecture.md), [ADR 0011](docs/adr/0011-funded-basket-and-research-execution.md), [ADR 0012](docs/adr/0012-causal-smc-limits-and-partial-accounting.md) | `crypto-paper-agent/src/strategies/` | `crypto-paper-agent/tests/test_trend_following_strategy.py`, `crypto-paper-agent/tests/test_breakout_retest.py`, `crypto-paper-agent/tests/test_smc_liquidity_sweep.py`, `crypto-paper-agent/tests/test_funding_arbitrage.py` |
| **Risk Management** | [ADR 0002](docs/adr/0002-risk-recovery-mode.md), [ADR 0006](docs/adr/0006-circuit-breaker-and-risk-gate-refinements.md) | `crypto-paper-agent/src/risk/` | `crypto-paper-agent/tests/test_position_sizing.py`, `crypto-paper-agent/tests/test_circuit_breakers.py`, `crypto-paper-agent/tests/test_invariant_checks.py`, `crypto-paper-agent/tests/test_liquidation_calc.py` |
| **Paper Execution** | [ADR 0007](docs/adr/0007-paper-execution-engine-architecture.md) | `crypto-paper-agent/src/execution/` | `crypto-paper-agent/tests/test_paper_broker.py`, `crypto-paper-agent/tests/test_execution_accounting.py`, `crypto-paper-agent/tests/test_execution_no_lookahead.py`, `crypto-paper-agent/tests/test_g0_settlement_lifecycle.py` |
| **Trade Logger & Metrics**| [ADR 0009](docs/adr/0009-trade-logging-and-performance-reporting.md) | `crypto-paper-agent/src/logging/`, `crypto-paper-agent/src/report/` | `crypto-paper-agent/tests/test_trade_logger.py`, `crypto-paper-agent/tests/test_report_metrics.py`, `crypto-paper-agent/tests/test_report_generator.py` |
| **Realtime Web Console** | [docs/operations/LOCAL_PAPER_WEB.md](docs/operations/LOCAL_PAPER_WEB.md) | `crypto-paper-agent/src/paper/`, `crypto-paper-agent/web-preview/` | `crypto-paper-agent/tests/test_local_paper_server.py`, `crypto-paper-agent/tests/test_local_paper_session.py`, `npm test` trong `crypto-paper-agent/web-preview` |
| **Reviewer / Verifier** | `docs/PROJECT_STATE.md`, spec/ADR liên quan, `git diff` | Toàn bộ repo liên quan | `pytest -q -m "not network"` (trong `crypto-paper-agent`), `npm test` (trong `crypto-paper-agent/web-preview`) |

---

## 4. Các Bất Biến Kỹ Thuật Bắt Buộc (Critical Invariants)

1. **Tuyệt đối không nhìn trước (Zero-Lookahead):**
   - Chỉ tính indicator trên nến đã đóng ($timestamp \le t$).
   - Tín hiệu sinh tại giá đóng nến $t$, thực thi tại giá mở nến $t+1$.
   - Phân kỳ CVD tại nến $i$ chỉ được công nhận tại nến $t = i + 3$, không gán ngược quá khứ.
2. **Kỷ luật Rủi ro & Cắt lỗ (Risk Invariants):**
   - Mọi vị thế bắt buộc có giá Stop Loss; đòn bẩy tối đa 5×; rủi ro tối đa cố định theo % vốn khả dụng.
   - Circuit Breaker: khóa 24h nếu lỗ quá 5%/ngày; giảm 50% risk sau 3 lệnh thua liên tiếp; phục hồi sau đúng 3 lệnh thắng liên tiếp.
3. **Thanh toán Funding & Hạch toán (Funding & Accounting):**
   - Funding thanh toán tại 00:00, 08:00, 16:00 UTC. Nếu dữ liệu funding chưa sẵn sàng $\to$ **FAIL-CLOSED** (không vào lệnh).
   - Kế toán oracle: bảo toàn công thức $Equity = Cash + Margin + UnrealizedPnL$.

---

## 5. Lệnh Thường Dùng (Essential Commands)

Tất cả lệnh Python đều thực thi với môi trường ảo tại `crypto-paper-agent/.venv-paper`:

```powershell
# 1. Chạy toàn bộ test suite Python (không bao gồm test mạng)
cd crypto-paper-agent
.\.venv-paper\Scripts\python.exe -m pytest -q -m "not network"

# 2. Chạy test có mục tiêu (ví dụ Risk & Execution)
.\.venv-paper\Scripts\python.exe -m pytest tests/test_circuit_breakers.py tests/test_paper_broker.py -v

# 3. Chạy test frontend Web UI
cd web-preview
npm test

# 4. Chạy nhanh ứng dụng Web Paper Trading nội bộ
cd ../..
.\start-paper-web.cmd
```

---

## 6. Quy chuẩn Đóng gói Công việc (Definition of Done)

Trước khi bàn giao hoặc tạo commit mới:
1. [ ] **Tests pass:** Chạy `pytest -q -m "not network"` đảm bảo không có bất kỳ regression nào so với baseline (450 passed, 2 skipped, 5 deselected).
2. [ ] **Web tests pass:** Nếu có chỉnh sửa frontend, chạy `npm test` (16 passed).
3. [ ] **Không leak secret:** Không commit file cấu hình chứa API key hay dữ liệu nhạy cảm.
4. [ ] **Git history:** Không force-push hay xóa branch; commit có prefix chuẩn (`feat`, `fix`, `docs`, `refactor`, `chore`).
5. [ ] **Cập nhật trạng thái:** Nếu hoàn thành một milestone kỹ thuật, cập nhật [docs/PROJECT_STATE.md](docs/PROJECT_STATE.md).
