
"""
NIDS BENCHMARK
Đo lường hiệu năng Kafka và Machine Learning.

Kafka:
- Send Throughput
- ACK Throughput
- Consume Throughput
- ACK Latency
- End-to-end Latency
- P50 / P95 / P99

Machine Learning:
- Scaler + Random Forest Inference Latency
- Inference Throughput
- Benchmark nhiều Batch Size

Output:
- CSV
- JSON
- HTML Charts
"""

import os
import sys
import json
import time
import uuid
import argparse
import threading

from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
import joblib
import plotly.graph_objects as go

from kafka import KafkaProducer, KafkaConsumer
from kafka import TopicPartition


# ==================================================
# 1. CONFIGURATION
# ==================================================

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

FEATURE_COLS = [
    "dst_port",
    "protocol",
    "packet_size",
    "duration",
    "packets_rate",
    "syn_flag",
    "ack_flag"
]

RESULT_DIR = Path("benchmark_results")
RESULT_DIR.mkdir(exist_ok=True)

RANDOM_SEED = 42
rng = np.random.default_rng(RANDOM_SEED)


# ==================================================
# 2. COMMON FUNCTIONS
# ==================================================

def get_latency_stats(values):

    if not values:
        return {
            "avg": None,
            "p50": None,
            "p95": None,
            "p99": None,
            "min": None,
            "max": None
        }

    values = np.asarray(values, dtype=float)

    return {
        "avg": float(np.mean(values)),
        "p50": float(np.percentile(values, 50)),
        "p95": float(np.percentile(values, 95)),
        "p99": float(np.percentile(values, 99)),
        "min": float(np.min(values)),
        "max": float(np.max(values))
    }


def save_json(data, filename):

    path = RESULT_DIR / filename

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    print(f"[✓] Saved: {path}")


def save_dataframe(data, filename):

    path = RESULT_DIR / filename

    pd.DataFrame(data).to_csv(
        path,
        index=False,
        encoding="utf-8-sig"
    )

    print(f"[✓] Saved: {path}")


# ==================================================
# 3. GENERATE TEST FEATURES FOR ML
# ==================================================

def generate_feature_matrix(n_samples):

    n = n_samples

    data = np.column_stack([

        rng.choice(
            [21, 22, 23, 53, 80, 443, 3389, 8080],
            size=n
        ),

        rng.choice(
            [6, 17],
            size=n
        ),

        np.clip(
            rng.normal(500, 250, n),
            40, 1500
        ),

        np.clip(
            rng.exponential(2.5, n),
            0.001, 60
        ),

        rng.uniform(1, 12000, n),

        rng.integers(0, 2, n),

        rng.integers(0, 2, n)

    ])

    return data.astype(float)


# ==================================================
# 4. MACHINE LEARNING BENCHMARK
# ==================================================

def benchmark_ml(args):

    print("\n" + "=" * 65)
    print("MACHINE LEARNING PERFORMANCE BENCHMARK")
    print("=" * 65)

    print("[*] Loading model and scaler...")

    model = joblib.load(args.model)
    scaler = joblib.load(args.scaler)

    print("[✓] Model loaded successfully.")

    batch_sizes = [
        int(x.strip())
        for x in args.batch_sizes.split(",")
    ]

    results = []

    warmup = 10
    iterations = args.iterations

    for batch_size in batch_sizes:

        print(f"\n[*] Testing Batch Size: {batch_size}")

        X = generate_feature_matrix(batch_size)

        # Warm-up: không tính vào kết quả
        for _ in range(warmup):

            X_scaled = scaler.transform(X)
            model.predict(X_scaled)

        latencies = []

        for _ in range(iterations):

            start = time.perf_counter_ns()

            # Đo cả Scaler + Random Forest
            X_scaled = scaler.transform(X)

            model.predict(X_scaled)

            elapsed = (
                time.perf_counter_ns() - start
            ) / 1_000_000

            latencies.append(elapsed)

        stats = get_latency_stats(latencies)

        avg_latency = stats["avg"]

        throughput = (
            batch_size / (avg_latency / 1000)
            if avg_latency > 0 else 0
        )

        row = {
            "batch_size": batch_size,
            "iterations": iterations,
            "avg_latency_ms": avg_latency,
            "p50_ms": stats["p50"],
            "p95_ms": stats["p95"],
            "p99_ms": stats["p99"],
            "min_ms": stats["min"],
            "max_ms": stats["max"],
            "throughput_eps": throughput
        }

        results.append(row)

        print(
            f"Average Latency : {avg_latency:.4f} ms"
        )

        print(
            f"P95 Latency     : {stats['p95']:.4f} ms"
        )

        print(
            f"P99 Latency     : {stats['p99']:.4f} ms"
        )

        print(
            f"Throughput      : {throughput:,.0f} samples/sec"
        )

    # Lưu kết quả
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    save_dataframe(
        results,
        f"ml_benchmark_{stamp}.csv"
    )

    save_json(
        results,
        f"ml_benchmark_{stamp}.json"
    )

    # Biểu đồ Throughput
    fig1 = go.Figure()

    fig1.add_trace(go.Bar(
        x=[r["batch_size"] for r in results],
        y=[r["throughput_eps"] for r in results],
        name="Inference Throughput"
    ))

    fig1.update_layout(
        title="Random Forest Inference Throughput",
        xaxis_title="Batch Size",
        yaxis_title="Samples per Second",
        template="plotly_dark"
    )

    fig1.write_html(
        str(RESULT_DIR / f"ml_throughput_{stamp}.html")
    )

    # Biểu đồ Latency
    fig2 = go.Figure()

    for key, label in [
        ("p50_ms", "P50"),
        ("p95_ms", "P95"),
        ("p99_ms", "P99")
    ]:

        fig2.add_trace(go.Scatter(
            x=[r["batch_size"] for r in results],
            y=[r[key] for r in results],
            mode="lines+markers",
            name=label
        ))

    fig2.update_layout(
        title="Random Forest Inference Latency",
        xaxis_title="Batch Size",
        yaxis_title="Latency (ms)",
        template="plotly_dark"
    )

    fig2.write_html(
        str(RESULT_DIR / f"ml_latency_{stamp}.html")
    )

    print("\n[✓] ML Benchmark completed.")

    return results


