#!/usr/bin/env bash
# ==============================================================================
# AWS NIDS - MASTER DEMO RUNNER (run_demo.sh)
# Hỗ trợ đầy đủ 4 Kịch bản Demo:
#   Kịch bản 1: "Khói mù và Dao găm" (Multi-Vector Attack)
#   Kịch bản 2: "Vũ khí Tương tác" (QR Code Hacker Demo)
#   Kịch bản 3: "Giám sát Không chạm" (Amazon SNS Push Notification)
#   Kịch bản 4: "Dòng chảy Hệ sinh thái" (Split Screen 4 Màn hình - Matrix Style)
# ==============================================================================

set -e

# Màu sắc hiển thị
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
NC='\033[0m' # No Color

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

# ── 1. NẠP MÔI TRƯỜNG & TỰ ĐỘNG DÒ TÌM PYTHON ─────────────────────────────────
[ -f ".env" ] && export $(grep -v '^#' .env | xargs -d '\n' 2>/dev/null || true)
[ -f "tv3/.env.tv3" ] && export $(grep -v '^#' tv3/.env.tv3 | xargs -d '\n' 2>/dev/null || true)

if [ -f "venv/bin/python3" ]; then
    PY="venv/bin/python3"
    ST="venv/bin/streamlit"
elif [ -f ".venv/bin/python3" ]; then
    PY=".venv/bin/python3"
    ST=".venv/bin/streamlit"
elif command -v python3 >/dev/null 2>&1; then
    PY="python3"
    ST="streamlit"
else
    echo -e "${RED}[✗] Không tìm thấy Python 3! Vui lòng cài đặt trước.${NC}"
    exit 1
fi

KAFKA_SERVER="${KAFKA_BOOTSTRAP_SERVERS:-${NIDS_KAFKA:-localhost:9092}}"
export KAFKA_BOOTSTRAP_SERVERS="$KAFKA_SERVER"
export NIDS_KAFKA="$KAFKA_SERVER"
export NIDS_DSN="${NIDS_DSN:-postgresql://nids_user:nids_password@localhost:5432/nids_db}"
export SNS_TOPIC_ARN="${SNS_TOPIC_ARN:-arn:aws:sns:us-east-1:400131408828:NIDS-Alerts}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"

# ── BANNER CHÍNH ─────────────────────────────────────────────────────────────
show_banner() {
    clear
    echo -e "${CYAN}${BOLD}"
    echo "  ╔═══════════════════════════════════════════════════════════════╗"
    echo "  ║         AWS NIDS ENTERPRISE SOC - MASTER DEMO LAUNCHER        ║"
    echo "  ║         Trung tâm Điều hành & Phòng thủ An ninh mạng          ║"
    echo "  ╚═══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo -e "  ${YELLOW}Kafka Broker :${NC} $KAFKA_SERVER"
    echo -e "  ${YELLOW}PostgreSQL   :${NC} $NIDS_DSN"
    echo -e "  ${YELLOW}SNS Alert ARN:${NC} $SNS_TOPIC_ARN"
    echo -e "  ${YELLOW}Python Exec  :${NC} $PY"
    echo "  ───────────────────────────────────────────────────────────────"
}

