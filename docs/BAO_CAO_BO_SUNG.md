# Nội dung bổ sung cho báo cáo (bám theo đề thi)

Đề thi yêu cầu: **Câu 1** (5 điểm) kiến trúc đề xuất, dịch vụ đám mây sử dụng, **ưu và nhược điểm** của dịch vụ lựa chọn. **Câu 2** (5 điểm) **sao lưu**, **bảo mật dữ liệu và dịch vụ**, **kỹ thuật điều phối lưu lượng**, **quy trình khôi phục dịch vụ**. Nộp **báo cáo tối thiểu 40 trang** và **bản phân công công việc**.

Các mục dưới đây viết sẵn để chép vào báo cáo Word. Đề xuất bố cục mới:

- Chương 1. Cơ sở lý thuyết (giữ nguyên, bổ sung 1.5)
- Chương 2. Kiến trúc đề xuất và dịch vụ đám mây (Câu 1): giữ 2.1 đến 2.4, thêm 2.5 đến 2.8
- **Chương 3 (mới). Sao lưu, bảo mật, điều phối lưu lượng và khôi phục dịch vụ (Câu 2)**
- Chương 4. Triển khai và đánh giá (chương 3 cũ, thêm 4.5 kiểm thử sao lưu/khôi phục)
- Chương 5. Kết luận (chương 4 cũ)
- Phụ lục A. Bảng phân công công việc. Phụ lục B. Mã nguồn chính. Phụ lục C. Cấu hình AWS.

---

## 1.5. Mô hình trách nhiệm chia sẻ (Shared Responsibility Model)

AWS chịu trách nhiệm bảo mật **của** đám mây: trung tâm dữ liệu, phần cứng, mạng vật lý, lớp ảo hóa. Nhóm chịu trách nhiệm bảo mật **trong** đám mây: hệ điều hành Ubuntu trên EC2, Docker, Kafka, PostgreSQL, mã nguồn, cấu hình Security Group, IAM, mã hóa dữ liệu và sao lưu. Vì nhóm dùng mô hình **IaaS** (tự quản lý Kafka và PostgreSQL trên EC2), phần trách nhiệm của nhóm lớn hơn so với dùng dịch vụ quản lý sẵn (Amazon MSK, Amazon RDS). Đây là lý do Chương 3 phải tự xây dựng cơ chế sao lưu, giám sát và khôi phục.

---

## 2.5. Kiến trúc triển khai trên AWS

- **Region**: us-east-1 (N. Virginia), chi phí thấp nhất và có đủ dịch vụ.
- **Mạng**: VPC mặc định, một subnet public, Internet Gateway. EC2 có IP Public để nhận Producer từ Internet.
- **Máy chủ**: 1 EC2 Ubuntu, ổ EBS gp3. Trên đó chạy Docker Compose gồm Zookeeper, Kafka, PostgreSQL; Consumer, Dashboard, Web QR chạy dưới dạng dịch vụ systemd.
- **Kafka 2 listener**: `EXTERNAL :9092` công bố bằng IP Public cho Producer bên ngoài (cổng cấu hình bằng biến `KAFKA_PORT`, mặc định 9092; trong buổi kiểm tra, giảng viên yêu cầu đổi sang 9091 và hệ thống chỉ cần sửa một dòng trong `.env` rồi khởi động lại); `INTERNAL :29092` chỉ nghe 127.0.0.1 cho tiến trình trên chính EC2.
- **Dịch vụ quản lý của AWS**: IAM (Role `NIDS-EC2-Role`), SNS (topic `NIDS-Alerts`), S3 (bucket sao lưu và dữ liệu lạnh), EBS Snapshot/AMI (sao lưu toàn máy), CloudWatch (giám sát, cảnh báo), CloudTrail (nhật ký thao tác API).

*(Chèn hình: sơ đồ kiến trúc trong README, xuất từ Mermaid hoặc vẽ lại bằng draw.io với icon AWS.)*

Luồng dữ liệu: Producer → Kafka 9092 (topic `network-traffic`, 3 partition) → Consumer group `nids-tv3-storage-v1` (chuẩn hóa bằng `scaler.joblib`, dự đoán bằng Random Forest 100 cây, độ chính xác 99,87% trên 10.000 mẫu kiểm thử) → PostgreSQL `nids_events` → Dashboard 8501. Khi nhãn khác "Bình thường", Consumer gọi `sns:Publish` (cooldown 30 giây mỗi loại tấn công). Định kỳ, dữ liệu được `pg_dump` lên S3 và bản ghi cũ hơn 24 giờ được chuyển sang S3 dạng JSONL nén.

