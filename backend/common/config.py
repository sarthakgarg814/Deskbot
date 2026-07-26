"""Runtime config: the low-level bootstrap values read before the DB exists.

Loaded from config/defaults.yaml. Dashboard-editable *settings* live in the DB
(see common/db + core/services/settings_service); this module only handles the
bootstrap layer (paths, ports, which hardware backend to use).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

# repo root = two levels up from this file: backend/common/config.py -> repo/
REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "config" / "defaults.yaml"
# Per-machine overrides (gitignored, not rsynced) — e.g. the Pi sets
# bus_backend: redis here so a redeploy never clobbers it.
LOCAL_PATH = REPO_ROOT / "config" / "local.yaml"


@dataclass(frozen=True)
class RuntimeConfig:
    hardware_backend: str = "mock"          # mock | real
    bus_backend: str = "inprocess"          # inprocess | redis
    redis_url: str = "redis://localhost:6379/0"
    preview_port: int = 8090
    # vision CPU knobs — cap processing rate (present vs away) and detection size
    vision_track_fps: int = 10
    vision_idle_fps: int = 2
    vision_detect_width: int = 256
    # servo GPIO wiring (BCM pin numbers) — signal wires
    servo_pan_pin: int = 12
    servo_tilt_pin: int = 13
    db_path: Path = REPO_ROOT / "deskbot.db"
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    frontend_dist: Path | None = None
    seed_settings: list[dict[str, Any]] = field(default_factory=list)


def _resolve(base: Path, value: str) -> Path:
    p = Path(value)
    return p if p.is_absolute() else (base / p).resolve()


@lru_cache
def load_config(path: Path | None = None) -> RuntimeConfig:
    path = path or CONFIG_PATH
    raw = yaml.safe_load(path.read_text()) if path.exists() else {}
    rt = dict((raw or {}).get("runtime", {}))
    # merge per-machine overrides on top of the defaults' runtime section
    if LOCAL_PATH.exists():
        local = yaml.safe_load(LOCAL_PATH.read_text()) or {}
        rt.update(local.get("runtime", {}))
    dist = rt.get("frontend_dist")
    return RuntimeConfig(
        hardware_backend=rt.get("hardware_backend", "mock"),
        bus_backend=rt.get("bus_backend", "inprocess"),
        redis_url=rt.get("redis_url", "redis://localhost:6379/0"),
        preview_port=int(rt.get("preview_port", 8090)),
        vision_track_fps=int(rt.get("vision_track_fps", 10)),
        vision_idle_fps=int(rt.get("vision_idle_fps", 2)),
        vision_detect_width=int(rt.get("vision_detect_width", 256)),
        servo_pan_pin=int(rt.get("servo_pan_pin", 12)),
        servo_tilt_pin=int(rt.get("servo_tilt_pin", 13)),
        db_path=_resolve(REPO_ROOT, rt.get("db_path", "deskbot.db")),
        host=rt.get("host", "0.0.0.0"),
        port=int(rt.get("port", 8000)),
        log_level=rt.get("log_level", "INFO"),
        frontend_dist=_resolve(REPO_ROOT, dist) if dist else None,
        seed_settings=list((raw or {}).get("settings", [])),
    )
