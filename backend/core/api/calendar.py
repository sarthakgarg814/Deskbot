from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from common.db import get_session
from core.services import calendar_service

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.get("/auth")
def calendar_auth():
    return calendar_service.auth_status()


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
