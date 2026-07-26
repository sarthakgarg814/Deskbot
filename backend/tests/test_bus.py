"""Exercises the Redis bus code paths with fakeredis — the paths that use
json.dumps/loads and never ran under the in-process bus. Guards against the
'json not imported' class of bug.
"""
from __future__ import annotations

import asyncio

import fakeredis
import pytest

from common.bus import InProcessBus, RedisBus, RedisPublisher


@pytest.fixture
def fake_redis(monkeypatch):
    """Point RedisBus (async) and RedisPublisher (sync) at a shared fake server."""
    import redis
    import redis.asyncio

    server = fakeredis.FakeServer()
    monkeypatch.setattr(
        redis.Redis, "from_url",
        staticmethod(lambda *a, **k: fakeredis.FakeStrictRedis(server=server)),
    )
    monkeypatch.setattr(
        redis.asyncio, "from_url",
        lambda *a, **k: fakeredis.FakeAsyncRedis(server=server),
    )
    return server


def test_publisher_set_and_bus_get_roundtrip(fake_redis):
    pub = RedisPublisher("redis://x")           # sync producer (vision)
    bus = RedisBus("redis://x")                 # async consumer (core)
    pub.set_state("state:camera", {"fps": 17.1, "present": True})
    got = asyncio.run(bus.get_state("state:camera"))
    assert got == {"fps": 17.1, "present": True}


def test_publisher_publish_serializes(fake_redis):
    # would have raised NameError: json before the fix
    RedisPublisher("redis://x").publish("camera", {"err_x": -0.04, "faces": 1})


async def test_bus_publish_subscribe_roundtrip(fake_redis):
    bus = RedisBus("redis://x")
    agen = bus.subscribe("presence")
    task = asyncio.create_task(agen.__anext__())
    await asyncio.sleep(0.05)                   # let the subscription register
    await bus.publish("presence", {"state": "present"})
    msg = await asyncio.wait_for(task, timeout=2)
    assert msg == {"state": "present"}
    await agen.aclose()


async def test_inprocess_bus_still_works():
    bus = InProcessBus()
    await bus.set_state("state:x", {"n": 1})
    assert await bus.get_state("state:x") == {"n": 1}
