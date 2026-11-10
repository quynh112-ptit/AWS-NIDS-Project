#!/usr/bin/env bash
# ==============================================================================
# AWS NIDS - MASTER DEMO LAUNCHER (run_demo.sh)
# Hỗ trợ đầy đủ các Kịch bản Trình diễn (Wow-Factor):
#   Kịch bản 1: 🟢 Lưu lượng Mạng Bình thường (Normal Traffic)
#   Kịch bản 2: 🔴 Bão DDoS Cực Đại (DDoS Attack - Tự động bắn Email SNS)
#   Kịch bản 3: ⚔️ "Khói mù và Dao găm" (Multi-Vector Attack - Tự động bắn Email SNS)
#   Kịch bản 4: 🚀 'Dòng chảy Hệ sinh thái' (Split Screen 4 Màn hình - Matrix Showcase)
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
    echo "  ║      Trung tâm Điều hành & Phòng thủ An ninh mạng AWS EC2     ║"
    echo "  ╚═══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo -e "  ${YELLOW}Kafka Broker  :${NC} $KAFKA_SERVER"
    echo -e "  ${YELLOW}PostgreSQL    :${NC} $NIDS_DSN"
    echo -e "  ${YELLOW}SNS Alert ARN :${NC} $SNS_TOPIC_ARN"
    echo -e "  ${GREEN}Web Dashboard :${NC} Đang mở sẵn trên Trình duyệt để Hội đồng xem trực tiếp"
    echo "  ───────────────────────────────────────────────────────────────"
}

# ── ĐẢM BẢO SERVICES ĐANG CHẠY TRÊN HỆ THỐNG ──────────────────────────────────
ensure_pipeline_running() {
    # 1. Đảm bảo Docker Kafka & Postgres chạy
    if ! docker ps | grep -q "aws-nids-project-kafka-1.*Up"; then
        echo -e "${YELLOW}[*] Khởi động Docker containers (Kafka, Postgres)...${NC}"
        docker compose up -d
        sleep 5
    fi

    # 2. Đảm bảo Consumer đang chạy để phân loại và tự động bắn SNS
    if ! pgrep -f "consumer_ids.py" >/dev/null 2>&1 && ! pgrep -f "consumer_tv3.py" >/dev/null 2>&1; then
        echo -e "${YELLOW}[*] Khởi chạy AI Consumer ngầm (sẵn sàng tự động gửi SNS khi có tấn công)...${NC}"
        if [ -f "tv3/consumer_tv3.py" ]; then
            nohup $PY -u tv3/consumer_tv3.py > /tmp/consumer.log 2>&1 &
        else
            nohup $PY -u consumer_ids.py > /tmp/consumer.log 2>&1 &
        fi
        sleep 2
    fi

    # 3. Đảm bảo Producer đang chạy
    if ! pgrep -f "producer.py" >/dev/null 2>&1; then
        echo -e "${YELLOW}[*] Khởi chạy Data Producer ngầm...${NC}"
        if [ -f "producer.py" ]; then
            nohup $PY -u producer.py > /tmp/producer.log 2>&1 &
        elif [ -f "tv3/producer.py" ]; then
            nohup $PY -u tv3/producer.py > /tmp/producer.log 2>&1 &
        fi
        sleep 2
    fi
}