## 2.6. Ưu điểm và nhược điểm của các dịch vụ lựa chọn

| Dịch vụ | Vai trò trong hệ thống | Ưu điểm | Nhược điểm / rủi ro | Cách nhóm giảm thiểu |
|---|---|---|---|---|
| **Amazon EC2** | Máy chủ chạy toàn bộ pipeline | Toàn quyền cấu hình hệ điều hành, cài Kafka/Docker tự do; trả theo giờ; bật/tắt nhanh; có Free Tier | Một máy là điểm lỗi đơn (SPOF); nhóm tự vá OS; IP Public đổi khi Stop/Start | Docker restart + systemd + healthcheck; AMI/Snapshot; `start_nids.sh` tự cập nhật IP; Elastic IP nếu cần |
| **Amazon EBS** | Ổ đĩa cho volume Kafka, PostgreSQL | Bền vững độc lập với instance; snapshot tăng dần lên S3; mã hóa được | Gắn với một AZ; dung lượng trả trước theo GB | Snapshot hằng ngày bằng Data Lifecycle Manager; dữ liệu cũ đẩy sang S3 |
| **Amazon S3** | Lưu bản sao lưu PostgreSQL, dữ liệu lạnh | Độ bền 99,999999999% (11 số 9); rẻ; versioning; lifecycle tự chuyển Glacier; mã hóa SSE mặc định | Không truy vấn trực tiếp như DB (cần Athena); phí request/egress | Phân vùng `dt=YYYY-MM-DD` để sau này dùng Athena; lifecycle giảm chi phí |
| **Amazon SNS** | Gửi email/SMS cảnh báo | Serverless, không cần máy chủ mail; pub/sub nhiều người nhận; tích hợp IAM | Có thể spam khi DDoS; SMS tốn phí; email cần xác nhận đăng ký | Cooldown 30 giây/loại tấn công; chỉ dùng email khi demo |
| **AWS IAM (Role)** | Cấp quyền SNS/S3 cho EC2 | Không lưu Access Key trong code; khóa tạm thời tự xoay vòng qua STS; phân quyền chi tiết | Cấu hình sai dễ cấp thừa quyền (ví dụ `AmazonSNSFullAccess`) | Thay bằng policy tối thiểu `deploy/iam/nids-ec2-policy.json` (chỉ `sns:Publish` đúng topic, S3 đúng prefix) |
| **Security Group** | Tường lửa ảo cấp ENI | Stateful, chỉ cần khai báo inbound; sửa có hiệu lực ngay; miễn phí | Không chặn theo nội dung gói; dễ mở `0.0.0.0/0` cho tiện | Chỉ mở 22 (IP quản trị), 9092 (IP Producer), 8501/8502 khi demo; 5432 và 2181 đóng |
| **Apache Kafka tự quản lý (trên EC2)** | Message broker | Miễn phí bản quyền; thông lượng cao; giữ dữ liệu để phát lại; tách rời producer/consumer | Tự vận hành, tự sao lưu; 1 broker không có replica; Zookeeper thêm thành phần | Volume bền vững, retention 24h, healthcheck; hướng phát triển: Amazon MSK đa AZ |
| **PostgreSQL trong Docker** | Lưu dữ liệu nóng cho Dashboard | Miễn phí; SQL mạnh; khóa chính chống ghi trùng | Không có backup/failover tự động như RDS | `backup_postgres_s3.sh` 6 giờ/lần + restore script; hướng phát triển: Amazon RDS Multi-AZ |
| **Docker / Docker Compose** | Đóng gói dịch vụ | Môi trường đồng nhất giữa máy cá nhân và EC2; khởi động một lệnh; healthcheck/restart có sẵn | Chỉ điều phối trên 1 máy | Hướng phát triển: Amazon ECS/EKS |
| **Amazon CloudWatch** | Giám sát CPU, status check | Có sẵn, alarm gửi thẳng SNS, tự recover instance | Metric chi tiết và log tốn phí | Chỉ bật metric cơ bản và 2 alarm |

### So sánh phương án thay thế

