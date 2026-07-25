"""HAL interfaces + shared value types. Real drivers and mocks both implement
these. See docs/02-hardware-layer.md.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class SystemStats:
    cpu_percent: float
    ram_percent: float
    ram_used_mb: float
    ram_total_mb: float
    temp_c: float | None
    storage_percent: float
    uptime_s: float


@dataclass
class PanTilt:
    pan: float
    tilt: float


# LED states (design: docs §I). Kept as plain strings on the wire.
LED_STATES = (
    "booting", "idle", "listening", "thinking",
    "working", "reminder", "meeting", "error", "off",
)


@runtime_checkable
class ServoController(Protocol):
    def set_angles(self, pan_deg: float, tilt_deg: float) -> None: ...
    def get_angles(self) -> PanTilt: ...
    def center(self) -> None: ...


@runtime_checkable
class LedStrip(Protocol):
    def set_state(self, state: str, **kw: object) -> None: ...
    def get_state(self) -> str: ...
    def off(self) -> None: ...


@runtime_checkable
class OledDisplay(Protocol):
    def show_text(self, lines: list[str]) -> None: ...
    def clear(self) -> None: ...
    def preview(self) -> list[str]: ...  # current lines (mock uses this for the dashboard)


@runtime_checkable
class HardwareMonitor(Protocol):
    def sample(self) -> SystemStats: ...
