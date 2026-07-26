"""The vision service: camera capture + face detection + presence.

Runs as its own process on the Pi (design decision D1). Publishes face targets
and presence to the bus; never writes SQLite directly. Face detection uses
OpenCV YuNet, not MediaPipe (D9 — MediaPipe is unavailable on Trixie/Py3.13).
"""