| Tiêu chí | Phương án nhóm chọn (Kafka + PostgreSQL trên EC2) | Phương án dịch vụ quản lý (Amazon MSK + RDS) | Phương án serverless (Kinesis + Lambda + DynamoDB) |
|---|---|---|---|
| Chi phí khi demo | Thấp (1 EC2, có thể Free Tier) | Cao (MSK tối thiểu 2 broker, RDS tính theo giờ) | Thấp khi ít dữ liệu, tăng theo lượng bản ghi |
| Công vận hành | Cao (tự backup, tự giám sát) | Thấp | Rất thấp |
| Tính sẵn sàng | 1 máy, khôi phục bằng script | Đa AZ, failover tự động | Đa AZ mặc định |
| Mức kiểm soát, học được gì | Hiểu sâu Kafka, mạng, Linux | Ít cấu hình hơn | Bị ràng buộc API AWS |
| Phù hợp đề tài | **Có**: phù hợp ngân sách và mục tiêu học tập | Hướng mở rộng cho doanh nghiệp | Cần viết lại toàn bộ |

### Ước tính chi phí hằng tháng (us-east-1, tham khảo bảng giá AWS)

| Hạng mục | Cấu hình | Ước tính |
|---|---|---|
| EC2 | t3.medium chạy 4 giờ/ngày × 30 ngày | khoảng 5 USD |
| EBS | 30 GB gp3 | khoảng 2,4 USD |
| S3 | < 5 GB + lifecycle | < 0,2 USD |
| SNS | < 1.000 email | 0 USD (trong hạn mức miễn phí) |
| EBS Snapshot | 7 bản tăng dần | < 1 USD |
| **Tổng** | | **khoảng 8 đến 9 USD/tháng** |

*(Nhóm kiểm tra lại đúng loại instance đang dùng và dùng AWS Pricing Calculator để chụp ảnh đưa vào báo cáo.)*

---

# CHƯƠNG 3 (MỚI). SAO LƯU, BẢO MẬT, ĐIỀU PHỐI LƯU LƯỢNG VÀ KHÔI PHỤC DỊCH VỤ

## 3.1. Giải pháp sao lưu dữ liệu

### 3.1.1. Phân loại dữ liệu cần bảo vệ

| Loại dữ liệu | Nơi lưu | Mức quan trọng | Có thể tái tạo? |
|---|---|---|---|
| Kết quả phân loại, cảnh báo (`nids_events`) | PostgreSQL (volume `postgres_data`) | Cao: bằng chứng điều tra | Không (nếu Kafka đã xóa dữ liệu thô) |
| Luồng NetFlow thô chưa xử lý | Kafka (volume `kafka_data`) | Trung bình | Một phần |
| Mô hình `nids_model.joblib`, `scaler.joblib` | Git + EC2 | Cao | Có (huấn luyện lại bằng `train_model.py`) |
| Mã nguồn, cấu hình | GitHub | Cao | Có |
| Bí mật (`.env`, khóa `.pem`) | Chỉ trên EC2 và máy quản trị | Rất cao | Không: phải quản lý riêng, **không** sao lưu lên Git |

### 3.1.2. Chiến lược 3-2-1

Nhóm áp dụng quy tắc **3-2-1**: 3 bản dữ liệu, trên 2 loại lưu trữ khác nhau, 1 bản ở ngoài máy chủ:

1. Bản chính trong PostgreSQL trên EBS.
2. Bản `pg_dump` cục bộ trong thư mục `backups/` (giữ 7 ngày).
3. Bản trên **Amazon S3** (khác loại lưu trữ, ngoài máy chủ, có versioning).

Ngoài ra **EBS Snapshot** hằng ngày bảo vệ toàn bộ ổ đĩa (cả cấu hình hệ điều hành), và **AMI** dùng khi cần dựng lại máy.

### 3.1.3. Sao lưu PostgreSQL lên S3

Script `scripts/backup_postgres_s3.sh` thực hiện:

1. `pg_dump -Fc` (định dạng custom, khôi phục chọn lọc được) ngay trong container PostgreSQL, không cần dừng dịch vụ.
2. Nén `gzip -9`, kiểm tra tính toàn vẹn bằng `gzip -t` và tính mã băm **SHA-256**.
3. Tải lên `s3://<bucket>/postgres/` với `--sse AES256` (mã hóa phía máy chủ) qua HTTPS, gắn metadata `sha256` để đối chiếu khi khôi phục.
4. Xóa bản cục bộ cũ hơn `BACKUP_RETENTION_DAYS`.