# ── KỊCH BẢN 1: MẠNG BÌNH THƯỜNG (NORMAL TRAFFIC) ────────────────────────────
run_scenario_normal() {
    ensure_pipeline_running
    echo -e "\n${GREEN}${BOLD}[!] KÍCH HOẠT KỊCH BẢN 1: 'MẠNG BÌNH THƯỜNG'${NC}"
    echo -e "    Bơm luồng traffic web thông thường (~150 gói/giây)..."
    
    $PY -c "
import os, json
from kafka import KafkaProducer
kafka_server = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
try:
    producer = KafkaProducer(
        bootstrap_servers=[kafka_server],
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
    cmd = {'scenario': 'normal', 'target_eps': 150, 'duration_sec': 120}
    producer.send('nids-control', cmd)
    producer.flush()
    print('[✓] Đã kích hoạt chế độ: NORMAL TRAFFIC')
except Exception as e:
    print(f'[✗] Lỗi kết nối Kafka điều khiển: {e}')
"
    echo ""
    echo -e "${GREEN}👉 TRÊN DASHBOARD:${NC} Biểu đồ lưu lượng màu xanh ổn định ở mức ~150 gói/giây."
    echo -e "${GREEN}👉 TRẠNG THÁI     :${NC} AN TOÀN (Safe). Không có cảnh báo email nào được gửi."
    echo ""
    read -p "Bấm [Enter] để quay lại Menu..."
}

# ── KỊCH BẢN 2: BÃO DDOS (DDOS FLOOD ATTACK) ─────────────────────────────────
run_scenario_ddos() {
    ensure_pipeline_running
    echo -e "\n${RED}${BOLD}[!] KÍCH HOẠT KỊCH BẢN 2: 'BÃO DDoS CƯỜNG ĐỘ CAO'${NC}"
    echo -e "    Nhồi lưu lượng DDoS cực đại (~8.000 gói/giây) vào Apache Kafka..."
    
    $PY -c "
import os, json
from kafka import KafkaProducer
kafka_server = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
try:
    producer = KafkaProducer(
        bootstrap_servers=[kafka_server],
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
    cmd = {'scenario': 'ddos', 'target_eps': 8000, 'duration_sec': 60}
    producer.send('nids-control', cmd)
    producer.flush()
    print('[✓] Đã kích hoạt chế độ: DDoS FLOOD ATTACK (8.000 EPS)')
except Exception as e:
    print(f'[✗] Lỗi kết nối Kafka điều khiển: {e}')
"
    echo ""
    echo -e "${YELLOW}👉 TRÊN DASHBOARD :${NC} Cột lưu lượng giật dựng đứng lên hàng ngàn gói/giây, đổi màu đỏ rực!"
    echo -e "${CYAN}👉 TRÊN KAFKA     :${NC} Kafka gánh tải hàng ngàn gói/giây mượt mà, hệ thống KHÔNG hề bị sập!"
    echo -e "${MAGENTA}👉 TỰ ĐỘNG BẮN SNS:${NC} AI Consumer phát hiện DDoS -> \033[1;33mTỰ ĐỘNG BẮN EMAIL CẢNH BÁO VỀ ĐIỆN THOẠI/HÒM THƯ!\033[0m"
    echo ""
    echo -e "${BOLD}📲 HÃY KIỂM TRA ĐIỆN THOẠI / HÒM THƯ NGAY BÂY GIỜ ĐỂ XEM EMAIL CẢNH BÁO TỰ ĐỘNG!${NC}"
    echo ""
    read -p "Bấm [Enter] để quay lại Menu..."
}

# ── KỊCH BẢN 3: "KHÓI MÙ VÀ DAO GĂM" (MULTI-VECTOR ATTACK) ───────────────────
run_scenario_multivector() {
    ensure_pipeline_running
    echo -e "\n${RED}${BOLD}[!] KÍCH HOẠT KỊCH BẢN 3: 'KHÓI MÙ VÀ DAO GĂM' (MULTI-VECTOR ATTACK)${NC}"
    echo -e "    - Khói mù: Bão DDoS ập tới (8.000 gói/giây đánh lạc hướng tường lửa)"
    echo -e "    - Dao găm: 1 IP Singapore (45.33.12.19) lén lút quét cổng SSH (22), RDP (3389)..."
    
    $PY -c "
import os, json
from kafka import KafkaProducer
kafka_server = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
try:
    producer = KafkaProducer(
        bootstrap_servers=[kafka_server],
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
    cmd = {'scenario': 'ddos_portscan', 'target_eps': 8000, 'duration_sec': 60}
    producer.send('nids-control', cmd)
    producer.flush()
    print('[✓] Đã kích hoạt chế độ: MULTI-VECTOR ATTACK (DDoS + Port Scan)')
except Exception as e:
    print(f'[✗] Lỗi kết nối Kafka điều khiển: {e}')
"
    echo ""
    echo -e "${YELLOW}👉 TRÊN DASHBOARD :${NC} Giữa tâm bão DDoS, AI bóc tách chính xác IP 45.33.12.19 đang dò cổng lén lút!"
    echo -e "${MAGENTA}👉 TỰ ĐỘNG BẮN SNS:${NC} AI Consumer phân loại Port Scan -> \033[1;33mTỰ ĐỘNG BẮN EMAIL BÁO CÁO ĐÍCH DANH IP VỪA DÒ CỔNG!\033[0m"
    echo ""
    echo -e "${BOLD}📲 HÃY MỞ ĐIỆN THOẠI VÀ ĐỌC TO THÔNG BÁO EMAIL CẢNH BÁO TRƯỚC HỘI ĐỒNG!${NC}"
    echo ""
    read -p "Bấm [Enter] để quay lại Menu..."
}

# ── KỊCH BẢN 4: CHIA 4 MÀN HÌNH SPLIT-SCREEN (THE MATRIX SHOWCASE) ───────────
run_scenario_splitscreen() {
    echo -e "\n${GREEN}[*] Đang khởi tạo Kịch bản 4: 'Dòng chảy Hệ sinh thái' (Split Screen 4 Màn hình)...${NC}"

    # Đảm bảo cụm Docker chạy
    if ! docker ps | grep -q "aws-nids-project-kafka-1.*Up"; then
        docker compose up -d
        sleep 5
    fi

    if ! command -v tmux >/dev/null 2>&1; then
        echo -e "${YELLOW}[!] Tmux chưa được cài đặt. Đang tự động cài đặt tmux...${NC}"
        sudo apt-get update -y && sudo apt-get install -y tmux
    fi

    SESSION="nids-matrix"
    echo ""
    echo -e "  ${BOLD}BẠN MUỐN CHẠY KỊCH BẢN 4 THEO CÁCH NÀO?${NC}"
    echo -e "  ${CYAN}[1] Mở xem trực tiếp 4 màn hình${NC} (Phô diễn Matrix, bấm ${YELLOW}Ctrl+Q${NC} hoặc ${YELLOW}F12${NC} để thoát về menu)"
    echo -e "  ${GREEN}[2] Chạy ngầm toàn bộ trong nền${NC} (Không chiếm terminal)"
    read -p "  👉 Lựa chọn [1-2] (Mặc định: 1): " mode_choice
    mode_choice="${mode_choice:-1}"

    tmux kill-session -t "$SESSION" 2>/dev/null || true

    tmux new-session -d -s "$SESSION" -x 160 -y 48
    tmux rename-window -t "$SESSION:0" "AWS-NIDS-SOC"
    tmux split-window -v -t "$SESSION:0"
    tmux split-window -h -t "$SESSION:0.0"
    tmux split-window -h -t "$SESSION:0.2"

    tmux send-keys -t "$SESSION:0.0" "clear; echo -e '\033[1;36m=== [1/4] DATA PRODUCER (LƯU LƯỢNG NETFLOW) ===\033[0m'; cd $ROOT_DIR && $PY -u producer.py || $PY -u tv3/producer.py" C-m
    tmux send-keys -t "$SESSION:0.1" "clear; echo -e '\033[1;33m=== [2/4] APACHE KAFKA (TRÁI TIM ĐỆM DỮ LIỆU) ===\033[0m'; docker logs -f --tail 40 aws-nids-project-kafka-1 2>/dev/null" C-m
    tmux send-keys -t "$SESSION:0.2" "clear; echo -e '\033[1;32m=== [3/4] AI ML CONSUMER (PHÂN TÍCH & AUTO SNS) ===\033[0m'; cd $ROOT_DIR && $PY -u consumer_ids.py || $PY -u tv3/consumer_tv3.py" C-m
    tmux send-keys -t "$SESSION:0.3" "clear; echo -e '\033[1;35m=== [4/4] STREAMLIT DASHBOARD SOC ===\033[0m'; cd $ROOT_DIR && $ST run tv3/dashboard.py --server.port 8501 --server.address 0.0.0.0 2>/dev/null || $ST run dashboard.py --server.port 8501 --server.address 0.0.0.0" C-m

    tmux bind-key -n C-q detach-client
    tmux bind-key -n F12 detach-client
    tmux bind-key -n C-x kill-session

    if [ "$mode_choice" = "2" ]; then
        echo -e "\n${GREEN}[✓] Đã khởi chạy 4 dịch vụ ngầm trong nền!${NC}"
        read -p "Bấm [Enter] để quay lại Menu..."
    else
        echo -e "\n${GREEN}[✓] Đang chuyển vào màn hình Matrix. Bấm Ctrl+Q hoặc F12 để thoát xem.${NC}"
        sleep 2
        tmux attach-session -t "$SESSION"
    fi
}

# ── DỪNG CÁC TIẾN TRÌNH DEMO ──────────────────────────────────────────────────
stop_all_demo() {
    echo -e "\n${YELLOW}[*] Đang dừng tất cả các tiến trình Demo...${NC}"
    tmux kill-session -t "nids-matrix" 2>/dev/null || true
    pkill -f "producer.py" 2>/dev/null || true
    pkill -f "consumer_ids.py" 2>/dev/null || true
    pkill -f "consumer_tv3.py" 2>/dev/null || true
    pkill -f "streamlit" 2>/dev/null || true
    echo -e "${GREEN}[✓] Đã dừng toàn bộ tiến trình Demo an toàn.${NC}"
    sleep 1
}

# ── VÒNG LẶP MENU ĐIỀU KHIỂN CHÍNH ───────────────────────────────────────────
while true; do
    show_banner
    echo -e "  ${BOLD}DANH SÁCH CÁC KỊCH BẢN TRÌNH DIỄN (WOW-FACTOR):${NC}"
    echo ""
    echo -e "  ${GREEN}[1] 🟢 KỊCH BẢN 1: Mạng Bình thường (Normal Traffic - Êm ả, an toàn)${NC}"
    echo ""
    echo -e "  ${RED}[2] 🔴 KỊCH BẢN 2: Bão DDoS Cực Đại (DDoS Surge -> \033[1;33mTỰ ĐỘNG BẮN EMAIL SNS\033[0m${RED})${NC}"
    echo ""
    echo -e "  ${MAGENTA}[3] ⚔️ KỊCH BẢN 3: 'Khói mù và Dao găm' (Multi-Vector -> \033[1;33mTỰ ĐỘNG BẮN EMAIL BẮT PORT SCAN\033[0m${MAGENTA})${NC}"
    echo ""
    echo -e "  ${CYAN}[4] 🚀 KỊCH BẢN 4: 'Dòng chảy Hệ sinh thái' (Split Screen 4 Màn hình - Matrix)${NC}"
    echo ""
    echo -e "  ${BLUE}[5] 🛑 Dừng toàn bộ tiến trình Demo${NC}"
    echo -e "  ${NC}[0] Thoát ra Terminal"
    echo ""
    read -p "  👉 Chọn kịch bản bạn muốn kích hoạt [0-5]: " choice

    case "$choice" in
        1) run_scenario_normal ;;
        2) run_scenario_ddos ;;
        3) run_scenario_multivector ;;
        4) run_scenario_splitscreen ;;
        5) stop_all_demo ;;
        0) echo -e "\n${GREEN}[✓] Tạm biệt! Chúc nhóm bảo vệ thành công!${NC}\n"; exit 0 ;;
        *) echo -e "\n${RED}[!] Lựa chọn không hợp lệ. Vui lòng thử lại.${NC}"; sleep 1 ;;
    esac
done
