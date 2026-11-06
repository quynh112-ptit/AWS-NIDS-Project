"""Điện thoại gửi bản ghi mô phỏng vào Kafka bằng các nút đã định sẵn."""
import hmac
import json
import os
import threading
import time
import uuid

import streamlit as st
from kafka import KafkaProducer
from kafka.errors import KafkaError

from tv3_config import FEATURES, TOPIC, kafka_servers
from tv3_ui import apply_theme, heading, hero

SCENARIOS = {
    "Bình thường": ("normal", (443, 6, 750, 3, 42, 0, 1)),
    "DDoS": ("ddos", (80, 6, 120, 0.04, 7000, 1, 0)),
    "Port Scan": ("port_scan", (3306, 6, 54, 0.02, 125, 1, 0)),
    "Brute Force": ("brute_force", (22, 6, 280, 2, 38, 0, 1)),
}


@st.cache_resource
def publisher():
    return KafkaProducer(
        bootstrap_servers=kafka_servers(), acks="all",
        api_version_auto_timeout_ms=10000, max_block_ms=5000,
        request_timeout_ms=10000, retries=0,
        value_serializer=lambda payload: json.dumps(payload).encode("utf-8"),
    )


@st.cache_resource
def rate_gate():
    return threading.Lock(), [0.0]


def make_event(label):
    scenario, values = SCENARIOS[label]
    demo_id = uuid.uuid4().hex[:12]
    return {**dict(zip(FEATURES, values)), "src_ip": "192.0.2.3",
            "traffic_type": scenario, "demo_id": demo_id}


def main():
    st.set_page_config(page_title="NIDS QR Demo", page_icon="📲", layout="centered")
    apply_theme()
    hero("Mô phỏng lưu lượng", "QR DEMO")

    access_code = os.getenv("NIDS_QR_CODE", "")
    if len(access_code) < 12:
        st.info("Chưa cấu hình mã truy cập.")
        return

    with st.form("send_demo", clear_on_submit=True):
        heading("Kịch bản")
        label = st.radio("Kịch bản", tuple(SCENARIOS), horizontal=True, label_visibility="collapsed")
        entered = st.text_input("Mã truy cập", type="password", max_chars=128)
        send = st.form_submit_button("Gửi mô phỏng", type="primary", width="stretch")
    if not send:
        return
    if not hmac.compare_digest(entered.encode("utf-8"), access_code.encode("utf-8")):
        st.error("Mã truy cập không đúng.")
        return
    lock, next_send = rate_gate()
    with lock:
        now = time.monotonic()
        if now < next_send[0]:
            st.warning("Thử lại sau 3 giây.")
            return
        next_send[0] = now + 3
    event = make_event(label)
    try:
        with st.spinner("Đang gửi…"):
            publisher().send(TOPIC, event).get(timeout=12)
    except KafkaError:
        st.error("Chưa nhận được xác nhận từ Kafka.")
        return
    st.success("Đã gửi · Kafka xác nhận")
    heading("Mã sự kiện")
    st.code(event["demo_id"], language=None)


if __name__ == "__main__":
    main()
