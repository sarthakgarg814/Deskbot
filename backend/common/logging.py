"""Tiny logging setup shared by every service. One line per service to configure."""
from __future__ import annotations

import logging
import sys

_CONFIGURED = False


def setup_logging(level: str = "INFO", service: str = "deskbot") -> logging.Logger:
    global _CONFIGURED
    if not _CONFIGURED:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s %(levelname)-7s [%(name)s] %(message)s",
                datefmt="%H:%M:%S",
            )
        )
        root = logging.getLogger()
        root.handlers[:] = [handler]
        root.setLevel(level.upper())
        _CONFIGURED = True
    return logging.getLogger(service)
