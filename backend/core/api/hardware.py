"""Hardware test endpoints. Core does NOT own the devices (D2) — it publishes
`cmd.*` to the bus and the hardware service acts on them. Live device state comes
back via `state:*`.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from common.bus import Bus
from hardware.hal.base import LED_STATES

from .deps import get_bus

router = APIRouter(tags=["hardware"])


class ServoTest(BaseModel):
    pan: float = 0.0
    tilt: float = 0.0


class LedState(BaseModel):
    state: str


@router.post("/servo/test")
async def servo_test(body: ServoTest, bus: Bus = Depends(get_bus)):
    # highest-priority owner so a manual move overrides face tracking briefly
    await bus.publish("cmd.servo.target", {
        "owner": "manual_test", "mode": "angle",
        "pan": body.pan, "tilt": body.tilt, "ttl_ms": 3000,
    })
    return {"pan": body.pan, "tilt": body.tilt, "owner": "manual_test"}


@router.get("/servo/status")
async def servo_status(bus: Bus = Depends(get_bus)):
    state = await bus.get_state("state:servo")
    return state or {"pan": 0, "tilt": 0, "owner": "off"}


@router.post("/led/state")
async def led_state(body: LedState, bus: Bus = Depends(get_bus)):
    state = body.state if body.state in LED_STATES else "idle"
    await bus.publish("cmd.led.state", {"state": state})
    return {"state": state, "valid_states": list(LED_STATES)}


@router.get("/oled/preview")
async def oled_preview(bus: Bus = Depends(get_bus)):
    state = await bus.get_state("state:oled")
    return {"lines": (state or {}).get("lines", [])}
