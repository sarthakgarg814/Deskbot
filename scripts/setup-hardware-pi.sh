#!/usr/bin/env bash
# Enable the hardware (servo) service on the Pi. RUN ON THE PI after setup-pi.sh
# and setup-vision-pi.sh. Installs gpiozero/lgpio, builds a hardware venv, and
# runs the servo arbiter as a systemd service.
#
# By default it leaves hardware_backend as-is (mock) so you can verify the whole
# vision -> arbiter -> dashboard pipeline BEFORE wiring servos. Pass `--real` once
# the SG90s are wired to GPIO 12 (pan) / 13 (tilt) to drive real servos.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_USER="$(id -un)"
HW_VENV="$REPO_DIR/backend/.venv-hardware"
REAL=0
[ "${1:-}" = "--real" ] && REAL=1

echo "==> repo: $REPO_DIR  user: $RUN_USER  real_servos: $REAL"

echo "==> apt: gpiozero + lgpio"
sudo apt-get update -qq
sudo apt-get install -y python3-gpiozero python3-lgpio

echo "==> hardware venv (--system-site-packages for gpiozero/lgpio)"
python3 -m venv --system-site-packages "$HW_VENV"
"$HW_VENV/bin/pip" install -q --upgrade pip
"$HW_VENV/bin/pip" install -q -e "$REPO_DIR/backend"

"$HW_VENV/bin/python" - <<'PY'
from hardware.arbiter import ServoArbiter
from common.bus import make_subscriber
print("hardware imports OK")
PY

if [ "$REAL" = "1" ]; then
  echo "==> forcing hardware_backend: real in config/local.yaml"
  python3 - "$REPO_DIR/config/local.yaml" <<'PY'
import sys, pathlib, re
p = pathlib.Path(sys.argv[1]); p.parent.mkdir(exist_ok=True)
txt = p.read_text() if p.exists() else "runtime:\n"
if "runtime:" not in txt:
    txt += "runtime:\n"
if re.search(r"^\s*hardware_backend:.*$", txt, re.M):
    txt = re.sub(r"^\s*hardware_backend:.*$", "  hardware_backend: real", txt, flags=re.M)
else:
    txt = txt.replace("runtime:\n", "runtime:\n  hardware_backend: real\n", 1)
p.write_text(txt)
print("hardware_backend: real")
PY
fi

echo "==> systemd unit: deskbot-hardware.service"
sudo tee /etc/systemd/system/deskbot-hardware.service >/dev/null <<UNIT
[Unit]
Description=DeskBot hardware (servo arbiter + PID)
After=network-online.target redis-server.service
Wants=redis-server.service

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$REPO_DIR/backend
ExecStart=$HW_VENV/bin/python -m hardware.service
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable deskbot-hardware.service
sudo systemctl restart deskbot-hardware.service   # restart (enable --now no-ops if already running)
sudo systemctl restart deskbot-core.service       # pick up config/topic changes
sleep 2
sudo systemctl --no-pager --lines=0 status deskbot-hardware.service || true

cat <<EOF

==> Hardware service enabled ($([ "$REAL" = 1 ] && echo "REAL servos" || echo "mock — no wiring needed yet")).
    Watch the arbiter:  journalctl -u deskbot-hardware -f
    Dashboard Hardware page shows live pan/tilt; move your face and the
    'driver: face_tracking' position should track it.
    When servos are wired to GPIO 12/13:  ./scripts/setup-hardware-pi.sh --real
EOF
