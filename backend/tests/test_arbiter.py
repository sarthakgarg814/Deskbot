"""Servo arbiter + PID logic (no hardware)."""
from __future__ import annotations

from hardware.arbiter import ArbiterConfig, Command, ServoArbiter


def _cfg(**kw):
    base = dict(kp=40.0, ki=0.0, kd=0.0, deadzone=0.06, max_speed=90.0, limit_deg=80.0)
    base.update(kw)
    return ArbiterConfig(**base)


def test_angle_mode_slews_toward_target():
    arb = ServoArbiter(_cfg())
    cmds = {"manual_test": Command("angle", 30.0, 0.0, expires_at=10.0)}
    # one 0.1s tick: max_speed 90°/s → moves ≤9° toward 30
    pan, _ = arb.update(cmds, now=1.0, dt=0.1)
    assert 0 < pan <= 9.001
    # after enough ticks it reaches the target
    for i in range(50):
        pan, _ = arb.update(cmds, now=1.1 + i * 0.1, dt=0.1)
    assert abs(pan - 30.0) < 0.01


def test_error_mode_moves_to_reduce_error():
    arb = ServoArbiter(_cfg())
    # face to the right (err_x = +0.5) → pan angle should increase (no invert)
    cmds = {"face_tracking": Command("error", 0.5, 0.0, expires_at=10.0)}
    pan, _ = arb.update(cmds, now=1.0, dt=0.1)
    assert pan > 0


def test_invert_flips_direction():
    arb = ServoArbiter(_cfg(pan_invert=True))
    cmds = {"face_tracking": Command("error", 0.5, 0.0, expires_at=10.0)}
    pan, _ = arb.update(cmds, now=1.0, dt=0.1)
    assert pan < 0


def test_deadzone_ignores_tiny_error():
    arb = ServoArbiter(_cfg(deadzone=0.1))
    cmds = {"face_tracking": Command("error", 0.05, 0.0, expires_at=10.0)}
    pan, _ = arb.update(cmds, now=1.0, dt=0.1)
    assert pan == 0.0


def test_priority_manual_overrides_tracking():
    arb = ServoArbiter(_cfg())
    cmds = {
        "face_tracking": Command("error", -1.0, 0.0, expires_at=10.0),
        "manual_test": Command("angle", 20.0, 0.0, expires_at=10.0),
    }
    pan, _ = arb.update(cmds, now=1.0, dt=0.1)
    assert pan > 0 and arb.owner == "manual_test"       # moved toward +20, not -


def test_expired_command_falls_back_to_hold():
    arb = ServoArbiter(_cfg())
    arb.pan = 15.0
    # command already expired → idle, hold position
    cmds = {"face_tracking": Command("error", 1.0, 0.0, expires_at=0.5)}
    pan, _ = arb.update(cmds, now=1.0, dt=0.1)
    assert pan == 15.0 and arb.owner == "idle"


def test_offset_applied_to_output():
    arb = ServoArbiter(_cfg(pan_offset=5.0))
    pan, _ = arb.update({}, now=1.0, dt=0.1)  # idle at 0 + offset
    assert pan == 5.0


def test_limit_clamps_angle():
    arb = ServoArbiter(_cfg(limit_deg=10.0))
    cmds = {"manual_test": Command("angle", 90.0, 0.0, expires_at=100.0)}
    for i in range(100):
        pan, _ = arb.update(cmds, now=1.0 + i * 0.1, dt=0.1)
    assert pan == 10.0
