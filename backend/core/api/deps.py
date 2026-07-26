"""Shared FastAPI dependencies — pull shared singletons off app.state."""
from __future__ import annotations

from fastapi import Request

from common.bus import Bus
from hardware.hal.base import HardwareMonitor


def get_bus(request: Request) -> Bus:
    return request.app.state.bus


def get_monitor(request: Request) -> HardwareMonitor:
    return request.app.state.monitor
