"""
Huấn luyện Mô hình Machine Learning cho Hệ thống NIDS (Network Intrusion Detection)
Đề tài: NIDS thời gian thực bằng Machine Learning & Apache Kafka trên AWS
"""
import json
import time
import sys
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
import joblib

# Thiết lập UTF-8 cho console Windows
sys.stdout.reconfigure(encoding='utf-8')

# Thiết lập seed để đảm bảo tính tái lập (Reproducibility)
np.random.seed(42)

def generate_nids_dataset(n_samples=50000):
    """
    Sinh tập dữ liệu lưu lượng mạng chuẩn NetFlow mô phỏng sát với thực tế (NSL-KDD / CICIDS).
    Bao gồm 4 lớp lưu lượng:
    - 0: Normal (Lưu lượng thông thường: lướt web 80/443, DNS 53, truyền file)
    - 1: DDoS (Tấn công từ chối dịch vụ: bão gói tin, tốc độ cực cao, SYN/UDP flood)
    - 2: Port Scan (Dò quét cổng lén lút: quét liên tiếp port 21, 22, 23, 80, 443, 3389)
    - 3: Brute Force (Tấn công bẻ khóa mật khẩu nhắm vào SSH 22, RDP 3389)
    """
    print(f"[*] Đang khởi tạo bộ dữ liệu lưu lượng mạng NetFlow ({n_samples:,} mẫu)...")
    
    # Phân bổ tỷ lệ các loại lưu lượng trong mạng thực tế:
    # 60% Bình thường, 20% DDoS, 12% Port Scan, 8% Brute Force
    n_normal = int(n_samples * 0.60)
    n_ddos = int(n_samples * 0.20)
    n_portscan = int(n_samples * 0.12)
    n_bruteforce = n_samples - (n_normal + n_ddos + n_portscan)

    # 1. Normal Traffic
    normal_dst_port = np.random.choice([80, 443, 53, 8080, 22, 123], size=n_normal, p=[0.25, 0.50, 0.15, 0.05, 0.03, 0.02])
    normal_protocol = np.random.choice([6, 17], size=n_normal, p=[0.75, 0.25])  # 6: TCP, 17: UDP
    normal_packet_size = np.random.normal(loc=750, scale=350, size=n_normal).clip(64, 1500)
    normal_duration = np.random.exponential(scale=2.5, size=n_normal).clip(0.01, 60.0)
    normal_packets_rate = np.random.poisson(lam=45, size=n_normal).clip(1, 250)
    normal_syn_flag = np.random.choice([0, 1], size=n_normal, p=[0.85, 0.15])
    normal_ack_flag = np.random.choice([0, 1], size=n_normal, p=[0.15, 0.85])
    normal_labels = np.zeros(n_normal, dtype=int)

    # 2. DDoS Attack (Bão gói tin, rate vọt cao, gói tin kích thước đồng nhất, SYN flood)
    ddos_dst_port = np.random.choice([80, 443, 53, 8080], size=n_ddos, p=[0.40, 0.35, 0.15, 0.10])
    ddos_protocol = np.random.choice([6, 17], size=n_ddos, p=[0.80, 0.20])
    ddos_packet_size = np.random.normal(loc=128, scale=30, size=n_ddos).clip(40, 512)
    ddos_duration = np.random.uniform(0.001, 0.2, size=n_ddos)
    ddos_packets_rate = np.random.uniform(2500, 12000, size=n_ddos) # Tốc độ cực cao
    ddos_syn_flag = np.random.choice([0, 1], size=n_ddos, p=[0.05, 0.95])
    ddos_ack_flag = np.zeros(n_ddos, dtype=int)
    ddos_labels = np.ones(n_ddos, dtype=int)

    # 3. Port Scan (Quét nhiều cổng, gói tin siêu nhỏ, SYN flag = 1, ACK = 0, duration cực ngắn)
    portscan_dst_port = np.random.choice([21, 22, 23, 25, 80, 110, 143, 443, 3306, 3389, 8080], size=n_portscan)
    portscan_protocol = np.full(n_portscan, 6) # Chủ yếu TCP SYN Scan
    portscan_packet_size = np.random.normal(loc=54, scale=6, size=n_portscan).clip(40, 80)
    portscan_duration = np.random.uniform(0.001, 0.05, size=n_portscan)
    portscan_packets_rate = np.random.uniform(50, 250, size=n_portscan)
    portscan_syn_flag = np.ones(n_portscan, dtype=int)
    portscan_ack_flag = np.zeros(n_portscan, dtype=int)
    portscan_labels = np.full(n_portscan, 2, dtype=int)

    # 4. Brute Force (Tấn công bẻ khóa mật mã SSH 22 hoặc RDP 3389, lặp đi lặp lại)
    brute_dst_port = np.random.choice([22, 3389, 21], size=n_bruteforce, p=[0.60, 0.30, 0.10])
    brute_protocol = np.full(n_bruteforce, 6) # TCP
    brute_packet_size = np.random.normal(loc=280, scale=60, size=n_bruteforce).clip(100, 600)
    brute_duration = np.random.uniform(0.5, 3.0, size=n_bruteforce)
    brute_packets_rate = np.random.uniform(15, 60, size=n_bruteforce)
    brute_syn_flag = np.random.choice([0, 1], size=n_bruteforce, p=[0.70, 0.30])
    brute_ack_flag = np.ones(n_bruteforce, dtype=int)
    brute_labels = np.full(n_bruteforce, 3, dtype=int)

    # Gộp toàn bộ dữ liệu vào DataFrame
    data = {
        'dst_port': np.concatenate([normal_dst_port, ddos_dst_port, portscan_dst_port, brute_dst_port]),
        'protocol': np.concatenate([normal_protocol, ddos_protocol, portscan_protocol, brute_protocol]),
        'packet_size': np.concatenate([normal_packet_size, ddos_packet_size, portscan_packet_size, brute_packet_size]),
        'duration': np.concatenate([normal_duration, ddos_duration, portscan_duration, brute_duration]),
        'packets_rate': np.concatenate([normal_packets_rate, ddos_packets_rate, portscan_packets_rate, brute_packets_rate]),
        'syn_flag': np.concatenate([normal_syn_flag, ddos_syn_flag, portscan_syn_flag, brute_syn_flag]),
        'ack_flag': np.concatenate([normal_ack_flag, ddos_ack_flag, portscan_ack_flag, brute_ack_flag]),
        'label': np.concatenate([normal_labels, ddos_labels, portscan_labels, brute_labels])
    }
    df = pd.DataFrame(data)
    
    # Shuffle dữ liệu
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)
    return df

