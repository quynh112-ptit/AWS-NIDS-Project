import json
import time
import random
from kafka import KafkaProducer

# Cấu hình Producer kết nối tới Kafka
producer = KafkaProducer(
    bootstrap_servers=['localhost:9092'],
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

print("Bắt đầu gửi dữ liệu traffic giả lập vào Kafka...")
try:
    while True:
        # Giả lập một gói tin mạng (NetFlow)
        packet = {
            "src_ip": f"192.168.1.{random.randint(2, 20)}",
            "dst_port": random.choice([80, 443, 22, 21, 3389]),
            "packet_size": random.randint(40, 1500),
            "protocol": random.choice(["TCP", "UDP"]),
            # Giả lập cờ độc hại (tỷ lệ 15% là traffic tấn công)
            "is_malicious_mock": random.random() < 0.15 
        }
        
        producer.send('network-traffic', packet)
        print(f"[Producer] Đã gửi: {packet}")
        
        # Gửi 2 gói mỗi giây
        time.sleep(0.5) 
except KeyboardInterrupt:
    print("Dừng Producer.")
    producer.close()
