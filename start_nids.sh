#!/bin/bash
# ============================================================
# Script khởi động NIDS trên EC2
# Chạy: bash start_nids.sh
# ============================================================

set -e  # Dừng ngay nếu có lỗi

echo "============================================================"
echo "   NIDS System Startup Script"
echo "============================================================"

# ── 1. Lấy IP Public hiện tại của EC2 ───────────────────────
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
git pull origin main
echo "[✓] Pull xong."

# ── 3. Cập nhật KAFKA_ADVERTISED_LISTENERS với IP mới ───────
# (IP EC2 đổi mỗi lần khởi động → cần cập nhật)
sed -i "s|KAFKA_ADVERTISED_LISTENERS:.*|KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://${EC2_IP}:9092|" docker-compose.yml
echo "[✓] Đã cập nhật Kafka Advertised Listener → $EC2_IP:9092"

# ── 4. Khởi động Kafka + PostgreSQL bằng Docker Compose ─────
echo "[*] Đang khởi động Kafka và PostgreSQL..."
docker compose up -d
echo "[✓] Docker services đang chạy."

# ── 5. Chờ Kafka sẵn sàng (khoảng 15 giây) ─────────────────
echo "[*] Chờ Kafka khởi động (15 giây)..."
sleep 15

# ── 6. Set biến môi trường cho Python scripts ───────────────
export KAFKA_BOOTSTRAP_SERVERS="${EC2_IP}:9092"
export AWS_DEFAULT_REGION="us-east-1"
export SNS_TOPIC_ARN="arn:aws:sns:us-east-1:400131408828:NIDS-Alerts"
# AWS_ACCESS_KEY_ID và AWS_SECRET_ACCESS_KEY đọc từ IAM Role EC2
# (không cần hardcode nếu EC2 đã được gán IAM Role đúng)

echo ""
echo "============================================================"
echo "   Hệ thống sẵn sàng!"
echo "   KAFKA_BOOTSTRAP_SERVERS = $EC2_IP:9092"
echo "============================================================"
echo ""
echo "   Chạy Producer (terminal 1):"
echo "     KAFKA_BOOTSTRAP_SERVERS=${EC2_IP}:9092 python3 producer.py"
echo ""
echo "   Chạy Consumer (terminal 2):"
echo "     KAFKA_BOOTSTRAP_SERVERS=${EC2_IP}:9092 python3 consumer_ids.py"
echo ""
echo "   Dừng hệ thống:"
echo "     docker compose down"
echo "============================================================"