Lịch chạy bằng cron 6 giờ/lần, tức **RPO ≤ 6 giờ** cho trường hợp mất cả database.

### 3.1.4. Lưu trữ phân tầng: dữ liệu lạnh lên S3

`scripts/archive_events_s3.py` chạy hằng ngày: chọn bản ghi cũ hơn 24 giờ, ghi thành tệp JSON Lines nén gzip theo phân vùng ngày `events/dt=YYYY-MM-DD/`, mã hóa SSE, xác nhận bằng `head_object`, **chỉ sau đó** mới xóa khỏi PostgreSQL. Cách làm này giữ bảng nóng nhỏ để Dashboard truy vấn nhanh, đồng thời giữ lịch sử để điều tra số. Dữ liệu dạng phân vùng có thể truy vấn trực tiếp bằng Amazon Athena sau này.

### 3.1.5. Vòng đời dữ liệu trên S3

| Prefix | 0–30 ngày | 30–90 ngày | Sau 90 ngày | Xóa |
|---|---|---|---|---|
| `postgres/` | S3 Standard | S3 Glacier Instant Retrieval | | 180 ngày |
| `events/` | S3 Standard | S3 Standard-IA | S3 Glacier Flexible Retrieval | 365 ngày |

Versioning bật để chống ghi đè hoặc xóa nhầm (bản cũ giữ 30 ngày).

### 3.1.6. Kafka như bộ đệm phát lại

Kafka giữ dữ liệu 24 giờ (`KAFKA_LOG_RETENTION_HOURS=24`, tối đa 1 GB/partition) trên volume bền vững. Consumer chỉ **commit offset sau khi ghi PostgreSQL thành công** (`enable_auto_commit=False`), nên nếu Consumer sập giữa chừng, dữ liệu chưa ghi sẽ được đọc lại khi khởi động. Bảng `nids_events` có khóa chính `(topic, partition_id, message_offset)` nên đọc lại không tạo bản ghi trùng (ngữ nghĩa *at-least-once* + *idempotent write* ≈ *exactly-once* ở tầng lưu trữ).

### 3.1.7. Kiểm tra bản sao lưu

Bản sao lưu chỉ có giá trị khi khôi phục được. Nhóm đã diễn tập: xóa toàn bộ 3.120 bản ghi trong `nids_events`, chạy `restore_postgres_s3.sh`, kết quả khôi phục đủ 3.120 bản ghi. *(Chụp ảnh lần diễn tập trên EC2 và ghi thời gian.)*

## 3.2. Giải pháp bảo mật dữ liệu

### 3.2.1. Mã hóa dữ liệu khi lưu trữ (at rest)

- **S3**: SSE-S3 (AES-256) bật mặc định; bucket policy `DenyUnencryptedUploads` từ chối mọi đối tượng tải lên không mã hóa.
- **EBS**: bật *EBS encryption by default* (EC2 → Settings) để volume và snapshot mới đều mã hóa bằng AWS KMS.
- **Bản sao lưu cục bộ**: thư mục `backups/` nằm trong `.gitignore`, không bao giờ lên GitHub.

### 3.2.2. Mã hóa khi truyền (in transit)

- Gọi SNS và S3 qua HTTPS (boto3 và AWS CLI mặc định dùng TLS). Bucket policy `DenyInsecureTransport` chặn mọi truy cập không dùng TLS.
- Kafka hiện dùng PLAINTEXT trên 9092 vì dữ liệu là NetFlow giả lập. Rủi ro được giảm bằng Security Group chỉ cho IP Producer. **Hướng nâng cấp**: listener `SASL_SSL` (TLS + xác thực SCRAM) hoặc chuyển sang Amazon MSK với TLS và IAM auth.

### 3.2.3. Kiểm soát truy cập dữ liệu

- PostgreSQL mặc định chỉ nghe `127.0.0.1:5432`; cổng 5432 **không mở** trên Security Group.
- Mật khẩu database lấy từ tệp `.env` (không commit), mẫu cấu hình ở `.env.example`.
- Dashboard có thể dùng tài khoản chỉ đọc (`NIDS_READ_DSN`) chỉ có quyền `SELECT`.
- Web QR yêu cầu mã truy cập `NIDS_QR_CODE` tối thiểu 12 ký tự; các lượt gửi từ QR được đánh dấu demo và không kích hoạt SNS.
- `.gitignore` chặn `.env`, `*.pem`, `*.key`, tệp credentials. Script `test_sns.py` đã được sửa để không in Access Key ra màn hình.

