"""Background jobs (APScheduler). Milestone 1 runs the 1 Hz hardware-monitor
sampler that feeds `state:system` and the `system` topic; later milestones add
calendar sync, reminder checks, and mood rollups here.
"""
from __future__ import annotations

import logging
from dataclasses import asdict

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from common.bus import Bus
from hardware.hal.base import HardwareMonitor

log = logging.getLogger("deskbot.scheduler")


class Scheduler:
    def __init__(self, bus: Bus, monitor: HardwareMonitor) -> None:
        self._bus = bus
        self._monitor = monitor
        self._sched = AsyncIOScheduler()
        self._last_cal_sync = 0.0

    def start(self) -> None:
        self._sched.add_job(self._sample_system, "interval", seconds=1, id="system_sample")
        self._sched.add_job(self._water_check, "interval", seconds=30, id="water_check")
        self._sched.add_job(self._calendar_sync, "interval", seconds=60, id="calendar_sync")
        self._sched.add_job(self._meeting_check, "interval", seconds=45, id="meeting_check")
        self._sched.start()
        log.info("scheduler started (system 1Hz, water 30s, calendar self-paced, meetings 45s)")

    def shutdown(self) -> None:
        if self._sched.running:
            self._sched.shutdown(wait=False)

    async def _sample_system(self) -> None:
        payload = asdict(self._monitor.sample())
        payload["services"] = {"core": True}
        await self._bus.set_state("state:system", payload, ttl=5)
        await self._bus.publish("system", payload)

    async def _water_check(self) -> None:
        """Fire a presence-gated water reminder when due (alerts: dashboard toast,
        OLED water animation, buzzer, LED)."""
        from common.db import session_scope
        from core.services import water_service

        cam = await self._bus.get_state("state:camera") or {}
        present = bool(cam.get("present"))

        fire, buzzer = False, False
        with session_scope() as s:
            if water_service.due(s, present):
                water_service.record(s, "reminder_sent")
                buzzer = water_service.config(s)["buzzer_enabled"]
                fire = True

        if not fire:
            return
        log.info("water reminder fired (present=%s)", present)
        await self._bus.publish("reminder", {"type": "water", "message": "Time to drink water 💧"})
        await self._bus.set_state("state:oled.alert", {"type": "water"}, ttl=8)
        await self._bus.publish("cmd.led.state", {"state": "reminder"})
        if buzzer:
            await self._bus.publish("cmd.buzzer.beep", {"count": 2})

    async def _calendar_sync(self) -> None:
        import time as _t

        from common.db import session_scope
        from core.services import calendar_service

        with session_scope() as s:
            cfg = calendar_service.config(s)
        if not cfg["enabled"]:
            return
        now = _t.monotonic()
        if now - self._last_cal_sync < cfg["sync_min"] * 60:  # self-paced (live setting)
            return
        self._last_cal_sync = now
        try:
            with session_scope() as s:
                n = calendar_service.sync(s)
            await self._bus.publish("calendar", {"synced": n})
        except Exception as e:  # noqa: BLE001 — missing libs / auth / network
            log.warning("calendar sync failed: %s", e)

    async def _meeting_check(self) -> None:
        from datetime import datetime, timezone

        from common.db import session_scope
        from core.services import calendar_service

        up = st = None
        with session_scope() as s:
            cfg = calendar_service.config(s)
            if not cfg["enabled"]:
                return
            nxt = calendar_service.next_event(s)
            ev = calendar_service.due_meeting(s, cfg["reminder_min"])
            if ev is not None:
                start = ev.start_utc.replace(tzinfo=timezone.utc)
                mins = max(0, int((start - datetime.now(timezone.utc)).total_seconds() // 60))
                up = {"title": ev.title, "mins": mins, "source": ev.source, "primary": ev.primary}
                ev.reminded = True
            sv = calendar_service.due_started(s) if cfg["meeting_mode"] else None
            if sv is not None:
                st = {"title": sv.title, "source": sv.source, "primary": sv.primary}
                sv.started_notified = True

        # next event → OLED stats footer + dashboard
        await self._bus.set_state("state:calendar", {"next": nxt}, ttl=180)

        if up:
            log.info("meeting reminder: %s in %dm", up["title"], up["mins"])
            await self._bus.publish("reminder", {"type": "meeting",
                                                 "message": f'{up["title"]} in {up["mins"]} min'})
            await self._bus.set_state("state:oled.alert",
                                      {"type": "meeting", "phase": "upcoming", **up}, ttl=12)
            await self._bus.publish("cmd.led.state", {"state": "meeting"})
            await self._bus.publish("cmd.buzzer.beep", {"count": 3})
        if st:
            log.info("meeting started: %s", st["title"])
            await self._bus.publish("reminder", {"type": "meeting",
                                                 "message": f'{st["title"]} — now'})
            await self._bus.set_state("state:oled.alert",
                                      {"type": "meeting", "phase": "started", **st}, ttl=10)
            await self._bus.publish("cmd.led.state", {"state": "meeting"})
            await self._bus.publish("cmd.buzzer.beep", {"count": 1})
