"""In-memory mock implementations of the servo, LED, and OLED interfaces."""
from __future__ import annotations

import logging

from ..base import PanTilt

log = logging.getLogger("deskbot.hw.mock")


class MockServo:
    def __init__(self) -> None:
        self._pan = 0.0
        self._tilt = 0.0
        self._logged_pan = 0.0
        self._logged_tilt = 0.0

    def set_angles(self, pan_deg: float, tilt_deg: float) -> None:
        self._pan = max(-90.0, min(90.0, pan_deg))
        self._tilt = max(-90.0, min(90.0, tilt_deg))
        # the control loop writes at 40 Hz — only log on a meaningful change so
        # the mock doesn't flood the log
        if abs(self._pan - self._logged_pan) >= 1.0 or abs(self._tilt - self._logged_tilt) >= 1.0:
            self._logged_pan, self._logged_tilt = self._pan, self._tilt
            log.info("servo -> pan=%.1f tilt=%.1f", self._pan, self._tilt)

    def get_angles(self) -> PanTilt:
        return PanTilt(self._pan, self._tilt)

    def center(self) -> None:
        self.set_angles(0.0, 0.0)


class MockLed:
    def __init__(self) -> None:
        self._state = "idle"

    def set_state(self, state: str, **kw: object) -> None:
        self._state = state
        log.info("led -> %s %s", state, kw or "")

    def get_state(self) -> str:
        return self._state

    def off(self) -> None:
        self.set_state("off")


class MockOled:
    def __init__(self) -> None:
        self._lines: list[str] = ["DeskBot", "ready"]

    def show_text(self, lines: list[str]) -> None:
        self._lines = list(lines)
        log.info("oled -> %s", " | ".join(self._lines))

    def render(self, fn) -> None:
        # no framebuffer on the mock — the service still publishes state:oled so
        # the dashboard shows the current mode/emotion.
        pass

    def clear(self) -> None:
        self._lines = []

    def preview(self) -> list[str]:
        return list(self._lines)
