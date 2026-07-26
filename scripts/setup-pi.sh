#!/usr/bin/env bash
# Provision & run DeskBot Milestone 1 on a Raspberry Pi (OS Trixie / Debian 13).
# RUN ON THE PI, after the repo has been copied over (see deploy-to-pi.sh).
#
# Milestone 1 uses the MOCK hardware backend, so this installs only the base
# Python deps — no servo/LED/camera libraries yet. It creates a venv, runs the
# smoke tests, and installs a systemd service so core starts on boot.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_USER="$(id -un)"
VENV="$REPO_DIR/backend/.venv"
PY="$VENV/bin/python"

echo "==> DeskBot repo : $REPO_DIR"
echo "==> service user : $RUN_USER"

echo "==> apt deps (base tooling)"
sudo apt-get update -qq
sudo apt-get install -y python3-venv python3-lgpio i2c-tools

echo "==> python venv + backend (mock hardware, base deps)"
python3 -m venv "$VENV"
"$PY" -m pip install -q --upgrade pip
"$PY" -m pip install -q -e "$REPO_DIR/backend[dev]"

if [ ! -f "$REPO_DIR/frontend/dist/index.html" ]; then
  echo "!! frontend/dist is missing — run 'make frontend-build' on your laptop and"
  echo "   redeploy. The API will run, but the dashboard won't be served yet."
fi

echo "==> smoke test"
( cd "$REPO_DIR/backend" && "$PY" -m pytest -q ) || echo "!! tests failed (continuing to install service)"

echo "==> installing systemd unit: deskbot-core.service"
sudo tee /etc/systemd/system/deskbot-core.service >/dev/null <<UNIT
[Unit]
Description=DeskBot core (FastAPI API + dashboard)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$REPO_DIR/backend
ExecStart=$VENV/bin/uvicorn core.main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable --now deskbot-core.service
sleep 2
sudo systemctl --no-pager --lines=0 status deskbot-core.service || true

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
cat <<EOF

==> DeskBot core is running as a service.
    Dashboard:  http://deskbot.local:8000
                http://${IP:-<pi-ip>}:8000
    Logs:       journalctl -u deskbot-core -f
    Restart:    sudo systemctl restart deskbot-core
EOF