# ── KỊCH BẢN 4: CHIA 4 MÀN HÌNH SPLIT-SCREEN (THE MATRIX) ────────────────────
run_scenario_4_splitscreen() {
    echo -e "\n${GREEN}[*] Đang khởi tạo Kịch bản 4: 'Dòng chảy Hệ sinh thái' (Split Screen 4 Màn hình)...${NC}"

    # Đảm bảo cụm Docker (Kafka, Zookeeper, PostgreSQL) đang chạy ổn định
    if ! docker ps | grep -q "aws-nids-project-kafka-1.*Up"; then
        echo -e "${YELLOW}[*] Kafka chưa sẵn sàng. Đang khởi động lại Docker compose...${NC}"
        docker compose down 2>/dev/null || true
        docker compose up -d
        echo -e "${YELLOW}[*] Đợi 10 giây để Kafka và Zookeeper đồng bộ...${NC}"
        sleep 10
    fi

    # Kiểm tra và cài đặt tmux nếu chưa có
    if ! command -v tmux >/dev/null 2>&1; then
        echo -e "${YELLOW}[!] Tmux chưa được cài đặt. Đang tự động cài đặt tmux...${NC}"
        if command -v apt-get >/dev/null 2>&1; then
            sudo apt-get update -y && sudo apt-get install -y tmux
        elif command -v yum >/dev/null 2>&1; then
            sudo yum install -y tmux
        else
            echo -e "${RED}[✗] Không thể tự cài đặt tmux. Hãy cài thủ công: sudo apt install tmux${NC}"
            return 1
        fi
    fi

    # Tên phiên tmux
    SESSION="nids-matrix"

    echo ""
    echo -e "  ${BOLD}BẠN MUỐN CHẠY KỊCH BẢN 4 THEO CÁCH NÀO?${NC}"
    echo -e "  ${CYAN}[1] Mở xem trực tiếp 4 màn hình${NC} (Phô diễn Matrix, bấm ${YELLOW}Ctrl+Q${NC} hoặc ${YELLOW}F12${NC} để thoát về menu)"
    echo -e "  ${GREEN}[2] Chạy ngầm toàn bộ trong nền${NC} (Không chiếm terminal, in link Web Dashboard)"
    read -p "  👉 Lựa chọn [1-2] (Mặc định: 1): " mode_choice
    mode_choice="${mode_choice:-1}"

    # Nếu session đã chạy thì đóng lại
    tmux kill-session -t "$SESSION" 2>/dev/null || true

    echo -e "${CYAN}[✓] Đang chia 4 màn hình giám sát...${NC}"

    # Tạo window chính (Pane 0: Top-Left - Data Producer)
    tmux new-session -d -s "$SESSION" -x 160 -y 48
    tmux rename-window -t "$SESSION:0" "AWS-NIDS-SOC"

    # Chia đôi ngang (Top / Bottom)
    tmux split-window -v -t "$SESSION:0"

    # Chia đôi dọc nửa trên (Pane 0 và Pane 1)
    tmux split-window -h -t "$SESSION:0.0"

    # Chia đôi dọc nửa dưới (Pane 2 và Pane 3)
    tmux split-window -h -t "$SESSION:0.2"

    # ── CẤU HÌNH LỆNH CHO TỪNG PANE ──────────────────────────────────────────
    # Pane 0 (Top-Left): Data Producer
    tmux send-keys -t "$SESSION:0.0" "clear; echo -e '\033[1;36m=== [1/4] DATA PRODUCER (LƯU LƯỢNG MẠNG NETFLOW) ===\033[0m'; sleep 5; cd $ROOT_DIR && $PY -u tv3/producer.py || $PY -u producer.py" C-m

    # Pane 1 (Top-Right): Kafka Message Broker Logs
    tmux send-keys -t "$SESSION:0.1" "clear; echo -e '\033[1;33m=== [2/4] APACHE KAFKA (TRÁI TIM TRUNG CHUYỂN DỮ LIỆU) ===\033[0m'; docker logs -f --tail 40 aws-nids-project-kafka-1 2>/dev/null || docker logs -f --tail 40 \$(docker ps -q -f name=kafka | head -n1)" C-m

    # Pane 2 (Bottom-Left): AI Consumer & PostgreSQL
    tmux send-keys -t "$SESSION:0.2" "clear; echo -e '\033[1;32m=== [3/4] AI ML CONSUMER (PHÂN TÍCH & GHI POSTGRESQL) ===\033[0m'; sleep 4; cd $ROOT_DIR && $PY -u tv3/consumer_tv3.py || $PY -u consumer_ids.py" C-m

    # Pane 3 (Bottom-Right): Web Dashboard SOC / SNS Monitor
    tmux send-keys -t "$SESSION:0.3" "clear; echo -e '\033[1;35m=== [4/4] STREAMLIT DASHBOARD SOC & AWS SNS ALERT ===\033[0m'; cd $ROOT_DIR && $ST run tv3/dashboard.py --server.port 8501 --server.address 0.0.0.0 2>/dev/null || $ST run dashboard.py --server.port 8501 --server.address 0.0.0.0" C-m

    # ── THIẾT LẬP PHÍM TẮT THOÁT SIÊU DỄ (KHÔNG CẦN BẤM CTRL+B) ───────────────
    # Bấm Ctrl+Q hoặc F12 trực tiếp để thoát xem (4 màn hình vẫn chạy ngầm)
    tmux bind-key -n C-q detach-client
    tmux bind-key -n F12 detach-client
    # Bấm Ctrl+X trực tiếp để tắt hẳn 4 màn hình
    tmux bind-key -n C-x kill-session

    # Thiết lập giao diện màu viền hacker cho tmux
    tmux set -t "$SESSION" pane-border-style "fg=#005533"
    tmux set -t "$SESSION" pane-active-border-style "fg=#00ff90"
    tmux set -t "$SESSION" status-style "bg=#050810,fg=#00ff90"
    tmux set -t "$SESSION" status-left "#[bold] 🛡️ AWS NIDS SOC #[default]| "
    tmux set -t "$SESSION" status-right "#[fg=yellow,bold]Thoát xem: Ctrl+Q hoặc F12 | Tắt hẳn: Ctrl+X #[default]"

    if [ "$mode_choice" = "2" ]; then
        echo ""
        echo -e "${GREEN}${BOLD}[✓] ĐÃ KHỞI CHẠY THÀNH CÔNG 4 DỊCH VỤ NGẦM TRONG NỀN!${NC}"
        echo -e "    • ${CYAN}Data Producer   :${NC} Đang bơm traffic vào Kafka topic 'network-traffic'"
        echo -e "    • ${YELLOW}Apache Kafka    :${NC} Đang trung chuyển dữ liệu"
        echo -e "    • ${GREEN}AI ML Consumer  :${NC} Đang phân loại và ghi vào PostgreSQL 'nids_events'"
        echo -e "    • ${MAGENTA}Web Dashboard   :${NC} http://${SERVER_IP:-localhost}:8501"
        echo ""
        echo -e "    ${YELLOW}Mẹo:${NC} Muốn mở xem trực tiếp 4 màn hình bất cứ lúc nào, gõ: ${BOLD}tmux attach -t $SESSION${NC}"
        echo ""
        read -p "Bấm [Enter] để quay lại Menu..."
    else
        echo -e "${GREEN}${BOLD}[✓] ĐÃ KHỞI TẠO XONG 4 MÀN HÌNH THE MATRIX!${NC}"
        echo -e "    → Đang chuyển bạn vào màn hình giám sát trực tiếp..."
        echo -e "    → ${YELLOW}${BOLD}CÁCH THOÁT CỰC KỲ ĐƠN GIẢN:${NC}"
        echo -e "       • Bấm ${BOLD}Ctrl + Q${NC} (hoặc phím ${BOLD}F12${NC}) để THOÁT VỀ MENU (4 màn hình vẫn chạy ngầm)."
        echo -e "       • Bấm ${BOLD}Ctrl + X${NC} để TẮT HẲN toàn bộ 4 màn hình."
        echo ""
        sleep 2
        tmux attach-session -t "$SESSION"
    fi
}

