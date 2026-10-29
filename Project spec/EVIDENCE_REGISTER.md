# Sổ nguồn và khác biệt — 29/10/2026

## 1. Snapshot

- Nguồn GitHub chính: `65960bff7341637557d8158c2440dcc087ce1a41` trên main lúc đọc.
- Nguồn nhánh nghiên cứu: checkout cục bộ `codex/eth-btc-cointegration-v1` tại `05a396f`; code ORB commit `0a9d941`, Backtest Lab `47fdd6d`, cointegration `dc418d3`.
- Trong lúc khảo sát, checkout dùng chung chuyển sang main và có merge conflicts từ tích hợp nghiên cứu. Lượt tài liệu không giải quyết/stage/reset các thay đổi đó; cập nhật GitHub bằng commit chỉ gồm các trang tài liệu được liệt kê trong Git diff.
- Không sửa file trong synced `sources/`; không sửa `Initial idea/AGENT_SPEC.docx`.

## 2. Nguồn trên main (pin trước cập nhật)

| ID | Nguồn | Nội dung được dùng |
| --- | --- | --- |
| S1 | [Charter](https://github.com/Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING/blob/65960bff7341637557d8158c2440dcc087ce1a41/crypto-paper-agent/docs/planning/PRODUCT_CHARTER_AND_GATE_SPEC.md) | Ý định, authority, G0–G6, chronology và giới hạn |
| S2 | [PROJECT_STATE](https://github.com/Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING/blob/65960bff7341637557d8158c2440dcc087ce1a41/crypto-paper-agent/PROJECT_STATE.md) | Checkpoint tổng hợp, integrity, OI và lịch sử; nhãn được tác giả ghi sẵn |
| S3 | [Handoff tổng hợp](https://github.com/Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING/blob/65960bff7341637557d8158c2440dcc087ce1a41/crypto-paper-agent/docs/reviews/SYNTHESIZED_1Y_MULTI_ASSET_BACKTEST_HANDOFF.md) | 6.455 lifecycles, 10.892 slices, PnL, funding, costs, các tests được báo cáo |
| S4 | [Config tổng hợp](https://github.com/Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING/blob/65960bff7341637557d8158c2440dcc087ce1a41/crypto-paper-agent/config/strategies/synthesized.yaml) | So sánh ADX, exits, risk và vốn với S3 |
| S5 | [Runner tổng hợp](https://github.com/Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING/blob/65960bff7341637557d8158c2440dcc087ce1a41/crypto-paper-agent/scripts/run_synthesized_backtest.py) | CLI vốn, funding defaults/readiness, report pipeline |
| S6 | [Universe loader](https://github.com/Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING/blob/65960bff7341637557d8158c2440dcc087ce1a41/crypto-paper-agent/src/data_layer/universe_loader.py) | Cache/network/synthetic fallback và lưu cache |
| S7 | [Method search](https://github.com/Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING/blob/65960bff7341637557d8158c2440dcc087ce1a41/crypto-paper-agent/docs/research/2026-10-16-method-search.md) | Funding carry; sample, costs, seen-data và giới hạn |
| S8 | [Research integrity](https://github.com/Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING/blob/65960bff7341637557d8158c2440dcc087ce1a41/crypto-paper-agent/docs/operations/RESEARCH_INTEGRITY.md) | Preregistration, matched control, drawdown và selection bias |
| S9 | [ADR 0013 core](https://github.com/Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING/blob/65960bff7341637557d8158c2440dcc087ce1a41/crypto-paper-agent/docs/decisions/0013-owner-directed-core-hardening-2026-10-16.md), [ADR 0014](https://github.com/Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING/blob/65960bff7341637557d8158c2440dcc087ce1a41/crypto-paper-agent/docs/decisions/0014-owner-futures-risk-10pct-2026-10-16.md) | Scope-specific risk/funding policy; không biến 10% của một sleeve thành mặc định mọi run |

## 3. Nguồn nhánh nghiên cứu cục bộ

Các đường dẫn dưới đây là locator cho người tiếp nối, **không phải link tới main ở snapshot S1–S9**. Sau tích hợp phải xác minh commit và bytes trước khi cập nhật trạng thái.

| ID | Locator | Mức bằng chứng |
| --- | --- | --- |
| L1 | `crypto-paper-agent/docs/reports-vi/2026-10-22-eth-btc-cointegration-v1.md` và `docs/reviews/evidence/eth-btc-2026-10-22/` tại `05a396f` | Đọc báo cáo kết quả và source review đã lưu; không chạy lại |
| L2 | `crypto-paper-agent/docs/research/crypto-orb-portfolio.md`, config `config/research/crypto_orb_portfolio.yaml` tại `0a9d941` | Đặc tả runner nghiên cứu, không phải nghiệm thu |
| L3 | Workspace ngoài repo: `output/crypto-orb-10pairs-2026-10-29/BAO_CAO.md`, `independent-test.md`, `independent-review.md` | Báo cáo bản causal cuối được lưu cục bộ; artifact đầy đủ chưa nằm trên main snapshot |
| L4 | `crypto-paper-agent/docs/operations/BACKTEST_LAB.md`, `knowledge/` tại `05a396f` | Công cụ và wiki nhánh riêng; có metadata nguồn stale cần kiểm lại |

ORB base run ID: `454c57d409baba535b4b5011a1f786f833d249ace1a8906c4d2fb5fbb99bc236`.
Stress run ID: `6f6810167bbe8656704864eac0a84ca9916122e6d74b9dd69b4b405c2fddde8f`.
Chỉ `base-causal` và `stress-causal` là kết quả cuối theo L3; không dùng các bản trung gian.

## 4. Khác biệt chưa được phép tự san bằng

- S2 mở đầu với các giá trị funding/accounting bị mất ký tự; S3 ghi funding -43,51 USDT và discrepancy 1,55 × 10^-10. Dùng S3 để thuật lại nhưng chưa đối soát artifact.
- S3 ADX 25/exits 1,5R & 2,5R khác S4 ADX 20/exits 1R & 2R. S5 ghi đè vốn; không thể lấy YAML hiện tại làm config của lần chạy cũ.
- S3 mô tả lịch sử Binance, nhưng S6 hỗ trợ fallback synthetic và S5 dùng funding giả định khi thiếu. Manifest của lần chạy còn thiếu trong cây main được kiểm tra.
- Câu khuyến nghị maker tự tạo net positive không được số gross PnL âm của S3 hỗ trợ. Đây là giả thuyết thử nghiệm, không phải kết luận.
- Benchmark gốc 2021-01-01 → 2026-09-01, run tổng hợp năm 2025 và ORB tháng 09/2026 là các cửa sổ riêng; không thay lẫn nhau.
- Hai ADR cùng số 0013 có tên khác nhau trên main. Khi viện dẫn phải dùng cả filename, không chỉ số.

## 5. Cách bảo trì

Khi thay nguồn, giữ kết luận cũ có ngày, thêm checkpoint với SHA mới và nêu phần nào đã tái hiện. Muốn nâng từ AUTHOR_REPORTED/NOT_VERIFIED lên VERIFIED cần chỉ rõ người kiểm chứng, lệnh, môi trường và artifact. Người dùng quyết định nghiệm thu; Git commit hay test pass không thay thế quyết định đó.
