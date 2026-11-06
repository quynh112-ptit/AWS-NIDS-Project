"""
Consumer ML-IDS: Lắng nghe Kafka, phân loại traffic bằng mô hình đã train,
gửi cảnh báo qua AWS SNS và lưu kết quả.
"""
import json
import sys
import os
import numpy as np
import joblib
import boto3
from kafka import KafkaConsumer

# Thiết lập UTF-8 cho console Windows
sys.stdout.reconfigure(encoding='utf-8')

# ─────────────────────────────────────────────
# 1. Load mô hình và bộ chuẩn hóa đã huấn luyện
# ─────────────────────────────────────────────
print("[*] Đang load mô hình Machine Learning từ file...")
try:
    model  = joblib.load("nids_model.joblib")
    scaler = joblib.load("scaler.joblib")
    print("[✓] Load mô hình và scaler thành công.")
except FileNotFoundError as e:
    print(f"[✗] Không tìm thấy file model/scaler: {e}")
    print("    → Hãy chạy train_model.py trước để sinh ra nids_model.joblib và scaler.joblib")
    sys.exit(1)

# Phải khớp đúng thứ tự với feature_cols trong train_model.py
FEATURE_COLS = ['dst_port', 'protocol', 'packet_size',
                'duration', 'packets_rate', 'syn_flag', 'ack_flag']

LABEL_NAMES = {
    0: 'Normal (Bình thường)',
    1: 'DDoS Attack (Tấn công từ chối dịch vụ)',
    2: 'Port Scan (Dò quét cổng lén lút)',
    3: 'Brute Force (Bẻ khóa mật khẩu SSH/RDP)'
}

# ─────────────────────────────────────────────
# 2. Cấu hình AWS SNS
# ─────────────────────────────────────────────
# Credentials đọc tự động từ biến môi trường:
#   AWS_ACCESS_KEY_ID     = AKIA... (do bạn phụ trách nhiệm vụ 1 cấp)
#   AWS_SECRET_ACCESS_KEY = ...
#   AWS_DEFAULT_REGION    = us-east-1  (hoặc region bạn kia dùng)
# Không cần hardcode key vào code — boto3 tự đọc biến môi trường.

# TODO: Thay ARN bằng ARN thực tế của Topic SNS bạn đã tạo trên AWS Console
SNS_TOPIC_ARN = os.environ.get(
    'SNS_TOPIC_ARN',
    'arn:aws:sns:us-east-1:123456789012:NIDS-Security-Alerts'
)
try:
    sns_client = boto3.client('sns', region_name=os.environ.get('AWS_DEFAULT_REGION', 'us-east-1'))
except Exception as e:
    print(f"[!] Không khởi tạo được SNS client: {e}")
    sns_client = None

# ─────────────────────────────────────────────
# 3. Kết nối Kafka Consumer
# ─────────────────────────────────────────────
# Local test : không cần set → dùng localhost:9092
# Deploy EC2  : export KAFKA_BOOTSTRAP_SERVERS=<IP_EC2>:9092
KAFKA_SERVERS = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092').split(',')

consumer = KafkaConsumer(
    'network-traffic',
    bootstrap_servers=KAFKA_SERVERS,
    auto_offset_reset='latest',
    group_id='nids-ml-consumer',
    value_deserializer=lambda m: json.loads(m.decode('utf-8'))
)

print("[✓] Consumer (ML-IDS) đang lắng nghe trên topic 'network-traffic'...")
print(f"    Kafka servers : {KAFKA_SERVERS}")
print(f"    Features mô hình sử dụng: {FEATURE_COLS}\n")

# ─────────────────────────────────────────────
# 4. Vòng lặp xử lý message (Micro-batching)
# ─────────────────────────────────────────────
BATCH_SIZE = 50  # Gom 50 gói tin rồi predict 1 lần → tăng throughput
batch_data  = []
batch_meta  = []

def send_sns_alert(src_ip: str, dst_port: int, protocol, label: str):
    """Gửi cảnh báo tấn công qua AWS SNS."""
    if sns_client is None:
        return
    alert_msg = (
        f"[NIDS ALERT] Phát hiện tấn công!\n"
        f"Loại tấn công : {label}\n"
        f"IP nguồn      : {src_ip}\n"
        f"Cổng đích     : {dst_port}\n"
        f"Giao thức     : {protocol}"
    )
    try:
        response = sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Message=alert_msg,
            Subject='[NIDS ALERT] Phát hiện bất thường mạng'
        )
        print(f"    [SNS] Đã gửi cảnh báo (MessageId: {response['MessageId']})")
    except Exception as e:
        print(f"    [SNS] Lỗi khi gửi cảnh báo (Bỏ qua): {e}")

try:
    for message in consumer:
        data = message.value

        # Kiểm tra dữ liệu đủ fields trước khi xử lý
        missing = [f for f in FEATURE_COLS if f not in data]
        if missing:
            print(f"[!] Bỏ qua gói tin thiếu fields: {missing}")
            continue

        # Gom vào batch
        batch_data.append([data[f] for f in FEATURE_COLS])
        batch_meta.append(data)

        if len(batch_data) >= BATCH_SIZE:
            # Chuẩn hóa và dự đoán cả batch một lần
            X_batch   = np.array(batch_data)
            X_scaled  = scaler.transform(X_batch)
            predictions = model.predict(X_scaled)

            for pred, meta in zip(predictions, batch_meta):
                label = LABEL_NAMES[int(pred)]
                src_ip    = meta.get('src_ip', 'N/A')
                dst_port  = meta.get('dst_port', 'N/A')
                protocol  = meta.get('protocol', 'N/A')

                if int(pred) == 0:
                    print(f"\033[92m[Bình thường] {src_ip} → port {dst_port} | {label}\033[0m")
                else:
                    print(f"\033[91m[TẤN CÔNG]    {src_ip} → port {dst_port} | {label}\033[0m")
                    send_sns_alert(src_ip, dst_port, protocol, label)

            # Reset batch
            batch_data.clear()
            batch_meta.clear()

except KeyboardInterrupt:
    # Flush batch còn lại trước khi thoát
    if batch_data:
        print(f"\n[*] Đang flush {len(batch_data)} gói tin còn lại trong batch...")
        X_batch      = np.array(batch_data)
        X_scaled     = scaler.transform(X_batch)
        predictions  = model.predict(X_scaled)
        for pred, meta in zip(predictions, batch_meta):
            label    = LABEL_NAMES[int(pred)]
            src_ip   = meta.get('src_ip', 'N/A')
            dst_port = meta.get('dst_port', 'N/A')
            protocol = meta.get('protocol', 'N/A')
            if int(pred) == 0:
                print(f"\033[92m[Bình thường] {src_ip} → port {dst_port} | {label}\033[0m")
            else:
                print(f"\033[91m[TẤN CÔNG]    {src_ip} → port {dst_port} | {label}\033[0m")
                send_sns_alert(src_ip, dst_port, protocol, label)
    print("[*] Dừng Consumer.")
    consumer.close()
