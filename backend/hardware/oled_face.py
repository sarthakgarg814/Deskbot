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


def _ic_cpu(draw, x, y):        # chip
    draw.rectangle((x + 1, y + 1, x + 8, y + 8), outline="white")
    draw.rectangle((x + 3, y + 3, x + 6, y + 6), fill="white")
    for i in (3, 6):
        draw.line((x + i, y - 1, x + i, y + 1), fill="white")
        draw.line((x + i, y + 8, x + i, y + 10), fill="white")
        draw.line((x - 1, y + i, x + 1, y + i), fill="white")
        draw.line((x + 8, y + i, x + 10, y + i), fill="white")


def _ic_temp(draw, x, y):       # thermometer
    draw.line((x + 4, y + 1, x + 4, y + 6), fill="white", width=2)
    draw.ellipse((x + 2, y + 5, x + 7, y + 10), outline="white")
    draw.ellipse((x + 3, y + 6, x + 6, y + 9), fill="white")


def _ic_ram(draw, x, y):        # memory stick
    draw.rectangle((x, y + 1, x + 9, y + 7), outline="white")
    for i in (2, 4, 6):
        draw.line((x + i, y + 2, x + i, y + 6), fill="white")
    draw.line((x + 2, y + 7, x + 2, y + 9), fill="white")
    draw.line((x + 7, y + 7, x + 7, y + 9), fill="white")


def _ic_disk(draw, x, y):       # cylinder
    draw.ellipse((x, y, x + 9, y + 3), outline="white")
    draw.line((x, y + 1, x, y + 7), fill="white")
    draw.line((x + 9, y + 1, x + 9, y + 7), fill="white")
    draw.arc((x, y + 5, x + 9, y + 9), 0, 180, fill="white")


def _ic_wifi(draw, x, y):       # signal arcs
    draw.arc((x, y, x + 10, y + 12), 215, 325, fill="white")
    draw.arc((x + 2, y + 2, x + 8, y + 12), 215, 325, fill="white")
    draw.rectangle((x + 4, y + 7, x + 6, y + 9), fill="white")


def draw_stats(draw, W: int, H: int, *, clock: str, cpu, temp, ram, disk,
               uptime: str, wifi: bool = True, next_event: str | None = None) -> None:
    """A dense one-frame system dashboard with tiny icons (128x64)."""
    draw.rectangle((0, 0, W, H), fill="black")

    # header: clock + wifi + separator
    draw.text((2, 0), clock, fill="white")
    if wifi:
        _ic_wifi(draw, W - 13, 0)
    draw.line((0, 11, W, 11), fill="white")

    def cell(x, y, icon, value):
        icon(draw, x, y)
        draw.text((x + 13, y + 1), value, fill="white")

    pct = lambda v: f"{v:.0f}%" if isinstance(v, (int, float)) else "--"
    cell(3, 16, _ic_cpu, pct(cpu))
    cell(66, 16, _ic_temp, f"{temp:.0f}C" if isinstance(temp, (int, float)) else "--")
    cell(3, 34, _ic_ram, pct(ram))
    cell(66, 34, _ic_disk, pct(disk))

    # footer: next calendar event if we have one, else uptime
    draw.line((0, 52, W, 52), fill="white")
    draw.text((2, 54), (">" + next_event)[:21] if next_event else f"up {uptime}", fill="white")


def _bell(draw, cx: int, cy: int, color: str) -> None:
    draw.line((cx, cy, cx, cy + 2), fill=color)                       # handle
    draw.arc((cx - 7, cy + 1, cx + 7, cy + 15), 180, 360, fill=color)  # dome
    draw.line((cx - 7, cy + 8, cx - 9, cy + 13), fill=color)
    draw.line((cx + 7, cy + 8, cx + 9, cy + 13), fill=color)
    draw.line((cx - 9, cy + 13, cx + 9, cy + 13), fill=color)          # base
    draw.ellipse((cx - 1, cy + 13, cx + 2, cy + 16), fill=color)       # clapper


def draw_meeting(draw, W: int, H: int, t: float, title: str = "Meeting",
                 mins: int = 0, started: bool = False) -> None:
    """Meeting alert. Upcoming: a shaking bell + 'in N min'. Started: flashing 'NOW'."""
    import math

    flash = started and int(t * 2) % 2 == 0
    bg = "white" if flash else "black"
    fg = "black" if flash else "white"
    draw.rectangle((0, 0, W, H), fill=bg)

    sway = 0 if started else int(3 * math.sin(t * 9))       # bell shakes when upcoming
    _bell(draw, W // 2 + sway, 2, fg)

    draw.text((6, 22), "MEETING", fill=fg)
    draw.text((6, 36), title[:18], fill=fg)
    draw.text((6, 50), "NOW" if started else f"in {mins} min", fill=fg)


def draw_water(draw, W: int, H: int, t: float) -> None:
    """'Drink water' reminder animation: a glass filling with a wavy surface and a
    droplet plopping in, next to the text. `t` = seconds (drives the animation)."""
    import math

    draw.rectangle((0, 0, W, H), fill="black")
    draw.text((6, 12), "TIME TO", fill="white")
    draw.text((6, 30), "DRINK!", fill="white")

    # glass on the right (tapered): top wider than bottom
    gx, gtop, gbot = W - 34, 10, H - 8
    gw_top, gw_bot = 30, 22
    tl, tr = gx - gw_top // 2, gx + gw_top // 2
    bl, br = gx - gw_bot // 2, gx + gw_bot // 2
    draw.line((tl, gtop, bl, gbot), fill="white", width=2)
    draw.line((tr, gtop, br, gbot), fill="white", width=2)
    draw.line((bl, gbot, br, gbot), fill="white", width=2)

    # water level rises over a 2s cycle, with a small wave
    phase = (t % 2.0) / 2.0
    level = gbot - int(phase * (gbot - gtop - 8))
    for x in range(bl, br + 1):
        wave = int(2 * math.sin((x - bl) / 3.0 + t * 4))
        draw.line((x, level + wave, x, gbot - 1), fill="white")

    # droplet falls from above into the glass, looping every 1s
    dphase = (t % 1.0)
    dy = gtop - 8 + int(dphase * (level - (gtop - 8)))
    draw.ellipse((gx - 3, dy - 3, gx + 3, dy + 3), fill="white")


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
