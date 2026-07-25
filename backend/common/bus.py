"""The message-bus seam (design decision D3).

Milestone 1 ships the in-process async backend below. When the `vision`/`voice`
processes come online we add a Redis-backed implementation of the SAME `Bus`
interface and select it by config — no caller changes. Everything the services
use goes through this interface:

    await bus.publish(topic, payload)          # fire-and-forget pub/sub
    async for msg in bus.subscribe(topic): ...  # consume a topic
    await bus.set_state(key, value, ttl=...)    # latest-value cache
    await bus.get_state(key)                     # read latest value

Topics/keys catalog: docs/04-api-contract.md
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncIterator, Protocol


class Bus(Protocol):
    async def publish(self, topic: str, payload: dict[str, Any]) -> None: ...
    def subscribe(self, topic: str) -> AsyncIterator[dict[str, Any]]: ...
    async def set_state(self, key: str, value: Any, ttl: float | None = None) -> None: ...
    async def get_state(self, key: str) -> Any | None: ...


class InProcessBus:
    """asyncio pub/sub + TTL state cache, all within one process (Milestone 1)."""

    def __init__(self) -> None:
        self._subs: dict[str, set[asyncio.Queue]] = {}
        self._state: dict[str, tuple[Any, float | None]] = {}  # key -> (value, expires_at)

    async def publish(self, topic: str, payload: dict[str, Any]) -> None:
        for q in list(self._subs.get(topic, ())):
            # drop-oldest on backpressure so a slow consumer can't stall producers
            if q.full():
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            q.put_nowait(payload)

    async def subscribe(self, topic: str) -> AsyncIterator[dict[str, Any]]:
        q: asyncio.Queue = asyncio.Queue(maxsize=64)
        self._subs.setdefault(topic, set()).add(q)
        try:
            while True:
                yield await q.get()
        finally:
            self._subs.get(topic, set()).discard(q)

    async def set_state(self, key: str, value: Any, ttl: float | None = None) -> None:
        expires = time.monotonic() + ttl if ttl else None
        self._state[key] = (value, expires)

    async def get_state(self, key: str) -> Any | None:
        entry = self._state.get(key)
        if entry is None:
            return None
        value, expires = entry
        if expires is not None and time.monotonic() > expires:
            self._state.pop(key, None)
            return None
        return value


def make_bus(backend: str = "inprocess") -> Bus:
    """Factory — swap to a RedisBus here when vision/voice land (D3)."""
    if backend in ("inprocess", "mock"):
        return InProcessBus()
    raise ValueError(f"unknown bus backend: {backend!r} (only 'inprocess' in Milestone 1)")