### 3.2.4. Toàn vẹn dữ liệu

- SHA-256 cho mỗi bản sao lưu; `gzip -t` trước khi tải lên.
- Ràng buộc `CHECK` trên `dst_port` (0–65535) và `prediction` (0–3); Consumer bỏ bản ghi sai định dạng, giá trị không hữu hạn.
- S3 Versioning giữ bản cũ khi bị ghi đè.

## 3.3. Giải pháp bảo mật dịch vụ

### 3.3.1. Định danh và phân quyền (IAM)

EC2 dùng **IAM Role `NIDS-EC2-Role`**, nhận khóa tạm thời qua STS từ Instance Metadata Service, tự xoay vòng, không lưu trong mã nguồn. Nhóm thay `AmazonSNSFullAccess` (cho phép tạo, xóa mọi topic) bằng chính sách tối thiểu:

```json
{ "Effect": "Allow", "Action": "sns:Publish",
  "Resource": "arn:aws:sns:us-east-1:400131408828:NIDS-Alerts" }
```

cùng quyền `s3:PutObject`/`s3:GetObject` chỉ trên `postgres/*` và `events/*` của bucket sao lưu (tệp `deploy/iam/nids-ec2-policy.json`). Nếu mã độc chiếm được EC2, nó chỉ có thể gửi tin vào đúng một topic và ghi vào đúng bucket, không thể xóa tài nguyên khác.

Khuyến nghị thêm: bật **IMDSv2 bắt buộc** (EC2 → Actions → Instance settings → Modify instance metadata options → IMDSv2 Required) để chống tấn công SSRF lấy khóa tạm; tài khoản root bật MFA; mỗi thành viên dùng IAM user riêng.

### 3.3.2. Bảo mật mạng

| Lớp | Biện pháp |
|---|---|
| Security Group | Chỉ mở 22 (IP quản trị), 9092 (IP Producer), 8501/8502 (khi demo), có thể thay 8501/8502 bằng 80/8080 qua Nginx |
| Kafka | Tách listener: 9092 ra ngoài, 29092 chỉ 127.0.0.1; Zookeeper 2181 không mở ra ngoài |
| PostgreSQL | Chỉ 127.0.0.1 |
| SSH | Chỉ khóa `.pem`, tắt đăng nhập mật khẩu |
| Web | Nginx giới hạn 10 request/giây/IP (`limit_req`), chống flood vào Dashboard |

### 3.3.3. Giám sát và kiểm toán

- **CloudTrail**: ghi mọi lời gọi API (ai sửa Security Group, ai gọi SNS).
- **CloudWatch Alarm**: CPU > 80% và StatusCheckFailed gửi tới SNS `NIDS-Alerts`.
- Chính hệ thống NIDS giám sát lưu lượng và cảnh báo qua SNS.
- `scripts/healthcheck.sh` theo dõi container, cổng Kafka, PostgreSQL, Consumer, Dashboard, độ trễ consumer (lag) và dung lượng ổ đĩa.

## 3.4. Kỹ thuật điều phối lưu lượng

### 3.4.1. Kafka làm bộ đệm hấp thụ đột biến (buffering, backpressure)

Khi DDoS bơm 8.000 bản ghi/giây, Producer ghi vào Kafka (ghi tuần tự trên đĩa, rất nhanh). Consumer đọc theo tốc độ xử lý của mình (`max_records=50` mỗi lần poll). Phần chênh lệch nằm trong Kafka thay vì làm tràn RAM Consumer. Độ trễ (consumer lag) được `healthcheck.sh` theo dõi.

### 3.4.2. Phân vùng (partition) và consumer group: cân bằng tải xử lý

Topic `network-traffic` có **3 partition**. Producer phân bố bản ghi vào các partition. Tất cả Consumer cùng `group_id` chia nhau các partition: chạy 1 Consumer thì nó nhận cả 3 partition, chạy 3 Consumer thì mỗi cái 1 partition, thông lượng xử lý tăng gần tuyến tính. Khi một Consumer chết, Kafka **rebalance** giao partition của nó cho Consumer còn sống (tự chuyển đổi dự phòng). Hai luồng tách biệt: luồng tải lớn (`producer.py`) và luồng Web QR được phân biệt bằng `demo_id`, để lượt gửi từ điện thoại không phải xếp hàng sau hàng nghìn bản ghi DDoS.