def train_and_evaluate():
    # 1. Sinh tập dữ liệu
    df = generate_nids_dataset(n_samples=50000)
    
    feature_cols = ['dst_port', 'protocol', 'packet_size', 'duration', 'packets_rate', 'syn_flag', 'ack_flag']
    X = df[feature_cols]
    y = df['label']

    label_names = {
        0: 'Normal (Bình thường)',
        1: 'DDoS Attack (Tấn công từ chối dịch vụ)',
        2: 'Port Scan (Dò quét cổng lén lút)',
        3: 'Brute Force (Bẻ khóa mật khẩu SSH/RDP)'
    }

    # 2. Phân chia Train / Test (80% Train, 20% Test)
    print("[*] Đang phân chia tập Train / Test (80/20)...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # 3. Chuẩn hóa dữ liệu (StandardScaler) cho các thuộc tính số liên tục
    print("[*] Đang chuẩn hóa dữ liệu với StandardScaler...")
    scaler = StandardScaler()
    scaler.fit(X_train)
    
    X_train_scaled = scaler.transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # 4. Huấn luyện Random Forest Classifier
    print("[*] Đang huấn luyện Random Forest Classifier (n_estimators=100, max_depth=12)...")
    start_time = time.time()
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=12,
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1
    )
    model.fit(X_train_scaled, y_train)
    train_duration = time.time() - start_time
    print(f"[✓] Huấn luyện hoàn tất trong: {train_duration:.2f} giây.")

    # 5. Đánh giá chất lượng mô hình trên tập Test
    print("\n" + "="*60)
    print("           KẾT QUẢ ĐÁNH GIÁ MÔ HÌNH MACHINE LEARNING")
    print("="*60)
    
    y_pred = model.predict(X_test_scaled)
    acc = accuracy_score(y_test, y_pred)
    print(f"\n[+] Độ chính xác tổng thể (Accuracy Score): {acc * 100:.2f}%\n")

    report_str = classification_report(
        y_test, y_pred, 
        target_names=[label_names[i] for i in range(4)], 
        digits=4
    )
    print("Báo cáo phân loại chi tiết (Classification Report):")
    print(report_str)

    cm = confusion_matrix(y_test, y_pred)
    print("Ma trận nhầm lẫn (Confusion Matrix):")
    print(cm)

    # Đánh giá độ quan trọng của các đặc trưng (Feature Importance)
    print("\nĐộ quan trọng của các đặc trưng (Feature Importances):")
    importances = model.feature_importances_
    for feat, imp in sorted(zip(feature_cols, importances), key=lambda x: x[1], reverse=True):
        print(f" - {feat:15s}: {imp * 100:6.2f}%")

    # 6. Đo lường tốc độ suy luận (Inference Speed / Latency)
    sample_batch = X_test_scaled[:100]
    t0 = time.perf_counter()
    _ = model.predict(sample_batch)
    batch_lat = (time.perf_counter() - t0) * 1000 # ms
    print(f"\n[+] Độ trễ dự đoán Micro-batch (100 gói tin): {batch_lat:.2f} ms (~{batch_lat/100:.4f} ms/gói)")
    print(f"[+] Throughput dự kiến: {100 / (batch_lat / 1000):,.0f} gói tin / giây (EPS)")

    # 7. Lưu trữ mô hình và bộ tiền xử lý ra file
    model_path = "nids_model.joblib"
    scaler_path = "scaler.joblib"
    metadata_path = "model_metadata.json"

    joblib.dump(model, model_path, compress=3)
    joblib.dump(scaler, scaler_path, compress=3)

    metadata = {
        "model_type": "RandomForestClassifier",
        "n_estimators": 100,
        "max_depth": 12,
        "accuracy": float(acc),
        "feature_names": feature_cols,
        "target_classes": {str(k): v for k, v in label_names.items()},
        "training_samples": len(df),
        "test_samples": len(X_test),
        "batch_latency_ms": float(batch_lat),
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=4, ensure_ascii=False)

    print(f"\n[✓] Đã lưu mô hình: {model_path}")
    print(f"[✓] Đã lưu bộ chuẩn hóa: {scaler_path}")
    print(f"[✓] Đã lưu siêu dữ liệu: {metadata_path}")
    print("="*60)

if __name__ == "__main__":
    train_and_evaluate()
