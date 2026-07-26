from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from common.db import get_session
from core.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


class Login(BaseModel):
    password: str


class ChangePassword(BaseModel):
    old_password: str
    new_password: str


@router.get("/status")           # public — lets the login page hint at the default pw
def auth_status(s: Session = Depends(get_session)):
    return {"is_default": auth_service.is_default(s)}


@router.post("/login")           # public
def login(body: Login, s: Session = Depends(get_session)):
    if not auth_service.verify_password(s, body.password):
        raise HTTPException(401, "wrong password")
    return {"token": auth_service.make_token()}


@router.post("/change")          # requires a valid token (guarded by middleware)
def change_password(body: ChangePassword, s: Session = Depends(get_session)):
    if not auth_service.verify_password(s, body.old_password):
        raise HTTPException(400, "current password is wrong")
    if len(body.new_password) < 4:
        raise HTTPException(400, "new password must be at least 4 characters")
    auth_service.set_password(s, body.new_password)
    s.commit()
    return {"ok": True}
