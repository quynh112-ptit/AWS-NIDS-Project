#!/bin/bash
# ============================================================
# Khôi phục PostgreSQL từ bản sao lưu trên Amazon S3
#   bash scripts/restore_postgres_s3.sh                 # lấy bản mới nhất
#   bash scripts/restore_postgres_s3.sh nids_db_<stamp>.dump.gz
# CẢNH BÁO: lệnh dùng pg_restore --clean, sẽ GHI ĐÈ dữ liệu hiện tại của database.
# ============================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
[ -f .env ] && set -a && . ./.env && set +a

PG_USER="${POSTGRES_USER:-nids_user}"
PG_DB="${POSTGRES_DB:-nids_db}"
BUCKET="${BACKUP_S3_BUCKET:?Chưa khai báo BACKUP_S3_BUCKET trong .env}"
NAME="${1:-}"

if [ -z "$NAME" ]; then
    NAME=$(aws s3 ls "s3://${BUCKET}/postgres/" | awk '{print $4}' | grep '^nids_db_' | sort | tail -1)
    [ -n "$NAME" ] || { echo "[✗] Không tìm thấy bản sao lưu nào trên S3" >&2; exit 1; }
fi

mkdir -p backups
LOCAL="backups/$NAME"
echo "[*] Tải s3://${BUCKET}/postgres/$NAME ..."
aws s3 cp "s3://${BUCKET}/postgres/$NAME" "$LOCAL" --only-show-errors
gzip -t "$LOCAL"

read -r -p "Sẽ ghi đè database '$PG_DB' bằng $NAME. Gõ YES để tiếp tục: " ok
[ "$ok" = "YES" ] || { echo "Đã hủy."; exit 1; }

docker compose up -d --wait postgres
gunzip -c "$LOCAL" | docker compose exec -T postgres pg_restore -U "$PG_USER" -d "$PG_DB" --clean --if-exists --no-owner
COUNT=$(docker compose exec -T postgres psql -U "$PG_USER" -d "$PG_DB" -tAc "SELECT count(*) FROM nids_events" 2>/dev/null || echo "?")
echo "[✓] Khôi phục xong. Bảng nids_events hiện có $COUNT bản ghi."
