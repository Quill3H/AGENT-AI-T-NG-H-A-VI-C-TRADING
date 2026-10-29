# Backtest Lab — chạy lại tiết kiệm trên dữ liệu cố định

## Danh mục crypto ORB + FVG

Đã có chế độ dùng chung tài khoản cho 10 cặp crypto, nhiều lệnh mỗi ngày,
tối đa 4 vị thế đồng thời. Lệnh chờ giữ chỗ; các coin xử lý đồng bộ theo
từng pha để kết quả cuối phút không ảnh hưởng lệnh khớp đầu phút.

```powershell
python scripts/backtest_lab.py --data-dir <THU_MUC_ZIP_VISION> --portfolio-config config/research/crypto_orb_portfolio.yaml --output <THU_MUC_KET_QUA_MOI> --cache-dir <THU_MUC_CACHE>
```

Chọn `--portfolio-config` hoặc `--batch`. Chế độ danh mục đọc ZIP 1m/15m,
funding và CHECKSUM; giữ phí, kế toán và ngắt mạch của PaperBroker. Báo cáo
60 lệnh/tuần đầy đủ và 240 lệnh/tháng đầy đủ là tiêu chí đủ mẫu; không ép
vào lệnh hoặc nới bộ lọc để đạt số lượng. Xem [quy tắc, giới hạn mô phỏng và
đầu ra](../research/crypto-orb-portfolio.md). Các phần bên dưới mô tả chế độ
`--batch` hiện có, chạy các tài khoản riêng.

## Chế độ batch hiện có

Từ thư mục crypto-paper-agent, dùng Python đã cài các thư viện của dự án:

```powershell
python scripts/backtest_lab.py --list-strategies
python scripts/backtest_lab.py --data-dir market-data/eth-btc-v1 --batch config/research/backtest_lab.example.yaml --output artifacts/lab-001
# Chạy lại cùng đầu vào, chọn thư mục báo cáo mới: kết quả lấy từ cache.
python scripts/backtest_lab.py --data-dir market-data/eth-btc-v1 --batch config/research/backtest_lab.example.yaml --output artifacts/lab-002
```

Mỗi phương án trong YAML có tên, chiến lược, coin và ngày bắt đầu/kết thúc.
Có thể thêm `configs: [my-variant.yaml]` để thay tham số theo định dạng cấu hình
hiện có; đường dẫn tính từ vị trí file YAML. Mỗi bộ tham số là một dòng thử
riêng trong `jobs`. `cost_multiplier: 2` nhân phí và trượt giá hai lần theo
runner hiện có. Các phương án giữ nguyên thứ tự, không tự chọn phương án thắng.

Kết quả nằm trong thư mục mới: comparison.md để đọc, comparison.csv để mở
bằng Excel, comparison.json chứa toàn bộ chỉ số, cấu hình và dấu vân tay.
`OK` nghĩa là chạy được; `ERROR` kèm lý do và không được lưu thành kết quả tốt.
Không có lệnh thì ghi 0 lệnh theo runner, không coi đó là bằng chứng hiệu quả.
Mã thoát: 0 = tất cả chạy được; 1 = có phương án lỗi nhưng đã có báo cáo;
2 = đầu vào/công bố báo cáo lỗi. Các phương án khác vẫn chạy khi một phương án lỗi.

Cache mặc định: artifacts/backtest-lab-cache; đổi bằng --cache-dir. Tool băm
nội dung tất cả Parquet và JSON ở ngay thư mục dữ liệu, mã Python thực tế,
cấu hình, requirements, phiên bản Python và các gói đã cài. Dữ liệu các coin
khác trong thư mục cũng được tính vì có chiến lược đọc đồng thời nhiều coin.
Đổi dữ liệu/mã/tham số/chi phí/khoảng thời gian/môi trường sẽ tạo lần chạy mới.
File tín hiệu ngoài thư mục cũng được băm nếu cấu hình có rules.signal_path
(đường dẫn đó theo thư mục làm việc, giống runner cũ).

Lần chạy trùng chỉ đọc lại cache, vẫn phải kiểm tra dấu vân tay trên ổ đĩa.
Do đó tiết kiệm mô phỏng và thao tác AI, không có nghĩa thời gian bằng 0.
Cache có checksum nội dung; cache hỏng sẽ được chạy lại. Dữ liệu/cấu hình/mã
phải giữ cố định trong suốt lệnh. Tool kiểm tra lại trước khi công bố kết quả;
không chạy đồng thời với tải/cập nhật dữ liệu. Không tải dữ liệu hay gọi AI.

Tool từ chối ghi đè thư mục báo cáo có sẵn; output/cache phải tách khỏi nguồn
dữ liệu và thư mục mã/cấu hình. Dữ liệu phải phủ đầy cửa sổ, đủ 120 ngày khởi
tạo đối với directional, đủ funding; thiếu dữ liệu được báo lỗi thay vì
âm thầm thu ngắn bài test. Forward-fill spot của carry giữ theo runner cũ.

Hỗ trợ registry chiến lược directional và funding_arbitrage qua hai runner
hiện có. Cointegration ETH–BTC dùng chung tài khoản và OI Reclaim có hợp đồng
đầu vào riêng, tiếp tục dùng runner chuyên dụng; không ép chúng thành hai
lần chạy từng coin. Bảng này so sánh các tài khoản độc lập, không phải danh mục.

Mọi bảng mang nhãn RETROSPECTIVE_RESEARCH. Giữ riêng giai đoạn kiểm tra cuối,
không tối ưu theo kết quả đã xem rồi gọi đó là dữ liệu chưa từng thấy. Tool
không thay đổi cơ chế khớp lệnh/rủi ro/funding và không xác nhận lợi nhuận tương lai.
