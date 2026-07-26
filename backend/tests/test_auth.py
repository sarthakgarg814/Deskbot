"""Auth: guarded endpoints need a token; login/change-password work."""
from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from core.main import create_app


@pytest.fixture
def app_client():
    from common import config as cfg_mod

    cfg_mod.load_config.cache_clear()
    with TestClient(create_app()) as c:
        yield c


def test_guarded_endpoint_requires_token(app_client):
    assert app_client.get("/api/system").status_code == 401       # no token
    assert app_client.get("/api/health").status_code == 200        # public
    assert app_client.get("/api/auth/status").status_code == 200   # public


def test_login_and_access(app_client):
    assert app_client.post("/api/auth/login", json={"password": "nope"}).status_code == 401
    tok = app_client.post("/api/auth/login", json={"password": "deskbot"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    assert app_client.get("/api/system", headers=h).status_code == 200


def test_change_password(app_client):
    tok = app_client.post("/api/auth/login", json={"password": "deskbot"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    # wrong current password rejected
    assert app_client.post("/api/auth/change",
                           json={"old_password": "x", "new_password": "abcd"}, headers=h).status_code == 400
    # change it
    assert app_client.post("/api/auth/change",
                           json={"old_password": "deskbot", "new_password": "s3cret"}, headers=h).status_code == 200
    # old password no longer works, new one does
    assert app_client.post("/api/auth/login", json={"password": "deskbot"}).status_code == 401
    tok2 = app_client.post("/api/auth/login", json={"password": "s3cret"}).json()["token"]
    assert tok2
    # restore the default so other tests sharing the repo DB still authenticate
    app_client.post("/api/auth/change",
                    json={"old_password": "s3cret", "new_password": "deskbot"},
                    headers={"Authorization": f"Bearer {tok2}"})
