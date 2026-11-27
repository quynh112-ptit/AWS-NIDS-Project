#!/bin/bash
# ============================================================
# Cài Consumer / Dashboard / Web QR thành dịch vụ systemd trên EC2
# → tự chạy khi EC2 khởi động lại, tự restart khi lỗi (khôi phục dịch vụ)
#   sudo bash scripts/install_services.sh
# ============================================================
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_USER="${SUDO_USER:-ubuntu}"
if [ -x "$ROOT_DIR/.venv/bin/python" ]; then PY="$ROOT_DIR/.venv/bin/python";
elif [ -x "$ROOT_DIR/venv/bin/python" ]; then PY="$ROOT_DIR/venv/bin/python";
else PY="$(command -v python3)"; fi

for unit in nids-consumer nids-dashboard nids-qr; do
    sed -e "s|__ROOT__|$ROOT_DIR|g" -e "s|__USER__|$RUN_USER|g" -e "s|__PY__|$PY|g" \
        "$ROOT_DIR/deploy/systemd/$unit.service" > "/etc/systemd/system/$unit.service"
    echo "[✓] /etc/systemd/system/$unit.service"
done
systemctl daemon-reload
systemctl enable --now nids-consumer nids-dashboard nids-qr
systemctl --no-pager status nids-consumer nids-dashboard nids-qr | grep -E '●|Active'
echo "[✓] Đã cài dịch vụ. Xem log: journalctl -u nids-consumer -f"
