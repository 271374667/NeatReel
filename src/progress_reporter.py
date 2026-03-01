from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import Callable

from tqdm.auto import tqdm
from src.utils.singleton import singleton


@dataclass
class ProgressState:
    phase: str = "idle"
    total_files: int = 0
    processed_files: int = 0
    current_file_index: int = 0
    current_file_path: str = ""
    current_frames: int = 0
    total_frames: int | None = None

    @property
    def files_percent(self) -> float:
        if self.total_files <= 0:
            return 0.0
        return self.processed_files / self.total_files

    @property
    def frames_percent(self) -> float | None:
        if self.total_frames is None or self.total_frames <= 0:
            return None
        return min(1.0, self.current_frames / self.total_frames)


@singleton
class ProgressReporter:
    """统一管理进度状态，并可选在终端显示 tqdm 进度条。"""

    def __init__(
        self,
        *,
        enable_tqdm: bool = True,
        on_state_change: Callable[[ProgressState], None] | None = None,
        emit_interval_seconds: float = 0.2,
    ) -> None:
        if getattr(self, "_initialized", False):
            if on_state_change is not None:
                self.on_state_change = on_state_change
            self.enable_tqdm = enable_tqdm
            self.emit_interval_seconds = max(0.0, emit_interval_seconds)
            return

        self.enable_tqdm = enable_tqdm
        self.on_state_change = on_state_change
        self.emit_interval_seconds = max(0.0, emit_interval_seconds)
        self.state = ProgressState()
        self._file_bar: tqdm | None = None
        self._frame_bar: tqdm | None = None
        self._last_emit_ts = 0.0
        self._initialized = True

    def start_merge(self, total_files: int) -> None:
        self.state.phase = "merging"
        self.state.total_files = max(0, total_files)
        self.state.processed_files = 0
        self.state.current_file_index = 0
        self.state.current_file_path = ""
        self.state.current_frames = 0
        self.state.total_frames = None
        if self.enable_tqdm:
            self._file_bar = tqdm(total=total_files, desc="合并进度", unit="file")
        self._emit(force=True)

    def start_file(
        self,
        file_index: int,
        file_path: Path,
        *,
        total_frames: int | None = None,
    ) -> None:
        self._close_frame_bar()
        self.state.phase = "processing_file"
        self.state.current_file_index = file_index
        self.state.current_file_path = str(file_path)
        self.state.current_frames = 0
        self.state.total_frames = total_frames if total_frames and total_frames > 0 else None
        if self.enable_tqdm:
            self._frame_bar = tqdm(
                total=self.state.total_frames,
                desc=f"帧处理 {file_index}/{self.state.total_files}",
                unit="frame",
                leave=False,
            )
        self._emit(force=True)

    def update_frame(self, step: int = 1) -> None:
        step = max(0, step)
        if step == 0:
            return
        self.state.current_frames += step
        if self._frame_bar is not None:
            self._frame_bar.update(step)
        self._emit()

    def finish_file(self) -> None:
        self.state.processed_files = min(
            self.state.total_files,
            self.state.processed_files + 1,
        )
        if self._file_bar is not None:
            self._file_bar.update(1)
        self._close_frame_bar()
        self._emit(force=True)

    def finish_merge(self) -> None:
        self.state.phase = "completed"
        self._close_frame_bar()
        self._emit(force=True)

    def close(self) -> None:
        self._close_frame_bar()
        if self._file_bar is not None:
            self._file_bar.close()
            self._file_bar = None

    def _close_frame_bar(self) -> None:
        if self._frame_bar is not None:
            self._frame_bar.close()
            self._frame_bar = None

    def _emit(self, *, force: bool = False) -> None:
        if self.on_state_change is not None:
            now = monotonic()
            if force or (now - self._last_emit_ts >= self.emit_interval_seconds):
                self._last_emit_ts = now
                self.on_state_change(self.state)