### 3.4.3. Tách listener nội bộ và bên ngoài

Kafka có 2 listener: `EXTERNAL://<IP_Public>:9092` cho Producer từ Internet và `INTERNAL://localhost:29092` cho tiến trình trên EC2. Lưu lượng nội bộ không phải đi vòng ra Internet Gateway, không phụ thuộc rule Security Group, và giảm độ trễ.

### 3.4.4. Micro-batching và kiểm soát cảnh báo

- Producer gom bản ghi (`linger_ms=5`, `batch_size=32 KB`, nén gzip) để giảm số gói TCP.
- Consumer dự đoán theo lô (đo thực tế: lô 1 bản ghi đạt 66 bản ghi/giây, lô 50 đạt khoảng 3.400 bản ghi/giây trên cùng phần cứng, xem `benchmark_results/ml_benchmark_*.json`).
- SNS có **cooldown 30 giây mỗi loại tấn công**: khi DDoS sinh 16.000 nhãn tấn công trong vài giây, quản trị viên chỉ nhận 1 email thay vì 16.000 email.

### 3.4.5. Reverse proxy và giới hạn tốc độ ở tầng web

`deploy/nginx/nids.conf`: Nginx nhận cổng 80 (Dashboard) và 8080 (Web QR), chuyển tiếp tới Streamlit 8501/8502, hỗ trợ WebSocket, giới hạn 10 request/giây/IP (burst 20), đánh dấu upstream lỗi (`max_fails=3`). Khối `upstream` cho phép thêm máy chủ thứ hai để chia tải round-robin.

### 3.4.6. Hướng mở rộng điều phối trên AWS

| Kỹ thuật | Dịch vụ AWS | Tác dụng |
|---|---|---|
| Cân bằng tải tầng 7 | Application Load Balancer + Target Group | Chia request Dashboard cho nhiều EC2, health check, HTTPS bằng ACM |
| Tự co giãn | EC2 Auto Scaling Group | Thêm Consumer khi CPU hoặc consumer lag cao |
| Điều hướng DNS và failover | Route 53 (health check, failover routing) | Chuyển sang vùng dự phòng khi vùng chính lỗi |
| Broker đa AZ | Amazon MSK (3 broker, replication factor 3) | Không mất dữ liệu khi một AZ lỗi |

## 3.5. Quy trình khôi phục dịch vụ

### 3.5.1. Mục tiêu RTO/RPO

| Tình huống | RPO | RTO mục tiêu | Cơ chế |
|---|---|---|---|
| Tiến trình Consumer/Dashboard chết | 0 (Kafka giữ dữ liệu) | ≤ 1 phút | systemd `Restart=always` |
| Container Kafka/PostgreSQL dừng | 0 | ≤ 3 phút | Docker `restart: unless-stopped` + `healthcheck.sh --recover` mỗi phút |
| Mất hoặc hỏng database | ≤ 6 giờ | ≤ 15 phút | `restore_postgres_s3.sh` + phát lại Kafka |
| Mất EC2 | ≤ 24 giờ (snapshot) / ≤ 6 giờ (S3) | ≤ 60 phút | AMI/Snapshot + GitHub + S3 |

### 3.5.2. Khôi phục tự động nhiều tầng

1. **Tầng container**: mọi dịch vụ có `healthcheck` và `restart: unless-stopped`; Kafka chỉ khởi động khi Zookeeper healthy.
2. **Tầng tiến trình**: Consumer, Dashboard, Web QR chạy bằng systemd, tự bật lại sau 5 giây và tự chạy khi EC2 khởi động lại.
3. **Tầng giám sát**: cron chạy `healthcheck.sh --recover` mỗi phút; phát hiện lỗi thì `docker compose up -d`, khởi động lại dịch vụ systemd và gửi email `[NIDS RECOVERY]` qua SNS.
4. **Tầng hạ tầng**: CloudWatch alarm `StatusCheckFailed_System` với hành động *Recover instance* chuyển EC2 sang phần cứng khác, giữ nguyên IP riêng và volume.

### 3.5.3. Quy trình 6 bước khi có sự cố

