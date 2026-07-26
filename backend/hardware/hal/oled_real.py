"""Real 0.96" SSD1306 OLED over I2C via luma.oled (128x64, addr 0x3C).

Owned by the hardware process. Renders simple text lines; the hardware service
composes a status screen and calls show_text() ~1 Hz.
"""
from __future__ import annotations

import logging

log = logging.getLogger("peekabot.hw.oled")

LINE_H = 11   # px per line → ~5-6 lines on a 64px panel


class RealOled:
    def __init__(self, address: int = 0x3C, port: int = 1) -> None:
        from luma.core.interface.serial import i2c
        from luma.oled.device import ssd1306

        serial = i2c(port=port, address=address)
        self._device = ssd1306(serial)
        self._lines: list[str] = []
        log.info("SSD1306 OLED on i2c-%d @ 0x%02X", port, address)

    def show_text(self, lines: list[str]) -> None:
        from luma.core.render import canvas

        self._lines = list(lines)
        with canvas(self._device) as draw:
            y = 0
            for line in lines[:6]:
                draw.text((0, y), line, fill="white")
                y += LINE_H

    def render(self, fn) -> None:
        """fn(draw, width, height) draws a custom frame (e.g. the eyes)."""
        from luma.core.render import canvas

        with canvas(self._device) as draw:
            fn(draw, self._device.width, self._device.height)

    def clear(self) -> None:
        self._device.clear()
        self._lines = []

    def preview(self) -> list[str]:
        return list(self._lines)
