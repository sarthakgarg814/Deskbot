"""Shared FastAPI dependencies — pull shared singletons off app.state."""
from __future__ import annotations

from fastapi import Request

from common.bus import Bus
from hardware.hal.factory import Hardware


def get_bus(request: Request) -> Bus:
    return request.app.state.bus


def get_hardware_dep(request: Request) -> Hardware:
    return request.app.state.hardware
