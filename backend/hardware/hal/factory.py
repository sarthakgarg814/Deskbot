"""Select the hardware backend from config (design: docs/02-hardware-layer.md).

Milestone 1 wires the `mock` backend. The `real` backend is a stub that raises
a clear message until the hardware milestones implement the pigpio/luma/ws281x
drivers — so a misconfigured `hardware_backend: real` on a laptop fails loudly
instead of silently doing nothing.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from .base import HardwareMonitor, LedStrip, OledDisplay, ServoController
from .monitor import RealMonitor

log = logging.getLogger("deskbot.hw")


@dataclass
class Hardware:
    servo: ServoController
    led: LedStrip
    oled: OledDisplay
    monitor: HardwareMonitor
    backend: str


def get_hardware(backend: str = "mock") -> Hardware:
    # The monitor is always the REAL one — psutil/vcgencmd work everywhere and
    # Milestone 1 shows genuine CPU/RAM/temp on the dashboard.
    monitor = RealMonitor()

    if backend == "mock":
        from .mock import MockLed, MockOled, MockServo

        log.info("hardware backend: mock")
        return Hardware(MockServo(), MockLed(), MockOled(), monitor, "mock")

    if backend == "real":
        raise NotImplementedError(
            "real hardware backend lands in the hardware milestone (pigpio servos, "
            "luma.oled, rpi_ws281x). Milestone 1 runs with hardware_backend: mock."
        )

    raise ValueError(f"unknown hardware backend: {backend!r}")