# ==================================================
# 5. GENERATE KAFKA TEST TRAFFIC
# ==================================================

def generate_packet(scenario, seq, run_id):

    # Mixed scenario: phân phối theo train_model.py
    if scenario == "mixed":

        roll = rng.random()

        if roll < 0.60:
            traffic_type = "normal"

        elif roll < 0.80:
            traffic_type = "ddos"

        elif roll < 0.92:
            traffic_type = "port_scan"

        else:
            traffic_type = "brute_force"

    elif scenario == "ddos_portscan":

        traffic_type = (
            "ddos" if rng.random() < 0.80
            else "port_scan"
        )

    else:

        traffic_type = scenario

    if traffic_type == "normal":

        packet = {
            "src_ip": "10.0.0.15",
            "dst_port": int(rng.choice([80, 443, 53, 8080, 22])),
            "protocol": int(rng.choice([6, 17])),
            "packet_size": float(np.clip(rng.normal(750, 350), 64, 1500)),
            "duration": float(np.clip(rng.exponential(2.5), 0.01, 60)),
            "packets_rate": float(np.clip(rng.poisson(45), 1, 250)),
            "syn_flag": int(rng.choice([0, 1], p=[0.85, 0.15])),
            "ack_flag": int(rng.choice([0, 1], p=[0.15, 0.85]))
        }

    elif traffic_type == "ddos":

        packet = {
            "src_ip": "185.220.100.5",
            "dst_port": int(rng.choice([80, 443, 53, 8080])),
            "protocol": int(rng.choice([6, 17])),
            "packet_size": float(np.clip(rng.normal(128, 30), 40, 512)),
            "duration": float(rng.uniform(0.001, 0.2)),
            "packets_rate": float(rng.uniform(2500, 12000)),
            "syn_flag": 1,
            "ack_flag": 0
        }

    elif traffic_type == "port_scan":

        packet = {
            "src_ip": "45.33.12.19",
            "dst_port": int(rng.choice([21, 22, 23, 25, 80, 443, 3389])),
            "protocol": 6,
            "packet_size": float(np.clip(rng.normal(54, 6), 40, 80)),
            "duration": float(rng.uniform(0.001, 0.05)),
            "packets_rate": float(rng.uniform(50, 250)),
            "syn_flag": 1,
            "ack_flag": 0
        }

    else:

        packet = {
            "src_ip": "185.220.100.8",
            "dst_port": int(rng.choice([22, 3389, 21])),
            "protocol": 6,
            "packet_size": float(np.clip(rng.normal(280, 60), 100, 600)),
            "duration": float(rng.uniform(0.5, 3.0)),
            "packets_rate": float(rng.uniform(15, 60)),
            "syn_flag": int(rng.choice([0, 1])),
            "ack_flag": 1
        }

    packet.update({
        "traffic_type": traffic_type,
        "scenario": scenario,
        "benchmark_id": run_id,
        "seq": seq,
    })

    return packet


