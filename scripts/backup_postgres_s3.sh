#!/bin/bash
# ============================================================
# Sao lưu PostgreSQL (dữ liệu nóng) lên Amazon S3
#   - pg_dump định dạng custom (-Fc), nén gzip
#   - Mã hóa phía máy chủ S3 (SSE-S3, AES-256), truyền qua HTTPS (TLS)
#   - Giữ BACKUP_RETENTION_DAYS bản trên ổ EBS, S3 dùng Lifecycle để chuyển Glacier/xóa
# Chạy thủ công:  bash scripts/backup_postgres_s3.sh
# Chạy định kỳ:   crontab -e  →  0 */6 * * * cd /home/ubuntu/AWS-NIDS-Project && bash scripts/backup_postgres_s3.sh >> /var/log/nids-backup.log 2>&1
# Yêu cầu: EC2 gắn IAM Role có quyền s3:PutObject trên bucket (deploy/iam/nids-ec2-policy.json)
# ============================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
[ -f .env ] && set -a && . ./.env && set +a

PG_USER="${POSTGRES_USER:-nids_user}"
PG_DB="${POSTGRES_DB:-nids_db}"
BUCKET="${BACKUP_S3_BUCKET:?Chưa khai báo BACKUP_S3_BUCKET trong .env}"
RETENTION="${BACKUP_RETENTION_DAYS:-7}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="$ROOT_DIR/backups"
FILE="$BACKUP_DIR/nids_db_${STAMP}.dump.gz"

mkdir -p "$BACKUP_DIR"

echo "[*] $(date -u) Bắt đầu sao lưu database $PG_DB ..."
docker compose exec -T postgres pg_dump -U "$PG_USER" -d "$PG_DB" -Fc | gzip -9 > "$FILE"

# Kiểm tra bản sao lưu không rỗng và đọc được (phát hiện bản hỏng sớm)
if [ ! -s "$FILE" ] || ! gzip -t "$FILE"; then
    echo "[✗] Bản sao lưu lỗi hoặc rỗng: $FILE" >&2
    exit 1
fi
SHA=$(sha256sum "$FILE" | cut -d' ' -f1)
echo "[✓] Đã tạo $FILE ($(du -h "$FILE" | cut -f1), sha256=$SHA)"

aws s3 cp "$FILE" "s3://${BUCKET}/postgres/$(basename "$FILE")" \
    --sse AES256 --only-show-errors \
    --metadata "sha256=${SHA},source=ec2-nids"
echo "[✓] Đã tải lên s3://${BUCKET}/postgres/$(basename "$FILE")"

# Xóa bản cục bộ quá hạn để giải phóng ổ EBS
find "$BACKUP_DIR" -name 'nids_db_*.dump.gz' -mtime +"$RETENTION" -delete
echo "[✓] Hoàn tất sao lưu."
