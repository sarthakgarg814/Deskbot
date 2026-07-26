"""The hardware service — sole owner of the servos (design decision D2).

Runs a fixed-rate control loop: it consumes cmd.servo.* from the bus, runs the
arbiter + PID, and writes the servo angles. A background thread handles the bus
subscription; the main thread runs the control loop at a steady cadence.

Run as its own process (systemd on the Pi):
    python -m hardware.service

Subscribes:  cmd.servo.target / cmd.servo.center / cmd.led.state
Publishes:   state:servo (cache) + servo (pub/sub) for the dashboard
Reads:       state:servo.config  (gains/limits core mirrors from settings — live tune)
"""
from __future__ import annotations

import logging
import threading
import time

from common.bus import make_publisher, make_subscriber
from common.config import load_config
from common.logging import setup_logging

from .arbiter import ArbiterConfig, Command, ServoArbiter
from .hal import get_hardware

log = logging.getLogger("deskbot.hw.service")

CONTROL_HZ = 40
STATE_PUB_HZ = 12
CENTER_TTL_S = 3.0
CONFIG_POLL_S = 2.0


def _config_from_state(vc: dict | None, base: ArbiterConfig) -> ArbiterConfig:
    if not isinstance(vc, dict):
        return base
    g = vc
    return ArbiterConfig(
        track_gain=float(g.get("track_gain", base.track_gain)),
        fov_pan=float(g.get("fov_pan", base.fov_pan)),
        fov_tilt=float(g.get("fov_tilt", base.fov_tilt)),
        deadzone=float(g.get("deadzone", base.deadzone)),
        max_speed=float(g.get("max_speed", base.max_speed)),
        limit_deg=float(g.get("limit_deg", base.limit_deg)),
        pan_offset=float(g.get("pan_offset", base.pan_offset)),
        tilt_offset=float(g.get("tilt_offset", base.tilt_offset)),
        pan_invert=bool(g.get("pan_invert", base.pan_invert)),
        tilt_invert=bool(g.get("tilt_invert", base.tilt_invert)),
        recenter_after_s=float(g.get("recenter_after_s", base.recenter_after_s)),
    )


def _subscriber_thread(sub, hw, commands: dict, lock: threading.Lock, pub) -> None:
    """Translate bus commands into arbiter commands / device actions."""
    for topic, payload in sub.listen(
        "cmd.servo.target", "cmd.servo.center", "cmd.led.state"
    ):
        now = time.monotonic()
        if topic == "cmd.servo.target":
            owner = payload.get("owner", "face_tracking")
            ttl = float(payload.get("ttl_ms", 400)) / 1000.0
            with lock:
                commands[owner] = Command(
                    mode=payload.get("mode", "error"),
                    pan=float(payload.get("pan", 0.0)),
                    tilt=float(payload.get("tilt", 0.0)),
                    expires_at=now + ttl,
                )
        elif topic == "cmd.servo.center":
            with lock:
                commands["center"] = Command("angle", 0.0, 0.0, now + CENTER_TTL_S)
        elif topic == "cmd.led.state":
            hw.led.set_state(payload.get("state", "idle"))
            pub.set_state("state:led", {"state": hw.led.get_state()})


def run() -> None:
    cfg = load_config()
    setup_logging(cfg.log_level, "deskbot.hw")
    pub = make_publisher(cfg.bus_backend, cfg.redis_url)
    sub = make_subscriber(cfg.bus_backend, cfg.redis_url)
    hw = get_hardware(cfg.hardware_backend)
    log.info("hardware service starting (bus=%s, hw=%s)", cfg.bus_backend, hw.backend)

    arbiter = ServoArbiter()
    commands: dict[str, Command] = {}
    lock = threading.Lock()

    threading.Thread(
        target=_subscriber_thread, args=(sub, hw, commands, lock, pub), daemon=True
    ).start()

    period = 1.0 / CONTROL_HZ
    last_pub = 0.0
    last_cfg = 0.0
    t_prev = time.monotonic()

    try:
        while True:
            now = time.monotonic()
            dt = now - t_prev
            t_prev = now

            # live-tune gains/limits from settings core mirrors
            if now - last_cfg >= CONFIG_POLL_S:
                last_cfg = now
                arbiter.set_config(_config_from_state(pub.get_state("state:servo.config"), arbiter.cfg))

            with lock:
                # drop expired commands so the dict doesn't grow
                for k in [k for k, c in commands.items() if c.expires_at <= now]:
                    del commands[k]
                snapshot = dict(commands)

            pan, tilt = arbiter.update(snapshot, now, dt)
            hw.servo.set_angles(pan, tilt)

            if now - last_pub >= 1.0 / STATE_PUB_HZ:
                last_pub = now
                state = {"pan": round(pan, 1), "tilt": round(tilt, 1), "owner": arbiter.owner}
                pub.set_state("state:servo", state, ttl=5)
                pub.publish("servo", state)

            time.sleep(max(0.0, period - (time.monotonic() - now)))
    finally:
        try:
            hw.servo.center()
            if hasattr(hw.servo, "detach"):
                hw.servo.detach()
        except Exception:  # noqa: BLE001
            pass
        pub.set_state("state:servo", {"pan": 0, "tilt": 0, "owner": "off"}, ttl=5)
        log.info("hardware service stopped")


if __name__ == "__main__":
    run()
