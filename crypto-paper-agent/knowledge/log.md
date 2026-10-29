# Nhật ký wiki

## [2026-10-29] ingest | Seed nguồn dự án

Đọc 11 nguồn, tạo 17 trang có metadata; chưa chạy lại backtest hoặc xác minh lợi nhuận. Graph và test ghi ở báo cáo kiểm chứng.

## [2026-10-29] lint | Kiểm chứng triển khai wiki

CLI và graph focused: 58 passed, 2 skipped (máy không cho tạo symlink/junction). Hồi quy offline tách graph fixture: 775 passed, 6 skipped, 5 network deselected; graph fixture 14 passed riêng. Không cộng số test bị trùng giữa các lượt. Nguồn giữ 11 hash đúng; 17 trang. Hai lỗi adapter do reviewer phát hiện đã có regression fix. Cảnh báo encoding ở test cũ đã recheck UTF-8 với -W error: 1 passed. Báo cáo và giới hạn xem docs/reviews/RESEARCH_WIKI_2026_10_29.md tính từ package. Dashboard remote chưa được phép chạy.

## [2026-10-29] ingest | QuantDinger và TradingAgents

Nhập 3 báo cáo nguyên bytes vào docs/research/external-repos, đăng ký 3 nguồn có SHA-256 và ngày/commit khảo sát; thêm 3 hồ sơ tổng hợp và mục lục. Wiki từ 17 lên 20 trang, từ 11 lên 14 nguồn. Giữ AUTHOR_REPORTED; chưa chạy repo ngoài hoặc xác minh lợi nhuận. Không sửa engine/risk/dataset. Kết quả kiểm tra nhập nguồn và graph ghi ở docs/reviews/EXTERNAL_REPO_INGEST_2026_10_29.md (tính từ package).

Kiểm tra nhập: lint/check-sources/handoff-check đều 0 findings (20 trang/14 nguồn); tìm TradingAgents có kết quả. Ba báo cáo khớp SHA-256 bản gốc; 5 file tracked dirty trước lượt này giữ nguyên hash. Graph wiki có đủ ba trang mới, 43 nodes/127 edges và 0 dangling edges. Graph code trước đó stale do scripts/build_wiki_graph.py đã đổi ngoài lượt nhập; đã dựng lại từ bytes hiện có, vẫn PARTIAL_STATIC. Không chạy lại test/backtest vì không sửa hành vi mã.
