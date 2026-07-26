"""Water-reminder logic: a presence-gated, schedule-bounded timed nudge.

Not vision-based water detection (dropped, D8) — just "remind me to drink every N
minutes while I'm here, within active hours/days." All times are LOCAL (the Pi's
clock); water events store local naive time so the schedule math is trivial.
"""
from __future__ import annotations

from datetime import datetime, time as dtime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from common.db.models import WaterEvent

from .settings_service import get_value


def _now() -> datetime:
    return datetime.now()


def _parse_hm(s: str, default: dtime) -> dtime:
    try:
        h, m = str(s).split(":")
        return dtime(int(h), int(m))
    except Exception:  # noqa: BLE001
        return default


def config(s: Session) -> dict:
    days = get_value(s, "water.active_days", [0, 1, 2, 3, 4, 5, 6])
    if not isinstance(days, list):
        days = [0, 1, 2, 3, 4, 5, 6]
    return {
        "reminder_enabled": bool(get_value(s, "water.reminder_enabled", True)),
        "interval_min": int(get_value(s, "water.interval_min", 60)),
        "only_when_present": bool(get_value(s, "water.only_when_present", True)),
        "buzzer_enabled": bool(get_value(s, "water.buzzer_enabled", True)),
        "daily_goal": int(get_value(s, "water.daily_goal", 8)),
        "active_start": str(get_value(s, "water.active_start", "09:00")),
        "active_end": str(get_value(s, "water.active_end", "21:00")),
        "active_days": [int(d) for d in days],
        "reset_hour": int(get_value(s, "water.reset_hour", 0)),
    }


def is_active_now(cfg: dict, now: datetime | None = None) -> bool:
    now = now or _now()
    if now.weekday() not in cfg["active_days"]:
        return False
    start = _parse_hm(cfg["active_start"], dtime(9, 0))
    end = _parse_hm(cfg["active_end"], dtime(21, 0))
    t = now.time()
    return start <= t <= end if start <= end else (t >= start or t <= end)


def _day_start(cfg: dict, now: datetime | None = None) -> datetime:
    now = now or _now()
    reset = now.replace(hour=cfg["reset_hour"], minute=0, second=0, microsecond=0)
    return reset if now >= reset else reset - timedelta(days=1)


def _baseline(s: Session) -> datetime | None:
    row = s.scalars(select(WaterEvent).order_by(WaterEvent.created_at.desc()).limit(1)).first()
    return row.created_at if row else None


def count_today(s: Session, cfg: dict) -> int:
    start = _day_start(cfg)
    return int(
        s.scalar(
            select(func.count(WaterEvent.id)).where(
                WaterEvent.kind == "drank", WaterEvent.created_at >= start
            )
        )
        or 0
    )


def due(s: Session, present: bool) -> bool:
    cfg = config(s)
    if not cfg["reminder_enabled"] or not is_active_now(cfg):
        return False
    if cfg["only_when_present"] and not present:
        return False
    last = _baseline(s)
    return last is None or (_now() - last) >= timedelta(minutes=cfg["interval_min"])


def status(s: Session) -> dict:
    cfg = config(s)
    last = _baseline(s)
    interval = timedelta(minutes=cfg["interval_min"])
    secs_next = 0 if last is None else max(0, int((last + interval - _now()).total_seconds()))
    return {
        **cfg,
        "count_today": count_today(s, cfg),
        "active_now": is_active_now(cfg),
        "last_event": last.isoformat() if last else None,
        "seconds_until_next": secs_next,
    }


def record(s: Session, kind: str) -> None:
    s.add(WaterEvent(kind=kind))
    s.flush()
