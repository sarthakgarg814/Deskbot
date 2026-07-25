"""Background jobs (APScheduler). Milestone 1 runs the 1 Hz hardware-monitor
sampler that feeds `state:system` and the `system` topic; later milestones add
calendar sync, reminder checks, and mood rollups here.
"""
from __future__ import annotations

import logging
from dataclasses import asdict

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from common.bus import Bus
from hardware.hal.factory import Hardware

log = logging.getLogger("deskbot.scheduler")


class Scheduler:
    def __init__(self, bus: Bus, hardware: Hardware) -> None:
        self._bus = bus
        self._hw = hardware
        self._sched = AsyncIOScheduler()

    def start(self) -> None:
        self._sched.add_job(self._sample_system, "interval", seconds=1, id="system_sample")
        self._sched.start()
        log.info("scheduler started (system sampler @ 1 Hz)")

    def shutdown(self) -> None:
        if self._sched.running:
            self._sched.shutdown(wait=False)

    async def _sample_system(self) -> None:
        stats = self._hw.monitor.sample()
        payload = asdict(stats)
        payload["services"] = {"core": True, "hardware": self._hw.backend == "mock" or True}
        await self._bus.set_state("state:system", payload, ttl=5)
        await self._bus.publish("system", payload)
