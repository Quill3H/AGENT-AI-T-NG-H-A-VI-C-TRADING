# Documentation Index & Architecture Map

Tài liệu này là bản đồ dẫn đường (Documentation Map) thống nhất cho toàn bộ repository. Mỗi tài liệu được định danh rõ mục đích và cấp bậc: **CANONICAL** (Source of Truth hiện hành) hoặc **HISTORICAL** (bằng chứng/lịch sử giai đoạn đã qua).

---

## 1. Bắt đầu từ đây (Start Here)

| Tài liệu | Loại | Mô tả |
| :--- | :--- | :--- |
| [AGENTS.md](../AGENTS.md) | **CANONICAL** | Sổ tay vận hành tối ưu cho AI Agent (quy tắc, boundaries, lệnh mẫu, routing map). |
| [README.md](../README.md) | **CANONICAL** | Điểm truy cập cho lập trình viên và người dùng (onboarding, setup, run, test). |
| [docs/PROJECT_STATE.md](PROJECT_STATE.md) | **CANONICAL** | Báo cáo trạng thái sống hiện hành của dự án, subsystems active, blockers và pending gates. |
| [docs/architecture/SYSTEM_ARCHITECTURE.md](architecture/SYSTEM_ARCHITECTURE.md) | **CANONICAL** | Tài liệu kiến trúc toàn diện của hệ thống paper trading (data pipeline, risk gate, execution, web stream). |
| [docs/specs/CRYPTO_PAPER_TRADING_AGENT_MASTER_SPEC.md](specs/CRYPTO_PAPER_TRADING_AGENT_MASTER_SPEC.md) | **CANONICAL** | Bản đặc tả kỹ thuật nền tảng điều khiển toàn bộ logic từ Giai đoạn 0 đến Giai đoạn 5+. |

---

## 1.1 Thứ bậc Ưu tiên Tài liệu & Xử lý Mâu thuẫn (Documentation Precedence)

Nếu xuất hiện sự khác biệt hoặc mâu thuẫn giữa các tài liệu trong repository:
1. **Accepted ADR hiện hành ([docs/adr/](adr/))** có giá trị cao nhất: supersede Master Spec ở quyết định cụ thể mà ADR đó đã thay đổi hoặc chuẩn hóa.
   *(Ví dụ thực tế: ADR 0002 quy định `recovery_mode = after_3_wins` — cần đúng 3 lệnh thắng liên tiếp để phục hồi 100% risk budget, ghi đè mô tả cũ `after_5_wins` / `after_1_win` trong Master Spec).*
2. **[docs/planning/PRODUCT_CHARTER_AND_GATE_SPEC.md](planning/PRODUCT_CHARTER_AND_GATE_SPEC.md)** điều khiển ranh giới sản phẩm, tiêu chí nghiệm thu (acceptance criteria) và gate pass/fail.
3. **[docs/PROJECT_STATE.md](PROJECT_STATE.md)** chỉ mô tả trạng thái hiện hành (current factual state), **không thay thế hay override** spec/ADR.
4. **Mã nguồn (`crypto-paper-agent/src/`) + Executable Tests (`crypto-paper-agent/tests/`)** phải triển khai đúng hợp đồng canonical hiện hành.
5. **Tài liệu lịch sử ([docs/history/](history/))** chỉ là hồ sơ lưu trữ bằng chứng kiểm định, **tuyệt đối không dùng làm Source of Truth** hiện hành.

---

## 2. Kiến trúc & Quyết định kỹ thuật (Architecture & ADRs)

