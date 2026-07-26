"""Milestone 1 smoke test — the whole app boots and the core endpoints work
against the mock hardware backend. Runs anywhere (no Pi needed)."""
from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from core.main import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    # isolate the DB per test run
    from common import config as cfg_mod

    cfg_mod.load_config.cache_clear()
    monkeypatch.setattr(cfg_mod, "CONFIG_PATH", cfg_mod.CONFIG_PATH)  # keep defaults.yaml
    with TestClient(create_app()) as c:
        yield c


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_system_stats(client):
    data = client.get("/api/system").json()
    assert 0 <= data["ram_percent"] <= 100
    assert "services" in data


def test_settings_seeded_and_updatable(client):
    rows = client.get("/api/settings").json()
    assert len(rows) >= 20
    client.post("/api/settings", json=[{"key": "camera.track_fps", "value": 8}])
    row = next(r for r in client.get("/api/settings?ns=camera").json() if r["key"] == "camera.track_fps")
    assert row["value"] == 8


def test_notes_crud(client):
    created = client.post("/api/notes", json={"body": "call Rahul", "tags": ["todo"]}).json()
    nid = created["id"]
    assert created["title"] == "call Rahul"  # derived from body
    assert [n["id"] for n in client.get("/api/notes?q=Rahul").json()] == [nid]
    client.put(f"/api/notes/{nid}", json={"title": "Call Rahul back"})
    assert client.get(f"/api/notes/{nid}").json()["title"] == "Call Rahul back"
    assert client.delete(f"/api/notes/{nid}").status_code == 204


def test_hardware_stubs(client):
    assert client.post("/api/servo/test", json={"pan": 10, "tilt": 5}).json()["pan"] == 10
    assert client.post("/api/led/state", json={"state": "working"}).json()["state"] == "working"
    assert "lines" in client.get("/api/oled/preview").json()
