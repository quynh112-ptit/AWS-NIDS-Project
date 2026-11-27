#!/bin/bash
# ============================================================
# Script khởi động NIDS trên EC2
# Chạy: bash start_nids.sh
# Cổng Kafka công khai = KAFKA_PORT trong .env (mặc định 9092, có thể đặt 9091)
# ============================================================

set -e  # Dừng ngay nếu có lỗi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

KAFKA_INTERNAL=localhost:29092   # cổng nội bộ cho tiến trình chạy trên EC2

echo "============================================================"
echo "   NIDS System Startup Script"
echo "============================================================"

# ── 1. Lấy IP Public hiện tại của EC2 (IMDSv2, dự phòng checkip) ──
TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600" 2>/dev/null || true)
if [ -n "$TOKEN" ]; then
    EC2_IP=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || true)
fi
if [ -z "$EC2_IP" ]; then
    EC2_IP=$(curl -s https://checkip.amazonaws.com 2>/dev/null || curl -s https://ifconfig.me 2>/dev/null || echo "127.0.0.1")
    EC2_IP=$(echo "$EC2_IP" | tr -d '[:space:]')
fi
echo "[*] IP Public EC2 hiện tại: $EC2_IP"

# ── 2. Giải phóng cổng 5432 nếu có PostgreSQL chạy ngầm ────
sudo systemctl stop postgresql 2>/dev/null || true

# ── 3. Pull code + model mới nhất từ GitHub ─────────────────
echo "[*] Đang pull code mới nhất từ GitHub..."
git pull origin main || echo "[!] Không pull được (có thay đổi local?). Tiếp tục với code hiện tại."

# ── 4. Ghi IP vào .env (docker-compose đọc KAFKA_PUBLIC_HOST) ──
# Không sửa docker-compose.yml bằng sed nữa → tránh xung đột khi git pull.
[ -f .env ] || cp .env.example .env
KAFKA_PORT=$(grep -E '^KAFKA_PORT=' .env | tail -1 | cut -d= -f2 | tr -d '[:space:]')
KAFKA_PORT="${KAFKA_PORT:-9092}"   # cổng công khai cho Producer bên ngoài
if grep -q '^KAFKA_PUBLIC_HOST=' .env; then
    sed -i "s|^KAFKA_PUBLIC_HOST=.*|KAFKA_PUBLIC_HOST=${EC2_IP}|" .env
else
    echo "KAFKA_PUBLIC_HOST=${EC2_IP}" >> .env
fi
# Tiến trình trên EC2 (consumer, dashboard, run_demo) dùng listener nội bộ
for key in KAFKA_BOOTSTRAP_SERVERS NIDS_KAFKA; do
    if grep -q "^${key}=" .env; then
        sed -i "s|^${key}=.*|${key}=${KAFKA_INTERNAL}|" .env
    else
        echo "${key}=${KAFKA_INTERNAL}" >> .env
    fi
done
echo "[✓] Kafka Advertised Listener → $EC2_IP:$KAFKA_PORT (ghi trong .env)"

# ── 5. Khởi động Kafka + PostgreSQL bằng Docker Compose ─────
echo "[*] Đang khởi động Zookeeper, Kafka và PostgreSQL..."
docker compose up -d --wait --wait-timeout 180 || docker compose up -d
echo "[✓] Docker services đang chạy."

# ── 6. Tạo topic với 3 partition (điều phối tải cho nhiều Consumer) ──
for t in network-traffic nids-control; do
    docker compose exec -T kafka kafka-topics --bootstrap-server ${KAFKA_INTERNAL} \
        --create --if-not-exists --topic "$t" --partitions 3 --replication-factor 1 >/dev/null 2>&1 || true
done
echo "[✓] Topic network-traffic / nids-control sẵn sàng."

# ── 7. Biến môi trường cho Python scripts ───────────────────
export KAFKA_BOOTSTRAP_SERVERS="${KAFKA_INTERNAL}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"
# SNS_TOPIC_ARN đọc từ .env. Thông tin xác thực AWS lấy từ IAM Role gắn vào EC2,
# KHÔNG cần (và không được) lưu Access Key trong mã nguồn.

echo ""
echo "============================================================"
echo "   Hệ thống sẵn sàng!"
echo "   Kafka cho Producer bên ngoài : $EC2_IP:$KAFKA_PORT"
echo "   Kafka cho tiến trình trên EC2: $KAFKA_INTERNAL"
echo "============================================================"
echo ""
echo "   Chạy Producer từ máy khác (terminal 1):"
echo "     KAFKA_BOOTSTRAP_SERVERS=${EC2_IP}:${KAFKA_PORT} python3 producer.py"
echo "   Chạy Producer ngay trên EC2:"
echo "     KAFKA_BOOTSTRAP_SERVERS=${KAFKA_INTERNAL} python3 producer.py"
echo ""
echo "   Chạy Consumer lưu PostgreSQL + SNS (terminal 2):"
echo "     cd tv3 && NIDS_KAFKA=${KAFKA_INTERNAL} python3 consumer_tv3.py"
echo ""
echo "   Hoặc chạy menu demo:  bash run_demo.sh"
echo "   Kiểm tra sức khỏe:     bash scripts/healthcheck.sh"
echo "   Sao lưu lên S3:        bash scripts/backup_postgres_s3.sh"
echo ""
echo "   Dừng hệ thống:"
echo "     docker compose down"
echo "============================================================"
