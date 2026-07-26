from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends

from common.bus import Bus
from common.schemas import SystemStatus
from hardware.hal.base import HardwareMonitor

from .deps import get_bus, get_monitor

router = APIRouter(tags=["system"])


@router.get("/system", response_model=SystemStatus)
async def get_system(bus: Bus = Depends(get_bus), monitor: HardwareMonitor = Depends(get_monitor)):
    # Prefer the cached sample the scheduler publishes; fall back to a live read.
    cached = await bus.get_state("state:system")
    if cached:
        return SystemStatus(**cached)
    data = asdict(monitor.sample())
    data["services"] = {"core": True}
    return SystemStatus(**data)
