"""The OLED eye renderer draws every emotion without error (no PIL needed —
a fake draw records the primitive calls)."""
from __future__ import annotations

from hardware.oled_face import EMOTIONS, draw_face


class _FakeDraw:
    def __init__(self) -> None:
        self.calls = 0

    def _rec(self, *a, **k):
        self.calls += 1

    rectangle = rounded_rectangle = ellipse = polygon = line = _rec


def test_draw_face_every_emotion():
    for emo in EMOTIONS:
        d = _FakeDraw()
        draw_face(d, 128, 64, emo, gaze_x=0.7, gaze_y=-0.4, blink=False)
        assert d.calls > 0


def test_draw_face_blink():
    d = _FakeDraw()
    draw_face(d, 128, 64, "neutral", blink=True)
    assert d.calls > 0
