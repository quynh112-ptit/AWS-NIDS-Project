import json
import joblib
import numpy as np
from kafka import KafkaConsumer
from sklearn.ensemble import RandomForestClassifier

# 1. Giả lập một mô hình ML đã được train
# (Trong thực tế, bạn sẽ dùng joblib.load('model.pkl') để load mô hình đã train trên dataset thật)
print("Đang khởi tạo/Load mô hình Machine Learning...")
mock_model = RandomForestClassifier()
# Train tạm trên dữ liệu dummy (Feature: dst_port, packet_size)
# 0: Normal, 1: Attack (vd: port 22 size lạ, port 3389)
X_dummy = [[80, 500], [22, 100], [3389, 1500], [443, 1200]]
y_dummy = [0, 1, 1, 0] 
mock_model.fit(X_dummy, y_dummy)

# 2. Khởi tạo Kafka Consumer
consumer = KafkaConsumer(
    'network-traffic',
    bootstrap_servers=['localhost:9092'],
    auto_offset_reset='latest',
    value_deserializer=lambda m: json.loads(m.decode('utf-8'))
)

print("Consumer (ML-IDS) đang lắng nghe trên topic 'network-traffic'...")

for message in consumer:
    data = message.value
    
    # Tiền xử lý (Module 04) - Lấy ra các feature cần thiết để đưa vào mô hình
    features = np.array([[data['dst_port'], data['packet_size']]])
    
    # Dự đoán (Module 05)
    prediction = mock_model.predict(features)[0]
    
    # Kết hợp kết quả ML và cờ giả lập để test
    if prediction == 1 or data.get('is_malicious_mock'):
        print(f"\033[91m[CẢNH BÁO TẤN CÔNG] Phát hiện bất thường từ IP: {data['src_ip']} (Port: {data['dst_port']})\033[0m")
        # TODO: Ở bước thực tế trên AWS, bạn sẽ chèn code ghi log vào PostgreSQL hoặc đẩy lên S3 tại đây
    else:
        print(f"\033[92m[Bình thường] Traffic từ {data['src_ip']} an toàn.\033[0m")
