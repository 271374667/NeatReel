from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
import sys
from tempfile import gettempdir
from time import perf_counter

from src.core.paths import PROJECT_ROOT


@dataclass(frozen=True)
class StartupMark:
    name: str
    timestamp: float


class StartupTrace:
    """记录启动阶段耗时，默认仅追加一行摘要到本地日志文件。"""

    def __init__(self, app_name: str = "NeatReel") -> None:
        self._app_name = app_name
        self._start = perf_counter()
        self._marks: list[StartupMark] = []
        self._flushed = False

    def mark(self, name: str) -> None:
        self._marks.append(StartupMark(name=name, timestamp=perf_counter()))

    def flush(self, *, success: bool, note: str = "") -> None:
        if self._flushed:
            return
        self._flushed = True

        try:
            log_path = self._resolve_log_path()
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as stream:
                stream.write(self._build_summary_line(success=success, note=note))
        except OSError:
            pass

    def _build_summary_line(self, *, success: bool, note: str) -> str:
        previous = self._start
        stage_parts: list[str] = []
        for mark in self._marks:
            stage_ms = (mark.timestamp - previous) * 1000
            stage_parts.append(f"{mark.name}={stage_ms:.1f}ms")
            previous = mark.timestamp

        total_ms = (previous - self._start) * 1000 if self._marks else 0.0
        note_suffix = f" note={note}" if note else ""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        stages = ", ".join(stage_parts)
        return (
            f"{timestamp} [{self._app_name}] success={int(success)} total_ms={total_ms:.1f}"
            f"{note_suffix} stages=[{stages}]\n"
        )

    @staticmethod
    def _resolve_log_path() -> Path:
        if not getattr(sys, "frozen", False):
            return PROJECT_ROOT / ".cache" / "startup.log"

        local_app_data = os.getenv("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "NeatReel" / "startup.log"
        return Path(gettempdir()) / "NeatReel" / "startup.log"