| Tài liệu | Loại | Mô tả |
| :--- | :--- | :--- |
| [docs/architecture/SYSTEM_ARCHITECTURE.md](architecture/SYSTEM_ARCHITECTURE.md) | **CANONICAL** | Thiết kế kiến trúc tổng thể, luồng dữ liệu 5 pha, cơ chế isolated margin và WebSocket stream. |
| [docs/architecture/architecture-and-task-tree.md](architecture/architecture-and-task-tree.md) | **CANONICAL** | Sơ đồ Mermaid luồng code, ma trận đối chiếu 6 quan hệ cốt lõi và cây tác vụ phụ thuộc. |
| [docs/adr/0001-oi-hybrid-fetch.md](adr/0001-oi-hybrid-fetch.md) | **CANONICAL** | ADR 0001: Cơ chế kéo Open Interest kết hợp Vision archive (>28 ngày) và REST API (gần). |
| [docs/adr/0002-risk-recovery-mode.md](adr/0002-risk-recovery-mode.md) | **CANONICAL** | ADR 0002: Cơ chế phục hồi 100% risk budget sau đúng 3 lệnh thắng liên tiếp (`after_3_wins`). |
| [docs/adr/0003-anti-lookahead-cvd-divergence.md](adr/0003-anti-lookahead-cvd-divergence.md) | **CANONICAL** | ADR 0003: Chống lookahead bias cho phân kỳ CVD (xác nhận swing point tại nến $t = i + k$). |
| [docs/adr/0004-python-313-numpy-compatibility.md](adr/0004-python-313-numpy-compatibility.md) | **CANONICAL** | ADR 0004: Tương thích Python 3.12/3.13 với numpy >= 2.1.0, pandas >= 2.2.3 và fallback indicators. |
| [docs/adr/0005-oi-confluence-optional-fallback.md](adr/0005-oi-confluence-optional-fallback.md) | **CANONICAL** | ADR 0005: Cho phép OI confluence ở chế độ optional và fallback graceful khi gặp NaN. |
| [docs/adr/0006-circuit-breaker-and-risk-gate-refinements.md](adr/0006-circuit-breaker-and-risk-gate-refinements.md) | **CANONICAL** | ADR 0006: Chuẩn hóa 6 nguyên tắc rủi ro cứng (R1–R6, F1–F5, G1–G3) cho Circuit Breaker và liquidation. |
| [docs/adr/0007-paper-execution-engine-architecture.md](adr/0007-paper-execution-engine-architecture.md) | **CANONICAL** | ADR 0007: Kiến trúc Paper Execution Engine 5 pha, isolated margin và hạch toán kế toán oracle. |
| [docs/adr/0008-trend-following-and-backtest-engine-architecture.md](adr/0008-trend-following-and-backtest-engine-architecture.md) | **CANONICAL** | ADR 0008: Kiến trúc chiến lược Trend Following đa khung (4h/15m) và BacktestEngine tích hợp. |
| [docs/adr/0009-trade-logging-and-performance-reporting.md](adr/0009-trade-logging-and-performance-reporting.md) | **CANONICAL** | ADR 0009: Kiến trúc SQLite Trade Logger và Report Generator sinh artifact JSON/CSV/PNG. |
| [docs/adr/0010-research-strategies-and-rl-boundary.md](adr/0010-research-strategies-and-rl-boundary.md) | **CANONICAL** | ADR 0010: Ranh giới độc lập giữa phân hệ nghiên cứu (Breakout, SMC, RL/PPO) và live execution. |
| [docs/adr/0011-funded-basket-and-research-execution.md](adr/0011-funded-basket-and-research-execution.md) | **CANONICAL** | ADR 0011: Hạch toán rổ Funding Arbitrage spot/perp nguyên tử và kiểm tra exact funding readiness. |
| [docs/adr/0012-causal-smc-limits-and-partial-accounting.md](adr/0012-causal-smc-limits-and-partial-accounting.md) | **CANONICAL** | ADR 0012: Luật nhân quả cho SMC limit order, FVG và hạch toán chốt lời từng phần 40/30/30. |

---

## 3. Vận hành & Hướng dẫn sử dụng (Operations)