# ==================================================
# 6. KAFKA BENCHMARK
# ==================================================

def benchmark_kafka(args):

    print("\n" + "=" * 65)
    print("KAFKA PERFORMANCE BENCHMARK")
    print("=" * 65)

    servers = [
        item.strip()
        for item in args.bootstrap_servers.split(",")
        if item.strip()
    ]

    run_id = str(uuid.uuid4())

    # --------------------------------------------------
    # 1. Create Observer Consumer
    # --------------------------------------------------

    print("[*] Connecting Kafka Observer...")

    consumer = KafkaConsumer(
        bootstrap_servers=servers,
        enable_auto_commit=False,
        auto_offset_reset="latest",
        value_deserializer=lambda message: json.loads(
            message.decode("utf-8")
        ),
        max_poll_records=1000
    )

    partitions = consumer.partitions_for_topic(args.topic)

    if not partitions:
        consumer.close()
        raise RuntimeError(
            f"Topic '{args.topic}' does not exist. "
            "Please create it before benchmarking."
        )

    topic_partitions = [
        TopicPartition(args.topic, partition)
        for partition in sorted(partitions)
    ]

    consumer.assign(topic_partitions)
    consumer.seek_to_end()

    # --------------------------------------------------
    # 2. Shared metrics and observer thread
    # --------------------------------------------------

    lock = threading.Lock()
    stop_event = threading.Event()

    ack_latencies = {}
    e2e_latencies = {}
    receive_times = {}

    send_errors = []
    observer_errors = []

    def consumer_loop():

        while not stop_event.is_set():

            try:
                records = consumer.poll(
                    timeout_ms=200,
                    max_records=1000
                )
            except Exception as exc:
                with lock:
                    observer_errors.append(str(exc))
                stop_event.set()
                break

            for messages in records.values():

                for message in messages:

                    data = message.value

                    # Ignore messages from other benchmark runs.
                    if data.get("benchmark_id") != run_id:
                        continue

                    try:
                        seq = int(data["seq"])
                        sent_ns = int(data["sent_ns"])
                    except (KeyError, TypeError, ValueError):
                        with lock:
                            observer_errors.append(
                                "Received benchmark message with invalid "
                                "'seq' or 'sent_ns'."
                            )
                        continue

                    # Producer and observer run on the same host,
                    # so perf_counter_ns() uses the same monotonic clock.
                    received_ns = time.perf_counter_ns()

                    latency_ms = (
                        received_ns - sent_ns
                    ) / 1_000_000

                    with lock:
                        # Avoid counting the same sequence more than once.
                        if seq not in e2e_latencies:
                            e2e_latencies[seq] = latency_ms
                            receive_times[seq] = time.perf_counter()

    observer_thread = threading.Thread(
        target=consumer_loop,
        daemon=True
    )
    observer_thread.start()

    # --------------------------------------------------
    # 3. Create Producer
    # --------------------------------------------------

    producer = KafkaProducer(
        bootstrap_servers=servers,
        acks="all",
        retries=5,
        linger_ms=5,
        batch_size=32768,
        compression_type="gzip",
        value_serializer=lambda value: json.dumps(value).encode("utf-8")
    )

    def ack_callback(seq, sent_ns):

        latency_ms = (
            time.perf_counter_ns() - sent_ns
        ) / 1_000_000

        with lock:
            ack_latencies[seq] = latency_ms

    def error_callback(seq, error):

        with lock:
            send_errors.append(
                f"Sequence {seq}: {error}"
            )

    # --------------------------------------------------
    # 4. Send benchmark messages
    # --------------------------------------------------

    print(f"Scenario : {args.scenario}")
    print(f"Messages : {args.messages:,}")
    print(f"Target EPS: {args.eps if args.eps > 0 else 'MAX'}")
    print(f"Topic    : {args.topic}")

    sent_count = 0

    send_start = time.perf_counter()
    next_send = send_start

    interval = (
        1.0 / args.eps
        if args.eps > 0 else 0
    )

    for seq in range(args.messages):

        # Optional rate limiting.
        if interval > 0:

            while True:

                now = time.perf_counter()

                if now >= next_send:
                    break

                time.sleep(
                    min(next_send - now, 0.001)
                )

            next_send += interval

        # Generate the packet before starting the latency timer.
        packet = generate_packet(
            args.scenario,
            seq,
            run_id
        )

        # Start timing immediately before Producer.send().
        # This timestamp is also carried to the observer consumer.
        sent_ns = time.perf_counter_ns()
        packet["sent_ns"] = sent_ns

        try:

            future = producer.send(
                args.topic,
                value=packet
            )

            future.add_callback(
                lambda metadata, s=seq, t=sent_ns:
                    ack_callback(s, t)
            )

            future.add_errback(
                lambda error, s=seq:
                    error_callback(s, error)
            )

            sent_count += 1

        except Exception as exc:

            with lock:
                send_errors.append(
                    f"Sequence {seq}: {exc}"
                )

    # End of Producer submission phase.
    send_end = time.perf_counter()

    # --------------------------------------------------
    # 5. Wait for Kafka acknowledgements
    # --------------------------------------------------

    print("\n[*] Waiting for Kafka acknowledgements...")

    try:
        producer.flush(timeout=60)
    finally:
        producer.close(timeout=10)

    # Record ACK phase end after Producer flush/close.
    ack_end = time.perf_counter()

    with lock:
        ack_count_at_flush = len(ack_latencies)
        ack_values = list(ack_latencies.values())

    # --------------------------------------------------
    # 6. Wait for Observer Consumer
    # --------------------------------------------------

    print("[*] Waiting for received messages...")

    deadline = time.monotonic() + args.timeout

    while time.monotonic() < deadline:

        with lock:
            received_count = len(e2e_latencies)

        if received_count >= sent_count:
            break

        if stop_event.is_set():
            break

        time.sleep(0.05)

    stop_event.set()
    observer_thread.join(timeout=3)

    consumer.close()

    # --------------------------------------------------
    # 7. Calculate metrics
    # --------------------------------------------------

    with lock:
        e2e_values = list(e2e_latencies.values())
        received_count = len(e2e_latencies)
        receive_time_values = list(receive_times.values())
        final_send_errors = list(send_errors)
        final_observer_errors = list(observer_errors)

    send_duration = max(
        send_end - send_start,
        0.000001
    )

    ack_duration = max(
        ack_end - send_start,
        0.000001
    )

    send_eps = sent_count / send_duration
    ack_eps = ack_count_at_flush / ack_duration

    if receive_time_values:

        receive_duration = max(
            max(receive_time_values) - send_start,
            0.000001
        )

        consume_eps = received_count / receive_duration

    else:
        consume_eps = 0.0

    ack_stats = get_latency_stats(ack_values)
    e2e_stats = get_latency_stats(e2e_values)

    unreceived = max(
        0,
        sent_count - received_count
    )

    unacknowledged = max(
        0,
        sent_count - ack_count_at_flush
    )

    summary = {
        "timestamp": datetime.now().isoformat(),
        "run_id": run_id,
        "scenario": args.scenario,
        "topic": args.topic,
        "target_eps": args.eps,
        "messages_submitted": sent_count,
        "broker_acknowledged": ack_count_at_flush,
        "consumed": received_count,
        "unacknowledged_at_flush": unacknowledged,
        "unreceived_at_timeout": unreceived,
        "send_errors": len(final_send_errors),
        "observer_errors": len(final_observer_errors),
        "send_eps": send_eps,
        "ack_eps": ack_eps,
        "consume_eps": consume_eps,
        "ack_latency_ms": ack_stats,
        "end_to_end_latency_ms": e2e_stats
    }

    # --------------------------------------------------
    # 8. Save results
    # --------------------------------------------------

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    save_json(
        summary,
        f"kafka_benchmark_{stamp}.json"
    )

    save_dataframe(
        [summary],
        f"kafka_benchmark_{stamp}.csv"
    )

    # Save raw latency samples.
    sample_rows = []

    for seq in range(sent_count):

        sample_rows.append({
            "seq": seq,
            "ack_latency_ms": ack_latencies.get(seq),
            "end_to_end_latency_ms": e2e_latencies.get(seq)
        })

    save_dataframe(
        sample_rows,
        f"kafka_latency_samples_{stamp}.csv"
    )

    # --------------------------------------------------
    # 9. Throughput chart
    # --------------------------------------------------

    fig1 = go.Figure()

    fig1.add_trace(go.Bar(
        x=[
            "Producer Send",
            "Kafka ACK",
            "Consumer Receive"
        ],
        y=[
            send_eps,
            ack_eps,
            consume_eps
        ],
        text=[
            f"{send_eps:,.0f}",
            f"{ack_eps:,.0f}",
            f"{consume_eps:,.0f}"
        ],
        textposition="auto",
        name="Throughput"
    ))

    fig1.update_layout(
        title="Kafka Throughput Benchmark",
        yaxis_title="Messages per Second (EPS)",
        template="plotly_dark"
    )

    fig1.write_html(
        str(RESULT_DIR / f"kafka_throughput_{stamp}.html")
    )

    # --------------------------------------------------
    # 10. Latency chart
    # --------------------------------------------------

    fig2 = go.Figure()

    for name, stats in [
        ("Kafka ACK", ack_stats),
        ("End-to-end", e2e_stats)
    ]:

        fig2.add_trace(go.Bar(
            name=name,
            x=["P50", "P95", "P99"],
            y=[
                stats["p50"] if stats["p50"] is not None else 0,
                stats["p95"] if stats["p95"] is not None else 0,
                stats["p99"] if stats["p99"] is not None else 0
            ]
        ))

    fig2.update_layout(
        title="Kafka Latency Benchmark",
        xaxis_title="Percentile",
        yaxis_title="Latency (ms)",
        barmode="group",
        template="plotly_dark"
    )

    fig2.write_html(
        str(RESULT_DIR / f"kafka_latency_{stamp}.html")
    )

    # --------------------------------------------------
    # 11. Print summary
    # --------------------------------------------------

    print("\n" + "=" * 65)
    print("KAFKA BENCHMARK RESULTS")
    print("=" * 65)

    print(f"Scenario              : {args.scenario}")
    print(f"Messages submitted    : {sent_count:,}")
    print(f"Kafka acknowledged    : {ack_count_at_flush:,}")
    print(f"Consumer received     : {received_count:,}")
    print(f"Unacknowledged at flush: {unacknowledged:,}")
    print(f"Unreceived at timeout : {unreceived:,}")
    print(f"Send errors           : {len(final_send_errors)}")
    print(f"Observer errors       : {len(final_observer_errors)}")

    print(f"\nSend Throughput       : {send_eps:,.2f} EPS")
    print(f"ACK Throughput        : {ack_eps:,.2f} EPS")
    print(f"Consume Throughput    : {consume_eps:,.2f} EPS")

    print("\nACK Latency:")
    print(f"Average : {ack_stats['avg']}")
    print(f"P50     : {ack_stats['p50']}")
    print(f"P95     : {ack_stats['p95']}")
    print(f"P99     : {ack_stats['p99']}")

    print("\nEnd-to-end Latency:")
    print(f"Average : {e2e_stats['avg']}")
    print(f"P50     : {e2e_stats['p50']}")
    print(f"P95     : {e2e_stats['p95']}")
    print(f"P99     : {e2e_stats['p99']}")

    print("=" * 65)

    return summary


