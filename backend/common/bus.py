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
import json
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


class RedisBus:
    """Async Redis-backed bus for the `core` consumer (pub/sub + state cache).
    Used when processes must talk across process boundaries (vision/voice, D3)."""

    def __init__(self, url: str = "redis://localhost:6379/0") -> None:
        import redis.asyncio as aioredis

        self._r = aioredis.from_url(url)

    async def publish(self, topic: str, payload: dict[str, Any]) -> None:
        await self._r.publish(topic, json.dumps(payload))

    async def subscribe(self, topic: str) -> AsyncIterator[dict[str, Any]]:
        pubsub = self._r.pubsub()
        await pubsub.subscribe(topic)
        try:
            async for msg in pubsub.listen():
                if msg.get("type") == "message":
                    yield json.loads(msg["data"])
        finally:
            await pubsub.unsubscribe(topic)
            await pubsub.aclose()

    async def set_state(self, key: str, value: Any, ttl: float | None = None) -> None:
        await self._r.set(key, json.dumps(value), ex=int(ttl) if ttl else None)

    async def get_state(self, key: str) -> Any | None:
        v = await self._r.get(key)
        return json.loads(v) if v is not None else None


class Publisher(Protocol):
    """Sync producer interface for standalone services (vision, hardware).
    Also exposes get_state so producers can read gate flags core mirrors."""
    def publish(self, topic: str, payload: dict[str, Any]) -> None: ...
    def set_state(self, key: str, value: Any, ttl: float | None = None) -> None: ...
    def get_state(self, key: str) -> Any | None: ...


class RedisPublisher:
    """Sync Redis producer — vision/hardware loops are synchronous."""

    def __init__(self, url: str = "redis://localhost:6379/0") -> None:
        import redis

        self._r = redis.Redis.from_url(url)

    def publish(self, topic: str, payload: dict[str, Any]) -> None:
        self._r.publish(topic, json.dumps(payload))

    def set_state(self, key: str, value: Any, ttl: float | None = None) -> None:
        self._r.set(key, json.dumps(value), ex=int(ttl) if ttl else None)

    def get_state(self, key: str) -> Any | None:
        v = self._r.get(key)
        return json.loads(v) if v is not None else None


class LogPublisher:
    """No-op producer that just logs — for laptop dev without Redis."""

    def __init__(self) -> None:
        import logging

        self._log = logging.getLogger("peekabot.bus.log")

    def publish(self, topic: str, payload: dict[str, Any]) -> None:
        self._log.debug("publish %s %s", topic, payload)

    def set_state(self, key: str, value: Any, ttl: float | None = None) -> None:
        self._log.debug("set_state %s %s", key, value)

    def get_state(self, key: str) -> Any | None:
        return None


class RedisSubscriber:
    """Sync pub/sub consumer for standalone services that must *receive* commands
    (the hardware arbiter subscribes to cmd.servo.*). Run `listen()` in a thread."""

    def __init__(self, url: str = "redis://localhost:6379/0") -> None:
        import redis

        self._r = redis.Redis.from_url(url)

    def listen(self, *topics: str):
        ps = self._r.pubsub()
        ps.subscribe(*topics)
        for msg in ps.listen():
            if msg.get("type") != "message":
                continue
            ch = msg["channel"]
            yield (ch.decode() if isinstance(ch, bytes) else ch), json.loads(msg["data"])


class NullSubscriber:
    """No-op subscriber for laptop/mock (no cross-process bus) — never yields."""

    def listen(self, *topics: str):
        while True:
            time.sleep(3600)
            yield  # pragma: no cover


def make_subscriber(backend: str = "redis", url: str = "redis://localhost:6379/0"):
    if backend == "redis":
        return RedisSubscriber(url)
    return NullSubscriber()


def make_bus(backend: str = "inprocess", url: str = "redis://localhost:6379/0") -> Bus:
    """Async bus for the core consumer. inprocess (single process) | redis (D3)."""
    if backend in ("inprocess", "mock"):
        return InProcessBus()
    if backend == "redis":
        return RedisBus(url)
    raise ValueError(f"unknown bus backend: {backend!r}")


def make_publisher(backend: str = "redis", url: str = "redis://localhost:6379/0") -> Publisher:
    """Sync publisher for producer services (vision). redis on the Pi; log for dev."""
    if backend == "redis":
        return RedisPublisher(url)
    return LogPublisher()