# ── KỊCH BẢN 1: MULTI-VECTOR ATTACK ("KHÓI MÙ VÀ DAO GĂM") ───────────────────
run_scenario_1_multivector() {
    echo -e "\n${RED}${BOLD}[!] KÍCH HOẠT KỊCH BẢN 1: 'KHÓI MÙ VÀ DAO GĂM' (MULTI-VECTOR ATTACK)${NC}"
    echo -e "    - Bước 1: Ổn định lưu lượng bình thường (100 gói/giây)"
    echo -e "    - Bước 2: Bão DDoS ập tới (8.000 gói/giây từ Nga, Trung Quốc, Brazil...)"
    echo -e "    - Bước 3: Đòn dao găm: 1 IP Singapore lén lút quét cổng SSH (22), RDP (3389)..."
    echo ""
    $PY -c "
import os, sys, time, json
from kafka import KafkaProducer

kafka_server = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
print(f'[*] Kết nối Kafka: {kafka_server}')
try:
    producer = KafkaProducer(
        bootstrap_servers=[kafka_server],
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
    # Gửi lệnh kích hoạt multi-vector vào topic nids-control
    cmd = {'scenario': 'ddos_portscan', 'target_eps': 8000, 'duration_sec': 30}
    producer.send('nids-control', cmd)
    producer.flush()
    print('[✓] Đã bắn lệnh kịch bản Multi-Vector vào Kafka topic nids-control!')
    print('[✓] Bão DDoS đang hoạt động cùng Port Scan tàng hình trong 30 giây.')
except Exception as e:
    print(f'[✗] Lỗi kết nối Kafka điều khiển: {e}')
"
    echo -e "\n${CYAN}[→] Mời hội đồng nhìn lên Dashboard để quan sát AI bóc tách đồng thời 2 đòn tấn công!${NC}"
    read -p "Bấm [Enter] để quay lại Menu..."
}

# ── KỊCH BẢN 2: QR CODE DEMO (HỘI ĐỒNG TỰ HACK) ──────────────────────────────
run_scenario_2_qr_demo() {
    echo -e "\n${MAGENTA}${BOLD}[!] KHỞI ĐỘNG KỊCH BẢN 2: VŨ KHÍ TƯƠNG TÁC (QR CODE ATTACK)${NC}"
    echo -e "    Khởi chạy Attack API trên cổng 5000..."
    
    if [ -f "attack_api.py" ]; then
        $PY attack_api.py &
        API_PID=$!
        echo -e "${GREEN}[✓] Attack API đang chạy tại http://0.0.0.0:5000 (PID: $API_PID)${NC}"
        echo -e "${YELLOW}[→] Để điện thoại quét được từ xa, mở terminal mới và chạy: ngrok http 5000${NC}"
    elif [ -f "tv3/qr_attack_app.py" ]; then
        $ST run tv3/qr_attack_app.py --server.port 8502 --server.address 0.0.0.0 &
        echo -e "${GREEN}[✓] Streamlit QR Attack App đang chạy tại http://0.0.0.0:8502${NC}"
    else
        echo -e "${RED}[✗] Không tìm thấy file attack_api.py hoặc tv3/qr_attack_app.py${NC}"
    fi
    echo ""
    read -p "Bấm [Enter] để quay lại Menu..."
}

# ── KỊCH BẢN 3: TEST BẮN CẢNH BÁO AMAZON SNS ─────────────────────────────────
run_scenario_3_sns_test() {
    echo -e "\n${YELLOW}${BOLD}[!] KÍCH HOẠT KỊCH BẢN 3: 'GIÁM SÁT KHÔNG CHẠM' (AMAZON SNS)${NC}"
    echo -e "    Bắn 1 cảnh báo khẩn cấp từ AWS SNS về điện thoại/email người quản trị..."
    
    $PY -c "
import os, boto3
from datetime import datetime

arn = os.getenv('SNS_TOPIC_ARN', 'arn:aws:sns:us-east-1:400131408828:NIDS-Alerts')
region = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
now = datetime.now().strftime('%H:%M:%S ngày %d/%m/%Y')

msg = f'''[NIDS SECURITY ALERT]
⚠️ PHÁT HIỆN TẤN CÔNG XÂM NHẬP MẠNG!
- Loại tấn công : DDoS Flood + Stealth Port Scan
- IP Nguồn      : 45.33.12.19 (Singapore)
- Cổng mục tiêu : 22 (SSH), 3389 (RDP)
- Thời gian     : {now}
- Trạng thái    : Đã tự động cách ly bởi AWS NIDS AI.
'''

try:
    sns = boto3.client('sns', region_name=region)
    res = sns.publish(
        TopicArn=arn,
        Subject='[NIDS ALERT] Phát hiện xâm nhập mạng!',
        Message=msg
    )
    print(f'[✓] GỬI SNS THÀNH CÔNG! MessageId: {res.get(\"MessageId\")}')
    print('    👉 Hãy kiểm tra điện thoại/đồng hồ thông minh nhận tin nhắn ngay bây giờ!')
except Exception as e:
    print(f'[✗] Không gửi được SNS: {e}')
"
    echo ""
    read -p "Bấm [Enter] để quay lại Menu..."
}

# ── DỪNG CÁC TIẾN TRÌNH DEMO ──────────────────────────────────────────────────
stop_all_demo() {
    echo -e "\n${YELLOW}[*] Đang dừng tất cả các tiến trình Demo...${NC}"
    tmux kill-session -t "nids-matrix" 2>/dev/null || true
    pkill -f "tv3/producer.py" 2>/dev/null || true
    pkill -f "producer.py" 2>/dev/null || true
    pkill -f "tv3/consumer_tv3.py" 2>/dev/null || true
    pkill -f "consumer_ids.py" 2>/dev/null || true
    pkill -f "attack_api.py" 2>/dev/null || true
    pkill -f "streamlit" 2>/dev/null || true
    echo -e "${GREEN}[✓] Đã dừng toàn bộ tiến trình Demo an toàn.${NC}"
    sleep 1
}

# ── VÒNG LẶP MENU ĐIỀU KHIỂN CHÍNH ───────────────────────────────────────────
while true; do
    show_banner
    echo -e "  ${BOLD}DANH SÁCH CÁC KỊCH BẢN TRÌNH DIỄN (WOW-FACTOR):${NC}"
    echo ""
    echo -e "  ${GREEN}[1] 🚀 KỊCH BẢN 4: 'Dòng chảy Hệ sinh thái' (Split Screen 4 Màn hình - Matrix)${NC}"
    echo -e "      ${CYAN}Màn 1: Data Producer | Màn 2: Kafka Broker | Màn 3: AI Consumer | Màn 4: Dashboard SOC${NC}"
    echo ""
    echo -e "  ${RED}[2] 🌪️ KỊCH BẢN 1: 'Khói mù và Dao găm' (Multi-Vector: DDoS + Port Scan lén lút)${NC}"
    echo ""
    echo -e "  ${MAGENTA}[3] 📱 KỊCH BẢN 2: 'Vũ khí Tương tác' (Hội đồng tự hack qua mã QR Code)${NC}"
    echo ""
    echo -e "  ${YELLOW}[4] 📲 KỊCH BẢN 3: 'Giám sát Không chạm' (Kích hoạt báo động qua AWS SNS)${NC}"
    echo ""
    echo -e "  ${BLUE}[5] 🛑 Dừng toàn bộ tiến trình Demo${NC}"
    echo -e "  ${NC}[0] Thoát ra Terminal"
    echo ""
    read -p "  👉 Chọn kịch bản bạn muốn kích hoạt [0-5]: " choice

    case "$choice" in
        1) run_scenario_4_splitscreen ;;
        2) run_scenario_1_multivector ;;
        3) run_scenario_2_qr_demo ;;
        4) run_scenario_3_sns_test ;;
        5) stop_all_demo ;;
        0) echo -e "\n${GREEN}[✓] Tạm biệt! Chúc nhóm bảo vệ thành công!${NC}\n"; exit 0 ;;
        *) echo -e "\n${RED}[!] Lựa chọn không hợp lệ. Vui lòng thử lại.${NC}"; sleep 1 ;;
    esac
done
