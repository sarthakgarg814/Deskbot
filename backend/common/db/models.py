"""ORM models. Milestone 1 defines the tables the skeleton actually uses
(users, settings, notes). Mood, calendar, voice_commands, etc. from
docs/03-database-schema.md are added in their own milestones.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _localnow() -> datetime:
    # water schedule/reset are user-local, so water events store local naive time
    return datetime.now()


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), default="me")
    is_default: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    notes: Mapped[list["Note"]] = relationship(back_populates="user")


class Setting(Base):
    """Dashboard-editable tunables (design decision D7). Key/value + type + ns."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[str] = mapped_column(Text)          # JSON-encoded scalar
    type: Mapped[str] = mapped_column(String(16))     # int|float|bool|str|json
    namespace: Mapped[str] = mapped_column(String(40), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[str] = mapped_column(Text, default="[]")   # JSON array
    source: Mapped[str] = mapped_column(String(20), default="dashboard")  # voice|dashboard
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    user: Mapped["User | None"] = relationship(back_populates="notes")


class CalendarEvent(Base):
    """Cache of synced Google Calendar events (source of truth is Google)."""

    __tablename__ = "calendar_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[str] = mapped_column(String(256), unique=True)
    title: Mapped[str] = mapped_column(String(300), default="")
    start_utc: Mapped[datetime] = mapped_column(DateTime, index=True)
    end_utc: Mapped[datetime] = mapped_column(DateTime)
    location: Mapped[str] = mapped_column(String(300), default="")
    all_day: Mapped[bool] = mapped_column(Boolean, default=False)
    reminded: Mapped[bool] = mapped_column(Boolean, default=False)
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class WaterEvent(Base):
    """Reminders sent and drinks logged — used to time the next reminder and
    count today's intake. Both kinds reset the reminder interval."""

    __tablename__ = "water_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(20))   # "reminder_sent" | "drank"
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_localnow)
