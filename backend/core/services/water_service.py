"""Water-reminder logic: a presence-gated timed nudge. Not vision-based water
detection (that was dropped, D8) — just "remind me to drink every N minutes,
but only when I'm actually here." Both a fired reminder and a logged drink reset
the interval.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from common.db.models import WaterEvent

from .settings_service import get_value


def _now() -> datetime:
    return datetime.now(timezone.utc)


def config(s: Session) -> dict:
    return {
        "reminder_enabled": bool(get_value(s, "water.reminder_enabled", True)),
        "interval_min": int(get_value(s, "water.interval_min", 60)),
        "only_when_present": bool(get_value(s, "water.only_when_present", True)),
        "buzzer_enabled": bool(get_value(s, "water.buzzer_enabled", True)),
        "daily_goal": int(get_value(s, "water.daily_goal", 8)),
    }


def _baseline(s: Session) -> datetime | None:
    """Latest reminder-or-drink — the interval counts from here."""
    row = s.scalars(select(WaterEvent).order_by(WaterEvent.created_at.desc()).limit(1)).first()
    return row.created_at.replace(tzinfo=timezone.utc) if row else None


def count_today(s: Session) -> int:
    start = _now().replace(hour=0, minute=0, second=0, microsecond=0)
    return int(
        s.scalar(
            select(func.count(WaterEvent.id)).where(
                WaterEvent.kind == "drank", WaterEvent.created_at >= start
            )
        )
        or 0
    )


def status(s: Session) -> dict:
    cfg = config(s)
    last = _baseline(s)
    interval = timedelta(minutes=cfg["interval_min"])
    if last is None:
        secs_next = 0
    else:
        secs_next = max(0, int((last + interval - _now()).total_seconds()))
    return {
        **cfg,
        "count_today": count_today(s),
        "last_event": last.isoformat() if last else None,
        "seconds_until_next": secs_next,
    }


def due(s: Session, present: bool) -> bool:
    """Should a reminder fire right now?"""
    cfg = config(s)
    if not cfg["reminder_enabled"]:
        return False
    if cfg["only_when_present"] and not present:
        return False
    last = _baseline(s)
    if last is None:
        return True
    return _now() - last >= timedelta(minutes=cfg["interval_min"])


def record(s: Session, kind: str) -> None:
    s.add(WaterEvent(kind=kind))
    s.flush()
