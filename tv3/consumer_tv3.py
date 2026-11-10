"""Phân loại theo mô hình TV2, lưu kết quả PostgreSQL và tự động bắn cảnh báo AWS SNS khi có tấn công."""
import json
import math
import os
import time
from datetime import datetime

import joblib
import pandas as pd
import psycopg
from kafka import KafkaConsumer

from tv3_config import FEATURES, LABELS, ROOT, TOPIC, database_dsn, kafka_servers

INSERT_SQL = """
INSERT INTO nids_events
(topic, partition_id, message_offset, src_ip, dst_port, protocol, prediction, scenario, demo_id)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (topic, partition_id, message_offset) DO NOTHING
RETURNING prediction
"""

ALERT_COOLDOWN_SECONDS = 30
last_alert_time = {}

def trigger_sns_alert(sns_client, topic_arn, label, src_ip, dst_port, protocol):
    """Tự động bắn email cảnh báo qua AWS SNS khi phát hiện tấn công."""
    if not sns_client or not topic_arn:
        return
    now = time.time()
    if (now - last_alert_time.get(label, 0)) < ALERT_COOLDOWN_SECONDS:
        return  # Đang trong thời gian cooldown, tránh spam mail
    
    last_alert_time[label] = now
    now_str = datetime.now().strftime("%H:%M:%S ngày %d/%m/%Y")
    alert_msg = (
        f"🚨 [CẢNH BÁO NIDS - HỆ THỐNG PHÁT HIỆN TẤN CÔNG]\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• Loại tấn công : {label}\n"
        f"• IP Kẻ tấn công: {src_ip}\n"
        f"• Cổng mục tiêu : {dst_port}\n"
        f"• Giao thức     : {protocol}\n"
        f"• Thời gian     : {now_str}\n"
        f"• Hành động     : Mô hình AI phát hiện tức thì và kích hoạt cảnh báo!\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    try:
        res = sns_client.publish(
            TopicArn=topic_arn,
            Subject=f"[AWS NIDS ALERT] Phát hiện {label} từ IP {src_ip}",
            Message=alert_msg
        )
        print(f"\n⚡ [AWS SNS AUTO-ALERT] Đã tự động bắn email cảnh báo tới Quản trị viên! (MsgId: {res.get('MessageId')})\n", flush=True)
    except Exception as exc:
        print(f"Gửi SNS thất bại ({type(exc).__name__}: {exc}).", flush=True)


def classify(messages, model, scaler):
    records = []
    inputs = []
    for message in messages:
        try:
            data = json.loads(message.value)
            features = [float(data[name]) for name in FEATURES]
            if not all(math.isfinite(value) for value in features):
                raise ValueError("non-finite feature")
            port, protocol = features[:2]
            if not (port.is_integer() and 0 <= port <= 65535 and protocol.is_integer() and 0 <= protocol <= 255):
                raise ValueError("invalid port or protocol")
        except (KeyError, TypeError, ValueError, OverflowError):
            print(f"Bỏ bản ghi sai định dạng: partition={message.partition}, offset={message.offset}", flush=True)
            continue
        inputs.append(features)
        records.append((message.topic, message.partition, message.offset,
                        str(data.get("src_ip", "N/A"))[:64], int(port), int(protocol),
                        str(data.get("traffic_type", "unknown"))[:48],
                        str(data["demo_id"])[:48] if data.get("demo_id") else None))
    if not inputs:
        return []
    matrix = pd.DataFrame(inputs, columns=FEATURES)
    predictions = model.predict(scaler.transform(matrix))
    return [(*record[:6], int(pred), *record[6:]) for record, pred in zip(records, predictions)]


def main():
    model = joblib.load(ROOT / "nids_model.joblib")
    scaler = joblib.load(ROOT / "scaler.joblib")
    arn = os.getenv("SNS_TOPIC_ARN")
    sns = None
    if arn:
        try:
            import boto3
            sns = boto3.client("sns", region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
        except Exception as e:
            print(f"[!] Không thể khởi tạo AWS SNS client: {e}")

    with psycopg.connect(database_dsn(), connect_timeout=5) as db:
        db.execute((ROOT / "schema.sql").read_text(encoding="utf-8-sig"))
        db.commit()
        consumer = KafkaConsumer(
            TOPIC, bootstrap_servers=kafka_servers(), group_id="nids-tv3-storage-v1",
            enable_auto_commit=False, auto_offset_reset="latest",
            api_version_auto_timeout_ms=10000,
        )
        ready = False
        try:
            while True:
                groups = consumer.poll(timeout_ms=1000, max_records=50)
                if not ready and consumer.assignment():
                    print("Consumer TV3 đã nhận phân vùng Kafka và sẵn sàng ghi PostgreSQL.", flush=True)
                    ready = True
                if not groups:
                    continue
                rows = classify((message for group in groups.values() for message in group), model, scaler)
                new_rows = []
                with db.transaction():
                    for row in rows:
                        if db.execute(INSERT_SQL, row).fetchone():
                            new_rows.append(row)
                consumer.commit()
                for row in new_rows:
                    pred_idx = row[6]
                    label_name = LABELS.get(pred_idx, f"Threat #{pred_idx}")
                    print(f"{label_name} | {row[3]}:{row[4]} | demo={row[8] or '-'}", flush=True)
                    
                    # TỰ ĐỘNG BẮN CẢNH BÁO AWS SNS KHI PHÁT HIỆN TẤN CÔNG (pred_idx != 0)
                    if sns and pred_idx != 0:
                        trigger_sns_alert(sns, arn, label_name, row[3], row[4], row[5])
        except KeyboardInterrupt:
            print("Đã dừng Consumer TV3.", flush=True)
        finally:
            consumer.close()


if __name__ == "__main__":
    main()
