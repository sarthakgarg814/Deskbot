"""Servo arbiter — the control brain (design decision D2).

One owner drives the servos at a time, chosen by priority:
    manual_test > center > face_tracking > idle
Each command carries a TTL so a dead publisher (e.g. vision crash) can't hold the
servos hostage — face-tracking targets self-expire and the arbiter falls back to
holding, then drifts home.

Control model — POSITION-STEP, not velocity (this is the key design):
  The camera rides on the servo, so a face at normalized error `e` (-1..1) is
  `e * (FOV/2)` degrees off the optical axis. On each NEW vision sample we compute
  an absolute target = current + track_gain * e * (FOV/2), slew smoothly to it,
  and then HOLD. We do NOT keep integrating a velocity — so once the face is in the
  deadzone the servo settles and stops, instead of hunting. track_gain < 1 damps
  the closed loop against vision latency (0.5 ≈ halve the error each sample).

Two command modes:
  - "angle": absolute target (manual test, center) — slew to it.
  - "error": normalized centering error from vision — position-step as above.

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
    expires_at: float  # monotonic seconds (also serves as the "new sample" marker)


@dataclass
class ArbiterConfig:
    track_gain: float = 0.5      # fraction of the geometric error corrected per sample
    fov_pan: float = 54.0        # camera horizontal FOV (deg) — Pi cam v1.3 ≈ 54
    fov_tilt: float = 41.0       # camera vertical FOV (deg)
    deadzone: float = 0.04       # ignore error smaller than this (settle)
    max_speed: float = 120.0     # deg/sec slew limit (smoothness of the move)
    limit_deg: float = 80.0      # ± clamp
    pan_offset: float = 0.0
    tilt_offset: float = 0.0
    pan_invert: bool = False
    tilt_invert: bool = False
    recenter_after_s: float = 3.0  # idle this long (face lost) → drift home


class ServoArbiter:
    def __init__(self, cfg: ArbiterConfig | None = None) -> None:
        self.cfg = cfg or ArbiterConfig()
        self.pan = 0.0                 # current angle (pre-offset)
        self.tilt = 0.0
        self._target_pan = 0.0         # where we're slewing to (settled when reached)
        self._target_tilt = 0.0
        self.owner = "idle"
        self._idle_since: float | None = None
        self._last_stamp: float | None = None   # last processed error sample

    def set_config(self, cfg: ArbiterConfig) -> None:
        self.cfg = cfg

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

    def _step(self, cur: float, error: float, fov: float, invert: bool) -> float:
        """Absolute target angle to center a face at normalized `error`."""
        e = 0.0 if abs(error) < self.cfg.deadzone else error
        delta = self.cfg.track_gain * e * (fov / 2.0)
        return self._clamp(cur + (-delta if invert else delta))

    def update(self, commands: dict[str, Command], now: float, dt: float) -> tuple[float, float]:
        """Advance one control tick. Returns servo angles to write (with offset)."""
        owner, cmd = self._active(commands, now)
        if owner != self.owner:
            self.owner = owner
            self._idle_since = now if owner == "idle" else None
            self._last_stamp = None
            self._target_pan, self._target_tilt = self.pan, self.tilt  # no jump on takeover

        if cmd is None:
            # idle → hold, then drift home once the face has been gone long enough
            if self._idle_since is not None and (now - self._idle_since) >= self.cfg.recenter_after_s:
                self._target_pan = self._target_tilt = 0.0
        elif cmd.mode == "angle":
            self._target_pan = self._clamp(cmd.pan)
            self._target_tilt = self._clamp(cmd.tilt)
        else:  # "error" — recompute the target only on a NEW vision sample
            if cmd.expires_at != self._last_stamp:
                self._last_stamp = cmd.expires_at
                self._target_pan = self._step(self.pan, cmd.pan, self.cfg.fov_pan, self.cfg.pan_invert)
                self._target_tilt = self._step(self.tilt, cmd.tilt, self.cfg.fov_tilt, self.cfg.tilt_invert)

        # one smooth slew toward the (fixed) target, then settle
        self.pan = self._slew(self.pan, self._target_pan, dt)
        self.tilt = self._slew(self.tilt, self._target_tilt, dt)
        return self.pan + self.cfg.pan_offset, self.tilt + self.cfg.tilt_offset
