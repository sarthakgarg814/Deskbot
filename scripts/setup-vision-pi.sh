#!/usr/bin/env bash
# Enable the vision service on the Pi (Milestone 2b): Redis bus + camera/opencv
# system packages + a vision venv + the deskbot-vision systemd service, and flip
# core over to the Redis bus. RUN ON THE PI after ./scripts/setup-pi.sh.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_USER="$(id -un)"
CORE_VENV="$REPO_DIR/backend/.venv"
VISION_VENV="$REPO_DIR/backend/.venv-vision"

echo "==> repo: $REPO_DIR  user: $RUN_USER"

echo "==> apt: redis + camera + opencv"
sudo apt-get update -qq
sudo apt-get install -y redis-server python3-picamera2 python3-opencv
sudo systemctl enable --now redis-server

echo "==> models"
[ -f "$REPO_DIR/models/face_detection_yunet_2023mar.onnx" ] || "$REPO_DIR/scripts/fetch-models.sh"

echo "==> per-machine config: bus_backend=redis (config/local.yaml)"
mkdir -p "$REPO_DIR/config"
cat > "$REPO_DIR/config/local.yaml" <<YAML
# Per-machine overrides for THIS Pi (gitignored, not rsynced).
runtime:
  bus_backend: redis
YAML

echo "==> core venv: ensure redis-py present"
"$CORE_VENV/bin/pip" install -q redis

echo "==> vision venv (--system-site-packages so it sees picamera2 + opencv)"
python3 -m venv --system-site-packages "$VISION_VENV"
"$VISION_VENV/bin/pip" install -q --upgrade pip
"$VISION_VENV/bin/pip" install -q -e "$REPO_DIR/backend"

echo "==> quick import check (cv2 + picamera2 + our packages)"
"$VISION_VENV/bin/python" - <<'PY'
import cv2, numpy  # from system site-packages
from vision.detector import YuNetDetector
from common.bus import make_publisher
print("vision imports OK — opencv", cv2.__version__)
PY

echo "==> systemd unit: deskbot-vision.service"
sudo tee /etc/systemd/system/deskbot-vision.service >/dev/null <<UNIT
[Unit]
Description=DeskBot vision (camera + face detection)
After=network-online.target redis-server.service
Wants=redis-server.service

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$REPO_DIR/backend
ExecStart=$VISION_VENV/bin/python -m vision.service
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable --now deskbot-vision.service
echo "==> restarting core so it picks up the Redis bus"
sudo systemctl restart deskbot-core.service
sleep 2
sudo systemctl --no-pager --lines=0 status deskbot-vision.service || true

cat <<EOF

==> Vision service enabled.
    Dashboard Camera page:  http://deskbot.local:8000/camera
    Vision logs:  journalctl -u deskbot-vision -f
    Core logs:    journalctl -u deskbot-core -f
EOF
