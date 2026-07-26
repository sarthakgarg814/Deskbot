"""Google Calendar sync (read-only). Google libraries are imported lazily so
`core` runs without them until you connect. Events are cached in calendar_events;
Google is the source of truth. All stored times are UTC-naive; the API returns
ISO+Z so the browser renders local time.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from common.config import load_config
from common.db.models import CalendarEvent

log = logging.getLogger("deskbot.calendar")
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def auth_status() -> dict:
    cfg = load_config()
    return {
        "has_client_secret": cfg.google_client_secret.exists(),
        "connected": cfg.google_token.exists(),
    }


def _credentials():
    """Load + refresh the stored token; None if not connected/invalid."""
    cfg = load_config()
    if not cfg.google_token.exists():
        return None
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    creds = Credentials.from_authorized_user_file(str(cfg.google_token), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        cfg.google_token.write_text(creds.to_json())
    return creds if (creds and creds.valid) else None


def _parse(dt: str) -> datetime:
    """Google date/dateTime → UTC-naive datetime."""
    if len(dt) == 10:                       # all-day 'YYYY-MM-DD'
        return datetime.fromisoformat(dt)
    d = datetime.fromisoformat(dt.replace("Z", "+00:00"))
    return d.astimezone(timezone.utc).replace(tzinfo=None) if d.tzinfo else d


def sync(s: Session) -> int:
    creds = _credentials()
    if creds is None:
        return 0
    from googleapiclient.discovery import build

    svc = build("calendar", "v3", credentials=creds, cache_discovery=False)
    now = datetime.now(timezone.utc)
    result = svc.events().list(
        calendarId="primary", timeMin=now.isoformat(),
        timeMax=(now + timedelta(days=7)).isoformat(),
        singleEvents=True, orderBy="startTime", maxResults=50,
    ).execute()
    items = result.get("items", [])

    now_naive = now.replace(tzinfo=None)
    seen: set[str] = set()
    for it in items:
        ext = it["id"]
        seen.add(ext)
        row = s.scalar(select(CalendarEvent).where(CalendarEvent.external_id == ext))
        if row is None:
            row = CalendarEvent(external_id=ext)
            s.add(row)
        row.title = it.get("summary", "(no title)")
        row.start_utc = _parse(it["start"].get("dateTime") or it["start"].get("date"))
        row.end_utc = _parse(it["end"].get("dateTime") or it["end"].get("date"))
        row.location = it.get("location", "") or ""
        row.all_day = "date" in it["start"]
        row.synced_at = now_naive

    # drop stale/cancelled events that already ended
    for row in s.scalars(select(CalendarEvent)).all():
        if row.external_id not in seen and row.end_utc < now_naive:
            s.delete(row)
    s.flush()
    log.info("calendar synced: %d events", len(items))
    return len(items)


def _out(r: CalendarEvent) -> dict:
    return {
        "id": r.id, "title": r.title,
        "start": r.start_utc.isoformat() + "Z", "end": r.end_utc.isoformat() + "Z",
        "location": r.location, "all_day": r.all_day,
    }


def _local_day_bounds() -> tuple[datetime, datetime]:
    now_l = datetime.now().astimezone()
    start_l = now_l.replace(hour=0, minute=0, second=0, microsecond=0)
    to_utc = lambda d: d.astimezone(timezone.utc).replace(tzinfo=None)
    return to_utc(start_l), to_utc(start_l + timedelta(days=1))


def today(s: Session) -> list[dict]:
    start, end = _local_day_bounds()
    rows = s.scalars(
        select(CalendarEvent).where(CalendarEvent.start_utc >= start,
                                    CalendarEvent.start_utc < end)
        .order_by(CalendarEvent.start_utc)
    ).all()
    return [_out(r) for r in rows]


def upcoming(s: Session, limit: int = 10) -> list[dict]:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    rows = s.scalars(
        select(CalendarEvent).where(CalendarEvent.end_utc >= now)
        .order_by(CalendarEvent.start_utc).limit(limit)
    ).all()
    return [_out(r) for r in rows]


def due_meeting(s: Session, within_min: int):
    """The next unreminded meeting starting within `within_min` (or None)."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    horizon = now + timedelta(minutes=within_min)
    return s.scalars(
        select(CalendarEvent).where(
            CalendarEvent.reminded == False,  # noqa: E712
            CalendarEvent.start_utc >= now,
            CalendarEvent.start_utc <= horizon,
        ).order_by(CalendarEvent.start_utc).limit(1)
    ).first()