| Tài liệu | Loại | Mô tả |
| :--- | :--- | :--- |
| [docs/operations/QUICKSTART.md](operations/QUICKSTART.md) | **CANONICAL** | Hướng dẫn chạy nhanh CLI offline cho backtest, synthetic validation và PPO evaluation. |
| [docs/operations/LOCAL_PAPER_WEB.md](operations/LOCAL_PAPER_WEB.md) | **CANONICAL** | Hướng dẫn khởi chạy ứng dụng web paper trading nội bộ với Binance realtime public stream. |
| [docs/operations/CAPABILITY_MATRIX.md](operations/CAPABILITY_MATRIX.md) | **CANONICAL** | Ma trận năng lực các phân hệ, trạng thái kiểm thử và ranh giới chấp nhận kỹ thuật. |

---

## 4. Quản lý dự án & Lập kế hoạch (Planning & Gates)

| Tài liệu | Loại | Mô tả |
| :--- | :--- | :--- |
| [docs/planning/PRODUCT_CHARTER_AND_GATE_SPEC.md](planning/PRODUCT_CHARTER_AND_GATE_SPEC.md) | **CANONICAL** | Điều lệ sản phẩm, chuỗi nghiệm thu kỹ thuật G0–G5 và quy tắc cấm nhìn trước. |
| [docs/planning/PM_SKILL_MCP_ROUTING.md](planning/PM_SKILL_MCP_ROUTING.md) | **CANONICAL** | Ma trận điều phối kỹ năng và MCP server tương ứng cho từng tác vụ chuyên biệt. |
| [docs/planning/2026-09-23-main-sync-decision.md](planning/2026-09-23-main-sync-decision.md) | **CANONICAL** | Quyết định hợp nhất quy trình tích hợp nhánh `main` duy nhất của chủ dự án. |
| [docs/planning/2026-09-25-two-hour-web-preview.md](planning/2026-09-25-two-hour-web-preview.md) | **CANONICAL** | Hợp đồng timebox xây dựng bản preview web dashboard an toàn không API key. |
| [docs/planning/STAGE_06_11_REPAIR_MATRIX.md](planning/STAGE_06_11_REPAIR_MATRIX.md) | **SUPPORTING** | Ma trận kiểm tra và khắc phục lỗi kỹ thuật cho các giai đoạn 6–11. |
| [docs/superpowers/plans/](superpowers/plans/) | **SUPPORTING** | Thư mục lưu trữ các kế hoạch thực thi chi tiết cho từng gate cụ thể. |

---

## 5. Bàn giao & Tiếp nối công việc (Handover)

| Tài liệu | Loại | Mô tả |
| :--- | :--- | :--- |
| [docs/handover/PLANNER_HANDOVER.md](handover/PLANNER_HANDOVER.md) | **SUPPORTING** | Hồ sơ bàn giao tiến độ kỹ thuật, bằng chứng nghiệm thu và ngữ cảnh các phiên làm việc. |

---

## 6. Tài liệu Lịch sử & Bằng chứng kiểm thử (History & Archive)

| Thư mục / Tài liệu | Loại | Mô tả |
| :--- | :--- | :--- |
| [docs/history/founding/AGENT_SPEC.docx](history/founding/AGENT_SPEC.docx) | **HISTORICAL** | Tài liệu ý tưởng sáng lập ban đầu của tác giả (file Word nguyên bản). |
| [docs/history/reports/](history/reports/) | **HISTORICAL** | Báo cáo nghiệm thu từng chặng phát triển từ Giai đoạn 0 đến Giai đoạn 6–11. |
| [docs/history/reviews/](history/reviews/) | **HISTORICAL** | Báo cáo kiểm định độc lập của GPT Reviewer (Review 02, 03, 04, 05, 06, 07, 09). |
| [docs/history/walkthroughs/](history/walkthroughs/) | **HISTORICAL** | Các bài walkthrough chi tiết mã nguồn qua từng đợt sửa lỗi kiến trúc. |
| [docs/history/evidence/](history/evidence/) | **HISTORICAL** | Dữ liệu bằng chứng chạy mẫu, log replay, SQLite database và biểu đồ equity mẫu. |
