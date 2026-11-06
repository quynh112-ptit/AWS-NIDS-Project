"""
Producer: Giả lập luồng traffic mạng NetFlow đẩy vào Kafka.
Sinh đủ 7 features khớp với train_model.py để consumer ML hoạt động đúng.
"""
import json
import os
import sys
import time
import random
import numpy as np
from kafka import KafkaProducer

# Thiết lập UTF-8 cho console Windows
sys.stdout.reconfigure(encoding='utf-8')

# ─── Đọc địa chỉ Kafka từ biến môi trường ───
# Local test : không cần set → dùng localhost:9092
# Deploy EC2  : export KAFKA_BOOTSTRAP_SERVERS=<IP_EC2>:9092
KAFKA_SERVERS = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092').split(',')

# Cấu hình Producer kết nối tới Kafka
producer = KafkaProducer(
    bootstrap_servers=KAFKA_SERVERS,
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

# ─── Cấu hình giả lập ───────────────────────
SEND_INTERVAL = 0.01   # 0.01s / gói → ~100 gói/giây
ATTACK_RATIO  = 0.20   # 20% là traffic tấn công

# Danh sách IP giả lập
NORMAL_IPS  = [f"10.0.0.{i}"     for i in range(2, 50)]
ATTACK_IPS  = [f"185.220.{i}.{j}" for i in range(100, 110) for j in range(1, 10)]

def gen_normal_packet(src_ip: str) -> dict:
    """Sinh gói tin traffic bình thường."""
    return {
        "src_ip"      : src_ip,
        "dst_port"    : int(np.random.choice([80, 443, 53, 8080, 22, 123],
                            p=[0.25, 0.50, 0.15, 0.05, 0.03, 0.02])),
        "protocol"    : int(np.random.choice([6, 17], p=[0.75, 0.25])),
        "packet_size" : float(np.clip(np.random.normal(750, 350), 64, 1500)),
        "duration"    : float(np.clip(np.random.exponential(2.5), 0.01, 60.0)),
        "packets_rate": float(np.clip(np.random.poisson(45), 1, 250)),
        "syn_flag"    : int(np.random.choice([0, 1], p=[0.85, 0.15])),
        "ack_flag"    : int(np.random.choice([0, 1], p=[0.15, 0.85])),
        "traffic_type": "normal"
    }

def gen_ddos_packet(src_ip: str) -> dict:
    """Sinh gói tin tấn công DDoS."""
    return {
        "src_ip"      : src_ip,
        "dst_port"    : int(np.random.choice([80, 443, 53, 8080], p=[0.40, 0.35, 0.15, 0.10])),
        "protocol"    : int(np.random.choice([6, 17], p=[0.80, 0.20])),
        "packet_size" : float(np.clip(np.random.normal(128, 30), 40, 512)),
        "duration"    : float(np.random.uniform(0.001, 0.2)),
        "packets_rate": float(np.random.uniform(2500, 12000)),
        "syn_flag"    : int(np.random.choice([0, 1], p=[0.05, 0.95])),
        "ack_flag"    : 0,
        "traffic_type": "ddos"
    }

def gen_portscan_packet(src_ip: str) -> dict:
    """Sinh gói tin tấn công Port Scan."""
    return {
        "src_ip"      : src_ip,
        "dst_port"    : int(np.random.choice([21, 22, 23, 25, 80, 110, 143, 443, 3306, 3389, 8080])),
        "protocol"    : 6,
        "packet_size" : float(np.clip(np.random.normal(54, 6), 40, 80)),
        "duration"    : float(np.random.uniform(0.001, 0.05)),
        "packets_rate": float(np.random.uniform(50, 250)),
        "syn_flag"    : 1,
        "ack_flag"    : 0,
        "traffic_type": "port_scan"
    }

def gen_bruteforce_packet(src_ip: str) -> dict:
    """Sinh gói tin tấn công Brute Force."""
    return {
        "src_ip"      : src_ip,
        "dst_port"    : int(np.random.choice([22, 3389, 21], p=[0.60, 0.30, 0.10])),
        "protocol"    : 6,
        "packet_size" : float(np.clip(np.random.normal(280, 60), 100, 600)),
        "duration"    : float(np.random.uniform(0.5, 3.0)),
        "packets_rate": float(np.random.uniform(15, 60)),
        "syn_flag"    : int(np.random.choice([0, 1], p=[0.70, 0.30])),
        "ack_flag"    : 1,
        "traffic_type": "brute_force"
    }

# ─── Vòng lặp gửi gói tin ───────────────────
print("[✓] Producer bắt đầu gửi dữ liệu traffic vào Kafka topic 'network-traffic'...")
print(f"    Kafka servers : {KAFKA_SERVERS}")
print(f"    Tốc độ: ~{int(1/SEND_INTERVAL)} gói/giây | Tỷ lệ tấn công: {ATTACK_RATIO*100:.0f}%\n")

sent_count = 0
try:
    while True:
        roll = random.random()

        if roll > ATTACK_RATIO:
            # Traffic bình thường
            packet = gen_normal_packet(random.choice(NORMAL_IPS))
        elif roll < ATTACK_RATIO * 0.40:
            # DDoS (40% trong nhóm tấn công)
            packet = gen_ddos_packet(random.choice(ATTACK_IPS))
        elif roll < ATTACK_RATIO * 0.70:
            # Port Scan (30%)
            packet = gen_portscan_packet(random.choice(ATTACK_IPS))
        else:
            # Brute Force (30%)
            packet = gen_bruteforce_packet(random.choice(ATTACK_IPS))

        producer.send('network-traffic', packet)
        sent_count += 1

        if sent_count % 100 == 0:
            print(f"[Producer] Đã gửi {sent_count:,} gói | Mới nhất: {packet['traffic_type']} từ {packet['src_ip']}")

        time.sleep(SEND_INTERVAL)

except KeyboardInterrupt:
    print(f"\n[*] Dừng Producer. Tổng đã gửi: {sent_count:,} gói tin.")
    producer.flush()
    producer.close()
