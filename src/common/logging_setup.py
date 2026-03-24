from __future__ import annotations

import sys
import threading
from pathlib import Path

from loguru import logger

from src.core.paths import PROJECT_ROOT

LOG_FILE = PROJECT_ROOT / "log.log"

_logger_configured = False
_logger_lock = threading.Lock()


def ensure_app_logger_configured() -> Path:
    global _logger_configured
    if _logger_configured:
        return LOG_FILE

    with _logger_lock:
        if _logger_configured:
            return LOG_FILE

        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

        logger.remove()
        logger.add(
            str(LOG_FILE),
            level="DEBUG",
            encoding="utf-8",
            enqueue=False,
            backtrace=False,
            diagnose=False,
        )

        stderr_sink = sys.stderr or sys.__stderr__
        if stderr_sink is not None:
            logger.add(
                stderr_sink,
                level="INFO",
                backtrace=False,
                diagnose=False,
            )

        _logger_configured = True
        return LOG_FILE
