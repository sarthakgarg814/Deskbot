"""The vision service — long-running capture+detect loop that publishes to the bus.

Run as its own process (systemd on the Pi):
    python -m vision.service

Publishes:
  state:camera   (cache)   latest {running,fps,detect_ms,present,face,faces}
  camera         (pub/sub) same payload, throttled ~6 Hz, for the dashboard WS
  presence       (pub/sub) {state} on change (present/away)
  cmd.servo.target (pub/sub) {owner,mode,pan,tilt,ttl_ms} — consumed by the servo
                   arbiter once hardware lands; harmless to publish now.

Uses the sync Publisher (Redis on the Pi, or a logging no-op for laptop dev).
"""
from __future__ import annotations

import argparse
import logging
import time

from common.bus import make_publisher
from common.config import load_config
from common.logging import setup_logging

from .camera import open_camera
from .detector import YuNetDetector

log = logging.getLogger("deskbot.vision.service")

AWAY_AFTER_S = 8.0          # no face this long → presence "away"
PUBLISH_HZ = 6.0            # throttle camera-status pushes to the dashboard
TARGET_TTL_MS = 400         # servo target self-expires if vision stalls/dies


def run(source: str, detect_width: int, width: int, height: int) -> None:
    cfg = load_config()
    pub = make_publisher(cfg.bus_backend, cfg.redis_url)
    log.info("vision service starting (bus=%s, source=%s)", cfg.bus_backend, source)

    if source == "auto":
        cam = open_camera("auto", width=width, height=height)
    else:
        src: int | str = int(source) if source.isdigit() else source
        cam = open_camera("opencv", source=src, width=width, height=height)
    det = YuNetDetector(detect_width=detect_width)

    presence = "unknown"
    last_face_t = 0.0
    last_pub = 0.0
    ema_fps = 0.0
    t_prev = time.monotonic()

    try:
        for frame in cam.frames():
            t0 = time.monotonic()
            faces = det.detect(frame)
            detect_ms = (time.monotonic() - t0) * 1000

            # instantaneous FPS, smoothed
            dt = t0 - t_prev
            t_prev = t0
            if dt > 0:
                ema_fps = 0.9 * ema_fps + 0.1 * (1.0 / dt) if ema_fps else 1.0 / dt

            now = time.monotonic()
            face = faces[0] if faces else None
            if face:
                last_face_t = now
                # feed the (future) servo arbiter with the centering error
                pub.publish("cmd.servo.target", {
                    "owner": "face_tracking", "mode": "error",
                    "pan": face.err_x, "tilt": face.err_y, "ttl_ms": TARGET_TTL_MS,
                })

            # presence state machine
            new_presence = "present" if (now - last_face_t) < AWAY_AFTER_S else "away"
            if new_presence != presence:
                presence = new_presence
                pub.publish("presence", {"state": presence})
                pub.set_state("state:presence", {"state": presence})
                log.info("presence -> %s", presence)

            payload = {
                "running": True,
                "fps": round(ema_fps, 1),
                "detect_ms": round(detect_ms, 1),
                "present": presence == "present",
                "faces": len(faces),
                "face": None if not face else {
                    "cx": round(face.cx, 3), "cy": round(face.cy, 3),
                    "err_x": round(face.err_x, 3), "err_y": round(face.err_y, 3),
                    "score": round(face.score, 2),
                },
            }
            pub.set_state("state:camera", payload, ttl=5)

            # throttle the pub/sub push to the dashboard
            if now - last_pub >= 1.0 / PUBLISH_HZ:
                last_pub = now
                pub.publish("camera", payload)
    finally:
        cam.close()
        pub.set_state("state:camera", {"running": False}, ttl=5)
        log.info("vision service stopped")


def main() -> None:
    ap = argparse.ArgumentParser(prog="vision.service")
    ap.add_argument("--source", default="auto")
    ap.add_argument("--detect-width", type=int, default=320)
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--height", type=int, default=480)
    args = ap.parse_args()

    setup_logging("INFO", "deskbot.vision")
    run(args.source, args.detect_width, args.width, args.height)


if __name__ == "__main__":
    main()
