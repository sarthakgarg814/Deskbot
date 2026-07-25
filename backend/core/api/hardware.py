"""Hardware test endpoints. In Milestone 1 the mock hardware lives in-process, so
these call it directly. On the Pi, `hardware` is a separate process and these
become `cmd.*` publishes on the bus (docs/04-api-contract.md) — the request/
response shape stays the same.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from common.bus import Bus
from hardware.hal.base import LED_STATES
from hardware.hal.factory import Hardware

from .deps import get_bus, get_hardware_dep

router = APIRouter(tags=["hardware"])


class ServoTest(BaseModel):
    pan: float = 0.0
    tilt: float = 0.0


class LedState(BaseModel):
    state: str


@router.post("/servo/test")
async def servo_test(body: ServoTest, hw: Hardware = Depends(get_hardware_dep), bus: Bus = Depends(get_bus)):
    hw.servo.set_angles(body.pan, body.tilt)
    angles = hw.servo.get_angles()
    state = {"pan": angles.pan, "tilt": angles.tilt, "owner": "manual_test"}
    await bus.set_state("state:servo", state, ttl=10)
    await bus.publish("hardware", {"device": "servo", **state})
    return state


@router.post("/led/state")
async def led_state(body: LedState, hw: Hardware = Depends(get_hardware_dep), bus: Bus = Depends(get_bus)):
    state = body.state if body.state in LED_STATES else "idle"
    hw.led.set_state(state)
    await bus.publish("hardware", {"device": "led", "state": state})
    return {"state": hw.led.get_state(), "valid_states": list(LED_STATES)}


@router.get("/oled/preview")
async def oled_preview(hw: Hardware = Depends(get_hardware_dep)):
    return {"lines": hw.oled.preview()}
