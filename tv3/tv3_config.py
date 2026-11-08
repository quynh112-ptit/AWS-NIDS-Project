import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env.tv3")

FEATURES = ("dst_port", "protocol", "packet_size", "duration",
            "packets_rate", "syn_flag", "ack_flag")
LABELS = {0: "Bình thường", 1: "DDoS", 2: "Port Scan", 3: "Brute Force"}
TOPIC = "network-traffic"


def kafka_servers():
    value = os.getenv("NIDS_KAFKA") or os.getenv("KAFKA_BOOTSTRAP_SERVERS") or "127.0.0.1:19092"
    return [server.strip() for server in value.split(",") if server.strip()]


def database_dsn(read_only=False):
    dsn = (os.getenv("NIDS_READ_DSN") if read_only else None) or os.getenv("NIDS_DSN")
    if not dsn:
        raise RuntimeError("Hãy khai báo NIDS_DSN trong .env.tv3.")
    return dsn
