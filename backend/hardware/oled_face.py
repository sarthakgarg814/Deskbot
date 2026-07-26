"""Animated robot eyes for the 128x64 OLED.

draw_face() renders two expressive eyes for a given emotion, with a gaze offset
(so the eyes glance toward the detected face) and a blink state. Pure PIL drawing
— works with luma's canvas on the Pi and renders to a PNG for testing.

Emotion is conveyed by the eye shape:
  happy      cup ◡ (smiling squint)
  neutral    full rounded rects
  sad        drooped outer top corner
  angry      pulled-down inner top corner (mean slant)
  surprised  big circles
  sleepy     thin bars (also used for blink)

When mood detection lands it will pick the emotion; until then the hardware
service uses happy (face present) / sleepy (away).
"""
from __future__ import annotations

EMOTIONS = ("happy", "neutral", "sad", "angry", "surprised", "sleepy")

EYE_W, EYE_H = 36, 44
GAP = 10
RADIUS = 12
SLANT = 22                 # how far the angry/sad corner is cut down
GAZE_X_MAX, GAZE_Y_MAX = 9, 6


def _box(cx: int, cy: int, w: int, h: int):
    return (cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2)


def draw_face(draw, W: int, H: int, emotion: str = "neutral",
              gaze_x: float = 0.0, gaze_y: float = 0.0, blink: bool = False) -> None:
    draw.rectangle((0, 0, W, H), fill="black")

    inner = GAP // 2 + EYE_W // 2
    cx_l, cx_r = W // 2 - inner, W // 2 + inner
    cy = H // 2
    cx_l += int(max(-1.0, min(1.0, gaze_x)) * GAZE_X_MAX)
    cx_r += int(max(-1.0, min(1.0, gaze_x)) * GAZE_X_MAX)
    cy += int(max(-1.0, min(1.0, gaze_y)) * GAZE_Y_MAX)

    if blink or emotion == "sleepy":
        h = 6 if blink else 12
        for cx in (cx_l, cx_r):
            draw.rounded_rectangle(_box(cx, cy, EYE_W, h), radius=h // 2, fill="white")
        return

    _eye(draw, cx_l, cy, emotion, "L")
    _eye(draw, cx_r, cy, emotion, "R")


def _eye(draw, cx: int, cy: int, emotion: str, side: str) -> None:
    if emotion == "surprised":
        r = 20
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill="white")
        return

    x1, y1, x2, y2 = _box(cx, cy, EYE_W, EYE_H)
    draw.rounded_rectangle((x1, y1, x2, y2), radius=RADIUS, fill="white")

    if emotion == "happy":
        # eat the top → a bottom cup ◡ (smiling eyes)
        draw.ellipse((x1 - 6, y1 - EYE_H * 0.5, x2 + 6, y1 + EYE_H * 0.55), fill="black")
    elif emotion == "angry":
        # cut the INNER top corner down → mean inward slant
        if side == "L":
            draw.polygon([(x1, y1 - 1), (x2 + 1, y1 - 1), (x2 + 1, y1 + SLANT)], fill="black")
        else:
            draw.polygon([(x2, y1 - 1), (x1 - 1, y1 - 1), (x1 - 1, y1 + SLANT)], fill="black")
    elif emotion == "sad":
        # cut the OUTER top corner down → drooped/worried
        if side == "L":
            draw.polygon([(x2, y1 - 1), (x1 - 1, y1 - 1), (x1 - 1, y1 + SLANT)], fill="black")
        else:
            draw.polygon([(x1, y1 - 1), (x2 + 1, y1 - 1), (x2 + 1, y1 + SLANT)], fill="black")
    # neutral: full rounded rect
