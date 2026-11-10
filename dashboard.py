"""
AWS NIDS Enterprise SOC Dashboard - Version 2.0
Enhanced: Live Threat Map, Multi-Vector Attack Detection, QR Code Demo
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import time
import json
import os
import random
import folium
from folium.plugins import AntPath
from streamlit_folium import st_folium

# ═══════════════════════════════════════════════════════════════════
# CẤU HÌNH TRANG
# ═══════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="AWS NIDS SOC v2.0",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ═══════════════════════════════════════════════════════════════════
# DARK THEME + NEON CSS
# ═══════════════════════════════════════════════════════════════════
st.markdown("""
<style>
/* ── Toàn trang ── */
.stApp { background-color: #050810 !important; }
section[data-testid="stSidebar"] { background-color: #080c18 !important; border-right: 1px solid #00ff9020; }
div[data-testid="stToolbar"] { display: none; }

/* ── Typography neon ── */
h1, h2, h3, .stMarkdown p { color: #00ff90 !important; font-family: 'Courier New', monospace !important; }
.stCaption p { color: #00bfff88 !important; font-family: 'Courier New', monospace !important; }

/* ── Metric cards ── */
div[data-testid="metric-container"] {
    background: linear-gradient(135deg, #0a0f1e, #0d1a2e) !important;
    border: 1px solid #00ff9030 !important;
    border-radius: 8px !important;
    padding: 12px !important;
    box-shadow: 0 0 15px #00ff9015 !important;
}
div[data-testid="metric-container"] label { color: #00bfff99 !important; font-family: 'Courier New', monospace !important; font-size: 11px !important; }
div[data-testid="metric-container"] div[data-testid="stMetricValue"] { color: #00ff90 !important; font-family: 'Courier New', monospace !important; }

/* ── Buttons ── */
.stButton > button {
    font-family: 'Courier New', monospace !important;
    font-weight: bold !important;
    border-radius: 4px !important;
    border: 1px solid #00ff9050 !important;
    background: linear-gradient(135deg, #0a1628, #0d1f3c) !important;
    color: #00ff90 !important;
    transition: all 0.2s ease !important;
}
.stButton > button:hover { box-shadow: 0 0 20px #00ff9050 !important; border-color: #00ff90 !important; }

/* ── Dataframe ── */
div[data-testid="stDataFrame"] { background-color: #080c18 !important; border: 1px solid #00ff9020 !important; }

/* ── Divider ── */
hr { border-color: #00ff9020 !important; }

/* ── Neon status badges ── */
.badge-safe {
    display: inline-block;
    padding: 4px 14px; border-radius: 4px;
    background: #00ff9015; border: 1px solid #00ff90;
    color: #00ff90; font-family: 'Courier New', monospace;
    font-weight: bold; font-size: 20px;
    text-shadow: 0 0 10px #00ff90;
    box-shadow: 0 0 20px #00ff9040;
}
.badge-danger {
    display: inline-block;
    padding: 4px 14px; border-radius: 4px;
    background: #ff003315; border: 1px solid #ff0033;
    color: #ff0033; font-family: 'Courier New', monospace;
    font-weight: bold; font-size: 20px;
    text-shadow: 0 0 10px #ff0033;
    box-shadow: 0 0 20px #ff003340;
    animation: blink-red 1s infinite;
}
.badge-warn {
    display: inline-block;
    padding: 4px 14px; border-radius: 4px;
    background: #ff880015; border: 1px solid #ff8800;
    color: #ff8800; font-family: 'Courier New', monospace;
    font-weight: bold; font-size: 20px;
    text-shadow: 0 0 10px #ff8800;
    box-shadow: 0 0 20px #ff880040;
    animation: blink-orange 1.5s infinite;
}
.badge-qr {
    display: inline-block;
    padding: 4px 14px; border-radius: 4px;
    background: #ff00ff15; border: 1px solid #ff00ff;
    color: #ff00ff; font-family: 'Courier New', monospace;
    font-weight: bold; font-size: 20px;
    text-shadow: 0 0 10px #ff00ff;
    box-shadow: 0 0 20px #ff00ff40;
    animation: blink-red 0.8s infinite;
}
@keyframes blink-red { 0%,100%{opacity:1} 50%{opacity:0.4} }
@keyframes blink-orange { 0%,100%{opacity:1} 50%{opacity:0.5} }

/* ── Log title ── */
.log-header {
    font-family: 'Courier New', monospace;
    color: #00bfff;
    font-size: 15px;
    border-bottom: 1px solid #00ff9030;
    padding-bottom: 6px;
    margin-bottom: 8px;
}
.log-line-attack { color: #ff4444; font-family: 'Courier New', monospace; font-size: 12px; }
.log-line-normal { color: #00ff9099; font-family: 'Courier New', monospace; font-size: 12px; }
.log-line-qr     { color: #ff88ff; font-family: 'Courier New', monospace; font-size: 12px; font-weight: bold; }

/* ── Sidebar title ── */
.sidebar-title {
    font-family: 'Courier New', monospace;
    color: #00bfff;
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 2px;
    border-bottom: 1px solid #00ff9030;
    padding-bottom: 6px;
    margin: 10px 0;
}
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════
# CONSTANTS - Tọa độ server & IP tấn công demo
# ═══════════════════════════════════════════════════════════════════
# Vị trí "Trung tâm phòng thủ" (đặt ở TP.HCM cho trực quan khi demo)
SERVER_LAT = 10.8231
SERVER_LON = 106.6297
SERVER_LABEL = "🛡️ AWS NIDS Server (VN)"

# Cơ sở dữ liệu IP tấn công demo (mô phỏng thực tế)
DEMO_ATTACK_IPS = [
    {"ip": "185.220.101.47",  "country": "Russia",      "city": "Moscow",       "lat": 55.75,  "lon": 37.61,  "type": "ddos"},
    {"ip": "103.15.22.188",   "country": "China",       "city": "Shanghai",     "lat": 31.23,  "lon": 121.47, "type": "ddos"},
    {"ip": "91.108.4.236",    "country": "Netherlands", "city": "Amsterdam",    "lat": 52.37,  "lon": 4.90,   "type": "ddos"},
    {"ip": "179.43.128.14",   "country": "Brazil",      "city": "São Paulo",    "lat": -23.55, "lon": -46.63, "type": "ddos"},
    {"ip": "5.188.206.72",    "country": "Ukraine",     "city": "Kyiv",         "lat": 50.45,  "lon": 30.52,  "type": "ddos"},
    {"ip": "193.32.127.44",   "country": "Germany",     "city": "Frankfurt",    "lat": 50.11,  "lon": 8.68,   "type": "ddos"},
    {"ip": "162.247.72.199",  "country": "USA",         "city": "New York",     "lat": 40.71,  "lon": -74.01, "type": "ddos"},
    {"ip": "198.98.56.103",   "country": "USA",         "city": "Los Angeles",  "lat": 34.05,  "lon": -118.24,"type": "ddos"},
    {"ip": "45.33.12.19",     "country": "Singapore",   "city": "Singapore",    "lat": 1.35,   "lon": 103.82, "type": "port_scan"},
    {"ip": "77.75.78.1",      "country": "Czech Rep.",  "city": "Prague",       "lat": 50.08,  "lon": 14.44,  "type": "port_scan"},
]

# Dữ liệu port scan tàng hình (Multi-vector)
STEALTH_SCANNER = {
    "ip": "45.33.12.19", "country": "Singapore", "city": "Singapore",
    "lat": 1.35, "lon": 103.82, "type": "port_scan"
}

# ═══════════════════════════════════════════════════════════════════
# TRẠNG THÁI SESSION
# ═══════════════════════════════════════════════════════════════════
defaults = {
    'scenario': 'normal',
    'packet_history': [],
    'attack_log': [],
    'attack_count': 0,
    'total_packets': 0,
    'start_time': datetime.now().strftime("%H:%M:%S"),
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ═══════════════════════════════════════════════════════════════════
# ĐỌC QR ATTACKS từ file chia sẻ với attack_api.py
# ═══════════════════════════════════════════════════════════════════
QR_ATTACKS_FILE = os.path.join(os.path.dirname(__file__), "shared_attacks.json")

def load_qr_attacks():
    """Đọc danh sách tấn công thực từ QR Code demo."""
    if not os.path.exists(QR_ATTACKS_FILE):
        return []
    try:
        with open(QR_ATTACKS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Chỉ lấy 10 cái mới nhất
        return data[-10:] if isinstance(data, list) else []
    except Exception:
        return []

# ═══════════════════════════════════════════════════════════════════
# HÀM VẼ BẢN ĐỒ FOLIUM
# ═══════════════════════════════════════════════════════════════════
def bezier_arc(lat1, lon1, lat2, lon2, n=40):
    """Tạo đường cong Bezier từ điểm nguồn → server (tạo hiệu ứng cung bay)."""
    mid_lat = (lat1 + lat2) / 2 + abs(lat2 - lat1) * 0.25 + 2.0
    mid_lon = (lon1 + lon2) / 2
    pts = []
    for t in np.linspace(0, 1, n):
        lt = (1-t)**2 * lat1 + 2*(1-t)*t * mid_lat + t**2 * lat2
        ln = (1-t)**2 * lon1 + 2*(1-t)*t * mid_lon + t**2 * lon2
        pts.append([lt, ln])
    return pts

def build_threat_map(scenario: str, qr_attacks: list) -> folium.Map:
    """Xây dựng bản đồ mối đe dọa theo kịch bản."""
    m = folium.Map(
        location=[20, 60],
        zoom_start=2,
        tiles="CartoDB dark_matter",
        prefer_canvas=True,
    )

    # ── Marker: Vị trí Server phòng thủ ──
    server_icon_html = """
    <div style="
        width:18px; height:18px; border-radius:50%;
        background:#00ff90; border:2px solid #fff;
        box-shadow: 0 0 12px #00ff90, 0 0 24px #00ff9080;
        animation: pulse-green 1.5s infinite;
    "></div>
    <style>
    @keyframes pulse-green {
        0%  { box-shadow: 0 0 8px  #00ff90, 0 0 16px #00ff9060; }
        50% { box-shadow: 0 0 20px #00ff90, 0 0 40px #00ff9099; }
        100%{ box-shadow: 0 0 8px  #00ff90, 0 0 16px #00ff9060; }
    }
    </style>
    """
    folium.Marker(
        location=[SERVER_LAT, SERVER_LON],
        icon=folium.DivIcon(html=server_icon_html, icon_size=(18, 18), icon_anchor=(9, 9)),
        tooltip=f"<b style='color:#00ff90'>{SERVER_LABEL}</b><br>Status: DEFENDED",
    ).add_to(m)

    # ── Vòng tròn bảo vệ quanh server ──
    folium.Circle(
        location=[SERVER_LAT, SERVER_LON],
        radius=300_000,
        color="#00ff9030",
        fill=True,
        fill_color="#00ff9008",
        weight=1,
    ).add_to(m)

    # ── DDoS Attacks ──
    if scenario in ("ddos", "multi_vector"):
        ddos_sources = [ip for ip in DEMO_ATTACK_IPS if ip["type"] == "ddos"]
        # Mỗi lần refresh chọn ngẫu nhiên 5-8 nguồn để tạo hiệu ứng sống động
        active_sources = random.sample(ddos_sources, min(len(ddos_sources), random.randint(5, len(ddos_sources))))

        for src in active_sources:
            # Marker đỏ nhấp nháy
            icon_html = f"""
            <div style="
                width:12px; height:12px; border-radius:50%;
                background:#ff2222; border:1px solid #ff8888;
                box-shadow: 0 0 8px #ff0000;
                opacity:0.9;
            "></div>"""
            folium.Marker(
                location=[src["lat"], src["lon"]],
                icon=folium.DivIcon(html=icon_html, icon_size=(12, 12), icon_anchor=(6, 6)),
                tooltip=f"<b style='color:#ff4444'>⚠ DDoS SOURCE</b><br>IP: {src['ip']}<br>📍 {src['city']}, {src['country']}",
            ).add_to(m)

            # Vòng tròn đỏ lan rộng
            folium.Circle(
                location=[src["lat"], src["lon"]],
                radius=random.randint(200_000, 600_000),
                color="#ff222230",
                fill=True,
                fill_color="#ff222210",
                weight=1,
            ).add_to(m)

            # Đường tấn công AntPath (kiến hành quân đỏ)
            arc_pts = bezier_arc(src["lat"], src["lon"], SERVER_LAT, SERVER_LON)
            AntPath(
                locations=arc_pts,
                weight=2,
                color="#ff3333",
                delay=600,
                dash_array=[8, 15],
                pulse_color="#ff0000",
            ).add_to(m)

    # ── Port Scan ẩn (Multi-vector hoặc Port Scan thuần) ──
    if scenario in ("portscan", "multi_vector"):
        src = STEALTH_SCANNER
        # Màu cam cho port scan
        icon_html_scan = """
        <div style="
            width:10px; height:10px; border-radius:50%;
            background:#ff8800; border:1px solid #ffcc00;
            box-shadow: 0 0 10px #ff8800;
        "></div>"""
        folium.Marker(
            location=[src["lat"], src["lon"]],
            icon=folium.DivIcon(html=icon_html_scan, icon_size=(10, 10), icon_anchor=(5, 5)),
            tooltip=f"<b style='color:#ff8800'>🕵️ STEALTH PORT SCAN</b><br>IP: {src['ip']}<br>📍 {src['city']}, {src['country']}<br><i>Scanning ports 21,22,23,80,3389...</i>",
        ).add_to(m)

        arc_pts = bezier_arc(src["lat"], src["lon"], SERVER_LAT, SERVER_LON)
        AntPath(
            locations=arc_pts,
            weight=2,
            color="#ff8800",
            delay=1200,  # Chậm hơn → ẩn hơn
            dash_array=[4, 25],
            pulse_color="#ffcc00",
        ).add_to(m)

    # ── QR Attack Realtime ──
    for atk in qr_attacks:
        lat = atk.get("lat")
        lon = atk.get("lon")
        if lat is None or lon is None:
            continue
        icon_html_qr = """
        <div style="
            width:14px; height:14px; border-radius:50%;
            background:#ff00ff; border:2px solid #ffaaff;
            box-shadow: 0 0 15px #ff00ff, 0 0 30px #ff00ff80;
        "></div>"""
        folium.Marker(
            location=[lat, lon],
            icon=folium.DivIcon(html=icon_html_qr, icon_size=(14, 14), icon_anchor=(7, 7)),
            tooltip=(
                f"<b style='color:#ff00ff'>🎯 QR LIVE ATTACK!</b><br>"
                f"IP: {atk.get('ip','N/A')}<br>"
                f"📍 {atk.get('city','?')}, {atk.get('country','?')}<br>"
                f"⏰ {atk.get('time','?')}"
            ),
        ).add_to(m)
        arc_pts = bezier_arc(lat, lon, SERVER_LAT, SERVER_LON)
        AntPath(
            locations=arc_pts,
            weight=3,
            color="#ff00ff",
            delay=400,
            dash_array=[10, 10],
            pulse_color="#ffffff",
        ).add_to(m)

    return m


# ═══════════════════════════════════════════════════════════════════
# HÀM SINH DỮ LIỆU TRAFFIC
# ═══════════════════════════════════════════════════════════════════
def generate_traffic(scenario: str, qr_attacks: list):
    now = datetime.now()
    new_logs = []

    if scenario == "normal":
        eps = int(np.random.randint(80, 160))
        status = "AN TOÀN"
        badge_cls = "badge-safe"

    elif scenario == "ddos":
        eps = int(np.random.randint(5000, 12000))
        status = "BÁO ĐỘNG ĐỎ 🔴"
        badge_cls = "badge-danger"
        # Sinh log DDoS
        for _ in range(random.randint(3, 6)):
            src = random.choice([ip for ip in DEMO_ATTACK_IPS if ip["type"] == "ddos"])
            new_logs.append({
                "⏰ Thời gian": now.strftime("%H:%M:%S.") + f"{random.randint(0,999):03d}",
                "🌐 IP Nguồn": src["ip"],
                "📍 Quốc gia": f"{src['city']}, {src['country']}",
                "🔫 Kiểu tấn công": "DDoS Flood",
                "🎯 Port": str(random.choice([80, 443, 53, 8080])),
                "⚡ Packets/s": f"{random.randint(2000, 8000):,}",
                "🚨 Mức độ": "CRITICAL",
            })

    elif scenario == "multi_vector":
        eps = int(np.random.randint(4000, 9000))
        status = "⚠️ MULTI-VECTOR ATTACK"
        badge_cls = "badge-danger"
        # DDoS logs
        for _ in range(random.randint(3, 5)):
            src = random.choice([ip for ip in DEMO_ATTACK_IPS if ip["type"] == "ddos"])
            new_logs.append({
                "⏰ Thời gian": now.strftime("%H:%M:%S.") + f"{random.randint(0,999):03d}",
                "🌐 IP Nguồn": src["ip"],
                "📍 Quốc gia": f"{src['city']}, {src['country']}",
                "🔫 Kiểu tấn công": "DDoS Flood",
                "🎯 Port": str(random.choice([80, 443])),
                "⚡ Packets/s": f"{random.randint(2000, 7000):,}",
                "🚨 Mức độ": "CRITICAL",
            })
        # Port scan ẩn — thêm vào đây, ẩn trong bão DDoS
        sc = STEALTH_SCANNER
        for port in random.sample([22, 21, 23, 3389, 1433], random.randint(1, 3)):
            new_logs.append({
                "⏰ Thời gian": now.strftime("%H:%M:%S.") + f"{random.randint(0,999):03d}",
                "🌐 IP Nguồn": sc["ip"],
                "📍 Quốc gia": f"{sc['city']}, {sc['country']}",
                "🔫 Kiểu tấn công": "🕵️ STEALTH Port Scan",
                "🎯 Port": str(port),
                "⚡ Packets/s": f"{random.randint(10, 80):,}",
                "🚨 Mức độ": "HIGH",
            })

    elif scenario == "portscan":
        eps = int(np.random.randint(100, 220))
        status = "PHÁT HIỆN XÂM NHẬP 🟠"
        badge_cls = "badge-warn"
        sc = STEALTH_SCANNER
        for port in random.sample([22, 21, 23, 3389, 1433, 5900, 8080, 3306], random.randint(2, 4)):
            new_logs.append({
                "⏰ Thời gian": now.strftime("%H:%M:%S.") + f"{random.randint(0,999):03d}",
                "🌐 IP Nguồn": sc["ip"],
                "📍 Quốc gia": f"{sc['city']}, {sc['country']}",
                "🔫 Kiểu tấn công": "Port Scan",
                "🎯 Port": str(port),
                "⚡ Packets/s": f"{random.randint(30, 150):,}",
                "🚨 Mức độ": "HIGH",
            })
    else:
        eps = int(np.random.randint(80, 160))
        status = "AN TOÀN"
        badge_cls = "badge-safe"

    # ── Overlay QR attacks ──
    for atk in qr_attacks:
        new_logs.append({
            "⏰ Thời gian": atk.get("time", now.strftime("%H:%M:%S")),
            "🌐 IP Nguồn": atk.get("ip", "?"),
            "📍 Quốc gia": f"{atk.get('city','?')}, {atk.get('country','?')}",
            "🔫 Kiểu tấn công": "🎯 QR LIVE ATTACK (Thật!)",
            "🎯 Port": str(random.choice([80, 443, 22, 3389])),
            "⚡ Packets/s": f"{random.randint(50, 300):,}",
            "🚨 Mức độ": "REAL ATTACK !!!",
        })
        status = "🎯 QR ATTACK DETECTED"
        badge_cls = "badge-qr"

    # Cập nhật lịch sử traffic
    st.session_state.packet_history.append({"time": now.strftime("%H:%M:%S"), "eps": eps})
    if len(st.session_state.packet_history) > 25:
        st.session_state.packet_history.pop(0)

    # Cập nhật log (giữ 60 dòng mới nhất)
    st.session_state.attack_log = (new_logs + st.session_state.attack_log)[:60]
    st.session_state.attack_count += len([l for l in new_logs if l.get("🚨 Mức độ") in ("CRITICAL","HIGH","REAL ATTACK !!!")])
    st.session_state.total_packets += eps

    return eps, status, badge_cls, new_logs


# ═══════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown('<div class="sidebar-title">[ NIDS SOC CONTROL ]</div>', unsafe_allow_html=True)
    st.caption("🕐 " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    st.markdown("---")

    st.markdown('<div class="sidebar-title">[ KỊCH BẢN DEMO ]</div>', unsafe_allow_html=True)

    if st.button("🟢  KỊCH BẢN 1 — Mạng Bình thường", use_container_width=True):
        st.session_state.scenario = "normal"
    if st.button("🔴  KỊCH BẢN 2 — Bão DDoS", use_container_width=True):
        st.session_state.scenario = "ddos"
    if st.button("⚔️  KỊCH BẢN 3 — MULTI-VECTOR (Khói mù + Dao găm)", use_container_width=True):
        st.session_state.scenario = "multi_vector"
    if st.button("🟠  KỊCH BẢN 4 — Port Scan Lén lút", use_container_width=True):
        st.session_state.scenario = "portscan"

    st.markdown("---")
    st.markdown('<div class="sidebar-title">[ QR CODE DEMO ]</div>', unsafe_allow_html=True)
    st.caption("Chạy `python attack_api.py` → dùng ngrok → tạo QR")
    st.caption("Khi thầy cô bấm nút → hiện ngay trên bản đồ!")

    if st.button("🗑️  Xóa log QR attacks", use_container_width=True):
        if os.path.exists(QR_ATTACKS_FILE):
            with open(QR_ATTACKS_FILE, "w") as f:
                json.dump([], f)
            st.success("Đã xóa!")

    st.markdown("---")
    st.markdown('<div class="sidebar-title">[ THỐNG KÊ PHIÊN ]</div>', unsafe_allow_html=True)
    st.markdown(f"⚡ **Tổng packets:** `{st.session_state.total_packets:,}`")
    st.markdown(f"🚨 **Tổng cảnh báo:** `{st.session_state.attack_count}`")
    st.markdown(f"🕐 **Từ:** `{st.session_state.start_time}`")

    if st.button("🔄  Reset thống kê", use_container_width=True):
        st.session_state.packet_history = []
        st.session_state.attack_log = []
        st.session_state.attack_count = 0
        st.session_state.total_packets = 0
        st.session_state.start_time = datetime.now().strftime("%H:%M:%S")


# ═══════════════════════════════════════════════════════════════════
# MAIN — LOAD DỮ LIỆU
# ═══════════════════════════════════════════════════════════════════
qr_attacks = load_qr_attacks()
eps, status, badge_cls, new_logs = generate_traffic(st.session_state.scenario, qr_attacks)

# ═══════════════════════════════════════════════════════════════════
# HEADER
# ═══════════════════════════════════════════════════════════════════
st.markdown(
    "# 🛡️ AWS NIDS — Trung tâm Điều hành An ninh mạng (SOC)",
    help="Network Intrusion Detection System | Powered by Apache Kafka + ML"
)
st.caption("⚡ Powered by AWS · Apache Kafka · Random Forest ML · Folium Live Map | Real-time Dashboard v2.0")
st.divider()

# ═══════════════════════════════════════════════════════════════════
# ROW 1 — METRICS
# ═══════════════════════════════════════════════════════════════════
c1, c2, c3, c4, c5 = st.columns(5)

with c1:
    st.metric(
        "⚡ Kafka Throughput",
        f"{eps:,} EPS",
        delta="🔺 Tải cực cao!" if eps > 1000 else "✅ Bình thường",
        delta_color="inverse" if eps > 1000 else "normal",
    )
with c2:
    latency = random.randint(8, 25) if eps < 500 else random.randint(25, 65)
    st.metric("🧠 AI Latency", f"{latency} ms", f"-{random.randint(1,3)} ms")
with c3:
    alert_count = len([l for l in new_logs if "CRITICAL" in str(l.get("🚨 Mức độ","")) or "HIGH" in str(l.get("🚨 Mức độ",""))])
    st.metric("🚨 Cảnh báo mới", f"{alert_count} hits", f"+ {alert_count}" if alert_count else "")
with c4:
    st.metric("📦 Tổng Packets", f"{st.session_state.total_packets:,}", "")
with c5:
    st.markdown("**🔰 Trạng thái Hệ thống**")
    st.markdown(f'<span class="{badge_cls}">{status}</span>', unsafe_allow_html=True)

st.divider()

# ═══════════════════════════════════════════════════════════════════
# ROW 2 — BIỂU ĐỒ TRAFFIC + BẢN ĐỒ
# ═══════════════════════════════════════════════════════════════════
col_chart, col_map = st.columns([1, 1.3])

with col_chart:
    st.subheader("📈 Lưu lượng Kafka Thời gian thực")
    df_hist = pd.DataFrame(st.session_state.packet_history)
    if not df_hist.empty:
        is_attack = st.session_state.scenario != "normal"
        color = "#ff3333" if is_attack else "#00ff90"
        fig = px.area(
            df_hist, x="time", y="eps",
            template="plotly_dark",
            color_discrete_sequence=[color],
            labels={"eps": "Events/sec", "time": "Thời gian"},
        )
        fig.update_layout(
            margin=dict(l=0, r=0, t=10, b=0),
            height=320,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=False, tickfont=dict(color="#00ff9070")),
            yaxis=dict(showgrid=True, gridcolor="#00ff9015", tickfont=dict(color="#00ff9070")),
        )
        fig.update_traces(
            fillcolor=color.replace(")", ",0.15)").replace("rgb","rgba") if "rgb" in color else color + "26",
            line=dict(width=2),
        )
        st.plotly_chart(fig, use_container_width=True)

        # Mini bar chart: phân bố loại tấn công
        if st.session_state.attack_log:
            df_log = pd.DataFrame(st.session_state.attack_log)
            type_counts = df_log["🔫 Kiểu tấn công"].value_counts().reset_index()
            type_counts.columns = ["Loại", "Số lượng"]
            fig2 = px.bar(
                type_counts, x="Loại", y="Số lượng",
                template="plotly_dark",
                color_discrete_sequence=["#ff3333", "#ff8800", "#ff00ff", "#00ff90"],
                height=180,
            )
            fig2.update_layout(
                margin=dict(l=0, r=0, t=5, b=0),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                showlegend=False,
                xaxis=dict(showgrid=False, tickfont=dict(color="#00ff9070", size=10)),
                yaxis=dict(showgrid=True, gridcolor="#00ff9015", tickfont=dict(color="#00ff9070")),
            )
            st.plotly_chart(fig2, use_container_width=True)

with col_map:
    st.subheader("🌍 Live Threat Map — Bản đồ Tấn công Thời gian thực")
    threat_map = build_threat_map(st.session_state.scenario, qr_attacks)
    st_folium(
        threat_map,
        width="100%",
        height=500,
        returned_objects=[],
        key=f"map_{st.session_state.scenario}_{int(time.time() / 3)}",
    )

st.divider()

# ═══════════════════════════════════════════════════════════════════
# ROW 3 — ATTACK LOG
# ═══════════════════════════════════════════════════════════════════
st.subheader("🚨 Nhật ký Phát hiện Tấn công (AI Detection Log)")

col_log, col_info = st.columns([2, 1])

with col_log:
    if st.session_state.attack_log:
        df_alerts = pd.DataFrame(st.session_state.attack_log)

        def style_row(row):
            sev = str(row.get("🚨 Mức độ", ""))
            if "REAL" in sev:
                return ["background-color: #3a0040; color: #ff88ff"] * len(row)
            elif "CRITICAL" in sev:
                return ["background-color: #2a0000; color: #ff6666"] * len(row)
            elif "HIGH" in sev:
                return ["background-color: #1a1000; color: #ffaa44"] * len(row)
            return ["color: #00ff9080"] * len(row)

        st.dataframe(
            df_alerts.style.apply(style_row, axis=1),
            use_container_width=True,
            height=320,
        )
    else:
        st.success("✅ Hệ thống ổn định. Chưa phát hiện hành vi bất thường.")

with col_info:
    # Thông tin kịch bản đang chạy
    scenario_info = {
        "normal": {
            "title": "🟢 MẠNG BÌNH THƯỜNG",
            "desc": "Kafka đang xử lý lưu lượng web thông thường.\nAI phân loại 100% là Normal traffic.",
            "color": "#00ff90",
        },
        "ddos": {
            "title": "🔴 BÃO DDoS",
            "desc": "Kafka đang chịu tải hàng ngàn packet/giây từ nhiều IP phân tán khắp toàn cầu.\nAI xác định: DDoS Flood Attack.",
            "color": "#ff3333",
        },
        "multi_vector": {
            "title": "⚔️ MULTI-VECTOR",
            "desc": "🌪️ Khói mù: DDoS cường độ cao từ 5+ quốc gia.\n🗡️ Dao găm: IP Singapore lén lút dò quét cổng SSH, RDP trong tâm bão.\nAI phát hiện CẢ HAI luồng đồng thời!",
            "color": "#ff4400",
        },
        "portscan": {
            "title": "🟠 PORT SCAN LÉN LUT",
            "desc": "1 IP duy nhất từ Singapore đang quét tuần tự các cổng nhạy cảm:\n22 (SSH), 21 (FTP), 23 (Telnet), 3389 (RDP)...",
            "color": "#ff8800",
        },
    }
    info = scenario_info.get(st.session_state.scenario, scenario_info["normal"])
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #080c18, #0a1020);
        border: 1px solid {info['color']}40;
        border-left: 3px solid {info['color']};
        border-radius: 6px;
        padding: 16px;
        font-family: 'Courier New', monospace;
    ">
        <div style="color:{info['color']}; font-weight:bold; font-size:14px; margin-bottom:10px;">
            {info['title']}
        </div>
        <div style="color:#88aacc; font-size:12px; line-height:1.7; white-space:pre-line;">
{info['desc']}
        </div>
        <hr style="border-color:{info['color']}20; margin:12px 0;">
        <div style="color:#00ff9060; font-size:11px;">
            🤖 Model: Random Forest Classifier<br>
            📊 Accuracy: 97.8% | Latency: &lt;5ms/batch<br>
            🔁 Kafka consumer: active<br>
            ☁️ SNS alerts: armed
        </div>
    </div>
    """, unsafe_allow_html=True)

    # QR attacks counter
    if qr_attacks:
        st.markdown(f"""
        <div style="
            margin-top:12px;
            background:#1a0025;
            border:1px solid #ff00ff60;
            border-left:3px solid #ff00ff;
            border-radius:6px; padding:12px;
            font-family:'Courier New',monospace;
        ">
            <div style="color:#ff00ff; font-weight:bold;">🎯 QR LIVE ATTACKS</div>
            <div style="color:#ffaaff; font-size:12px; margin-top:6px;">
                {len(qr_attacks)} kết nối thực từ điện thoại!<br>
                Người tham gia đang tấn công hệ thống.
            </div>
        </div>
        """, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════
# AUTO-REFRESH
# ═══════════════════════════════════════════════════════════════════
time.sleep(1.8)
st.rerun()
