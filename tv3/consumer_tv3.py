"""Phân loại theo mô hình TV2 và lưu kết quả để dashboard truy vấn."""
import json
import math
import os

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
        import boto3
        sns = boto3.client("sns", region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
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
                    print(f"{LABELS[row[6]]} | {row[3]}:{row[4]} | demo={row[8] or '-'}", flush=True)
                    if sns and row[6] and row[8] is None:
                        try:
                            sns.publish(TopicArn=arn, Subject="[NIDS ALERT]",
                                        Message=f"{LABELS[row[6]]} | {row[3]}:{row[4]}")
                        except Exception as exc:
                            print(f"Gửi SNS thất bại ({type(exc).__name__}).", flush=True)
        except KeyboardInterrupt:
            print("Đã dừng Consumer TV3.", flush=True)
        finally:
            consumer.close()


if __name__ == "__main__":
    main()
