"""WiFi management via NetworkManager (`nmcli`) — Raspberry Pi OS Trixie's
default network stack. Needs privileges to connect (core runs as root on the Pi).
Degrades gracefully when nmcli isn't present (e.g. a dev laptop).
"""
from __future__ import annotations

import re
import shutil
import subprocess


def available() -> bool:
    return shutil.which("nmcli") is not None


def _run(args: list[str], timeout: int = 20) -> subprocess.CompletedProcess:
    return subprocess.run(["nmcli", *args], capture_output=True, text=True, timeout=timeout)


def _split(line: str) -> list[str]:
    # nmcli -t escapes field-separator ':' as '\:'; split on UNescaped ':' then unescape
    parts = re.split(r"(?<!\\):", line)
    return [p.replace("\\:", ":").replace("\\\\", "\\") for p in parts]


def _ip() -> str | None:
    try:
        out = subprocess.run(["hostname", "-I"], capture_output=True, text=True, timeout=5).stdout
        toks = out.split()
        return toks[0] if toks else None
    except Exception:  # noqa: BLE001
        return None


def status() -> dict:
    if not available():
        return {"available": False}
    ssid, signal = None, None
    try:
        r = _run(["-t", "-f", "ACTIVE,SSID,SIGNAL", "device", "wifi"])
        for line in r.stdout.splitlines():
            p = _split(line)
            if len(p) >= 3 and p[0] == "yes":
                ssid = p[1] or None
                signal = int(p[2]) if p[2].isdigit() else None
                break
    except Exception:  # noqa: BLE001
        pass
    return {"available": True, "connected": ssid is not None, "ssid": ssid,
            "signal": signal, "ip": _ip()}


def scan() -> dict:
    if not available():
        return {"available": False, "networks": []}
    try:
        r = _run(["-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "device", "wifi", "list",
                  "--rescan", "auto"], timeout=25)
    except Exception as e:  # noqa: BLE001
        return {"available": True, "networks": [], "error": str(e)}

    nets: dict[str, dict] = {}
    for line in r.stdout.splitlines():
        p = _split(line)
        if len(p) < 4 or not p[1]:
            continue
        ssid = p[1]
        sig = int(p[2]) if p[2].isdigit() else 0
        entry = {"ssid": ssid, "signal": sig, "security": p[3] or "open",
                 "in_use": p[0] == "*"}
        if ssid not in nets or sig > nets[ssid]["signal"] or entry["in_use"]:
            nets[ssid] = entry
    return {"available": True,
            "networks": sorted(nets.values(), key=lambda n: n["signal"], reverse=True)}


def connect(ssid: str, password: str = "") -> dict:
    """Connect to `ssid`. Uses the given password, or saved credentials if empty.
    NOTE: switching to a different network can drop the Pi's current connection."""
    if not available():
        return {"ok": False, "message": "NetworkManager (nmcli) not available on this host"}
    if not ssid:
        return {"ok": False, "message": "ssid required"}
    args = ["device", "wifi", "connect", ssid]
    if password:
        args += ["password", password]
    try:
        r = _run(args, timeout=40)
    except subprocess.TimeoutExpired:
        return {"ok": False, "message": "connection timed out"}
    return {"ok": r.returncode == 0, "message": (r.stdout or r.stderr).strip()}