# ==================================================
# 7. MAIN
# ==================================================

def main():

    parser = argparse.ArgumentParser(
        description="NIDS Performance Benchmark"
    )

    parser.add_argument(
        "--mode",
        choices=["all", "ml", "kafka"],
        default="all"
    )

    parser.add_argument(
        "--bootstrap-servers",
        default=os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS",
            "localhost:9092"
        )
    )

    parser.add_argument(
        "--topic",
        default="network-traffic"
    )

    parser.add_argument(
        "--messages",
        type=int,
        default=10000
    )

    parser.add_argument(
        "--eps",
        type=int,
        default=8000,
        help="Target EPS; 0 means maximum speed"
    )

    parser.add_argument(
        "--scenario",
        choices=[
            "normal",
            "ddos",
            "port_scan",
            "brute_force",
            "ddos_portscan",
            "mixed"
        ],
        default="ddos"
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=30
    )

    parser.add_argument(
        "--model",
        default="nids_model.joblib"
    )

    parser.add_argument(
        "--scaler",
        default="scaler.joblib"
    )

    parser.add_argument(
        "--batch-sizes",
        default="1,10,50,100,500"
    )

    parser.add_argument(
        "--iterations",
        type=int,
        default=100
    )

    args = parser.parse_args()

    if args.messages <= 0:
        parser.error("--messages must be greater than 0")

    if args.eps < 0:
        parser.error("--eps cannot be negative")

    if args.timeout <= 0 or args.iterations <= 0:
        parser.error("--timeout and --iterations must be positive")

    print("\nNIDS PERFORMANCE TEST SYSTEM")
    print("Mode:", args.mode)

    if args.mode in ["all", "ml"]:

        benchmark_ml(args)

    if args.mode in ["all", "kafka"]:

        benchmark_kafka(args)

    print("\n[✓] ALL BENCHMARK TASKS COMPLETED.")
    print(f"[✓] Results directory: {RESULT_DIR.resolve()}")


if __name__ == "__main__":
    main()
