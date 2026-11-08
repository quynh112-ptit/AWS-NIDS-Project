# Bàn giao thành viên 3 · Dashboard SOC và Web QR

Bản này dùng model, scaler và Producer từ nhánh main của nhóm (bb9c6ed187346703abc9ff3868ff77e2b33e279f). Mở thư mục sau khi giải nén bằng VS Code. Demo xử lý bản ghi mô phỏng theo luồng:

```text
Điện thoại → Web QR → Kafka → Consumer + model TV2 → PostgreSQL → Dashboard
```

## Chạy trên Windows trước

Mở Docker Desktop. Trong PowerShell, vào thư mục vừa giải nén chứa file này. Dùng Python 3.13 như môi trường đã kiểm thử.

```powershell
python -m venv .venv-tv3
$py = ".\.venv-tv3\Scripts\python.exe"
& $py -m pip install -r requirements.tv3.txt
Copy-Item .env.tv3.example .env.tv3
docker compose -p nids-tv3 -f compose.tv3.yml up -d --wait --wait-timeout 180
docker compose -p nids-tv3 -f compose.tv3.yml exec -T kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:29092 --create --if-not-exists --topic network-traffic --partitions 1 --replication-factor 1
```

Mở .env.tv3 bằng VS Code và điền NIDS_QR_CODE do bạn tự chọn, tối thiểu 12 ký tự. Giữ file này trên máy. Docker Compose dùng Kafka 19092 và PostgreSQL 15432 cho bản demo local.

Mở ba terminal trong cùng thư mục. Chạy lần lượt, mỗi terminal một lệnh.

```powershell
& .\.venv-tv3\Scripts\python.exe -u consumer_tv3.py
```

```powershell
& .\.venv-tv3\Scripts\python.exe -m streamlit run dashboard.py --server.address 127.0.0.1 --server.port 8501
```

```powershell
& .\.venv-tv3\Scripts\python.exe -m streamlit run qr_attack_app.py --server.address 127.0.0.1 --server.port 8502
```

1. Đợi Consumer báo đã nhận phân vùng Kafka.
2. Mở dashboard http://127.0.0.1:8501 và trang mô phỏng http://127.0.0.1:8502.
3. Chọn DDoS hoặc Port Scan, nhập mã demo rồi gửi. Web trả về mã demo sau khi Kafka xác nhận.
4. Đối chiếu mã đó trên terminal Consumer và cột **Mã demo** của dashboard. Dashboard tự đọc lại dữ liệu mỗi 3 giây. Sự kiện được mô hình xếp bình thường vẫn tăng tổng số bản ghi.
5. Nếu muốn chạy thêm luồng nền của nhóm, mở terminal mới rồi dùng:

```powershell
$env:KAFKA_BOOTSTRAP_SERVERS = "127.0.0.1:19092"
& .\.venv-tv3\Scripts\python.exe -u producer.py
```

Dừng các chương trình bằng Ctrl+C, sau đó chạy `docker compose -p nids-tv3 -f compose.tv3.yml down`. Volume dữ liệu vẫn được giữ lại.

## Quét QR bằng điện thoại qua ngrok

Cài ngrok và cấu hình authtoken bằng hướng dẫn [ngrok CLI Quickstart](https://ngrok.com/docs/gateway/endpoints/agent-cli-quickstart). Khi Web QR đang chạy, mở terminal riêng:

```powershell
ngrok http 8502
```

Chép URL HTTPS mà ngrok cấp vào NIDS_QR_URL trong .env.tv3. Khởi động lại dashboard để tạo mã QR mới. Dùng điện thoại quét mã, mở trang, chọn kịch bản rồi nhập mã demo. Chỉ mở đường hầm cho cổng 8502. Kết thúc buổi demo thì nhấn Ctrl+C ở terminal ngrok.

## Kết nối EC2 của nhóm

Dùng Public IPv4 hiện tại do TV1 xác nhận. File bàn giao ghi Kafka cổng 9092 và PostgreSQL cổng 5432, database nids_db. Địa chỉ có thể đổi khi EC2 được bật lại. Cập nhật cả địa chỉ broker công bố trong Compose trên EC2 theo cách nhóm vận hành.

Trong .env.tv3, đổi NIDS_KAFKA thành địa chỉ Kafka của EC2, và NIDS_DSN thành chuỗi kết nối PostgreSQL do TV1 cấp. Nhập mật khẩu tại máy và mã hóa URL cho ký tự đặc biệt trong DSN. Tránh đưa file .env.tv3 lên Git. Nếu có tài khoản chỉ đọc cho dashboard, đặt thêm NIDS_READ_DSN. Dashboard chỉ thực hiện SELECT. Consumer cần quyền tạo bảng/chỉ mục và INSERT/SELECT trên nids_events. TV1 có thể cấp quyền trước khi chạy. Hạn chế nguồn truy cập Kafka/PostgreSQL theo cấu hình mạng của nhóm.

Consumer trong gói này dùng đúng model và bảy feature của TV2, ghi mọi kết quả vào nids_events và chống ghi lặp theo vị trí Kafka. Consumer trên nhánh main ở thời điểm bàn giao chỉ in nhãn và gọi SNS, vì vậy cần chạy consumer_tv3.py để có dữ liệu cho dashboard. Phối hợp với TV2 khi thay tiến trình Consumer đang chạy trên EC2. Nếu dùng SNS, cài boto3 riêng, cấu hình ARN và quyền qua môi trường chạy. Lượt gửi QR được đánh dấu demo và bỏ qua SNS. Dữ liệu dự đoán được ghi PostgreSQL. Tích hợp S3 thuộc phần của TV2.

Các chỉ số dashboard lấy từ PostgreSQL. Bản ghi gửi qua QR là mô phỏng và nhãn hiển thị là kết quả mô hình, có thể khác tên kịch bản.


## Trạng thái kiểm thử

Đã kiểm tra cú pháp Compose/Python, nạp model và scaler thật, và xác nhận model dự đoán đúng bốn mẫu QR cố định. Đã kiểm tra logic mã truy cập QR, nội dung gửi Kafka và cách dashboard dựng số liệu bằng dịch vụ mô phỏng. Cần chạy thử toàn luồng với Docker Desktop và kiểm tra đường hầm ngrok trên máy dùng demo.
