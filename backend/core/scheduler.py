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

    def start(self) -> None:
        self._sched.add_job(self._sample_system, "interval", seconds=1, id="system_sample")
        self._sched.add_job(self._water_check, "interval", seconds=30, id="water_check")
        self._sched.start()
        log.info("scheduler started (system sampler @ 1 Hz, water check @ 30 s)")

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
