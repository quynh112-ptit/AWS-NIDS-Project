# Bản Demo: Hệ thống ML-IDS với Apache Kafka

## Yêu cầu
- Docker và Docker Compose (để chạy Kafka/Zookeeper)
- Python 3.9+

## Hướng dẫn chạy (Local test trước khi đưa lên AWS)

1. Khởi động hạ tầng Kafka & Zookeeper (Mở Terminal 1):
   ```bash
   docker-compose up -d
   ```
   *Đợi khoảng 10-15 giây để Kafka khởi động hoàn toàn.*

2. Cài đặt thư viện Python môi trường ảo:
   ```bash
   pip install -r requirements.txt
   ```

3. Chạy NIDS Consumer (Mở Terminal 2 - để lắng nghe và phân tích bằng ML):
   ```bash
   python consumer_ids.py
   ```

4. Chạy Traffic Producer (Mở Terminal 3 - để bắn dữ liệu giả lập vào hệ thống):
   ```bash
   python producer.py
   ```
   
5. Quan sát Terminal 2, bạn sẽ thấy hệ thống lập tức bắt được các gói tin và phân loại Normal/Attack theo thời gian thực (Real-time Streaming).
