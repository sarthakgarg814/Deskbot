"""Camera sources behind one interface.

- `PiCamera2Source`  — the Pi Camera (CSI), via picamera2. Used on the Pi.
- `OpenCVSource`     — a webcam index or a video/image file, via OpenCV. Used for
                       development on a laptop (no picamera2 there) and as a
                       USB-webcam option.

The factory picks picamera2 when available, else OpenCV, unless forced by config.
Frames are returned as BGR numpy arrays (OpenCV's convention) so the detector
sees a consistent format regardless of source.
"""
from __future__ import annotations

import logging
from typing import Iterator, Protocol

import numpy as np

log = logging.getLogger("peekabot.vision.camera")


class CameraSource(Protocol):
    def frames(self) -> Iterator[np.ndarray]: ...  # yields BGR frames
    def close(self) -> None: ...


class PiCamera2Source:
    """Pi Camera via picamera2 (Pi only). picamera2 is a system package — the
    vision venv must be created with --system-site-packages to import it."""

    def __init__(self, width: int = 640, height: int = 480, fps: int | None = None) -> None:
        from picamera2 import Picamera2  # imported lazily; Pi-only

        self._cam = Picamera2()
        # Cap the sensor frame rate so the ISP isn't doing 30–60 fps of work when
        # we only process ~10 — a meaningful CPU saving on the Pi.
        controls = {}
        if fps:
            dur = int(1_000_000 / fps)  # microseconds per frame
            controls["FrameDurationLimits"] = (dur, dur)
        cfg = self._cam.create_video_configuration(
            main={"size": (width, height), "format": "RGB888"}, controls=controls
        )
        self._cam.configure(cfg)
        self._cam.start()
        log.info("picamera2 started @ %dx%d%s", width, height, f" (cap {fps}fps)" if fps else "")

    def frames(self) -> Iterator[np.ndarray]:
        while True:
            # picamera2's "RGB888" delivers a BGR-ordered array (a known quirk) —
            # already what OpenCV/imencode expect, so NO conversion. Converting
            # here double-swaps R/B and makes the preview come out purple.
            yield self._cam.capture_array()

    def close(self) -> None:
        try:
            self._cam.stop()
        except Exception:
            pass


class OpenCVSource:
    """Webcam index (0,1,…) or a path to a video/image file. Laptop/dev + USB."""

    def __init__(self, source: int | str = 0, width: int = 640, height: int = 480,
                 **_: object) -> None:  # ignore extras (e.g. fps) it doesn't use
        import cv2

        self._is_image = isinstance(source, str) and source.lower().endswith(
            (".jpg", ".jpeg", ".png", ".bmp")
        )
        if self._is_image:
            self._image = cv2.imread(source)
            if self._image is None:
                raise FileNotFoundError(f"cannot read image: {source}")
            log.info("OpenCV image source: %s", source)
            return
        self._cap = cv2.VideoCapture(source)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        if not self._cap.isOpened():
            raise RuntimeError(f"cannot open camera source: {source!r}")
        log.info("OpenCV capture source: %s @ %dx%d", source, width, height)

    def frames(self) -> Iterator[np.ndarray]:
        if self._is_image:
            while True:
                yield self._image.copy()
        while True:
            ok, frame = self._cap.read()
            if not ok:
                break
            yield frame

    def close(self) -> None:
        if not self._is_image:
            self._cap.release()


def open_camera(backend: str = "auto", **kw) -> CameraSource:
    """backend: 'auto' | 'picamera2' | 'opencv'. 'auto' prefers picamera2."""
    if backend in ("auto", "picamera2"):
        try:
            return PiCamera2Source(**{k: v for k, v in kw.items() if k in ("width", "height", "fps")})
        except Exception as e:  # noqa: BLE001
            if backend == "picamera2":
                raise
            log.info("picamera2 unavailable (%s) — falling back to OpenCV", e)
    return OpenCVSource(**kw)
