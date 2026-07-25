"""Seed the DB on first boot: a default user + the settings rows from
config/defaults.yaml. Idempotent — existing keys are never overwritten, so
dashboard edits survive restarts and re-seeds.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select

from .base import session_scope
from .models import Setting, User

log = logging.getLogger("deskbot")


def _encode(value: Any) -> str:
    return json.dumps(value)


def seed(seed_settings: list[dict[str, Any]]) -> None:
    with session_scope() as s:
        if s.scalar(select(User).limit(1)) is None:
            s.add(User(name="me", is_default=True))
            log.info("seeded default user")

        existing = {row.key for row in s.scalars(select(Setting)).all()}
        added = 0
        for item in seed_settings:
            key = item["key"]
            if key in existing:
                continue
            s.add(
                Setting(
                    key=key,
                    value=_encode(item["value"]),
                    type=item.get("type", "str"),
                    namespace=item.get("namespace", "system"),
                )
            )
            added += 1
        if added:
            log.info("seeded %d settings", added)
