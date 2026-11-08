
"""
NIDS Producer - Data Generator & Traffic Benchmark
Sinh NetFlow traffic và gửi vào Kafka.
Hỗ trợ điều khiển kịch bản qua Kafka topic: nids-control.
"""

import json
import os
import sys
import time
import random
import threading
import numpy as np

from kafka import KafkaProducer, KafkaConsumer


# ==================================================
# 1. CONFIGURATION
# ==================================================

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

KAFKA_SERVERS = [
    x.strip()
    for x in os.getenv(
        "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
    ).split(",")
    if x.strip()
]

DATA_TOPIC = "network-traffic"
CONTROL_TOPIC = "nids-control"

WINDOW_SECONDS = 0.1
MAX_EPS = 50000

DEFAULT_EPS = {
    "normal": 150,
    "ddos": 8000,
    "portscan": 150,
    "brute_force": 150,
    "ddos_portscan": 8000,
    "mixed": 1000
}

VALID_SCENARIOS = set(DEFAULT_EPS.keys())

NORMAL_IPS = [
    f"10.0.0.{i}" for i in range(2, 50)
]

ATTACK_IPS = [
    f"185.220.{i}.{j}"
    for i in range(100, 110)
    for j in range(1, 10)
]

PORTSCAN_IP = "45.33.12.19"


# ==================================================
# 2. KAFKA CONNECTION
# ==================================================

print("=" * 60)
print("NIDS TRAFFIC GENERATOR")
print("=" * 60)

print(f"Kafka servers: {KAFKA_SERVERS}")

producer = KafkaProducer(
    bootstrap_servers=KAFKA_SERVERS,
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    acks=1,
    retries=5,
    linger_ms=5,
    batch_size=32768,
    compression_type="gzip"
)

control_consumer = KafkaConsumer(
    CONTROL_TOPIC,
    bootstrap_servers=KAFKA_SERVERS,
    group_id="nids-producer-control",
    auto_offset_reset="latest",
    enable_auto_commit=True,
    value_deserializer=lambda m: json.loads(m.decode("utf-8"))
)

# Khởi tạo Kafka Consumer và nhận phân vùng
control_consumer.poll(timeout_ms=1000)

print("[✓] Kafka Producer connected.")
print("[✓] Kafka Control Consumer connected.")


# ==================================================
# 3. TRAFFIC GENERATORS
# ==================================================

def gen_normal_packet(src_ip):

    return {
        "src_ip": src_ip,

        "dst_port": int(np.random.choice(
            [80, 443, 53, 8080, 22, 123],
            p=[0.25, 0.50, 0.15, 0.05, 0.03, 0.02]
        )),

        "protocol": int(np.random.choice(
            [6, 17], p=[0.75, 0.25]
        )),

        "packet_size": float(
            np.clip(np.random.normal(750, 350), 64, 1500)
        ),

        "duration": float(
            np.clip(np.random.exponential(2.5), 0.01, 60)
        ),

        "packets_rate": float(
            np.clip(np.random.poisson(45), 1, 250)
        ),

        "syn_flag": int(
            np.random.choice([0, 1], p=[0.85, 0.15])
        ),

        "ack_flag": int(
            np.random.choice([0, 1], p=[0.15, 0.85])
        ),

        "traffic_type": "normal"
    }


def gen_ddos_packet(src_ip):

    return {
        "src_ip": src_ip,

        "dst_port": int(np.random.choice(
            [80, 443, 53, 8080],
            p=[0.40, 0.35, 0.15, 0.10]
        )),

        "protocol": int(np.random.choice(
            [6, 17], p=[0.80, 0.20]
        )),

        "packet_size": float(
            np.clip(np.random.normal(128, 30), 40, 512)
        ),

        "duration": float(
            np.random.uniform(0.001, 0.2)
        ),

        "packets_rate": float(
            np.random.uniform(2500, 12000)
        ),

        "syn_flag": int(
            np.random.choice([0, 1], p=[0.05, 0.95])
        ),

        "ack_flag": 0,

        "traffic_type": "ddos"
    }


