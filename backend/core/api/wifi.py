from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from core.services import wifi_service

router = APIRouter(prefix="/wifi", tags=["wifi"])


class WifiConnect(BaseModel):
    ssid: str
    password: str = ""


# sync defs → FastAPI runs them in a threadpool (nmcli/subprocess is blocking)
@router.get("/status")
def wifi_status():
    return wifi_service.status()


@router.get("/scan")
def wifi_scan():
    return wifi_service.scan()


@router.post("/connect")
def wifi_connect(body: WifiConnect):
    return wifi_service.connect(body.ssid, body.password)
