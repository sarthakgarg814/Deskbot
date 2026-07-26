"""WebSocket hub: bridges the internal bus to browser clients.

Subscribes to a set of bus topics and fans each message out to every connected
browser as an envelope {topic, ts, data}. This is the live-update path for the
dashboard (docs/04-api-contract.md#websocket-ws).
"""
from __future__ import annotations

import asyncio
import logging
import time

from fastapi import WebSocket

from common.bus import Bus

log = logging.getLogger("deskbot.ws")

# Topics forwarded to browsers. More get added as services come online.
FORWARDED_TOPICS = ("system", "notes", "settings", "hardware", "camera", "presence")


class WsHub:
    def __init__(self, bus: Bus) -> None:
        self._bus = bus
        self._clients: set[WebSocket] = set()
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        for topic in FORWARDED_TOPICS:
            self._tasks.append(asyncio.create_task(self._pump(topic)))
        log.info("ws hub forwarding topics: %s", ", ".join(FORWARDED_TOPICS))

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        self._tasks.clear()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._clients.add(ws)
        # send the latest system snapshot immediately so the UI isn't blank
        snapshot = await self._bus.get_state("state:system")
        if snapshot is not None:
            await self._safe_send(ws, "system", snapshot)

    def disconnect(self, ws: WebSocket) -> None:
        self._clients.discard(ws)

    async def _pump(self, topic: str) -> None:
        async for payload in self._bus.subscribe(topic):
            await self.broadcast(topic, payload)

    async def broadcast(self, topic: str, data: dict) -> None:
        dead = []
        for ws in list(self._clients):
            if not await self._safe_send(ws, topic, data):
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    async def _safe_send(self, ws: WebSocket, topic: str, data: dict) -> bool:
        try:
            await ws.send_json({"topic": topic, "ts": time.time(), "data": data})
            return True
        except Exception:
            return False