def gen_portscan_packet(src_ip):

    return {
        "src_ip": src_ip,

        "dst_port": int(np.random.choice([
            21, 22, 23, 25, 80, 110,
            143, 443, 3306, 3389, 8080
        ])),

        "protocol": 6,

        "packet_size": float(
            np.clip(np.random.normal(54, 6), 40, 80)
        ),

        "duration": float(
            np.random.uniform(0.001, 0.05)
        ),

        "packets_rate": float(
            np.random.uniform(50, 250)
        ),

        "syn_flag": 1,
        "ack_flag": 0,

        "traffic_type": "port_scan"
    }


def gen_bruteforce_packet(src_ip):

    return {
        "src_ip": src_ip,

        "dst_port": int(np.random.choice(
            [22, 3389, 21],
            p=[0.60, 0.30, 0.10]
        )),

        "protocol": 6,

        "packet_size": float(
            np.clip(np.random.normal(280, 60), 100, 600)
        ),

        "duration": float(
            np.random.uniform(0.5, 3.0)
        ),

        "packets_rate": float(
            np.random.uniform(15, 60)
        ),

        "syn_flag": int(
            np.random.choice([0, 1], p=[0.70, 0.30])
        ),

        "ack_flag": 1,

        "traffic_type": "brute_force"
    }


# ==================================================
# 4. SCENARIO CONTROLLER
# ==================================================

def generate_packet(scenario):

    if scenario == "normal":

        packet = gen_normal_packet(
            random.choice(NORMAL_IPS)
        )

    elif scenario == "ddos":

        packet = gen_ddos_packet(
            random.choice(ATTACK_IPS)
        )

    elif scenario == "portscan":

        packet = gen_portscan_packet(PORTSCAN_IP)

    elif scenario == "brute_force":

        packet = gen_bruteforce_packet(
            random.choice(ATTACK_IPS)
        )

    elif scenario == "ddos_portscan":

        # 80% DDoS + 20% Port Scan
        if random.random() < 0.80:

            packet = gen_ddos_packet(
                random.choice(ATTACK_IPS)
            )

        else:

            packet = gen_portscan_packet(PORTSCAN_IP)

    elif scenario == "mixed":

        # Phân phối tương ứng tập dữ liệu huấn luyện
        roll = random.random()

        if roll < 0.60:

            packet = gen_normal_packet(
                random.choice(NORMAL_IPS)
            )

        elif roll < 0.80:

            packet = gen_ddos_packet(
                random.choice(ATTACK_IPS)
            )

        elif roll < 0.92:

            packet = gen_portscan_packet(PORTSCAN_IP)

        else:

            packet = gen_bruteforce_packet(
                random.choice(ATTACK_IPS)
            )

    else:

        raise ValueError(f"Invalid scenario: {scenario}")

    # Metadata bổ sung, không ảnh hưởng 7 features ML
    packet["timestamp"] = time.time()
    packet["scenario"] = scenario

    return packet


# ==================================================
# 5. RECEIVE CONTROL COMMANDS
# ==================================================

state = {
    "scenario": "normal",
    "target_eps": DEFAULT_EPS["normal"],
    "expires_at": None
}


def handle_control_commands():

    records = control_consumer.poll(timeout_ms=0)

    for messages in records.values():

        for message in messages:

            command = message.value

            if not isinstance(command, dict):
                print("[!] Invalid control command.")
                continue

            scenario = str(
                command.get("scenario", "")
            ).lower()

            if scenario == "stop":

                state["target_eps"] = 0
                state["expires_at"] = None

                print("[CONTROL] Producer paused.")
                continue

            if scenario not in VALID_SCENARIOS:

                print(f"[!] Unknown scenario: {scenario}")
                continue

            try:

                target_eps = int(
                    command.get(
                        "target_eps",
                        DEFAULT_EPS[scenario]
                    )
                )

                if not 1 <= target_eps <= MAX_EPS:
                    raise ValueError("EPS out of allowed range.")

                duration = command.get("duration_sec")

                if duration is not None:

                    duration = float(duration)

                    if duration <= 0:
                        raise ValueError("duration_sec must be positive.")

                    expires_at = time.monotonic() + duration

                else:

                    expires_at = None

                state["scenario"] = scenario
                state["target_eps"] = target_eps
                state["expires_at"] = expires_at

                print("\n" + "=" * 50)
                print("[CONTROL] NEW SCENARIO")
                print(f"Scenario : {scenario}")
                print(f"Target   : {target_eps:,} EPS")
                print(f"Duration : {duration if duration is not None else 'Until next command'}")
                print("=" * 50)

            except (ValueError, TypeError) as e:

                print(f"[!] Invalid control parameters: {e}")


