# PROJECT_STATE — Trạng thái Hiện tại của Dự án

> **Tài liệu trạng thái sống (Living Project State)**  
> Cập nhật lần cuối: 2026-09-28  
> Quy tắc: Tài liệu này **chỉ mô tả trạng thái hiện tại**. Toàn bộ nhật ký kiểm định, walkthrough và lịch sử phát triển chi tiết được lưu trữ tại [docs/history/](history/) và [docs/handover/](handover/).

---

## 1. Tóm tắt Trạng thái Hiện tại (Current Snapshot)

| Thông số | Trạng thái Hiện tại |
| :--- | :--- |
| **Giai đoạn dự án** | Stage 06–11 nghiên cứu/backtest; Local Paper Web đang kiểm định tích hợp |
| **Nhánh nền phát triển** | `codex/local-paper-futures-app` (PR #4 đã merge tại `9fd81e7`); `main` (`fe1c133`) chưa cập nhật theo nhánh này |
| **Trạng thái bản sửa** | PR #4 đã hợp nhất vào nhánh nền; tiếp tục kiểm định Windows và nguồn dữ liệu trước khi nghiệm thu vận hành |
| **Chế độ giao dịch** | **PAPER TRADING ONLY** (mô phỏng, không API key, không nạp/rút, không ví tiền) |
| **Nguồn dữ liệu thị trường** | Backend dùng public Binance USD-M Futures `/market` WebSocket và xác minh nến đóng qua REST; trình duyệt hiển thị stream riêng. Không có endpoint đặt lệnh sàn. |
| **Kết quả kiểm thử ứng viên**| Python offline: **507 passed, 4 skipped, 5 deselected** sau khi cài phụ thuộc RL/Torch CPU; nhóm paper: **76 passed, 2 skipped** (Windows trên Linux); web: **23 passed**, build đạt. Chưa chạy thực tế Windows hoặc stream Binance lâu dài. |

Candidate backend contract work is prepared on `codex/paper-futures-api-contract`
from base `codex/local-paper-futures-app` at
`d1cd95a726e12245ede22326e05b09990975ccd6`. It adds the read-only closed-candle
chart contract and backend-owned Trend Following decision states for review; it
is not merged into `main` or the base branch. The current host's offline run is
reported separately in the handoff because PPO dependencies remain unavailable.

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
- [ ] **Local Paper Web Console (ứng viên):** Backend stream public xác minh nến đóng qua REST và lưu journal/checkpoint; frontend React hiển thị giá live khi WebSocket còn tươi, hoặc giá nến đóng backend gần đây với nhãn riêng. Bằng chứng cũ/hỏng khóa `RECOVERY_REQUIRED`. Cần kiểm thử khởi động lại trên Windows và quan sát stream dài hạn trước khi nghiệm thu vận hành.

---

## 3. Tài liệu Quy chuẩn Điều phối Dự án (Canonical Governance)

| Vai trò | Tài liệu Source of Truth |
| :--- | :--- |
| **Sổ tay AI Agent** | [AGENTS.md](../AGENTS.md) |
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
2. **Cài đặt môi trường độc lập với thư viện C và Windows:**
   - Cài đặt mới từ zero trên một số môi trường Windows có thể gặp lỗi build C extension. Lịch chạy ở Windows, tự khởi động sau đăng nhập và xử lý gián đoạn điện/mạng chưa được xác minh trên máy chủ dự án.
3. **Nghiệm thu Độc lập (Independent Acceptance):**
   - Phân hệ Stage 6–11 và Web Preview đã hoàn thiện code và vượt qua author tests, nhưng vẫn chờ Tester và Independent Reviewer đánh giá chính thức trước khi tuyên bố nghiệm thu kinh tế (economic validation).

---

## 5. Kế hoạch Được phê duyệt Tiếp theo (Next Approved Work)

1. PR #4 đã merge vào `codex/local-paper-futures-app`; xác minh trên Windows với journal cũ/mới, tự khởi động và tái kết nối trước khi nghiệm thu vận hành.
2. Theo dõi dữ liệu public dài hạn và kiểm định độc lập G2–G5; hiệu quả kinh tế chưa được chứng minh.
3. [Dọn nhánh](planning/2026-09-28-branch-consolidation.md) đã hoàn tất: còn sáu nhánh trên GitHub gồm `main`, nhánh nền và bốn nhánh phân kỳ cần xem xét riêng; không merge vào `main` trong lượt này.
4. Không nạp/rút tiền thật hoặc kết nối API key trading.
