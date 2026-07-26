"""The tiny auto-migration adds columns that were added to a model after the
table already existed (the calendar_events.primary case)."""
from __future__ import annotations

from sqlalchemy import create_engine, inspect, text

from common.db import models  # noqa: F401 — register models on Base.metadata
from common.db.base import _ensure_columns


def test_ensure_columns_adds_missing(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'm.db'}")
    # an OLD calendar_events table, missing primary/started_notified
    with eng.begin() as c:
        c.execute(text(
            "CREATE TABLE calendar_events ("
            "id INTEGER PRIMARY KEY, external_id VARCHAR, title VARCHAR, "
            "start_utc DATETIME, end_utc DATETIME, location VARCHAR, source VARCHAR, "
            "all_day BOOLEAN, reminded BOOLEAN, synced_at DATETIME)"
        ))
    _ensure_columns(eng)
    cols = {c["name"] for c in inspect(eng).get_columns("calendar_events")}
    assert "primary" in cols
    assert "started_notified" in cols
    _ensure_columns(eng)  # idempotent — no error on a second run
