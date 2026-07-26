"""Privacy-gated MJPEG preview server for the vision service.

Streams the annotated camera frames over HTTP (multipart/x-mixed-replace) — but
ONLY while enabled (mirrored from the `camera.preview_enabled` setting). Off by
default. Stdlib only; runs in a daemon thread inside the vision process. The feed
is local-only (the Pi/LAN) and nothing is written to disk.
"""
from __future__ import annotations

import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

log = logging.getLogger("deskbot.vision.preview")


class FramePreview:
    """Shared latest-JPEG holder + enabled flag, written by the capture loop."""

    def __init__(self) -> None:
        self._jpeg: bytes | None = None
        self._lock = threading.Lock()
        self.enabled = False

    def update(self, jpeg: bytes) -> None:
        with self._lock:
            self._jpeg = jpeg

    def latest(self) -> bytes | None:
        with self._lock:
            return self._jpeg


def _make_handler(preview: FramePreview):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):  # silence per-request stderr logging
            pass

        def do_GET(self):  # noqa: N802
            if self.path.rstrip("/") not in ("/stream", ""):
                self.send_error(404)
                return
            if not preview.enabled:
                self.send_error(503, "preview disabled")
                return

            self.send_response(200)
            self.send_header("Age", "0")
            self.send_header("Cache-Control", "no-cache, private")
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.end_headers()
            try:
                while preview.enabled:
                    jpeg = preview.latest()
                    if jpeg:
                        self.wfile.write(b"--frame\r\n")
                        self.wfile.write(b"Content-Type: image/jpeg\r\n")
                        self.wfile.write(f"Content-Length: {len(jpeg)}\r\n\r\n".encode())
                        self.wfile.write(jpeg)
                        self.wfile.write(b"\r\n")
                    threading.Event().wait(1 / 15)  # ~15 fps cap on the wire
            except (BrokenPipeError, ConnectionResetError):
                pass  # client closed the tab

    return Handler


def start_preview_server(preview: FramePreview, port: int) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("0.0.0.0", port), _make_handler(preview))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    log.info("preview server on :%d (gated by camera.preview_enabled)", port)
    return server
