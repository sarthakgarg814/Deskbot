"""Face detection via OpenCV YuNet (design decision D9).

YuNet is a small (~350 KB) ONNX face detector bundled with OpenCV's model zoo.
Runs on CPU on the Pi, installs cleanly on Python 3.13 (unlike MediaPipe). Kept
behind the `FaceDetector` interface so it can be swapped later.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

log = logging.getLogger("deskbot.vision.detector")

# Repo-root/models/… (models/ is gitignored; fetched by scripts/fetch-models.sh)
MODELS_DIR = Path(__file__).resolve().parents[2] / "models"
YUNET_MODEL = MODELS_DIR / "face_detection_yunet_2023mar.onnx"


@dataclass
class Face:
    x: int
    y: int
    w: int
    h: int
    score: float
    # center of the face in normalized [0,1] frame coords
    cx: float
    cy: float
    # error from frame center in [-1,1] (0 = centered). Drives the servo target.
    err_x: float
    err_y: float


class FaceDetector(Protocol):
    def detect(self, frame: np.ndarray) -> list[Face]: ...


class YuNetDetector:
    def __init__(self, model_path: Path = YUNET_MODEL, score_threshold: float = 0.7) -> None:
        import cv2

        if not model_path.exists():
            raise FileNotFoundError(
                f"YuNet model not found at {model_path}. Run scripts/fetch-models.sh."
            )
        # input size is set per-frame in detect(); start with a placeholder
        self._det = cv2.FaceDetectorYN.create(
            str(model_path), "", (320, 320), score_threshold, 0.3, 5000
        )
        self._size: tuple[int, int] | None = None
        log.info("YuNet loaded (score_threshold=%.2f)", score_threshold)

    def detect(self, frame: np.ndarray) -> list[Face]:
        h, w = frame.shape[:2]
        if self._size != (w, h):
            self._det.setInputSize((w, h))
            self._size = (w, h)

        _, faces = self._det.detect(frame)
        if faces is None:
            return []

        out: list[Face] = []
        for f in faces:
            fx, fy, fw, fh = (int(v) for v in f[:4])
            score = float(f[-1])
            cx = (fx + fw / 2) / w
            cy = (fy + fh / 2) / h
            out.append(
                Face(
                    x=fx, y=fy, w=fw, h=fh, score=score,
                    cx=cx, cy=cy,
                    err_x=(cx - 0.5) * 2,   # -1 (left) … +1 (right)
                    err_y=(cy - 0.5) * 2,   # -1 (top)  … +1 (bottom)
                )
            )
        # largest face first (closest / primary subject)
        out.sort(key=lambda f: f.w * f.h, reverse=True)
        return out
