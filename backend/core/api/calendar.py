from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from common.db import get_session
from core.services import calendar_service

router = APIRouter(prefix="/calendar", tags=["calendar"])


class ClientSecret(BaseModel):
    content: str


class AuthCode(BaseModel):
    code: str


@router.get("/auth")
def calendar_auth():
    return calendar_service.auth_status()


@router.post("/client-secret")
def calendar_client_secret(body: ClientSecret):
    try:
        calendar_service.save_client_secret(body.content)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"invalid client secret: {e}")
    return {"ok": True}


@router.get("/auth-url")
def calendar_auth_url():
    try:
        return {"url": calendar_service.auth_url()}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"cannot build auth url: {e}")


@router.post("/exchange")
def calendar_exchange(body: AuthCode, s: Session = Depends(get_session)):
    from core.services import settings_service

    try:
        calendar_service.exchange(body.code)
        settings_service.update_settings(s, [("calendar.enabled", True)])  # auto-enable
        n = calendar_service.sync(s)
        s.commit()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"auth failed: {e}")
    return {"ok": True, "synced": n}


@router.post("/disconnect")
def calendar_disconnect():
    calendar_service.disconnect()
    return {"ok": True}


@router.get("/config")
def calendar_config(s: Session = Depends(get_session)):
    return {**calendar_service.auth_status(), **calendar_service.config(s)}


@router.get("/calendars")
def calendar_list(s: Session = Depends(get_session)):
    try:
        return calendar_service.calendars(s)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"cannot list calendars: {e}")


@router.get("/today")
def calendar_today(s: Session = Depends(get_session)):
    return calendar_service.today(s)


@router.get("/upcoming")
def calendar_upcoming(limit: int = 10, s: Session = Depends(get_session)):
    return calendar_service.upcoming(s, limit=limit)


@router.post("/sync")
def calendar_sync(s: Session = Depends(get_session)):
    try:
        n = calendar_service.sync(s)
        s.commit()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"sync failed: {e}")
    return {"synced": n, "events": calendar_service.upcoming(s)}
