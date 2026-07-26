#!/usr/bin/env bash
# Build the dashboard and copy Peekabot to the Raspberry Pi. RUN ON YOUR LAPTOP.
#
#   scripts/deploy-to-pi.sh [user@host]      (default: peekabot@peekabot.local)
#
# Builds frontend/dist locally (design decision D5 — never build on the Pi),
# then rsyncs the working tree (including the built dist) to ~/peekabot on the Pi.
# First time, follow up on the Pi with ./scripts/setup-pi.sh. After that, just
# re-run this and `sudo systemctl restart peekabot-core`.
set -euo pipefail

PI_HOST="${1:-peekabot@peekabot.local}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="peekabot"   # lands at ~/peekabot on the Pi

echo "==> building dashboard (vite build)"
( cd "$REPO_DIR/frontend" && npm run build )

echo "==> rsync -> $PI_HOST:~/$DEST/"
# --progress works on macOS's ancient built-in rsync 2.6.9 (unlike --info);
# timeouts + ssh keepalive so a bad connection fails fast instead of hanging.
# Tip: `brew install rsync` for a modern 3.x if you want nicer output.
rsync -az --delete --progress --timeout=60 \
  -e "ssh -o ConnectTimeout=15 -o ServerAliveInterval=15 -o ServerAliveCountMax=3" \
  --exclude '.git/' \
  --exclude 'backend/.venv/' \
  --exclude 'backend/.venv-vision/' \
  --exclude 'backend/.venv-hardware/' \
  --exclude 'frontend/node_modules/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude 'peekabot.db*' \
  --exclude 'models/' \
  --exclude 'config/local.yaml' \
  --exclude 'config/google/' \
  --exclude 'config/.session_secret' \
  "$REPO_DIR/" "$PI_HOST:~/$DEST/"

cat <<EOF

==> Copied to $PI_HOST:~/$DEST
    First time:   ssh $PI_HOST 'cd ~/$DEST && ./scripts/setup-pi.sh'
    Later deploys: re-run this script, then:
                   ssh $PI_HOST 'sudo systemctl restart peekabot-core'
EOF
