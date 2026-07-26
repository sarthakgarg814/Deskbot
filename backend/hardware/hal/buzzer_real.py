"""Active buzzer on a GPIO pin via gpiozero. Owned by the hardware process."""
from __future__ import annotations

import logging
import time

log = logging.getLogger("deskbot.hw.buzzer")


class RealBuzzer:
    def __init__(self, pin: int) -> None:
        from gpiozero import Buzzer as _Buzzer

        self._buz = _Buzzer(pin)
        log.info("buzzer on GPIO %d", pin)

    def beep(self, count: int = 1, on: float = 0.15, off: float = 0.1) -> None:
        for i in range(max(1, count)):
            self._buz.on()
            time.sleep(on)
            self._buz.off()
            if i < count - 1:
                time.sleep(off)
