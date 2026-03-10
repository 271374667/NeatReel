from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QImage


class MergeCancelled(Exception):
    """Raised when the user cancels the merge operation."""


class MergeSignals(QObject):
    """Singleton signal hub between VideoMerger (worker thread) and ProcessingService (main thread)."""

    # Emitted by VideoMerger
    mergeStarted = Signal(int, float)        # total_files, effective_fps
    fileStarted = Signal(int, str, int, float)  # file_index(1-based), file_name, total_frames, effective_fps
    frameProcessed = Signal(int, int)        # current_frames, total_frames
    fileFinished = Signal(int)               # file_index(1-based)
    mergeFinished = Signal()
    mergeError = Signal(str)
    displayFrameReady = Signal(QImage)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._cancel_event = threading.Event()

    def request_cancel(self) -> None:
        self._cancel_event.set()

    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def reset(self) -> None:
        self._cancel_event.clear()


_instance: MergeSignals | None = None
_lock = threading.Lock()


def get_merge_signals() -> MergeSignals:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = MergeSignals()
    return _instance
