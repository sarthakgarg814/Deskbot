from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from common.bus import Bus
from common.db import get_session
from core.services import water_service

from .deps import get_bus

router = APIRouter(prefix="/water", tags=["water"])


async def _fire_alert(bus: Bus, buzzer: bool) -> None:
    await bus.publish("reminder", {"type": "water", "message": "Time to drink water 💧"})
    await bus.set_state("state:oled.alert", {"type": "water"}, ttl=8)
    await bus.publish("cmd.led.state", {"state": "reminder"})
    if buzzer:
        await bus.publish("cmd.buzzer.beep", {"count": 2})


@router.get("/status")
def water_status(s: Session = Depends(get_session)):
    return water_service.status(s)


@router.post("/drank")
def water_drank(s: Session = Depends(get_session)):
    water_service.record(s, "drank")   # resets the reminder interval + counts today
    s.commit()
    return water_service.status(s)


@router.post("/test")
async def water_test(s: Session = Depends(get_session), bus: Bus = Depends(get_bus)):
    """Fire a reminder now — to preview the buzzer + OLED water animation."""
    cfg = water_service.config(s)
    water_service.record(s, "reminder_sent")
    s.commit()
    await _fire_alert(bus, cfg["buzzer_enabled"])
    return {"ok": True}
