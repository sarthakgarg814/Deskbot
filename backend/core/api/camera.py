from __future__ import annotations

from fastapi import APIRouter, Depends

from common.bus import Bus

from .deps import get_bus

router = APIRouter(prefix="/camera", tags=["camera"])


@router.get("/status")
async def camera_status(bus: Bus = Depends(get_bus)):
    """Latest camera/tracking status from the vision service (via state cache).
    Returns running=false if the vision service hasn't published recently."""
    state = await bus.get_state("state:camera")
    if state is None:
        return {"running": False}
    return {"running": True, **state}


@router.post("/center")
async def camera_center(bus: Bus = Depends(get_bus)):
    await bus.publish("cmd.servo.center", {"owner": "api"})
    return {"ok": True}


@router.post("/start")
async def camera_start(bus: Bus = Depends(get_bus)):
    await bus.publish("cmd.vision.start", {})
    return {"ok": True}


@router.post("/stop")
async def camera_stop(bus: Bus = Depends(get_bus)):
    await bus.publish("cmd.vision.stop", {})
    return {"ok": True}
