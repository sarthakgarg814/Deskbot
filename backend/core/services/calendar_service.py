"""Google Calendar sync (read-only). Google libraries are imported lazily so
`core` runs without them until you connect. Events are cached in calendar_events;
Google is the source of truth. All stored times are UTC-naive; the API returns
ISO+Z so the browser renders local time.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

# Google often returns the granted scope in a slightly different form than
# requested; without this, oauthlib raises "Scope has changed" on token exchange.
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

from sqlalchemy import select
from sqlalchemy.orm import Session

from common.config import load_config
from common.db.models import CalendarEvent

log = logging.getLogger("deskbot.calendar")
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


REDIRECT_URI = "http://localhost"   # Google auto-allows loopback for Desktop clients


def auth_status() -> dict:
    cfg = load_config()
    return {
        "has_client_secret": cfg.google_client_secret.exists(),
        "connected": cfg.google_token.exists(),
    }


def save_client_secret(content: str) -> None:
    import json

    data = json.loads(content)                       # validate it's JSON
    if not ("installed" in data or "web" in data):
        raise ValueError("not a Google OAuth client JSON (expected 'installed'/'web')")
    cfg = load_config()
    cfg.google_client_secret.parent.mkdir(parents=True, exist_ok=True)
    cfg.google_client_secret.write_text(content)


def _flow():
    from google_auth_oauthlib.flow import Flow

    cfg = load_config()
    return Flow.from_client_secrets_file(
        str(cfg.google_client_secret), scopes=SCOPES, redirect_uri=REDIRECT_URI
    )


def _verifier_path():
    return load_config().google_client_secret.parent / ".pkce_verifier"


def auth_url() -> str:
    flow = _flow()
    url, _ = flow.authorization_url(prompt="consent", access_type="offline")
    # PKCE: stash the verifier so the (separate) exchange request can reuse it
    _verifier_path().write_text(getattr(flow, "code_verifier", None) or "")
    return url


def exchange(code_or_url: str) -> None:
    """Exchange the pasted code (or the whole redirected URL) for a token."""
    import re

    code = code_or_url.strip()
    m = re.search(r"[?&]code=([^&]+)", code)
    if m:
        from urllib.parse import unquote

        code = unquote(m.group(1))

    flow = _flow()
    vp = _verifier_path()
    if vp.exists():
        v = vp.read_text().strip()
        if v:
            flow.code_verifier = v
    flow.fetch_token(code=code)
    cfg = load_config()
    cfg.google_token.write_text(flow.credentials.to_json())
    if vp.exists():
        vp.unlink()


def disconnect() -> None:
    cfg = load_config()
    if cfg.google_token.exists():
        cfg.google_token.unlink()


def config(s: Session) -> dict:
    from core.services.settings_service import get_value

    ids = get_value(s, "calendar.enabled_ids", [])
    return {
        "enabled": bool(get_value(s, "calendar.enabled", False)),
        "sync_min": int(get_value(s, "calendar.sync_min", 15)),
        "reminder_min": int(get_value(s, "calendar.reminder_min", 5)),
        "hide_busy": bool(get_value(s, "calendar.hide_busy", False)),
        "meeting_mode": bool(get_value(s, "calendar.meeting_mode", True)),
        "enabled_ids": [str(x) for x in ids] if isinstance(ids, list) else [],
    }


def calendars(s: Session) -> list[dict]:
    """List the account's calendars + whether each is included in DeskBot."""
    creds = _credentials()
    if creds is None:
        return []
    from googleapiclient.discovery import build

    svc = build("calendar", "v3", credentials=creds, cache_discovery=False)
    items = svc.calendarList().list().execute().get("items", [])
    ids = config(s)["enabled_ids"]
    out = []
    for c in items:
        cid = c["id"]
        enabled = (cid in ids) if ids else bool(c.get("selected") or c.get("primary"))
        out.append({
            "id": cid,
            "name": c.get("summaryOverride") or c.get("summary") or cid,
            "primary": bool(c.get("primary")),
            "enabled": enabled,
        })
    return out


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
    now_naive = now.replace(tzinfo=None)
    time_min, time_max = now.isoformat(), (now + timedelta(days=7)).isoformat()

    # which calendars to pull: the user's explicit selection, else all visible ones
    cals = svc.calendarList().list().execute().get("items", [])
    chosen = config(s)["enabled_ids"]
    if chosen:
        cal_ids = [c["id"] for c in cals if c["id"] in chosen] or ["primary"]
    else:
        cal_ids = [c["id"] for c in cals if c.get("selected") or c.get("primary")] or ["primary"]
    cal_name = {c["id"]: (c.get("summaryOverride") or c.get("summary") or c["id"]) for c in cals}
    cal_primary = {c["id"]: bool(c.get("primary")) for c in cals}

    seen: set[str] = set()
    total = 0
    for cid in cal_ids:
        try:
            result = svc.events().list(
                calendarId=cid, timeMin=time_min, timeMax=time_max,
                singleEvents=True, orderBy="startTime", maxResults=50,
            ).execute()
        except Exception as e:  # noqa: BLE001 — a single bad calendar shouldn't stop the rest
            log.warning("skip calendar %s: %s", cid, e)
            continue
        for it in result.get("items", []):
            ext = f"{cid}::{it['id']}"          # unique across calendars
            seen.add(ext)
            row = s.scalar(select(CalendarEvent).where(CalendarEvent.external_id == ext))
            if row is None:
                row = CalendarEvent(external_id=ext)
                s.add(row)
            row.title = it.get("summary") or "Busy"    # free/busy-shared events have no title
            row.start_utc = _parse(it["start"].get("dateTime") or it["start"].get("date"))
            row.end_utc = _parse(it["end"].get("dateTime") or it["end"].get("date"))
            row.location = it.get("location", "") or ""
            row.source = cal_name.get(cid, "")
            row.primary = cal_primary.get(cid, False)
            row.all_day = "date" in it["start"]
            row.synced_at = now_naive
            total += 1

    # drop stale/cancelled events that already ended
    for row in s.scalars(select(CalendarEvent)).all():
        if row.external_id not in seen and row.end_utc < now_naive:
            s.delete(row)
    s.flush()
    log.info("calendar synced: %d events across %d calendars", total, len(cal_ids))
    return total


