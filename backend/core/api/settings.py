from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from common.bus import Bus
from common.db import get_session
from common.schemas import SettingOut, SettingUpdate
from core.services import settings_service

from .deps import get_bus

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=list[SettingOut])
def get_settings(ns: str | None = None, s: Session = Depends(get_session)):
    return settings_service.list_settings(s, namespace=ns)


@router.post("", response_model=list[SettingOut])
async def update_settings(
    updates: list[SettingUpdate],
    s: Session = Depends(get_session),
    bus: Bus = Depends(get_bus),
):
    changed = settings_service.update_settings(s, [(u.key, u.value) for u in updates])
    s.commit()
    if changed:
        # hot-reload signal for services (D7)
        await bus.publish("settings", {"keys": changed})
    return settings_service.list_settings(s)
