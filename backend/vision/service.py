"""The vision service — long-running capture+detect loop that publishes to the bus.

Run as its own process (systemd on the Pi):
    python -m vision.service

CPU-streamlined: the loop is rate-capped (vision_track_fps when a face is present,
vision_idle_fps when away) so YuNet doesn't run flat-out, and it backs off hard
when nobody's there. The MJPEG preview only encodes JPEGs while enabled.

Publishes:
  state:camera   (cache)   latest {running,fps,detect_ms,present,face,faces}
  camera         (pub/sub) same payload, throttled, for the dashboard WS
  presence       (pub/sub) {state} on change (present/away)
  cmd.servo.target (pub/sub) {owner,mode,pan,tilt,ttl_ms} — consumed by the servo
                   arbiter once hardware lands; harmless to publish now.
Reads:
  state:camera.preview_enabled  gate flag core mirrors from the settings table.
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
from .preview import FramePreview, start_preview_server

log = logging.getLogger("deskbot.vision.service")

AWAY_AFTER_S = 8.0          # no face this long → presence "away"
PUBLISH_HZ = 6.0           # cap dashboard pushes + state writes
FLAG_POLL_S = 2.0          # how often to re-read the preview gate flag
TARGET_TTL_MS = 400        # servo target self-expires if vision stalls/dies
JPEG_QUALITY = 70


def run(source: str, width: int, height: int, detect_width: int | None = None) -> None:
    cfg = load_config()
    pub = make_publisher(cfg.bus_backend, cfg.redis_url)
    dw = detect_width or cfg.vision_detect_width
    track_dt = 1.0 / max(1, cfg.vision_track_fps)
    idle_dt = 1.0 / max(1, cfg.vision_idle_fps)
    log.info(
        "vision starting (bus=%s, source=%s, detect_width=%d, track=%dfps, idle=%dfps)",
        cfg.bus_backend, source, dw, cfg.vision_track_fps, cfg.vision_idle_fps,
    )

    if source == "auto":
        # cap the sensor a little above our processing rate for headroom
        cam = open_camera("auto", width=width, height=height, fps=cfg.vision_track_fps + 5)
    else:
        src: int | str = int(source) if source.isdigit() else source
        cam = open_camera("opencv", source=src, width=width, height=height)
    det = YuNetDetector(detect_width=dw)

    # privacy-gated MJPEG preview (off unless camera.preview_enabled is on).
    # Optional — a port conflict must never take down face tracking.
    preview = FramePreview()
    try:
        start_preview_server(preview, cfg.preview_port)
    except OSError as e:
        log.warning("preview server not started (%s) — tracking continues", e)

    presence = "unknown"
    last_face_t = 0.0
    last_pub = 0.0
    last_flag_check = 0.0
    ema_fps = 0.0
    t_prev = time.monotonic()

    try:
        for frame in cam.frames():
            loop_start = time.monotonic()
            faces = det.detect(frame)
            detect_ms = (time.monotonic() - loop_start) * 1000

            # smoothed processing FPS (actual loop cadence, post-cap)
            dt = loop_start - t_prev
            t_prev = loop_start
            if dt > 0:
                ema_fps = 0.9 * ema_fps + 0.1 * (1.0 / dt) if ema_fps else 1.0 / dt

            now = loop_start
            face = faces[0] if faces else None
            if face:
                last_face_t = now
                pub.publish("cmd.servo.target", {
                    "owner": "face_tracking", "mode": "error",
                    "pan": face.err_x, "tilt": face.err_y, "ttl_ms": TARGET_TTL_MS,
                })

            present = (now - last_face_t) < AWAY_AFTER_S
            new_presence = "present" if present else "away"
            if new_presence != presence:
                presence = new_presence
                pub.publish("presence", {"state": presence})
                pub.set_state("state:presence", {"state": presence})
                log.info("presence -> %s", presence)

            # throttled outward writes (state cache + dashboard push)
            if now - last_pub >= 1.0 / PUBLISH_HZ:
                last_pub = now
                payload = {
                    "running": True,
                    "fps": round(ema_fps, 1),
                    "detect_ms": round(detect_ms, 1),
                    "present": present,
                    "faces": len(faces),
                    "preview": preview.enabled,
                    "face": None if not face else {
                        "cx": round(face.cx, 3), "cy": round(face.cy, 3),
                        "err_x": round(face.err_x, 3), "err_y": round(face.err_y, 3),
                        "score": round(face.score, 2),
                    },
                }
                pub.set_state("state:camera", payload, ttl=5)
                pub.publish("camera", payload)

            # refresh live-tunable config (fps caps, detect size, preview) from the
            # settings the UI edits — core mirrors them to state:vision.config.
            if now - last_flag_check >= FLAG_POLL_S:
                last_flag_check = now
                vc = pub.get_state("state:vision.config")
                if isinstance(vc, dict):
                    track_dt = 1.0 / max(1, int(vc.get("track_fps", cfg.vision_track_fps)))
                    idle_dt = 1.0 / max(1, int(vc.get("idle_fps", cfg.vision_idle_fps)))
                    det.detect_width = int(vc.get("detect_width", det.detect_width))
                    preview.enabled = bool(vc.get("preview_enabled", False))

            # encode a preview JPEG ONLY while someone is watching (else zero cost)
            if preview.enabled:
                _push_preview(preview, frame, faces)

            # adaptive rate cap: sleep the remainder of the target frame interval.
            # This is the main CPU win — YuNet stops running flat-out, and the loop
            # backs off to idle_fps when nobody's there.
            budget = track_dt if present else idle_dt
            sleep = budget - (time.monotonic() - loop_start)
            if sleep > 0:
                time.sleep(sleep)
    finally:
        cam.close()
        pub.set_state("state:camera", {"running": False}, ttl=5)
        log.info("vision service stopped")


def _push_preview(preview: FramePreview, frame, faces) -> None:
    import cv2

    img = frame.copy()
    for f in faces:
        cv2.rectangle(img, (f.x, f.y), (f.x + f.w, f.y + f.h), (0, 255, 0), 2)
    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
    if ok:
        preview.update(buf.tobytes())


def main() -> None:
    ap = argparse.ArgumentParser(prog="vision.service")
    ap.add_argument("--source", default="auto")
    ap.add_argument("--detect-width", type=int, default=None,
                    help="override vision_detect_width from config")
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--height", type=int, default=480)
    args = ap.parse_args()

    setup_logging("INFO", "deskbot.vision")
    run(args.source, args.width, args.height, detect_width=args.detect_width)


if __name__ == "__main__":
    main()
