"""
Lưu trữ phân tầng (Data Tiering): chuyển dữ liệu "lạnh" từ PostgreSQL lên Amazon S3.

- Lấy các bản ghi nids_events cũ hơn ARCHIVE_AFTER_HOURS (mặc định 24h)
- Ghi thành file JSON Lines nén gzip, phân vùng theo ngày: s3://<bucket>/events/dt=YYYY-MM-DD/...
- Mã hóa SSE-S3 (AES-256); chỉ xóa khỏi PostgreSQL SAU KHI S3 xác nhận đã lưu (--delete)

Chạy:  python3 scripts/archive_events_s3.py            # chỉ sao chép lên S3
       python3 scripts/archive_events_s3.py --delete   # sao chép rồi xóa bản ghi cũ khỏi DB
Cron:  30 2 * * * cd /home/ubuntu/AWS-NIDS-Project && .venv/bin/python scripts/archive_events_s3.py --delete
"""
import argparse
import gzip
import io
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Archive NIDS events to S3")
    parser.add_argument("--hours", type=int, default=int(os.getenv("ARCHIVE_AFTER_HOURS", "24")))
    parser.add_argument("--delete", action="store_true", help="Xóa bản ghi đã lưu S3 khỏi PostgreSQL")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ đếm, không ghi S3")
    args = parser.parse_args()

    import boto3
    import psycopg

    bucket = os.getenv("BACKUP_S3_BUCKET")
    dsn = os.getenv("NIDS_DSN")
    if not bucket or not dsn:
        print("Thiếu BACKUP_S3_BUCKET hoặc NIDS_DSN trong .env", file=sys.stderr)
        return 1

    cutoff = datetime.now(timezone.utc) - timedelta(hours=args.hours)
    s3 = boto3.client("s3", region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"))

    with psycopg.connect(dsn, connect_timeout=5) as db:
        rows = db.execute(
            "SELECT topic, partition_id, message_offset, observed_at, src_ip, dst_port, "
            "protocol, prediction, scenario, demo_id FROM nids_events "
            "WHERE observed_at < %s ORDER BY observed_at",
            (cutoff,),
        ).fetchall()
        print(f"[*] {len(rows)} bản ghi cũ hơn {cutoff.isoformat()}")
        if not rows or args.dry_run:
            return 0

        cols = ["topic", "partition_id", "message_offset", "observed_at", "src_ip",
                "dst_port", "protocol", "prediction", "scenario", "demo_id"]
        by_day: dict[str, list[dict]] = {}
        for r in rows:
            rec = dict(zip(cols, r))
            rec["observed_at"] = rec["observed_at"].isoformat()
            by_day.setdefault(rec["observed_at"][:10], []).append(rec)

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        for day, recs in by_day.items():
            buf = io.BytesIO()
            with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
                for rec in recs:
                    gz.write((json.dumps(rec, ensure_ascii=False) + "\n").encode("utf-8"))
            key = f"events/dt={day}/nids_events_{stamp}.jsonl.gz"
            s3.put_object(Bucket=bucket, Key=key, Body=buf.getvalue(),
                          ServerSideEncryption="AES256", ContentType="application/gzip")
            s3.head_object(Bucket=bucket, Key=key)  # xác nhận đã lưu trước khi xóa
            print(f"[✓] s3://{bucket}/{key} ({len(recs)} bản ghi)")

        if args.delete:
            with db.transaction():
                cur = db.execute("DELETE FROM nids_events WHERE observed_at < %s", (cutoff,))
            print(f"[✓] Đã xóa {cur.rowcount} bản ghi khỏi PostgreSQL (đã có trên S3)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