Phát hiện (email SNS / CloudWatch) → Đánh giá (`healthcheck.sh`) → Khoanh vùng (log Docker, journalctl) → Khôi phục (theo mức sự cố) → Xác minh (healthcheck OK, chạy kịch bản 1, Dashboard có bản ghi mới) → Ghi nhận (nguyên nhân, RTO thực tế, bài học).

*(Chèn hình: lưu đồ quy trình 6 bước.)*

### 3.5.4. Khôi phục khi mất toàn bộ máy chủ

1. Launch EC2 mới từ AMI (hoặc từ snapshot), cùng Security Group, gắn `NIDS-EC2-Role`.
2. Nếu dùng Ubuntu trống: cài Docker, `git clone` repo, tạo `.env`.
3. `bash start_nids.sh`: tự lấy IP Public mới, ghi vào `.env`, Kafka công bố `<IP mới>:9092`.
4. `bash scripts/restore_postgres_s3.sh` lấy bản sao lưu mới nhất.
5. `sudo bash scripts/install_services.sh`, cài lại crontab.
6. Báo IP mới cho các máy Producer (hoặc dùng Elastic IP).

### 3.5.5. Kết quả diễn tập khôi phục

| Kịch bản diễn tập | Thao tác gây lỗi | Kết quả | Thời gian khôi phục |
|---|---|---|---|
| Kafka dừng | `docker compose stop kafka` | `healthcheck.sh --recover` phát hiện 4 lỗi, khởi động lại Kafka đến trạng thái healthy | *(điền số đo trên EC2)* |
| Consumer bị kill | `sudo systemctl kill nids-consumer` | systemd tự khởi động lại | *(điền)* |
| Mất dữ liệu | `DELETE FROM nids_events` | Khôi phục đủ 3.120/3.120 bản ghi từ S3 | *(điền)* |

---

## 4.x. Sửa lại số liệu hiệu năng cho khớp kết quả đo

Báo cáo hiện ghi "độ trễ toàn trình 1,2 đến 1,8 giây" và "dưới 2 giây", nhưng các tệp trong `benchmark_results/` cho thấy:

| Lần đo | Kịch bản | Số bản ghi | Thông lượng tiêu thụ | Độ trễ đầu-cuối p50 | p95 |
|---|---|---|---|---|---|
| 07/11 01:06 | mixed | 10.000 | khoảng 11.560 bản ghi/giây | 11,6 ms | 18,5 ms |
| 08/11 23:11 | normal | 500 | khoảng 131 bản ghi/giây | 533 ms | 784 ms |
| 08/11 23:30 | mixed | 10.000 | khoảng 1.285 bản ghi/giây | 3.784 ms | 6.170 ms |

Nên ghi đúng số đo và giải thích: lần 07/11 có độ trễ rất thấp (có thể đo cùng máy với broker), lần 08/11 Producer gửi qua Internet tới EC2 nên độ trễ tăng. Giảng viên dễ hỏi nếu số trong báo cáo khác số trong repo.

## Những lỗi nhỏ cần sửa trong báo cáo hiện tại

1. Mục 2.3.2 ghi role dùng **AmazonSNSFullAccess**, mâu thuẫn với "đặc quyền tối thiểu". Sửa theo 3.3.1 ở trên.
2. Mục 4.1 ghi "tối thiểu **4** cổng cốt lõi" nhưng liệt kê **5** cổng (22, 9091, 5432, 8501, 8502). Sửa lại cho khớp bảng Security Group mới (5432 đã đóng).
3. Mục 2.4 nói dữ liệu lạnh "được nén lại và chuyển định kỳ lên S3", trước đây repo chưa có mã làm việc này. Giờ đã có `scripts/archive_events_s3.py`, hãy dẫn chứng bằng ảnh.
4. Mục 1.2.3 ghi 5432 là cổng mở; sửa thành "chỉ nghe nội bộ".
5. Mục lục chưa có số hình, danh mục bảng, danh mục từ viết tắt. Đánh số hình "Hình 2.1, 2.2…" và thêm *Danh mục hình*, *Danh mục bảng*, *Danh mục từ viết tắt* (AWS, EC2, S3, SNS, IAM, SG, NIDS, SOC, RPO, RTO, SSE, TLS…).
6. Tài liệu tham khảo số 1: "Proceedings of lalu. Net Workshop" sai tên, sửa thành "Proceedings of the NetDB Workshop".
7. **Cổng Kafka**: báo cáo hiện ghi 9091 ở các mục 1.2.3, 2.2, 2.3.1, 3.1.1, 3.3. Repo giờ mặc định 9092 và đổi được bằng `KAFKA_PORT`. Sửa các chỗ đó thành 9092 và thêm một câu: "Cổng Kafka được tham số hóa bằng biến KAFKA_PORT; trong buổi kiểm tra, nhóm đã đổi sang 9091 theo yêu cầu của giảng viên chỉ bằng một dòng cấu hình."
8. Bổ sung tài liệu tham khảo: AWS Well-Architected Framework (Reliability Pillar, Security Pillar); AWS Shared Responsibility Model; Amazon S3 Lifecycle; Amazon EBS Snapshots; PostgreSQL Documentation: pg_dump.

