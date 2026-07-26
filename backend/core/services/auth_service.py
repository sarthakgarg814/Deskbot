"""Single-user password auth for the dashboard + API. Stdlib only (pbkdf2 hash,
HMAC-signed bearer token). Default password is 'peekabot' until the user changes
it (then a pbkdf2 hash is stored in settings). The signing secret lives in
config/.session_secret (gitignored, per-machine).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time

from sqlalchemy.orm import Session

from common.config import REPO_ROOT
from common.db.models import Setting

from .settings_service import get_value

DEFAULT_PASSWORD = "peekabot"
TOKEN_TTL = 30 * 24 * 3600            # 30 days
_SECRET_PATH = REPO_ROOT / "config" / ".session_secret"
_PBKDF2_ROUNDS = 200_000


def _secret() -> bytes:
    if _SECRET_PATH.exists():
        return _SECRET_PATH.read_bytes()
    _SECRET_PATH.parent.mkdir(parents=True, exist_ok=True)
    s = secrets.token_bytes(32)
    _SECRET_PATH.write_bytes(s)
    try:
        _SECRET_PATH.chmod(0o600)
    except OSError:
        pass
    return s


# --- password ---
def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, _PBKDF2_ROUNDS)
    return f"{salt.hex()}${h.hex()}"


def _check_hash(pw: str, stored: str) -> bool:
    try:
        salt_hex, h_hex = stored.split("$", 1)
        h = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt_hex), _PBKDF2_ROUNDS)
        return hmac.compare_digest(h.hex(), h_hex)
    except Exception:  # noqa: BLE001
        return False


def is_default(s: Session) -> bool:
    return not get_value(s, "auth.password_hash", None)


def verify_password(s: Session, pw: str) -> bool:
    stored = get_value(s, "auth.password_hash", None)
    if not stored:
        return pw == DEFAULT_PASSWORD
    return _check_hash(pw, str(stored))


def set_password(s: Session, new_pw: str) -> None:
    row = s.get(Setting, "auth.password_hash")
    value = json.dumps(hash_password(new_pw))
    if row is None:
        s.add(Setting(key="auth.password_hash", value=value, type="str", namespace="auth"))
    else:
        row.value = value
    s.flush()


# --- token ---
def make_token() -> str:
    exp = int(time.time()) + TOKEN_TTL
    msg = f"peekabot:{exp}"
    sig = hmac.new(_secret(), msg.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{msg}:{sig}".encode()).decode()


def verify_token(token: str | None) -> bool:
    if not token:
        return False
    try:
        raw = base64.urlsafe_b64decode(token.encode()).decode()
        msg, sig = raw.rsplit(":", 1)
        if time.time() > int(msg.split(":")[1]):
            return False
        expected = hmac.new(_secret(), msg.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig, expected)
    except Exception:  # noqa: BLE001
        return False
