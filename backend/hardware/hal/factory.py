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
        # Real servos (SG90 via gpiozero/lgpio). LED + OLED stay mocked until their
        # own milestone, so `real` today = real neck, simulated lights/display.
        from common.config import load_config

        from .mock import MockLed, MockOled

        cfg = load_config()
        servo = _make_real_servo(cfg.servo_pan_pin, cfg.servo_tilt_pin)
        oled = _make_real_oled()
        log.info("hardware backend: real (servo + oled) + mock (led)")
        return Hardware(servo, MockLed(), oled, monitor, "real")

    raise ValueError(f"unknown hardware backend: {backend!r}")


def _make_real_servo(pan_pin: int, tilt_pin: int):
    """Prefer hardware PWM (jitter-free); fall back to software PWM, then mock."""
    try:
        from .servo_hwpwm import HardwarePWMServo

        return HardwarePWMServo(pan_pin, tilt_pin)
    except Exception as e:  # noqa: BLE001
        log.warning(
            "hardware PWM unavailable (%s) — is the pwm-2chan overlay enabled + "
            "rpi-hardware-pwm installed? Falling back to software PWM (may jitter).", e
        )
    try:
        from .servo_real import RealServo

        return RealServo(pan_pin, tilt_pin)
    except Exception as e:  # noqa: BLE001
        log.error("real servo init failed (%s) — falling back to mock servo", e)
        from .mock import MockServo

        return MockServo()


def _make_real_oled():
    """Real SSD1306 OLED; fall back to mock if it isn't wired / luma missing."""
    try:
        from .oled_real import RealOled

        return RealOled()
    except Exception as e:  # noqa: BLE001
        log.warning("OLED init failed (%s) — falling back to mock OLED", e)
        from .mock import MockOled

        return MockOled()
