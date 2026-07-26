"""Real servos via the Pi's HARDWARE PWM — jitter-free (design decision D6, rev).

Software PWM (gpiozero/lgpio) times pulses on the CPU, so the pulse width wobbles
and SG90s buzz/jitter. The Pi has two hardware-PWM channels exposed on GPIO 12
(PWM0, channel 0) and GPIO 13 (PWM1, channel 1) — timed by silicon, rock steady.

Requires:
  - the device-tree overlay mapping 12/13 to PWM (setup-hardware-pi.sh adds it):
      dtoverlay=pwm-2chan,pin=12,func=4,pin2=13,func2=4   (then reboot)
  - the `rpi-hardware-pwm` package (drives /sys/class/pwm)

SG90: 50 Hz frame, ~0.5–2.5 ms pulse over the sweep. Only the hardware process
constructs this (single GPIO owner).
"""
from __future__ import annotations

import logging

from .base import PanTilt

log = logging.getLogger("peekabot.hw.servo")

# GPIO -> hardware PWM channel (BCM2711: 12/18 = ch0, 13/19 = ch1)
_PIN_TO_CHANNEL = {12: 0, 13: 1, 18: 0, 19: 1}


def _make_pwm(channel: int, chip: int):
    from rpi_hardware_pwm import HardwarePWM

    try:
        return HardwarePWM(pwm_channel=channel, hz=50, chip=chip)
    except TypeError:
        # older rpi-hardware-pwm has no `chip` kwarg (defaults to Pi4's chip0)
        return HardwarePWM(pwm_channel=channel, hz=50)


class HardwarePWMServo:
    def __init__(
        self,
        pan_pin: int,
        tilt_pin: int,
        limit_deg: float = 80.0,
        min_pulse_ms: float = 0.5,
        max_pulse_ms: float = 2.5,
        chip: int = 0,           # Pi 4 = pwmchip0
    ) -> None:
        if pan_pin not in _PIN_TO_CHANNEL or tilt_pin not in _PIN_TO_CHANNEL:
            raise ValueError(
                f"hardware PWM needs GPIO 12/13 (or 18/19); got {pan_pin}/{tilt_pin}"
            )
        self._limit = limit_deg
        self._min, self._max = min_pulse_ms, max_pulse_ms
        self._pan = _make_pwm(_PIN_TO_CHANNEL[pan_pin], chip)
        self._tilt = _make_pwm(_PIN_TO_CHANNEL[tilt_pin], chip)
        self._pan_a = 0.0
        self._tilt_a = 0.0
        self._pan.start(self._duty(0.0))
        self._tilt.start(self._duty(0.0))
        log.info(
            "hardware-PWM servos: GPIO %d=ch%d, %d=ch%d (chip%d) — jitter-free",
            pan_pin, _PIN_TO_CHANNEL[pan_pin], tilt_pin, _PIN_TO_CHANNEL[tilt_pin], chip,
        )

    def _duty(self, angle: float) -> float:
        frac = (angle + 90.0) / 180.0                      # -90..90 -> 0..1
        pulse = self._min + frac * (self._max - self._min)
        pulse = max(self._min, min(self._max, pulse))
        return pulse / 20.0 * 100.0                         # ms of a 20ms frame -> duty %

    def set_angles(self, pan_deg: float, tilt_deg: float) -> None:
        p = max(-self._limit, min(self._limit, pan_deg))
        t = max(-self._limit, min(self._limit, tilt_deg))
        # Only rewrite the duty on a real change. When holding, we stop writing
        # entirely so the hardware just maintains a steady pulse (no dither).
        if abs(p - self._pan_a) >= 0.2:
            self._pan_a = p
            self._pan.change_duty_cycle(self._duty(p))
        if abs(t - self._tilt_a) >= 0.2:
            self._tilt_a = t
            self._tilt.change_duty_cycle(self._duty(t))

    def get_angles(self) -> PanTilt:
        return PanTilt(self._pan_a, self._tilt_a)

    def center(self) -> None:
        self.set_angles(0.0, 0.0)

    def detach(self) -> None:
        self._pan.stop()
        self._tilt.stop()
