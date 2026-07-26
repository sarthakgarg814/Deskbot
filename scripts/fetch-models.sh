#!/usr/bin/env bash
# Download the ML model files DeskBot needs into models/ (gitignored).
# Run on whichever machine will run the vision service (the Pi, and/or your Mac
# for local detector testing).
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODELS="$REPO_DIR/models"
mkdir -p "$MODELS"

# YuNet face detector (OpenCV Zoo) — ~350 KB, used by backend/vision/detector.py
YUNET="face_detection_yunet_2023mar.onnx"
YUNET_URL="https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/${YUNET}"

if [ -f "$MODELS/$YUNET" ]; then
  echo "==> $YUNET already present"
else
  echo "==> downloading $YUNET"
  curl -fL "$YUNET_URL" -o "$MODELS/$YUNET"
fi

echo "==> models in $MODELS:"
ls -lh "$MODELS"
