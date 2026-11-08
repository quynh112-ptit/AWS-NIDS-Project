from datetime import datetime
from io import BytesIO
from zoneinfo import ZoneInfo
import os

import altair as alt
import pandas as pd
import psycopg
import qrcode
import streamlit as st

from tv3_config import LABELS, database_dsn
from tv3_ui import apply_theme, heading, hero, kpi

LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
ALERT_COLORS = ["#ff7890", "#ffc477", "#9baaff"]

st.set_page_config(page_title="NIDS SOC", page_icon="🛡️", layout="wide")
apply_theme()
hero("Trung tâm giám sát", "SOC")

with st.sidebar:
    st.html('<div class="nids-brand"><span class="nids-mark" aria-hidden="true">◆</span> NIDS / SOC</div>')
    minutes = st.selectbox("Khoảng thời gian", (5, 15, 60), index=1,
                           format_func=lambda value: f"{value} phút gần nhất")
    qr_url = os.getenv("NIDS_QR_URL")
    if qr_url:
        st.divider()
        heading("Web QR")
        image = BytesIO()
        qrcode.make(qr_url).save(image, format="PNG")
        st.image(image.getvalue(), width=172)
        st.link_button("Mở Web QR ↗", qr_url, width="stretch")


def read_snapshot(window):
    args = (window,)
    time_filter = "observed_at >= now() - make_interval(mins => %s)"
    with psycopg.connect(database_dsn(read_only=True), connect_timeout=3,
                         options="-c statement_timeout=4000") as db:
        db.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        counts = db.execute(
            f"SELECT prediction, count(*) FROM nids_events WHERE {time_filter} GROUP BY prediction", args
        ).fetchall()
        timeline = db.execute(f"""
            SELECT date_trunc('minute', observed_at), count(*),
                   count(*) FILTER (WHERE prediction <> 0)
            FROM nids_events WHERE {time_filter} GROUP BY 1 ORDER BY 1
        """, args).fetchall()
        alerts = db.execute(f"""
            SELECT observed_at, src_ip, dst_port, protocol, prediction, scenario, demo_id
            FROM nids_events WHERE {time_filter} AND prediction <> 0
            ORDER BY observed_at DESC LIMIT 100
        """, args).fetchall()
    return dict(counts), timeline, alerts


def finish_chart(chart):
    return (chart.properties(height=205, background="transparent")
            .configure_view(stroke=None)
            .configure_axis(domain=False, tickColor="#334767", gridColor="#223451",
                            labelColor="#a0b2ce", labelPadding=7)
            .configure_legend(labelColor="#dbe7f7", orient="top", title=None))


def timeline_chart(timeline):
    trend = pd.DataFrame(timeline, columns=["Phút", "Đã xử lý", "Cảnh báo"])
    trend["Phút"] = (pd.to_datetime(trend["Phút"], utc=True)
                     .dt.tz_convert(LOCAL_TZ).dt.strftime("%Y-%m-%d %H:%M"))
    series = trend.melt(id_vars="Phút", var_name="Chỉ số", value_name="Bản ghi")
    series["Giờ"] = series["Phút"].str[-5:]
    chart = alt.Chart(series).mark_line(strokeWidth=2.6, point={"filled": True, "size": 48}).encode(
        x=alt.X("Phút:O", title=None, axis=alt.Axis(labelExpr="slice(datum.label, -5)", labelOverlap="greedy",
                                                  labelAngle=0, grid=False)),
        y=alt.Y("Bản ghi:Q", title=None, axis=alt.Axis(tickMinStep=1)),
        color=alt.Color("Chỉ số:N", scale=alt.Scale(domain=["Đã xử lý", "Cảnh báo"],
                                                     range=["#53e6c0", "#ff7890"])),
        tooltip=["Giờ:N", "Chỉ số:N", "Bản ghi:Q"],
    )
    return finish_chart(chart)


def distribution_chart(counts):
    labels = [LABELS[i] for i in (1, 2, 3)]
    data = pd.DataFrame({"Loại": labels, "Số lượng": [counts.get(i, 0) for i in (1, 2, 3)]})
    chart = alt.Chart(data).mark_bar(cornerRadiusEnd=5, size=19).encode(
        x=alt.X("Số lượng:Q", title=None, axis=alt.Axis(tickMinStep=1)),
        y=alt.Y("Loại:N", sort=labels, title=None),
        color=alt.Color("Loại:N", scale=alt.Scale(domain=labels, range=ALERT_COLORS), legend=None),
        tooltip=["Loại:N", "Số lượng:Q"],
    )
    return finish_chart(chart)


@st.fragment(run_every="3s")
def render_live():
    try:
        counts, timeline, alerts = read_snapshot(minutes)
    except psycopg.errors.UndefinedTable:
        st.info("Chưa có bảng sự kiện.")
        return
    except (psycopg.Error, RuntimeError):
        st.error("Mất kết nối PostgreSQL.")
        return

    updated = datetime.now(LOCAL_TZ).strftime("%H:%M:%S")
    st.html(f'<span class="nids-status">TRỰC TUYẾN · {updated}</span>')
    total = sum(counts.values())
    attack_count = total - counts.get(0, 0)
    cols = st.columns(4)
    for col, (label, value, color) in zip(cols, (
        ("Đã phân loại", f"{total:,}", "#53e6c0"),
        ("Bình thường", f"{counts.get(0, 0):,}", "#79a8ff"),
        ("Cảnh báo", f"{attack_count:,}", "#ff7890"),
        ("Tỷ lệ cảnh báo", f"{(100 * attack_count / total if total else 0):.1f}%", "#ffc477"),
    )):
        with col:
            kpi(label, value, color)

    left, right = st.columns([1.8, 1])
    with left.container(key="soc-panel-trend"):
        heading("Lưu lượng theo phút")
        if timeline:
            st.altair_chart(timeline_chart(timeline), width="stretch", theme=None)
        else:
            st.info("Chưa có lưu lượng.")
    with right.container(key="soc-panel-types"):
        heading("Phân bố cảnh báo")
        st.altair_chart(distribution_chart(counts), width="stretch", theme=None)

    with st.container(key="soc-panel-alerts"):
        heading("Cảnh báo gần nhất")
        if not alerts:
            st.info("Chưa có cảnh báo.")
            return
        data = pd.DataFrame(alerts, columns=["Thời điểm", "IP nguồn", "Cổng", "Giao thức",
                                            "Loại cảnh báo", "Kịch bản", "Mã sự kiện"])
        data["Thời điểm"] = pd.to_datetime(data["Thời điểm"], utc=True).dt.tz_convert(LOCAL_TZ)
        data["Loại cảnh báo"] = data["Loại cảnh báo"].map(LABELS)
        data["Giao thức"] = data["Giao thức"].map(lambda value: {6: "TCP", 17: "UDP"}.get(value, str(value)))
        data = data[["Thời điểm", "Loại cảnh báo", "IP nguồn", "Cổng", "Giao thức", "Mã sự kiện"]]
        st.dataframe(data, hide_index=True, width="stretch",
                     column_config={"Thời điểm": st.column_config.DatetimeColumn(format="DD/MM HH:mm:ss")})


render_live()
