# Hướng dẫn triển khai trên AWS (làm tay trên Console và EC2)

Các bước dưới đây dùng region **us-east-1** và tài khoản đang chứa topic `NIDS-Alerts`. Mỗi bước có ghi chú **[Chụp ảnh]** để đưa vào báo cáo.

## Bước 1. Security Group: mở đúng cổng Kafka

EC2 → Security Groups → chọn SG của máy NIDS → **Edit inbound rules**:

1. Đảm bảo có rule TCP **9092** (bằng giá trị `KAFKA_PORT` trong `.env`), nguồn là IP các máy chạy Producer (hoặc `0.0.0.0/0` chỉ trong lúc demo).
2. Nếu chuyển sang 9091 (đặt `KAFKA_PORT=9091`), thêm rule 9091; chỉ giữ rule của cổng đang dùng.
3. Rule 22 chỉ để nguồn **My IP**.
4. Rule 5432: xóa, hoặc chỉ để IP thành viên cần truy cập từ xa (`/32`).
5. Xóa rule 2181 nếu có (Zookeeper giờ chỉ chạy nội bộ).

**[Chụp ảnh]** bảng Inbound rules sau khi sửa.

## Bước 2. Tạo bucket S3 cho sao lưu

S3 → Create bucket:

- Tên: ví dụ `nids-backup-nhom07` (tên phải duy nhất toàn cầu; nếu trùng thì đổi và sửa tên trong `.env` và `deploy/iam/*.json`).
- Region: us-east-1. **Block all public access: bật**.
- **Bucket Versioning: Enable**.
- Default encryption: **SSE-S3**.

Sau khi tạo:

- Tab Permissions → Bucket policy → dán nội dung `deploy/iam/s3-bucket-policy.json` (đổi tên bucket nếu khác).
- Tab Management → Lifecycle rules: tạo theo `deploy/iam/s3-lifecycle.json`, hoặc chạy lệnh trên EC2:
  ```bash
  aws s3api put-bucket-lifecycle-configuration --bucket nids-backup-nhom07 \
      --lifecycle-configuration file://deploy/iam/s3-lifecycle.json
  ```

**[Chụp ảnh]** trang Properties (Versioning, Encryption) và Lifecycle rules.

## Bước 3. Thu hẹp quyền IAM Role (đặc quyền tối thiểu)

IAM → Roles → `NIDS-EC2-Role`:

1. **Add permissions → Create inline policy → JSON**, dán `deploy/iam/nids-ec2-policy.json`, đặt tên `NIDS-LeastPrivilege`.
2. Gỡ `AmazonSNSFullAccess` khỏi role (policy mới đã đủ quyền `sns:Publish` cho đúng topic).
3. Kiểm tra trên EC2: `python3 test_sns_role.py` phải báo gửi SNS thành công.

**[Chụp ảnh]** trang Permissions của role và nội dung policy JSON.

## Bước 4. Cập nhật code trên EC2

```bash
ssh -i nids-key.pem ubuntu@<IP_PUBLIC>
cd ~/AWS-NIDS-Project
git stash                 # cất các sửa cổng làm tay trước đó (code mới đọc cổng từ KAFKA_PORT)
git pull origin main
git stash drop            # bỏ bản sửa tay (sau khi đã kiểm tra không còn gì cần giữ: git stash show -p)
cp -n .env.example .env && nano .env    # đặt POSTGRES_PASSWORD giống mật khẩu đang dùng, BACKUP_S3_BUCKET
docker compose down       # dừng bản cũ (dữ liệu Postgres vẫn nằm trong volume)
bash start_nids.sh
```

Lưu ý: nếu database đang dùng mật khẩu `nids_password`, hãy để `POSTGRES_PASSWORD=nids_password` trong `.env`. Muốn đổi mật khẩu mạnh hơn, chạy:
`docker compose exec postgres psql -U nids_user -d nids_db -c "ALTER USER nids_user PASSWORD '<mật_khẩu_mới>';"` rồi sửa `.env` và `NIDS_DSN` theo.

Kiểm tra Kafka đã chạy trên 9092:

```bash
docker compose ps                          # cột PORTS phải có 0.0.0.0:9092->9092 và 127.0.0.1:29092->29092
docker compose exec kafka kafka-topics --bootstrap-server localhost:29092 --describe --topic network-traffic
```

**[Chụp ảnh]** `docker compose ps` và mô tả topic (3 partition).

## Bước 5. Cài dịch vụ tự khởi động lại và lịch sao lưu

```bash
sudo apt install -y awscli postgresql-client   # nếu chưa có lệnh aws
python3 -m venv .venv && .venv/bin/pip install -r tv3/requirements.tv3.txt
# tv3/.env.tv3 đặt NIDS_KAFKA=localhost:29092, NIDS_DSN, NIDS_QR_CODE, NIDS_QR_URL=http://<IP_PUBLIC>:8502
sudo bash scripts/install_services.sh
bash scripts/backup_postgres_s3.sh          # chạy thử 1 lần
crontab -e
```

Thêm vào crontab:

```cron
0 */6 * * * cd /home/ubuntu/AWS-NIDS-Project && bash scripts/backup_postgres_s3.sh >> /home/ubuntu/nids-backup.log 2>&1
30 2 * * *  cd /home/ubuntu/AWS-NIDS-Project && .venv/bin/python scripts/archive_events_s3.py --delete >> /home/ubuntu/nids-archive.log 2>&1
* * * * *   cd /home/ubuntu/AWS-NIDS-Project && bash scripts/healthcheck.sh --recover >> /home/ubuntu/nids-health.log 2>&1
```

**[Chụp ảnh]** `systemctl status nids-consumer`, kết quả backup, file trong S3 (`aws s3 ls s3://nids-backup-nhom07/postgres/`).

## Bước 6. EBS Snapshot tự động (sao lưu toàn máy)

EC2 → Elastic Block Store → **Lifecycle Manager** → Create lifecycle policy → EBS snapshot policy:
target theo tag `Name = NIDS-Server` (gắn tag này cho volume), lịch 24 giờ/lần, giữ 7 bản.

Tùy chọn: EC2 → Instances → Actions → Image and templates → **Create image (AMI)** để có ảnh máy dùng khi khôi phục thảm họa.

**[Chụp ảnh]** policy DLM và danh sách snapshot.

## Bước 7. Giám sát bằng CloudWatch (khuyến nghị)

CloudWatch → Alarms → Create alarm:

- Metric `EC2 > Per-Instance > CPUUtilization` > 80% trong 5 phút → gửi tới SNS `NIDS-Alerts`.
- Metric `StatusCheckFailed_System` ≥ 1 → hành động **Recover this instance** (tự chuyển sang phần cứng khác).

**[Chụp ảnh]** danh sách alarm.

## Bước 8. Diễn tập khôi phục (lấy số liệu cho báo cáo)

```bash
docker compose stop kafka && bash scripts/healthcheck.sh --recover   # đo thời gian tự khôi phục
sudo systemctl kill nids-consumer                                    # systemd tự bật lại sau 5 giây
bash scripts/restore_postgres_s3.sh                                  # khôi phục DB từ S3
```

Ghi lại thời gian mỗi lần (dùng `time`) để điền bảng RTO thực đo trong báo cáo. **[Chụp ảnh]** từng bước và email SNS "[NIDS RECOVERY]".

## Bước 9. Tiết kiệm chi phí

Sau buổi demo: `docker compose down` (giữ volume) rồi **Stop** instance. Snapshot và S3 tính phí rất nhỏ theo dung lượng.