# ==================================================
# 6. PRODUCER PERFORMANCE COUNTERS
# ==================================================

metrics_lock = threading.Lock()

metrics = {
    "acked": 0,
    "errors": 0
}


def on_send_success(metadata):

    with metrics_lock:
        metrics["acked"] += 1


def on_send_error(error):

    with metrics_lock:
        metrics["errors"] += 1


# ==================================================
# 7. MAIN PRODUCER LOOP
# ==================================================

sent_total = 0

last_report = time.perf_counter()

last_sent = 0
last_acked = 0
last_errors = 0

print("\n[✓] Producer is running.")
print("[✓] Waiting for control commands...\n")

try:

    while True:

        # 1. Nhận lệnh điều khiển từ Kafka
        handle_control_commands()

        now = time.monotonic()

        # 2. Tự động quay về Normal khi hết thời gian
        if (
            state["expires_at"] is not None
            and now >= state["expires_at"]
        ):

            state["scenario"] = "normal"
            state["target_eps"] = DEFAULT_EPS["normal"]
            state["expires_at"] = None

            print("\n[CONTROL] Scenario expired. Returning to NORMAL.")

        scenario = state["scenario"]
        target_eps = state["target_eps"]

        # 3. Nếu đang dừng, tiếp tục lắng nghe lệnh mới
        if target_eps <= 0:

            time.sleep(0.1)
            continue

        # 4. Điều chỉnh số packet mỗi cửa sổ 100ms
        batch_count = max(
            1,
            round(target_eps * WINDOW_SECONDS)
        )

        window_start = time.perf_counter()

        # 5. Sinh và gửi dữ liệu
        for _ in range(batch_count):

            packet = generate_packet(scenario)

            try:

                future = producer.send(
                    DATA_TOPIC,
                    packet
                )

                future.add_callback(on_send_success)
                future.add_errback(on_send_error)

                sent_total += 1

            except Exception as e:

                with metrics_lock:
                    metrics["errors"] += 1

                print(f"[SEND ERROR] {e}")

        # 6. Giữ tốc độ gửi theo EPS mục tiêu
        elapsed = time.perf_counter() - window_start

        sleep_time = WINDOW_SECONDS - elapsed

        if sleep_time > 0:
            time.sleep(sleep_time)

        # 7. In thống kê mỗi giây
        current_time = time.perf_counter()

        if current_time - last_report >= 1:

            elapsed_report = current_time - last_report

            with metrics_lock:

                acked_now = metrics["acked"]
                errors_now = metrics["errors"]

            send_eps = (
                sent_total - last_sent
            ) / elapsed_report

            ack_eps = (
                acked_now - last_acked
            ) / elapsed_report

            error_count = errors_now - last_errors

            print(
                f"[Producer] "
                f"Scenario={scenario:<14} | "
                f"Target={target_eps:>6,} EPS | "
                f"Send={send_eps:>8,.0f} EPS | "
                f"ACK={ack_eps:>8,.0f} EPS | "
                f"Errors={error_count}"
            )

            last_report = current_time

            last_sent = sent_total
            last_acked = acked_now
            last_errors = errors_now


except KeyboardInterrupt:

    print("\n[*] Stopping Producer...")

finally:

    print("[*] Flushing Kafka messages...")

    try:
        producer.flush(timeout=10)
    except Exception as e:
        print(f"[!] Flush error: {e}")

    producer.close(timeout=10)
    control_consumer.close()

    print(f"[✓] Total packets submitted: {sent_total:,}")
    print("[✓] Producer stopped.")
