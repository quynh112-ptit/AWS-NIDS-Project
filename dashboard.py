import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time

# --- CẤU HÌNH GIAO DIỆN (DARK MODE TỰ ĐỘNG) ---
st.set_page_config(page_title="AWS NIDS Enterprise SOC", page_icon="🛡️", layout="wide")

# CSS Tùy chỉnh (Hiệu ứng Neon chữ đỏ/xanh)
st.markdown("""
    <style>
    .metric-safe { color: #00FF00 !important; font-size: 28px; font-weight: bold; text-shadow: 0 0 5px #00FF00;}
    .metric-danger { color: #FF0000 !important; font-size: 28px; font-weight: bold; text-shadow: 0 0 10px #FF0000; animation: blink 1s infinite;}
    @keyframes blink { 50% { opacity: 0.5; } }
    </style>
    """, unsafe_allow_html=True)

# --- KHỞI TẠO BIẾN TRẠNG THÁI (CHO KỊCH BẢN DEMO) ---
if 'scenario' not in st.session_state:
    st.session_state.scenario = 'normal'
if 'packet_history' not in st.session_state:
    st.session_state.packet_history = []

# --- MENU ĐIỀU KHIỂN BÊN TRÁI (SIDEBAR DEMO) ---
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/9/93/Amazon_Web_Services_Logo.svg", width=150)
    st.title("Bảng Điều khiển Demo")
    st.markdown("Chọn kịch bản để giả lập luồng dữ liệu:")
    
    if st.button("🟢 Kịch bản 1: Mạng Bình thường", use_container_width=True):
        st.session_state.scenario = 'normal'
    if st.button("🔴 Kịch bản 2: Bão DDoS", use_container_width=True):
        st.session_state.scenario = 'ddos'
    if st.button("🟠 Kịch bản 3: Port Scan Lén lút", use_container_width=True):
        st.session_state.scenario = 'portscan'

# --- HÀM SINH DỮ LIỆU GIẢ LẬP THEO KỊCH BẢN ---
def generate_traffic(scenario):
    now = datetime.now()
    if scenario == 'normal':
        eps = np.random.randint(50, 150)
        alerts = []
        status = "AN TOÀN"
    elif scenario == 'ddos':
        eps = np.random.randint(5000, 12000) # Tốc độ nhảy vọt
        alerts = [
            {"time": now.strftime("%H:%M:%S"), "ip": f"103.15.22.{np.random.randint(1, 255)}", 
             "port": 80, "type": "DDoS", "severity": "Critical", "lat": np.random.uniform(10, 50), "lon": np.random.uniform(70, 120)} 
            for _ in range(5)
        ]
        status = "BÁO ĐỘNG ĐỎ"
    else: # portscan
        eps = np.random.randint(100, 200)
        alerts = [
            {"time": now.strftime("%H:%M:%S"), "ip": "45.33.12.19", # Duy nhất 1 IP
             "port": np.random.choice([22, 21, 3389, 1433, 23]), "type": "Port Scan", "severity": "High", "lat": 55.75, "lon": 37.61}
        ]
        status = "PHÁT HIỆN XÂM NHẬP"

    # Cập nhật lịch sử lưu lượng (Giữ 20 mốc gần nhất)
    st.session_state.packet_history.append({"time": now.strftime("%H:%M:%S"), "eps": eps})
    if len(st.session_state.packet_history) > 20:
        st.session_state.packet_history.pop(0)
        
    return eps, alerts, status

eps, current_alerts, sys_status = generate_traffic(st.session_state.scenario)

# --- HEADER GIAO DIỆN CHÍNH ---
st.title("🛡️ Trung tâm Điều hành An ninh mạng (NIDS SOC)")
st.caption("Powered by AWS, Apache Kafka & Machine Learning | Real-time Dashboard")

# --- 1. KHU VỰC THÔNG SỐ (TOP METRICS) ---
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Tốc độ Xử lý (Kafka)", f"{eps:,} EPS", delta="Cao bất thường" if eps > 1000 else "Bình thường", delta_color="inverse" if eps > 1000 else "normal")
with col2:
    st.metric("Độ trễ AI (Latency)", f"{np.random.randint(12, 45)} ms", "-2 ms")
with col3:
    num_alerts = len(current_alerts) if current_alerts else 0
    st.metric("Cảnh báo khẩn", f"{num_alerts} hits", "+ Nguy hiểm" if num_alerts > 0 else "")
with col4:
    css_class = "metric-danger" if sys_status != "AN TOÀN" else "metric-safe"
    st.markdown(f"Trạng thái Hệ thống<br><span class='{css_class}'>{sys_status}</span>", unsafe_allow_html=True)

st.divider()

# --- 2. KHU VỰC BIỂU ĐỒ & BẢN ĐỒ ---
col_left, col_right = st.columns([1.2, 1])

with col_left:
    st.subheader("📈 Lưu lượng Mạng Thời gian thực")
    df_traffic = pd.DataFrame(st.session_state.packet_history)
    if not df_traffic.empty:
        fig_line = px.area(df_traffic, x="time", y="eps", template="plotly_dark", 
                           color_discrete_sequence=["#00F5FF"] if st.session_state.scenario == 'normal' else ["#FF3333"])
        fig_line.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=300, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_line, use_container_width=True)

with col_right:
    st.subheader("🌍 Bản đồ Nguồn Tấn công (Live Map)")
    if current_alerts:
        df_map = pd.DataFrame(current_alerts)
        fig_map = px.scatter_geo(df_map, lat="lat", lon="lon", color="severity", size_max=15, 
                                 hover_name="ip", template="plotly_dark", projection="orthographic")
        fig_map.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=300, geo=dict(bgcolor='rgba(0,0,0,0)'), paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_map, use_container_width=True)
    else:
        # Bản đồ trống khi an toàn
        fig_map = px.scatter_geo(template="plotly_dark", projection="orthographic")
        fig_map.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=300, geo=dict(bgcolor='rgba(0,0,0,0)'), paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_map, use_container_width=True)

# --- 3. NHẬT KÝ CẢNH BÁO (LOG) ---
st.subheader("🚨 Nhật ký Đánh chặn (Alert Logs)")
if current_alerts:
    df_alerts = pd.DataFrame(current_alerts)
    # Đổi màu dòng cảnh báo
    st.dataframe(df_alerts.style.applymap(lambda _: 'background-color: #4A0000; color: #FFF', subset=['severity']), use_container_width=True)
else:
    st.success("Hệ thống đang ổn định. Chưa ghi nhận luồng IP độc hại nào trong 24h qua.")

# --- VÒNG LẶP AUTO-REFRESH ---
time.sleep(1.5) # Cứ 1.5 giây web tự động vẽ lại 1 lần
st.rerun()