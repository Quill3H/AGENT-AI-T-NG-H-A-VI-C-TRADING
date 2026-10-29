<!-- wiki-meta {"id": "backtest-lab", "type": "project", "title": "Backtest Lab và tái lập kết quả", "updated_at": "2026-10-29", "source_ids": ["lab", "lab-review"], "verification": "AUTHOR_REPORTED", "page_ids": []} -->

# Backtest Lab và tái lập kết quả

CLI batch chạy các phương án khai báo; portfolio-config là luồng ORB bổ sung trong working tree hiện tại. Đọc đúng hướng dẫn phiên bản trước dùng. Cache theo nội dung giúp tránh chạy trùng, không chứng minh hiệu quả kinh tế.

Output mới, cache/output không chồng đầu vào/source/config. Báo cáo `comparison.json/csv/md` của batch giữ kết quả lỗi và không tự chọn người thắng. Review ngày 27/10 ghi các test trên phiên bản riêng; không coi đó là test trên dirty broker/ORB hôm nay.

Ví dụ batch: `python scripts/backtest_lab.py --data-dir <DATA> --batch <BATCH_YAML> --output <NEW_OUTPUT>`. Xem [[experiment-register]] và [[evidence-standard]].

## Nguồn

- [lab](<../../docs/operations/BACKTEST_LAB.md>), mục `Chế độ batch hiện có`; chưa commit hoặc đang sửa; xem SHA trong manifest.
- [lab-review](<../../docs/reviews/BACKTEST_LAB_2026_10_27.md>), mục `Author verification on final code`; đã tracked ở snapshot; xem SHA trong manifest.
