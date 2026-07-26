#!/usr/bin/env bash
# Peekabot one-line installer for Raspberry Pi OS (Trixie, 64-bit).
#
#   curl -fsSL https://raw.githubusercontent.com/sarthakgarg814/Peekabot/main/install.sh | bash
#
# Installs everything: system deps, Redis, camera/opencv, GPIO libs, clones the
# repo, builds the dashboard, creates the three service venvs, enables hardware
# PWM, and installs+starts the core/vision/hardware systemd services.
# Idempotent — safe to re-run to update.
set -euo pipefail

REPO_URL="${DESKBOT_REPO:-https://github.com/sarthakgarg814/Peekabot.git}"
BRANCH="${DESKBOT_BRANCH:-main}"
DIR="${DESKBOT_DIR:-$HOME/peekabot}"
USER_NAME="$(id -un)"

log() { printf "\n\033[1;36m==> %s\033[0m\n" "$*"; }

log "Peekabot installer  (user=$USER_NAME  dir=$DIR)"

log "System packages"
sudo apt-get update -qq
sudo apt-get install -y git curl python3-venv python3-lgpio i2c-tools redis-server \
  python3-picamera2 python3-opencv python3-gpiozero nodejs npm
sudo systemctl enable --now redis-server

log "Enabling I2C / SPI / camera"
sudo raspi-config nonint do_i2c 0 || true
sudo raspi-config nonint do_spi 0 || true
sudo raspi-config nonint do_camera 0 || true

log "Fetching Peekabot"
if [ -d "$DIR/.git" ]; then
  git -C "$DIR" fetch --depth 1 origin "$BRANCH" && git -C "$DIR" reset --hard "origin/$BRANCH"
else
  git clone --depth 1 -b "$BRANCH" "$REPO_URL" "$DIR"
fi
cd "$DIR"

log "ML models (YuNet)"
./scripts/fetch-models.sh || true

log "Building the dashboard"
( cd frontend && npm install --no-audit --no-fund --silent && npm run build )

log "Core venv"
python3 -m venv backend/.venv
backend/.venv/bin/pip install -q -U pip
backend/.venv/bin/pip install -q -e "backend[dev,calendar]"

log "Vision venv (system-site: picamera2 + opencv)"
python3 -m venv --system-site-packages backend/.venv-vision
backend/.venv-vision/bin/pip install -q -U pip
backend/.venv-vision/bin/pip install -q -e backend

log "Hardware venv (system-site: gpiozero/lgpio)"
python3 -m venv --system-site-packages backend/.venv-hardware
backend/.venv-hardware/bin/pip install -q -U pip
backend/.venv-hardware/bin/pip install -q -e backend rpi-hardware-pwm luma.oled

log "Per-machine config: redis bus + real hardware"
mkdir -p config
cat > config/local.yaml <<YAML
runtime:
  bus_backend: redis
  hardware_backend: real
YAML

log "Hardware-PWM overlay (GPIO 12/13)"
CONFIG_TXT=/boot/firmware/config.txt
[ -f "$CONFIG_TXT" ] || CONFIG_TXT=/boot/config.txt
OVERLAY="dtoverlay=pwm-2chan,pin=12,func=4,pin2=13,func2=4"
if ! grep -qF "$OVERLAY" "$CONFIG_TXT"; then
  echo "$OVERLAY" | sudo tee -a "$CONFIG_TXT" >/dev/null
  NEED_REBOOT=1
fi

log "systemd services"
sudo tee /etc/systemd/system/peekabot-core.service >/dev/null <<UNIT
[Unit]
Description=Peekabot core (API + dashboard)
After=network-online.target redis-server.service
Wants=redis-server.service network-online.target
[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$DIR/backend
ExecStart=$DIR/backend/.venv/bin/uvicorn core.main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=3
[Install]
WantedBy=multi-user.target
UNIT

for svc in vision hardware; do
  venv=".venv-$svc"
  sudo tee /etc/systemd/system/peekabot-$svc.service >/dev/null <<UNIT
[Unit]
Description=Peekabot $svc
After=network-online.target redis-server.service
Wants=redis-server.service
[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$DIR/backend
ExecStart=$DIR/backend/$venv/bin/python -m $svc.service
Restart=on-failure
RestartSec=3
[Install]
WantedBy=multi-user.target
UNIT
done

sudo systemctl daemon-reload
sudo systemctl enable peekabot-core peekabot-vision peekabot-hardware
sudo systemctl restart peekabot-core peekabot-vision peekabot-hardware || true

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
cat <<EOF

============================================================
  Peekabot is installed and running.
  Dashboard:  http://$(hostname).local:8000   (or http://${IP:-<pi-ip>}:8000)
  Login password:  peekabot   (change it under Account)
============================================================
EOF
[ "${NEED_REBOOT:-0}" = 1 ] && echo "  *** REBOOT REQUIRED for hardware PWM + camera:  sudo reboot ***"
