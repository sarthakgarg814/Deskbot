"""Real pan/tilt servos via gpiozero on the lgpio backend (design decision D6).

SG90 micro-servos: 50 Hz PWM, ~0.5–2.5 ms pulse for the full sweep. Pulse widths
are approximate and vary per unit — tune min/max if the ends don't line up.
Only the `hardware` process constructs this (single owner of the GPIO).
"""
from __future__ import annotations

import logging

from .base import PanTilt

log = logging.getLogger("deskbot.hw.servo")


class RealServo:
    def __init__(
        self,
        pan_pin: int,
        tilt_pin: int,
        limit_deg: float = 80.0,
        min_pulse_s: float = 0.0005,
        max_pulse_s: float = 0.0025,
    ) -> None:
        from gpiozero import AngularServo

        # Prefer the lgpio pin factory (Trixie's native backend); fall back to
        # gpiozero's default if that import path isn't available.
        factory = None
        try:
            from gpiozero.pins.lgpio import LGPIOFactory

            factory = LGPIOFactory()
        except Exception as e:  # noqa: BLE001
            log.info("lgpio factory unavailable (%s) — using gpiozero default", e)

        kw = dict(
            min_angle=-limit_deg, max_angle=limit_deg,
            min_pulse_width=min_pulse_s, max_pulse_width=max_pulse_s,
        )
        if factory is not None:
            kw["pin_factory"] = factory
        self._pan = AngularServo(pan_pin, **kw)
        self._tilt = AngularServo(tilt_pin, **kw)
        self._limit = limit_deg
        self._pan_a = 0.0
        self._tilt_a = 0.0
        self.center()
        log.info("real servos on GPIO pan=%d tilt=%d (±%.0f°)", pan_pin, tilt_pin, limit_deg)

    def set_angles(self, pan_deg: float, tilt_deg: float) -> None:
        self._pan_a = max(-self._limit, min(self._limit, pan_deg))
        self._tilt_a = max(-self._limit, min(self._limit, tilt_deg))
        self._pan.angle = self._pan_a
        self._tilt.angle = self._tilt_a

    def get_angles(self) -> PanTilt:
        return PanTilt(self._pan_a, self._tilt_a)

    def center(self) -> None:
        self.set_angles(0.0, 0.0)

    def detach(self) -> None:
        # stop holding torque (lets the servo relax) — used on shutdown
        self._pan.detach()
        self._tilt.detach()
