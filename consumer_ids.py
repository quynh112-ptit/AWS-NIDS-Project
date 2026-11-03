import json
import numpy as np
import boto3
from kafka import KafkaConsumer
from sklearn.ensemble import RandomForestClassifier

# Cấu hình AWS SNS (Thay ARN bằng ARN thực tế của bạn sau)
SNS_TOPIC_ARN = 'arn:aws:sns:us-east-1:123456789012:NIDS-Security-Alerts'
sns_client = boto3.client('sns', region_name='us-east-1')

print("Đang khởi tạo/Load mô hình Machine Learning...")
mock_model = RandomForestClassifier()
X_dummy = [[80, 500], [22, 100], [3389, 1500], [443, 1200]]
y_dummy = [0, 1, 1, 0] 
mock_model.fit(X_dummy, y_dummy)

consumer = KafkaConsumer(
    'network-traffic',
    bootstrap_servers=['localhost:9092'],
    auto_offset_reset='latest',
    value_deserializer=lambda m: json.loads(m.decode('utf-8'))
)

print("Consumer (ML-IDS) đang lắng nghe trên topic 'network-traffic'...")

for message in consumer:
    data = message.value
    features = np.array([[data['dst_port'], data['packet_size']]])
    prediction = mock_model.predict(features)[0]
    
    if prediction == 1 or data.get('is_malicious_mock'):
        alert_msg = f"CẢNH BÁO: Phát hiện truy cập độc hại!\nIP Nguồn: {data['src_ip']}\nCổng Đích: {data['dst_port']}\nGiao thức: {data['protocol']}"
        print(f"\033[91m[TẤN CÔNG] {alert_msg}\033[0m")
        
        try:
            response = sns_client.publish(
                TopicArn=SNS_TOPIC_ARN,
                Message=alert_msg,
                Subject='[NIDS ALERT] Phát hiện bất thường mạng'
            )
            print(f"Đã gửi cảnh báo thành công (MessageId: {response['MessageId']})")
        except Exception as e:
            print(f"Lỗi khi gửi cảnh báo SNS (Bỏ qua): {e}")
            
    else:
        print(f"\033[92m[Bình thường] Traffic từ {data['src_ip']} an toàn.\033[0m")