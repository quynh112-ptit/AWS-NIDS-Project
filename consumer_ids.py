"""
Consumer ML-IDS: Lắng nghe Kafka, phân loại traffic bằng mô hình đã train,
tự động gửi cảnh báo qua AWS SNS khi phát hiện tấn công mạng và lưu kết quả.
"""
import json
import sys
import os
import time
from datetime import datetime
import numpy as np
import joblib
import boto3
from kafka import KafkaConsumer

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

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
# 2. Cấu hình AWS SNS (Cảnh báo thời gian thực)
# ─────────────────────────────────────────────
SNS_TOPIC_ARN = os.environ.get(
    'SNS_TOPIC_ARN',
    'arn:aws:sns:us-east-1:400131408828:NIDS-Alerts'
)
try:
    sns_client = boto3.client('sns', region_name=os.environ.get('AWS_DEFAULT_REGION', 'us-east-1'))
except Exception as e:
    print(f"[!] Không khởi tạo được SNS client: {e}")
    sns_client = None

# Quản lý thời gian gửi cảnh báo tự động (Cooldown chống spam)
ALERT_COOLDOWN_SECONDS = 30  # Mỗi loại tấn công chỉ gửi 1 email cảnh báo mỗi 30 giây
last_alert_time = {}

def send_sns_alert(src_ip: str, dst_port: int, protocol, label: str):
    """
    TỰ ĐỘNG BẮN EMAIL / CẢNH BÁO QUA AWS SNS KHI PHÁT HIỆN TẤN CÔNG
    Áp dụng Cooldown thông minh để không spam hàng ngàn mail khi bị DDoS.
    """
    if sns_client is None:
        return

    now = time.time()
    # Kiểm tra thời gian gửi gần nhất của loại tấn công này
    last_sent = last_alert_time.get(label, 0)
    if (now - last_sent) < ALERT_COOLDOWN_SECONDS:
        return  # Đang trong thời gian cooldown, bỏ qua gửi lặp lại

    last_alert_time[label] = now
    now_str = datetime.now().strftime("%H:%M:%S ngày %d/%m/%Y")

    alert_msg = (
        f"🚨 [CẢNH BÁO NIDS - HỆ THỐNG PHÁT HIỆN XÂM NHẬP MẠNG]\n"
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
        response = sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Message=alert_msg,
            Subject=f'[AWS NIDS ALERT] Phát hiện {label} từ IP {src_ip}'
        )
        msg_id = response.get('MessageId', 'OK')
        print(f"\n\033[93m⚡ [AWS SNS AUTO-ALERT] Đã tự động bắn email cảnh báo! (MessageId: {msg_id})\033[0m\n")
    except Exception as e:
        print(f"    [SNS] Lỗi khi gửi cảnh báo tự động (Bỏ qua): {e}")

# ─────────────────────────────────────────────
# 3. Kết nối Kafka Consumer
# ─────────────────────────────────────────────
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
                    # TỰ ĐỘNG BẮN CẢNH BÁO AWS SNS KHI CÓ TẤN CÔNG
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