---

## Phụ lục A. Bảng phân công công việc (mẫu, nhóm điền tên và % đóng góp)

Dựa trên cách repo chia TV1/TV2/TV3, đề xuất:

| STT | Thành viên | Mã SV | Nhiệm vụ chính | Sản phẩm bàn giao | Mức hoàn thành |
|---|---|---|---|---|---|
| 1 | Phạm Thị Trúc Quỳnh (nhóm trưởng, TV1) | B24DCKD076 | Hạ tầng AWS: EC2, Security Group, cấu hình cổng Kafka, IAM Role, Docker Compose Kafka/PostgreSQL, S3 + sao lưu/khôi phục; tổng hợp báo cáo | `docker-compose.yml`, `start_nids.sh`, `scripts/`, `deploy/`, Chương 2–3 | 100% |
| 2 | *(TV2)* | | Mô hình Học máy: sinh dữ liệu, huấn luyện Random Forest, Consumer + SNS, benchmark | `train_model.py`, `producer.py`, `consumer_ids.py`, `benchmark.py`, mục 1.4, 4.x | |
| 3 | *(TV3)* | | Dashboard SOC, Web QR, Consumer ghi PostgreSQL, kịch bản demo | `tv3/`, `run_demo.sh`, mục 4.2–4.3 | |
| 4 | *(TV4)* | | Lý thuyết, kiểm thử, diễn tập khôi phục, chụp ảnh minh chứng, slide | Chương 1, bảng diễn tập 3.5.5, slide | |

*(Các thành viên còn lại: Nguyễn Hải Yến B24DCKD106, Kim Việt Anh B24DCKD004, Đinh Đức Minh B24DCKD052. Nhóm tự xếp đúng người vào TV2/TV3/TV4.)*

Thêm bảng **tiến độ** theo tuần (tuần 1: chọn đề tài, tuần 2: dựng EC2 + Kafka, tuần 3: mô hình ML, tuần 4: Dashboard + SNS, tuần 5: sao lưu, bảo mật, khôi phục, tuần 6: kiểm thử, viết báo cáo).

## Phụ lục B, C (giúp đạt 40 trang)

- **Phụ lục B. Mã nguồn chính**: `docker-compose.yml`, `consumer_tv3.py` (hàm `classify` và vòng lặp chính), `backup_postgres_s3.sh`, `healthcheck.sh`. Mỗi đoạn kèm 2–3 câu giải thích.
- **Phụ lục C. Cấu hình AWS**: ảnh Security Group, IAM policy JSON, bucket policy, lifecycle, CloudWatch alarm, DLM snapshot policy.

### Ước lượng số trang sau khi bổ sung

| Phần | Trang hiện có | Bổ sung | Ghi chú |
|---|---|---|---|
| Phần đầu (bìa, cam đoan, mở đầu, mục lục, danh mục) | 7 | +3 | Danh mục hình, bảng, từ viết tắt |
| Chương 1 | 4 | +1 | 1.5 trách nhiệm chia sẻ |
| Chương 2 (Câu 1) | 5 | +6 | 2.5–2.6, bảng ưu/nhược, so sánh, chi phí |
| Chương 3 mới (Câu 2) | 0 | +12 | Sao lưu, bảo mật, điều phối, khôi phục, kèm ảnh |
| Chương 4 (triển khai, đánh giá) | 8 | +3 | Ảnh diễn tập, số liệu benchmark đúng |
| Chương 5, tài liệu tham khảo | 4 | +1 | |
| Phụ lục A, B, C | 0 | +6 | |
| **Tổng** | **28** | **+32** | **khoảng 60 trang**, vượt yêu cầu 40 trang |
