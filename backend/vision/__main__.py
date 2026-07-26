"""Standalone vision smoke test — validates camera + YuNet before any bus wiring.

On the Pi:
    python -m vision                      # Pi camera, print detections + FPS
    python -m vision --frames 100         # run 100 frames then report avg FPS
    python -m vision --preview out.jpg    # save one annotated frame to inspect

On a laptop:
    python -m vision --source 0           # webcam
    python -m vision --source face.jpg    # a still image (great for CI/dev)
"""
from __future__ import annotations

import argparse
import logging
import time

from common.logging import setup_logging

from .camera import open_camera
from .detector import YuNetDetector


def main() -> None:
    ap = argparse.ArgumentParser(prog="vision")
    ap.add_argument("--source", default="auto",
                    help="'auto' (Pi cam), a webcam index like '0', or a video/image path")
    ap.add_argument("--frames", type=int, default=60, help="frames to process")
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--height", type=int, default=480)
    ap.add_argument("--detect-width", type=int, default=320,
                    help="downscale width for detection (0 = full frame)")
    ap.add_argument("--preview", default=None, help="save one annotated frame to this path")
    args = ap.parse_args()

    setup_logging("INFO", "deskbot.vision")
    log = logging.getLogger("deskbot.vision")

    # 'auto' -> Pi camera; a bare integer -> webcam index; else a file path
    if args.source == "auto":
        cam = open_camera("auto", width=args.width, height=args.height)
    else:
        src: int | str = int(args.source) if args.source.isdigit() else args.source
        cam = open_camera("opencv", source=src, width=args.width, height=args.height)

    det = YuNetDetector(detect_width=args.detect_width)

    n, faces_seen = 0, 0
    cap_s, det_s = 0.0, 0.0          # cumulative capture / detect seconds
    last_frame = None
    last_faces: list = []
    frames = cam.frames()
    t0 = time.monotonic()
    try:
        while n < args.frames:
            tc = time.monotonic()
            frame = next(frames)
            cap_s += time.monotonic() - tc

            td = time.monotonic()
            faces = det.detect(frame)
            det_s += time.monotonic() - td

            last_frame, last_faces = frame, faces
            if faces:
                faces_seen += 1
                f = faces[0]
                log.info(
                    "face @ (%.2f,%.2f) err=(%+.2f,%+.2f) score=%.2f  [%d face(s)]",
                    f.cx, f.cy, f.err_x, f.err_y, f.score, len(faces),
                )
            n += 1
    finally:
        cam.close()

    dt = time.monotonic() - t0
    fps = n / dt if dt else 0.0
    log.info("processed %d frames in %.1fs — %.1f FPS, face in %d/%d frames",
             n, dt, fps, faces_seen, n)
    log.info("timing/frame: capture %.1f ms, detect %.1f ms  (detect_width=%d)",
             1000 * cap_s / n, 1000 * det_s / n, args.detect_width)

    if args.preview and last_frame is not None:
        import cv2

        for f in last_faces:
            cv2.rectangle(last_frame, (f.x, f.y), (f.x + f.w, f.y + f.h), (0, 255, 0), 2)
        cv2.imwrite(args.preview, last_frame)
        log.info("wrote annotated preview -> %s", args.preview)


if __name__ == "__main__":
    main()
