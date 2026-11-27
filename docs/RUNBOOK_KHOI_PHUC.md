# Runbook: Quy trình khôi phục dịch vụ NIDS

## 1. Mục tiêu khôi phục

| Chỉ số | Mục tiêu | Cơ sở |
|---|---|---|
| **RPO** dữ liệu cảnh báo (PostgreSQL) | ≤ 6 giờ (bản sao lưu S3), ≈ 0 với sự cố tiến trình | Backup 6 giờ/lần; Kafka giữ dữ liệu 24h và consumer commit offset sau khi ghi DB |
| **RTO** lỗi tiến trình (consumer, dashboard) | ≤ 1 phút | systemd `Restart=always`, `RestartSec=5` |
| **RTO** lỗi container (Kafka/Postgres/Zookeeper) | ≤ 3 phút | Docker `restart: unless-stopped` + `healthcheck.sh --recover` chạy mỗi phút |
| **RTO** mất database | ≤ 15 phút | `restore_postgres_s3.sh` |
| **RTO** mất toàn bộ EC2 | ≤ 60 phút | AMI/EBS Snapshot + GitHub + S3 |

## 2. Phân cấp sự cố

| Mức | Ví dụ | Cách phát hiện | Xử lý |
|---|---|---|---|
| 1. Tiến trình | Consumer bị kill, Streamlit treo | systemd, healthcheck | Tự động restart |
| 2. Container | Kafka dừng, Postgres crash | Docker healthcheck, healthcheck.sh | `docker compose up -d` (tự động) + email SNS |
| 3. Dữ liệu | Xóa nhầm bảng, volume hỏng | Dashboard trống, healthcheck | Khôi phục từ S3 (mục 4) |
| 4. Máy chủ | EC2 hỏng phần cứng, bị terminate, AZ sự cố | CloudWatch StatusCheck, SNS | Auto-recover hoặc dựng lại EC2 (mục 5) |
| 5. Bảo mật | Lộ khóa, IP lạ truy cập 22/9092 | CloudTrail, log SSH, cảnh báo NIDS | Cô lập (mục 6) |

## 3. Quy trình chung (khi nhận email cảnh báo)

1. **Phát hiện**: email SNS `[NIDS RECOVERY]` hoặc CloudWatch alarm.
2. **Đánh giá**: SSH vào EC2, chạy `bash scripts/healthcheck.sh` để biết thành phần lỗi.
3. **Khoanh vùng**: `docker compose logs --tail 100 <service>`, `journalctl -u nids-consumer -n 100`.
4. **Khôi phục** theo mức sự cố (bảng trên).
5. **Xác minh**: healthcheck toàn OK, chạy kịch bản 1 của `run_demo.sh`, Dashboard có bản ghi mới.
6. **Ghi nhận**: thời điểm lỗi, nguyên nhân, thời gian khôi phục (RTO thực tế), bài học.

## 4. Khôi phục database từ S3

```bash
cd ~/AWS-NIDS-Project
sudo systemctl stop nids-consumer              # tránh ghi trong lúc khôi phục
bash scripts/restore_postgres_s3.sh            # bản mới nhất, hoặc truyền tên file cụ thể
sudo systemctl start nids-consumer
```

Dữ liệu từ thời điểm backup đến lúc sự cố: nếu vẫn còn trong Kafka (≤ 24h), đặt lại offset để xử lý lại:

```bash
docker compose exec kafka kafka-consumer-groups --bootstrap-server localhost:29092 \
  --group nids-tv3-storage-v1 --reset-offsets --to-datetime <YYYY-MM-DDTHH:MM:SS.000> --topic network-traffic --execute
```

Bảng `nids_events` có khóa chính (topic, partition, offset) nên xử lý lại không tạo bản ghi trùng.

## 5. Khôi phục khi mất EC2

1. EC2 → Launch instance từ **AMI** mới nhất (hoặc tạo volume từ **EBS Snapshot**), cùng Security Group, gắn **IAM Role NIDS-EC2-Role**.
2. Nếu không có AMI: Ubuntu mới → cài Docker, `git clone` repo, tạo `.env`.
3. `bash start_nids.sh` (tự cập nhật IP Public mới vào Kafka 9092).
4. `bash scripts/restore_postgres_s3.sh` để lấy dữ liệu.
5. `sudo bash scripts/install_services.sh`, cài lại crontab.
6. Báo các máy Producer IP mới (hoặc dùng Elastic IP để không phải đổi).

## 6. Sự cố bảo mật

1. Thu hẹp Security Group ngay (chỉ giữ 22 từ IP quản trị).
2. Nếu nghi lộ khóa: IAM → vô hiệu khóa / thay phiên role session (Revoke active sessions).
3. Lưu bằng chứng: tạo snapshot EBS trước khi sửa.
4. Đổi mật khẩu PostgreSQL, `NIDS_QR_CODE`.
5. Dựng lại máy sạch theo mục 5 nếu máy bị xâm nhập.
