"""Pydantic request/response models shared by the API routers."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# --- system ---
class SystemStatus(BaseModel):
    cpu_percent: float
    ram_percent: float
    ram_used_mb: float
    ram_total_mb: float
    temp_c: float | None
    storage_percent: float
    uptime_s: float
    services: dict[str, bool] = Field(default_factory=dict)


# --- notes ---
class NoteCreate(BaseModel):
    title: str = ""
    body: str = ""
    tags: list[str] = Field(default_factory=list)
    source: str = "dashboard"


class NoteUpdate(BaseModel):
    title: str | None = None
    body: str | None = None
    tags: list[str] | None = None


class NoteOut(BaseModel):
    id: int
    title: str
    body: str
    tags: list[str]
    source: str
    created_at: datetime
    updated_at: datetime


# --- settings ---
class SettingOut(BaseModel):
    key: str
    value: Any
    type: str
    namespace: str
    updated_at: datetime


class SettingUpdate(BaseModel):
    key: str
    value: Any
