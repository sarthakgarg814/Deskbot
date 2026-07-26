"""Servo arbiter + PID — the control brain (design decision D2).

One owner drives the servos at a time, chosen by priority:
    manual_test > center > face_tracking > idle
Each command carries a TTL so a dead publisher (e.g. vision crash) can't hold the
servos hostage — face-tracking targets self-expire and the arbiter falls back to
holding position.

Two command modes:
  - "angle": absolute target angle (manual test, center). Slew-limited move.
  - "error": normalized centering error (-1..1) from vision → PID → deg/sec →
             integrated into the angle. This is face tracking.

Pure logic (no hardware, no bus) so it unit-tests cleanly.
"""
from __future__ import annotations

from dataclasses import dataclass

PRIORITY = ("manual_test", "center", "face_tracking", "idle")


@dataclass
class Command:
    mode: str          # "angle" | "error"
    pan: float         # angle mode: degrees; error mode: normalized error
    tilt: float
    expires_at: float  # monotonic seconds


class PID:
    def __init__(self, kp: float, ki: float, kd: float) -> None:
        self.kp, self.ki, self.kd = kp, ki, kd
        self._integral = 0.0
        self._prev = 0.0

    def reset(self) -> None:
        self._integral = 0.0
        self._prev = 0.0

    def compute(self, error: float, dt: float) -> float:
        self._integral += error * dt
        deriv = (error - self._prev) / dt if dt > 0 else 0.0
        self._prev = error
        return self.kp * error + self.ki * self._integral + self.kd * deriv


@dataclass
class ArbiterConfig:
    kp: float = 40.0
    ki: float = 0.0
    kd: float = 0.0
    deadzone: float = 0.06
    max_speed: float = 90.0     # deg/sec
    limit_deg: float = 80.0     # ± clamp
    pan_offset: float = 0.0
    tilt_offset: float = 0.0
    pan_invert: bool = False
    tilt_invert: bool = False


class ServoArbiter:
    def __init__(self, cfg: ArbiterConfig | None = None) -> None:
        self.cfg = cfg or ArbiterConfig()
        self.pan = 0.0             # current commanded angle (pre-offset)
        self.tilt = 0.0
        self.owner = "idle"
        self._pan_pid = PID(self.cfg.kp, self.cfg.ki, self.cfg.kd)
        self._tilt_pid = PID(self.cfg.kp, self.cfg.ki, self.cfg.kd)

    def set_config(self, cfg: ArbiterConfig) -> None:
        self.cfg = cfg
        for pid in (self._pan_pid, self._tilt_pid):
            pid.kp, pid.ki, pid.kd = cfg.kp, cfg.ki, cfg.kd

    def _active(self, commands: dict[str, Command], now: float) -> tuple[str, Command | None]:
        for owner in PRIORITY:
            cmd = commands.get(owner)
            if cmd is not None and cmd.expires_at > now:
                return owner, cmd
        return "idle", None

    def _clamp(self, a: float) -> float:
        return max(-self.cfg.limit_deg, min(self.cfg.limit_deg, a))

    def _slew(self, cur: float, target: float, dt: float) -> float:
        step = self.cfg.max_speed * dt
        if abs(target - cur) <= step:
            return target
        return cur + step * (1 if target > cur else -1)

    def _track(self, pid: PID, cur: float, error: float, invert: bool, dt: float) -> float:
        e = 0.0 if abs(error) < self.cfg.deadzone else error
        vel = pid.compute(e, dt)                                  # deg/sec
        vel = max(-self.cfg.max_speed, min(self.cfg.max_speed, vel))
        return cur + (-vel if invert else vel) * dt

    def update(self, commands: dict[str, Command], now: float, dt: float) -> tuple[float, float]:
        """Advance one control tick. Returns the servo angles to write (with offset)."""
        owner, cmd = self._active(commands, now)
        if owner != self.owner:
            self._pan_pid.reset()
            self._tilt_pid.reset()
            self.owner = owner

        if cmd is None:
            pass  # idle → hold current angle
        elif cmd.mode == "angle":
            self.pan = self._slew(self.pan, self._clamp(cmd.pan), dt)
            self.tilt = self._slew(self.tilt, self._clamp(cmd.tilt), dt)
        else:  # "error" — face tracking
            self.pan = self._clamp(self._track(self._pan_pid, self.pan, cmd.pan, self.cfg.pan_invert, dt))
            self.tilt = self._clamp(self._track(self._tilt_pid, self.tilt, cmd.tilt, self.cfg.tilt_invert, dt))

        return self.pan + self.cfg.pan_offset, self.tilt + self.cfg.tilt_offset
