#!/bin/bash
# ============================================================
# Kiểm tra sức khỏe & TỰ ĐỘNG KHÔI PHỤC dịch vụ NIDS
#   bash scripts/healthcheck.sh            # chỉ kiểm tra
#   bash scripts/healthcheck.sh --recover  # kiểm tra và tự khởi động lại thành phần lỗi
# Cron (mỗi phút):  * * * * * cd /home/ubuntu/AWS-NIDS-Project && bash scripts/healthcheck.sh --recover >> /var/log/nids-health.log 2>&1
# Khi phải khôi phục, script gửi thông báo qua SNS (nếu có SNS_TOPIC_ARN).
# ============================================================
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
[ -f .env ] && set -a && . ./.env && set +a

RECOVER=0
[ "${1:-}" = "--recover" ] && RECOVER=1
KAFKA_PORT="${KAFKA_PORT:-9092}"
KAFKA_INTERNAL=localhost:29092
FAILED=()

ok()   { echo "  [OK]   $1"; }
fail() { echo "  [LỖI]  $1"; FAILED+=("$1"); }

echo "=== NIDS healthcheck $(date '+%F %T') ==="

# 1. Container hạ tầng
for svc in zookeeper kafka postgres; do
    state=$(docker compose ps --format '{{.Service}} {{.State}} {{.Health}}' 2>/dev/null | awk -v s="$svc" '$1==s{print $2" "$3}')
    if [[ "$state" == running* && "$state" != *unhealthy* ]]; then ok "container $svc ($state)"; else fail "container $svc (${state:-không chạy})"; fi
done

# 2. Kafka trả lời (listener nội bộ)
if docker compose exec -T kafka kafka-topics --bootstrap-server $KAFKA_INTERNAL --list >/dev/null 2>&1; then
    ok "Kafka broker (:$KAFKA_PORT ngoài, :29092 nội bộ)"
else
    fail "Kafka broker (:$KAFKA_PORT ngoài, :29092 nội bộ)"
fi

# 3. PostgreSQL nhận kết nối
if docker compose exec -T postgres pg_isready -U "${POSTGRES_USER:-nids_user}" >/dev/null 2>&1; then
    ok "PostgreSQL :5432"
else
    fail "PostgreSQL :5432"
fi

# 4. Tiến trình ứng dụng (systemd nếu đã cài, nếu không thì kiểm tra tiến trình)
for unit in nids-consumer nids-dashboard nids-qr; do
    if systemctl list-unit-files "$unit.service" >/dev/null 2>&1 && systemctl is-enabled "$unit" >/dev/null 2>&1; then
        if systemctl is-active --quiet "$unit"; then ok "service $unit"; else fail "service $unit"; fi
    fi
done
pgrep -f "consumer_tv3.py|consumer_ids.py" >/dev/null && ok "Consumer ML" || fail "Consumer ML"
curl -fs -o /dev/null --max-time 5 http://localhost:8501/_stcore/health && ok "Dashboard :8501" || fail "Dashboard :8501"

# 5. Độ trễ xử lý (consumer lag) của group lưu PostgreSQL
LAG=$(docker compose exec -T kafka kafka-consumer-groups --bootstrap-server $KAFKA_INTERNAL \
      --describe --group nids-tv3-storage-v1 2>/dev/null | awk 'NR>1 && $6 ~ /^[0-9]+$/ {s+=$6} END{print s+0}')
echo "  [INFO] Consumer lag (nids-tv3-storage-v1): ${LAG:-?} bản ghi"

# 6. Dung lượng ổ đĩa EBS
USE=$(df --output=pcent / | tail -1 | tr -dc '0-9')
if [ "${USE:-0}" -lt 85 ]; then ok "Ổ đĩa / dùng ${USE}%"; else fail "Ổ đĩa / dùng ${USE}% (>85%)"; fi

if [ ${#FAILED[@]} -eq 0 ]; then
    echo "=== Tất cả dịch vụ bình thường ==="
    exit 0
fi

echo "=== ${#FAILED[@]} thành phần lỗi ==="
[ $RECOVER -eq 1 ] || exit 1

echo "[*] Bắt đầu quy trình tự khôi phục..."
docker compose up -d --wait --wait-timeout 180 || docker compose up -d
for unit in nids-consumer nids-dashboard nids-qr; do
    if systemctl is-enabled "$unit" >/dev/null 2>&1 && ! systemctl is-active --quiet "$unit"; then
        sudo systemctl restart "$unit" && echo "  [↻] Đã khởi động lại $unit"
    fi
done

if [ -n "${SNS_TOPIC_ARN:-}" ] && command -v aws >/dev/null; then
    aws sns publish --topic-arn "$SNS_TOPIC_ARN" --region "${AWS_DEFAULT_REGION:-us-east-1}" \
        --subject "[NIDS RECOVERY] Tự động khôi phục dịch vụ" \
        --message "Healthcheck phát hiện lỗi: ${FAILED[*]}. Đã chạy quy trình tự khôi phục lúc $(date '+%F %T')." >/dev/null 2>&1 || true
fi
echo "[✓] Đã chạy xong quy trình khôi phục. Chạy lại healthcheck để xác nhận."
