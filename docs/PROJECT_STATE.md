# PROJECT_STATE — Trạng thái Hiện tại của Dự án

> **Tài liệu trạng thái sống (Living Project State)**  
> Cập nhật lần cuối: 2026-09-28  
> Quy tắc: Tài liệu này **chỉ mô tả trạng thái hiện tại**. Toàn bộ nhật ký kiểm định, walkthrough và lịch sử phát triển chi tiết được lưu trữ tại [docs/history/](../docs/history/) và [docs/handover/](../docs/handover/).

---

## 1. Tóm tắt Trạng thái Hiện tại (Current Snapshot)

| Thông số | Trạng thái Hiện tại |
| :--- | :--- |
| **Giai đoạn dự án** | **Stage 06–11 Functional Complete & Local Paper Web Console Active** |
| **Nhánh tích hợp chính** | `main` (commit `fe1c1330d913e78239db575ff8433cf069fe1b01`) |
| **Nhánh làm việc hiện tại** | `codex/repository-information-architecture-cleanup` |
| **Chế độ giao dịch** | **PAPER TRADING ONLY** (mô phỏng, không API key, không nạp/rút, không ví tiền) |
| **Cơ sở dữ liệu giá** | Binance USD-M Futures public REST API + WebSocket (BTC, ETH, SOL) |
| **Kết quả kiểm thử baseline**| **450 passed, 2 skipped, 5 deselected** (Python pytest) + **16 passed** (Vitest Web UI) |

---

## 2. Tình trạng các Phân hệ (Subsystem Status)

### 2.1 Các phân hệ đã hoàn thành & đã nghiệm thu kỹ thuật (Completed Subsystems)
- [x] **Data Layer (Giai đoạn 1):** Kéo OHLCV, Open Interest, Funding Rate từ Binance public API; lưu trữ cache Parquet; Vision downloader cho dữ liệu lịch sử >28 ngày (ADR 0001, ADR 0004).
- [x] **Feature Engine (Giai đoạn 2):** Tính toán EMA, RSI, MACD, ATR, CVD phân kỳ nhân quả (ADR 0003), OI Delta có fallback (ADR 0005) và cấu trúc thị trường SMC.
- [x] **Risk Manager (Giai đoạn 3):** Tính kích thước lệnh theo % rủi ro cố định, Circuit Breaker 24h/streak (ADR 0002), đệm thanh lý an toàn (ADR 0006).
- [x] **Paper Execution Engine (Giai đoạn 4):** Động cơ khớp lệnh Isolated Margin 5 pha, hạch toán kế toán oracle, thanh toán funding 8h chính xác (ADR 0007).
- [x] **Trend Following Strategy (Giai đoạn 5):** Chiến lược xu hướng đa khung (tín hiệu 4h, khớp 15m) kèm stoploss dời theo swing causal (ADR 0008).

### 2.2 Các phân hệ đang hoạt động (Active & Candidate Subsystems)
- [x] **Trade Logger & Metrics Report (Giai đoạn 6):** Lưu sự kiện vào SQLite (`trades.sqlite`), xuất báo cáo đa định dạng (JSON, CSV, PNG) (ADR 0009).
- [x] **Breakout & Retest Strategy (Giai đoạn 7):** Chiến lược phá vỡ cản kèm kiểm định lại, hỗ trợ cả 2 chiều LONG và SHORT (ADR 0010).
- [x] **Funding Arbitrage Strategy (Giai đoạn 8):** Rổ kinh doanh chênh lệch funding Spot/Perpetual nguyên tử (ADR 0011).
- [x] **SMC Liquidity Sweep (Giai đoạn 9):** Quét thanh khoản, lệnh limit tại FVG, chốt lời đa tầng 40/30/30 (ADR 0012).
- [x] **Multi-Strategy Walk-Forward Engine (Giai đoạn 10):** So sánh đa chiến lược với tài khoản vốn phân lập cho từng fold.
- [x] **Reinforcement Learning Environment (Giai đoạn 11):** Môi trường Gymnasium + Stable-Baselines3 PPO hoàn chỉnh.
- [x] **Local Paper Web Console (Mới):** Ứng dụng web cục bộ chạy trên cổng 8765, tự động cập nhật nến BTC/ETH/SOL trực tiếp từ Binance WebSocket, hiển thị biểu đồ Candlestick và sổ lệnh mô phỏng.

---

## 3. Tài liệu Quy chuẩn Điều phối Dự án (Canonical Governance)

| Vai trò | Tài liệu Source of Truth |
| :--- | :--- |
| **Sổ tay AI Agent** | [AGENTS.md](../../AGENTS.md) |
| **Đặc tả Kỹ thuật gốc** | [docs/specs/CRYPTO_PAPER_TRADING_AGENT_MASTER_SPEC.md](specs/CRYPTO_PAPER_TRADING_AGENT_MASTER_SPEC.md) |
| **Kiến trúc Hệ thống** | [docs/architecture/SYSTEM_ARCHITECTURE.md](architecture/SYSTEM_ARCHITECTURE.md) |
| **Quy chuẩn Quyết định** | [docs/adr/](adr/) (ADR 0001 đến 0012) |
| **Điều lệ Sản phẩm & Gates** | [docs/planning/PRODUCT_CHARTER_AND_GATE_SPEC.md](planning/PRODUCT_CHARTER_AND_GATE_SPEC.md) |
| **Bản đồ Tài liệu tổng hợp** | [docs/INDEX.md](INDEX.md) |

---

## 4. Vấn đề Tồn đọng & Nợ Kỹ thuật (Known Blockers & Technical Debt)

1. **Millisecond-late Funding Source Timestamps (G2 Diagnostic):**
   - *Bối cảnh:* Một số sự kiện funding của sàn Binance đến trễ từ 1–6 ms so với mốc tròn giờ (00:00, 08:00, 16:00 UTC).
   - *Hành vi hiện tại:* Hệ thống tuân thủ nghiêm ngặt nguyên tắc **fail-closed** theo ADR 0011 (từ chối khớp lệnh nếu dữ liệu nguồn chưa đạt trạng thái sẵn sàng).
   - *Hướng xử lý:* Cần quyết định chính sách từ chủ dự án trước khi nới lỏng hoặc mô hình hóa độ trễ ms.
2. **Cài đặt môi trường độc lập với thư viện C:**
   - Cài đặt mới từ zero trên một số môi trường Windows có thể gặp lỗi build C extension (`coincurve`/cffi); môi trường kiểm thử QA Python 3.12 (`.venv-paper`) hiện tại chạy ổn định 100%.
3. **Nghiệm thu Độc lập (Independent Acceptance):**
   - Phân hệ Stage 6–11 và Web Preview đã hoàn thiện code và vượt qua author tests, nhưng vẫn chờ Tester và Independent Reviewer đánh giá chính thức trước khi tuyên bố nghiệm thu kinh tế (economic validation).

---

## 5. Kế hoạch Được phê duyệt Tiếp theo (Next Approved Work)

1. Duy trì tính ổn định của ứng dụng web cục bộ (`start-paper-web.cmd`) phục vụ quan sát thị trường realtime.
2. Thực hiện kiểm định độc lập cho chuỗi dữ liệu G2–G5.
3. Không thực hiện bất kỳ lệnh nạp/rút tiền thật, không kết nối API key trading.