def _out(r: CalendarEvent) -> dict:
    return {
        "id": r.id, "title": r.title,
        "start": r.start_utc.isoformat() + "Z", "end": r.end_utc.isoformat() + "Z",
        "location": r.location, "source": r.source, "primary": r.primary,
        "all_day": r.all_day,
    }


def _base_query(s: Session):
    q = select(CalendarEvent)
    if config(s)["hide_busy"]:
        q = q.where(CalendarEvent.title != "Busy")
    return q


def _local_day_bounds() -> tuple[datetime, datetime]:
    now_l = datetime.now().astimezone()
    start_l = now_l.replace(hour=0, minute=0, second=0, microsecond=0)
    to_utc = lambda d: d.astimezone(timezone.utc).replace(tzinfo=None)
    return to_utc(start_l), to_utc(start_l + timedelta(days=1))


def today(s: Session) -> list[dict]:
    start, end = _local_day_bounds()
    rows = s.scalars(
        _base_query(s).where(CalendarEvent.start_utc >= start, CalendarEvent.start_utc < end)
        .order_by(CalendarEvent.start_utc)
    ).all()
    return [_out(r) for r in rows]


def upcoming(s: Session, limit: int = 10) -> list[dict]:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    rows = s.scalars(
        _base_query(s).where(CalendarEvent.end_utc >= now)
        .order_by(CalendarEvent.start_utc).limit(limit)
    ).all()
    return [_out(r) for r in rows]


def next_event(s: Session) -> dict | None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    r = s.scalars(
        _base_query(s).where(CalendarEvent.start_utc >= now)
        .order_by(CalendarEvent.start_utc).limit(1)
    ).first()
    return _out(r) if r else None


def due_meeting(s: Session, within_min: int):
    """The next unreminded meeting starting within `within_min` (or None)."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    horizon = now + timedelta(minutes=within_min)
    return s.scalars(
        _base_query(s).where(
            CalendarEvent.reminded == False,  # noqa: E712
            CalendarEvent.start_utc >= now,
            CalendarEvent.start_utc <= horizon,
        ).order_by(CalendarEvent.start_utc).limit(1)
    ).first()


def due_started(s: Session):
    """A meeting that has just started and hasn't had its 'now' alert (or None)."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return s.scalars(
        _base_query(s).where(
            CalendarEvent.started_notified == False,  # noqa: E712
            CalendarEvent.start_utc <= now,
            CalendarEvent.start_utc >= now - timedelta(minutes=2),
        ).order_by(CalendarEvent.start_utc).limit(1)
    ).first()
