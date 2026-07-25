"""REAL hardware monitor — works on both laptop and Pi. Temperature comes from
`vcgencmd` on the Pi, psutil sensors elsewhere, or None if unavailable.
"""
from __future__ import annotations

import shutil
import subprocess
import time

import psutil

from .base import SystemStats

_BOOT_TIME = psutil.boot_time()


def _read_temp() -> float | None:
    # Pi: `vcgencmd measure_temp` -> "temp=48.3'C"
    vcgencmd = shutil.which("vcgencmd")
    if vcgencmd:
        try:
            out = subprocess.check_output([vcgencmd, "measure_temp"], text=True, timeout=1)
            return float(out.strip().split("=")[1].split("'")[0])
        except Exception:
            pass
    # Fallback: psutil sensors (Linux laptops / some SBCs)
    try:
        temps = psutil.sensors_temperatures()  # type: ignore[attr-defined]
        for entries in temps.values():
            if entries:
                return float(entries[0].current)
    except Exception:
        pass
    return None  # macOS dev machine has no accessible sensor here


class RealMonitor:
    def sample(self) -> SystemStats:
        vm = psutil.virtual_memory()
        return SystemStats(
            cpu_percent=psutil.cpu_percent(interval=None),
            ram_percent=vm.percent,
            ram_used_mb=round(vm.used / 1e6, 1),
            ram_total_mb=round(vm.total / 1e6, 1),
            temp_c=_read_temp(),
            storage_percent=psutil.disk_usage("/").percent,
            uptime_s=round(time.time() - _BOOT_TIME, 1),
        )
