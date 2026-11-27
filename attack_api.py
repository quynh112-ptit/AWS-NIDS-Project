"""
NIDS Attack API - Server cho Kịch bản QR Code Demo
Chạy: python attack_api.py
Sau đó dùng ngrok để expose ra internet:
  ngrok http 5000
Lấy URL ngrok → tạo QR Code → cho hội đồng quét
"""
from flask import Flask, request, jsonify, render_template_string
import json
import os
import requests
from datetime import datetime

app = Flask(__name__)

SHARED_FILE = os.path.join(os.path.dirname(__file__), "shared_attacks.json")

# ── HTML trang tấn công (mobile-friendly, hacker style) ──
ATTACK_PAGE_HTML = """
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<title>NIDS Attack Demo</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body {
    background:#050810; color:#00ff90;
    font-family:'Courier New',monospace;
    display:flex; flex-direction:column;
    align-items:center; justify-content:center;
    min-height:100vh; padding:20px;
  }
  .container {
    width:100%; max-width:400px;
    background:#080c18;
    border:1px solid #00ff9030;
    border-radius:12px; padding:28px 24px;
    text-align:center;
    box-shadow: 0 0 40px #00ff9015;
  }
  .logo { font-size:48px; margin-bottom:8px; }
  h1 { font-size:18px; color:#ff3333; margin-bottom:6px; letter-spacing:2px; }
  .subtitle { font-size:12px; color:#00bfff88; margin-bottom:28px; line-height:1.6; }
  .ip-box {
    background:#0a1020; border:1px solid #00ff9020;
    border-radius:8px; padding:12px; margin-bottom:20px;
    font-size:13px; color:#00ff9099;
  }
  .ip-box span { color:#00ff90; font-weight:bold; font-size:15px; }
  .btn-attack {
    width:100%; padding:18px;
    background:linear-gradient(135deg, #ff0033, #cc0022);
    color:#fff; font-family:'Courier New',monospace;
    font-size:20px; font-weight:bold;
    border:none; border-radius:10px; cursor:pointer;
    letter-spacing:1px;
    box-shadow: 0 0 25px #ff003350;
    transition: all 0.2s ease;
    text-transform:uppercase;
  }
  .btn-attack:hover { box-shadow: 0 0 40px #ff003380; transform:scale(1.02); }
  .btn-attack:active { transform:scale(0.97); }
  .btn-attack:disabled {
    background:linear-gradient(135deg, #333, #222);
    color:#666; cursor:not-allowed;
    box-shadow:none;
  }
  .status-box {
    display:none; margin-top:20px;
    background:#0d1f10; border:1px solid #00ff9050;
    border-radius:8px; padding:14px;
    font-size:13px; line-height:1.8;
  }
  .status-box.show { display:block; }
  .status-box.error { background:#1f0d0d; border-color:#ff003350; color:#ff6666; }
  .sent { color:#00ff90; }
  .footer {
    margin-top:20px; font-size:11px; color:#00ff9030;
    line-height:1.6;
  }
  .pulse { animation: pulse 1.5s infinite; }
  @keyframes pulse {
    0%,100%{ text-shadow: 0 0 5px #ff0033; }
    50%    { text-shadow: 0 0 20px #ff0033, 0 0 40px #ff003380; }
  }
  .scanner-line {
    height:2px; width:100%;
    background:linear-gradient(90deg, transparent, #00ff90, transparent);
    margin:16px 0; animation:scan 2s linear infinite;
  }
  @keyframes scan { 0%{opacity:0.3} 50%{opacity:1} 100%{opacity:0.3} }
</style>
</head>
<body>
<div class="container">
  <div class="logo">☠️</div>
  <h1 class="pulse">[ THAM GIA TẤN CÔNG ]</h1>
  <p class="subtitle">
    Đây là demo cho đề tài NIDS<br>
    Bấm nút bên dưới để đóng vai Hacker<br>
    tấn công vào máy chủ của nhóm!
  </p>

  <div class="scanner-line"></div>

  <div class="ip-box">
    📡 IP của bạn:<br>
    <span id="myip">Đang xác định...</span>
  </div>

  <button class="btn-attack" id="btn" onclick="doAttack()">
    ⚡ BẤM ĐỂ TẤN CÔNG! ⚡
  </button>

  <div class="status-box" id="status-box">
    <div id="status-text"></div>
  </div>

  <div class="footer">
    Dữ liệu IP chỉ dùng cho mục đích demo<br>
    Hệ thống NIDS AI sẽ phát hiện ngay lập tức 🛡️
  </div>
</div>

<script>
  // Hiển thị IP người dùng
  fetch('/api/myip')
    .then(r=>r.json())
    .then(d=>{ document.getElementById('myip').textContent = d.ip || 'Không xác định'; })
    .catch(()=>{ document.getElementById('myip').textContent = 'Không xác định'; });

  async function doAttack() {
    const btn = document.getElementById('btn');
    const box = document.getElementById('status-box');
    const txt = document.getElementById('status-text');

    btn.disabled = true;
    btn.textContent = '⏳ Đang tấn công...';
    box.className = 'status-box show';
    txt.innerHTML = '<span style="color:#ffcc00">⚡ Đang gửi gói tin độc hại...</span>';

    try {
      const res = await fetch('/api/attack', {method:'POST'});
      const data = await res.json();
      if (data.success) {
        txt.innerHTML = `
          <span class="sent">✅ TẤN CÔNG THÀNH CÔNG!</span><br><br>
          🌐 IP của bạn: <b>${data.ip}</b><br>
          📍 Vị trí: <b>${data.city}, ${data.country}</b><br>
          ⏰ Thời gian: <b>${data.time}</b><br><br>
          <span style="color:#ff8800">👀 Nhìn lên màn hình chiếu!</span><br>
          <span style="color:#ff8800">Hệ thống NIDS đã phát hiện bạn!</span>
        `;
        btn.textContent = '🚨 Đã bị phát hiện!';
        btn.style.background = 'linear-gradient(135deg,#ff8800,#cc6600)';
      } else {
        throw new Error(data.error || 'Lỗi không xác định');
      }
    } catch(e) {
      box.className = 'status-box show error';
      txt.innerHTML = `❌ Lỗi: ${e.message}<br>Hãy thử lại!`;
      btn.disabled = false;
      btn.textContent = '⚡ BẤM ĐỂ TẤN CÔNG! ⚡';
    }
  }
</script>
</body>
</html>
"""


