"""Settings read/write. Values are JSON-encoded in the DB and decoded by `type`
for the API. Writing emits `event.settings.changed` on the bus so services can
hot-reload (design decision D7)."""
from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from common.db.models import Setting
from common.schemas import SettingOut


def _decode(row: Setting):
    try:
        return json.loads(row.value)
    except (json.JSONDecodeError, TypeError):
        return row.value


def list_settings(s: Session, namespace: str | None = None) -> list[SettingOut]:
    stmt = select(Setting).order_by(Setting.namespace, Setting.key)
    if namespace:
        stmt = stmt.where(Setting.namespace == namespace)
    return [
        SettingOut(
            key=r.key, value=_decode(r), type=r.type,
            namespace=r.namespace, updated_at=r.updated_at,
        )
        for r in s.scalars(stmt).all()
    ]


def update_settings(s: Session, updates: list[tuple[str, object]]) -> list[str]:
    """Apply {key: value} updates. Returns the keys that actually changed."""
    changed: list[str] = []
    for key, value in updates:
        row = s.get(Setting, key)
        if row is None:
            continue  # unknown keys are ignored (dashboard only sends known ones)
        new = json.dumps(value)
        if new != row.value:
            row.value = new
            changed.append(key)
    s.flush()
    return changed
