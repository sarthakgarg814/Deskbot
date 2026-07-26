"""Water-reminder logic: presence gating + interval reset (settings fall back to
defaults, so no seeding needed)."""
from __future__ import annotations

import json

from common.db import init_db, session_scope
from common.db.models import Setting
from core.services import water_service


def _always_active(s):
    # pin the schedule window wide open so the test doesn't depend on wall-clock
    s.add(Setting(key="water.active_start", value=json.dumps("00:00"), type="str", namespace="water"))
    s.add(Setting(key="water.active_end", value=json.dumps("23:59"), type="str", namespace="water"))
    s.flush()


def test_reminder_presence_gating_and_reset(tmp_path):
    init_db(tmp_path / "water.db")

    with session_scope() as s:
        _always_active(s)
        # never reminded → due, but only when present
        assert water_service.due(s, present=True) is True
        assert water_service.due(s, present=False) is False   # only_when_present default True

        water_service.record(s, "reminder_sent")              # fire → resets interval
        assert water_service.due(s, present=True) is False

    with session_scope() as s:
        # a logged drink counts toward today and also resets the interval
        water_service.record(s, "drank")
        st = water_service.status(s)
        assert st["count_today"] == 1
        assert st["seconds_until_next"] > 0