def geoip_lookup(ip: str) -> dict:
    """Tra cứu vị trí địa lý của IP qua ip-api.com (miễn phí, không cần key)."""
    try:
        # Bỏ qua IP localhost/private
        if ip.startswith(("127.", "10.", "192.168.", "172.", "::1")):
            return {
                "country": "Vietnam (Local)",
                "city": "Local Network",
                "lat": 10.8231,
                "lon": 106.6297,
            }
        resp = requests.get(
            f"http://ip-api.com/json/{ip}",
            timeout=4,
            params={"fields": "country,city,lat,lon,status,message"},
        )
        d = resp.json()
        if d.get("status") == "success":
            return {
                "country": d.get("country", "Unknown"),
                "city": d.get("city", "Unknown"),
                "lat": d.get("lat", 0.0),
                "lon": d.get("lon", 0.0),
            }
    except Exception as e:
        print(f"[GeoIP] Lỗi: {e}")
    return {"country": "Unknown", "city": "Unknown", "lat": 0.0, "lon": 0.0}


def get_client_ip() -> str:
    """Lấy IP thực của client (hỗ trợ ngrok / reverse proxy)."""
    # ngrok và các proxy đặt IP thực vào X-Forwarded-For
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "Unknown"


def save_attack(attack_data: dict):
    """Lưu tấn công vào file JSON chia sẻ với dashboard."""
    attacks = []
    if os.path.exists(SHARED_FILE):
        try:
            with open(SHARED_FILE, "r", encoding="utf-8") as f:
                attacks = json.load(f)
        except Exception:
            attacks = []

    attacks.append(attack_data)
    # Giữ tối đa 50 bản ghi
    attacks = attacks[-50:]

    with open(SHARED_FILE, "w", encoding="utf-8") as f:
        json.dump(attacks, f, ensure_ascii=False, indent=2)


# ── ROUTES ──

@app.route("/")
def index():
    """Trang chính với nút tấn công (dành cho QR code)."""
    return render_template_string(ATTACK_PAGE_HTML)


@app.route("/api/myip")
def my_ip():
    """Trả về IP của client để hiển thị trên trang."""
    ip = get_client_ip()
    return jsonify({"ip": ip})


@app.route("/api/attack", methods=["POST"])
def receive_attack():
    """Nhận tấn công từ điện thoại, geolocate, lưu file → dashboard sẽ đọc."""
    ip = get_client_ip()
    now = datetime.now()

    print(f"\n[⚠️  QR ATTACK] IP: {ip} | Thời gian: {now.strftime('%H:%M:%S')}")

    # Tra cứu vị trí
    geo = geoip_lookup(ip)
    print(f"    └─ Vị trí: {geo['city']}, {geo['country']} ({geo['lat']}, {geo['lon']})")

    attack_data = {
        "ip": ip,
        "country": geo["country"],
        "city": geo["city"],
        "lat": geo["lat"],
        "lon": geo["lon"],
        "time": now.strftime("%H:%M:%S"),
        "date": now.strftime("%Y-%m-%d"),
        "type": "qr_live_attack",
    }

    save_attack(attack_data)
    print(f"    └─ Đã lưu vào {SHARED_FILE}")

    return jsonify({
        "success": True,
        "ip": ip,
        "country": geo["country"],
        "city": geo["city"],
        "time": now.strftime("%H:%M:%S"),
        "message": "Attack recorded! Check the dashboard.",
    })


@app.route("/api/status")
def status():
    """Kiểm tra server đang chạy."""
    attacks = []
    if os.path.exists(SHARED_FILE):
        try:
            with open(SHARED_FILE, "r") as f:
                attacks = json.load(f)
        except Exception:
            pass
    return jsonify({
        "status": "running",
        "attack_count": len(attacks),
        "time": datetime.now().strftime("%H:%M:%S"),
    })


if __name__ == "__main__":
    print("=" * 60)
    print("  NIDS Attack API Server - QR Code Demo")
    print("=" * 60)
    print(f"\n[✓] Server đang chạy tại: http://0.0.0.0:5000")
    print(f"[✓] File chia sẻ: {SHARED_FILE}")
    print("\n[→] Để expose ra internet, chạy lệnh sau trong terminal KHÁC:")
    print("    ngrok http 5000")
    print("\n[→] Lấy URL từ ngrok (vd: https://abc123.ngrok.io)")
    print("    → Tạo QR code tại: https://qr-code-generator.com/")
    print("    → Chèn QR code khổng lồ vào slide PowerPoint!")
    print("\n[🕐] Đang chờ kết nối từ điện thoại hội đồng...")
    print("-" * 60)
    app.run(host="0.0.0.0", port=5000, debug=False)
