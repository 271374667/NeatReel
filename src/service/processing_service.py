from __future__ import annotations

from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from time import monotonic

from loguru import logger
from PySide6.QtCore import QCoreApplication, QObject, Property, QThread, QTimer, QUuid, QUrl, Signal, Slot
from PySide6.QtGui import QImage

from src.core.paths import OUTPUT_DIR
from src.image_provider import ThumbnailImageProvider
from src.merge_signals import get_merge_signals
from src.utils.window_utils import WindowUtils


# ── helpers ──────────────────────────────────────────────────────
_PROCESS_MODE_MAP = {
    0: "speed",
    1: "balanced",
    2: "quality",
    3: "gpu",
}
_ORIENTATION_HORIZONTAL = "horizontal"
_ORIENTATION_VERTICAL = "vertical"
_MERGE_CANCELLED_MESSAGE = "已取消"


def _load_processing_runtime():
    from src.common.video_info_reader import CropResult, VideoInfoReader
    from src.common.video_merger import InputVideoInfo, Orientation, Rotation, VideoMerger, VideoProcessMode

    return {
        "CropResult": CropResult,
        "InputVideoInfo": InputVideoInfo,
        "Orientation": Orientation,
        "Rotation": Rotation,
        "VideoInfoReader": VideoInfoReader,
        "VideoMerger": VideoMerger,
        "VideoProcessMode": VideoProcessMode,
    }


# ── merge worker ─────────────────────────────────────────────────
class _MergeWorker(QThread):
    """Background thread: parallel read_info + merge."""

    def __init__(
        self,
        video_items: list[dict],
        process_mode_key: str,
        orientation_key: str,
        cover_path: Path | None,
        output_path: Path,
        merge_into_one: bool,
    ):
        super().__init__()
        self._video_items = video_items
        self._process_mode_key = process_mode_key
        self._orientation_key = orientation_key
        self._cover_path = cover_path
        self._output_path = output_path
        self._merge_into_one = merge_into_one

    @staticmethod
    def _normalize_rotation_for_merge(angle: int, manually_edited: bool) -> int:
        normalized = int(angle) % 360
        if manually_edited:
            return normalized
        return 90 if normalized in (90, 270) else 0

    def run(self) -> None:
        signals = get_merge_signals()
        try:
            runtime = _load_processing_runtime()
            crop_result_cls = runtime["CropResult"]
            input_video_info_cls = runtime["InputVideoInfo"]
            orientation_enum = runtime["Orientation"]
            rotation_enum = runtime["Rotation"]
            video_info_reader_cls = runtime["VideoInfoReader"]
            video_merger_cls = runtime["VideoMerger"]
            video_process_mode_enum = runtime["VideoProcessMode"]

            rotation_map = {
                0: rotation_enum.ROTATE_0,
                90: rotation_enum.ROTATE_90,
                180: rotation_enum.ROTATE_180,
                270: rotation_enum.ROTATE_270,
            }
            process_mode_map = {
                "speed": video_process_mode_enum.SPEED,
                "balanced": video_process_mode_enum.BALANCED,
                "quality": video_process_mode_enum.QUALITY,
                "gpu": video_process_mode_enum.GPU,
            }
            process_mode = process_mode_map.get(self._process_mode_key, video_process_mode_enum.QUALITY)
            orientation = (
                orientation_enum.HORIZONTAL
                if self._orientation_key == _ORIENTATION_HORIZONTAL
                else orientation_enum.VERTICAL
            )

            def _manual_crop_from_item(item: dict):
                if not item.get("manualCropEnabled"):
                    return None

                try:
                    x = int(item.get("manualCropX", 0))
                    y = int(item.get("manualCropY", 0))
                    width = int(item.get("manualCropWidth", 0))
                    height = int(item.get("manualCropHeight", 0))
                except (TypeError, ValueError):
                    return None

                if width <= 0 or height <= 0:
                    return None

                return crop_result_cls(
                    x=x,
                    y=y,
                    width=width,
                    height=height,
                    confidence=1.0,
                    has_border=True,
                )

            def _read_single(item: dict):
                reader = video_info_reader_cls()
                path = Path(item["filePath"])
                use_auto_crop = bool(item.get("autoCropEnabled", True))
                manual_crop = _manual_crop_from_item(item)
                info = reader.read_info(
                    path,
                    crop_result=manual_crop if use_auto_crop else None,
                    enable_border_detection=use_auto_crop,
                )
                effective_crop = None
                if use_auto_crop:
                    effective_crop = manual_crop if manual_crop is not None else info.crop_result
                    effective_crop = video_info_reader_cls.normalize_crop_result(
                        effective_crop,
                        int(info.width),
                        int(info.height),
                    )
                return item, info, effective_crop

            results = [None] * len(self._video_items)
            total_items = len(self._video_items)
            with ThreadPoolExecutor() as pool:
                future_to_index = {
                    pool.submit(_read_single, item): index
                    for index, item in enumerate(self._video_items)
                }
                completed = 0
                for future in as_completed(future_to_index):
                    index = future_to_index[future]
                    results[index] = future.result()
                    completed += 1
                    signals.preprocessProgress.emit(completed, total_items)

            input_files = []
            for result in results:
                if result is None:
                    continue
                item, info, effective_crop = result
                manually_edited = bool(item.get("manualRotationEdited", False))
                angle = self._normalize_rotation_for_merge(
                    int(item.get("rotation", 0)),
                    manually_edited,
                )
                rotation = rotation_map.get(angle, rotation_enum.ROTATE_0)
                input_files.append(
                    input_video_info_cls(
                        file_path=Path(item["filePath"]),
                        crop_result=effective_crop,
                        rotation=rotation,
                        width=info.width,
                        height=info.height,
                        fps=info.fps,
                        audio_sample_rate=info.audio_sample_rate,
                        total_frames=info.total_frames,
                        manually_edited=manually_edited,
                    )
                )

            merger = video_merger_cls()
            if self._merge_into_one:
                merger.merge(
                    input_files=input_files,
                    output_file=self._output_path,
                    process_mode=process_mode,
                    enable_border_detection=False,
                    orientation=orientation,
                    cover_image_path=self._cover_path,
                )
            else:
                merger.export_separately(
                    input_files=input_files,
                    output_dir=self._output_path,
                    process_mode=process_mode,
                    enable_border_detection=False,
                    orientation=orientation,
                    cover_image_path=self._cover_path,
                )
        except Exception:
            # All errors/cancellations are already emitted by VideoMerger
            # via MergeSignals. If read_info fails before merge(), emit here.
            if not signals.is_cancelled():
                import traceback
                signals.mergeError.emit(traceback.format_exc())


# ── ProcessingService (exposed to QML as context property) ───────
class ProcessingService(QObject):
    # signals -> QML
    preprocessVisibleChanged = Signal(bool)
    preprocessCurrentChanged = Signal(int)
    preprocessTotalChanged = Signal(int)
    totalProgressChanged = Signal(float)
    totalCurrentChanged = Signal(int)
    totalCountChanged = Signal(int)
    stageProgressChanged = Signal(float)
    stageNameChanged = Signal(str)
    elapsedTimeChanged = Signal(str)
    processingSpeedChanged = Signal(float)
    estimatedRemainingChanged = Signal(str)
    processingStatusChanged = Signal(int)   # 0=processing, 1=done, 2=error
    displayStateChanged = Signal(int)
    frameSourceChanged = Signal(str)
    projectIdChanged = Signal(str)

    @Property(bool, notify=preprocessVisibleChanged)
    def preprocessVisible(self) -> bool:
        return self._preprocess_visible

    @Property(int, notify=preprocessCurrentChanged)
    def preprocessCurrent(self) -> int:
        return self._preprocess_current

    @Property(int, notify=preprocessTotalChanged)
    def preprocessTotal(self) -> int:
        return self._preprocess_total

    @staticmethod
    def _tr(text: str) -> str:
        return QCoreApplication.translate("ProcessingService", text)

    @staticmethod
    def _format_elapsed(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    @staticmethod
    def _format_remaining(seconds: float) -> str:
        seconds = max(0, int(seconds))
        if seconds < 60:
            return ProcessingService._tr("{seconds} 秒").format(seconds=seconds)
        if seconds < 3600:
            m = seconds // 60
            s = seconds % 60
            return ProcessingService._tr("{minutes} 分 {seconds} 秒").format(
                minutes=m,
                seconds=s,
            )
        h = seconds // 3600
        m = (seconds % 3600) // 60
        return ProcessingService._tr("{hours} 小时 {minutes} 分").format(
            hours=h,
            minutes=m,
        )

    @staticmethod
    def _coerce_local_path(raw_path: str) -> Path | None:
        if not raw_path:
            return None

        url = QUrl(raw_path)
        local_path = url.toLocalFile() if url.isLocalFile() else raw_path
        return Path(local_path).expanduser()

    def __init__(self, image_provider: ThumbnailImageProvider, parent: QObject | None = None):
        super().__init__(parent)
        self._image_provider = image_provider
        self._worker: _MergeWorker | None = None
        self._output_path = OUTPUT_DIR / "output.mp4"
        self._project_id = ""
        self._merge_into_one = True

        # Elapsed time
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(1000)
        self._elapsed_timer.timeout.connect(self._update_elapsed)
        self._start_time = 0.0

        # State tracking
        self._total_files = 0
        self._completed_files = 0
        self._effective_fps = 30
        self._current_frames = 0
        self._current_total_frames = 0
        self._frame_counter = 0
        self._preprocess_visible = False
        self._preprocess_current = 0
        self._preprocess_total = 0

        # Speed tracking (sliding window)
        self._speed_samples: deque[tuple[float, int]] = deque(maxlen=30)
        self._cumulative_frames = 0
        self._file_start_time = 0.0

        # Connect MergeSignals
        signals = get_merge_signals()
        signals.mergeStarted.connect(self._on_merge_started)
        signals.fileStarted.connect(self._on_file_started)
        signals.frameProcessed.connect(self._on_frame_processed)
        signals.preprocessProgress.connect(self._on_preprocess_progress)
        signals.fileFinished.connect(self._on_file_finished)
        signals.mergeFinished.connect(self._on_merge_finished)
        signals.mergeError.connect(self._on_merge_error)
        signals.displayFrameReady.connect(self._on_display_frame)

    # ── slots (called from QML) ──────────────────────────────────

    @Slot(int, bool, int, str, str, "QVariantList")
    def startMerge(
        self,
        process_mode_index: int,
        is_landscape: bool,
        output_mode_index: int,
        cover_path: str,
        output_directory: str,
        video_items: list,
    ) -> None:
        process_mode_key = _PROCESS_MODE_MAP.get(process_mode_index, "quality")
        orientation_key = _ORIENTATION_HORIZONTAL if is_landscape else _ORIENTATION_VERTICAL
        merge_into_one = output_mode_index == 0

        cover = self._coerce_local_path(cover_path)
        output_dir = self._coerce_local_path(output_directory) or OUTPUT_DIR
        output_dir.mkdir(parents=True, exist_ok=True)
        self._project_id = self._generate_project_id()
        self._merge_into_one = merge_into_one
        if merge_into_one:
            self._output_path = output_dir / f"{self._project_id}.mp4"
        else:
            self._output_path = output_dir / self._project_id

        # Reset state
        self._total_files = 0
        self._completed_files = 0
        self._current_frames = 0
        self._current_total_frames = 0
        self._cumulative_frames = 0
        self._effective_fps = 30.0
        self._speed_samples.clear()
        self._start_time = monotonic()
        self._set_preprocess_total(len(video_items))
        self._set_preprocess_current(0)
        self._set_preprocess_visible(bool(video_items))

        self.processingStatusChanged.emit(0)
        self.totalProgressChanged.emit(0.0)
        self.totalCountChanged.emit(0)
        self.totalCurrentChanged.emit(0)
        self.stageProgressChanged.emit(0.0)
        self.stageNameChanged.emit(self._tr("准备中"))
        self.elapsedTimeChanged.emit("00:00:00")
        self.processingSpeedChanged.emit(0.0)
        self.estimatedRemainingChanged.emit("")
        self.displayStateChanged.emit(1)  # Loading
        self.projectIdChanged.emit(self._project_id)

        self._elapsed_timer.start()

        get_merge_signals().reset()

        self._worker = _MergeWorker(
            video_items,
            process_mode_key,
            orientation_key,
            cover,
            self._output_path,
            merge_into_one,
        )
        self._worker.start()

    @Slot()
    def onCancel(self) -> None:
        signals = get_merge_signals()
        signals.request_cancel()

    @Slot()
    def onOpenOutputDir(self) -> None:
        try:
            WindowUtils.open_explorer_target(
                self._output_path,
                select_file=self._merge_into_one,
            )
        except Exception:
            logger.exception("Failed to open output directory")

    @Slot()
    def reset(self) -> None:
        self._elapsed_timer.stop()
        self._speed_samples.clear()
        self._set_preprocess_visible(False)
        self._set_preprocess_current(0)
        self._set_preprocess_total(0)

    # ── MergeSignals handlers ────────────────────────────────────

    def _on_merge_started(self, total_files: int, effective_fps: float) -> None:
        self._total_files = total_files
        self._effective_fps = max(1.0, float(effective_fps))
        self._completed_files = 0
        self._cumulative_frames = 0
        self._speed_samples.clear()
        self._start_time = monotonic()
        self._set_preprocess_visible(False)

        self.totalCountChanged.emit(total_files)
        self.totalCurrentChanged.emit(0)
        self.displayStateChanged.emit(2)  # Normal (show frame)

    def _on_file_started(self, file_index: int, file_name: str, total_frames: int, effective_fps: float) -> None:
        self._current_frames = 0
        self._current_total_frames = max(1, total_frames)
        self._effective_fps = max(1.0, float(effective_fps))
        self._speed_samples.clear()
        self._cumulative_frames = 0
        self._file_start_time = monotonic()

        self.totalCurrentChanged.emit(file_index)
        self.stageNameChanged.emit(
            self._tr("处理文件 {current}/{total}: {file_name}").format(
                current=file_index,
                total=self._total_files,
                file_name=file_name,
            )
        )
        self.stageProgressChanged.emit(0.0)

    def _on_frame_processed(self, current_frames: int, total_frames: int) -> None:
        self._current_frames = current_frames
        if total_frames > 0:
            self._current_total_frames = total_frames

        # Speed tracking
        now = monotonic()
        self._cumulative_frames = current_frames
        self._speed_samples.append((now, current_frames))

        # Stage progress
        stage_progress = 0.0
        if self._current_total_frames > 0:
            raw_stage_progress = min(1.0, current_frames / self._current_total_frames)
            # 只有文件真正结束时（_on_file_finished）才显示 100%，
            # 避免视频帧已经处理完但音频/flush 仍在继续时界面提前到 100%。
            stage_progress = min(raw_stage_progress, 0.994)
        self.stageProgressChanged.emit(stage_progress)

        # Total progress
        if self._total_files > 0:
            total = (self._completed_files + stage_progress) / self._total_files
            self.totalProgressChanged.emit(min(1.0, total))

        # Speed
        speed = self._compute_speed()
        if speed > 0:
            self.processingSpeedChanged.emit(speed)

        # Remaining time
        remaining = self._compute_remaining()
        if remaining:
            self.estimatedRemainingChanged.emit(remaining)

    def _on_preprocess_progress(self, current: int, total: int) -> None:
        self._set_preprocess_total(total)
        self._set_preprocess_current(current)
        if total > 0:
            self._set_preprocess_visible(True)

    def _on_file_finished(self, file_index: int) -> None:
        self._completed_files = file_index
        self.stageProgressChanged.emit(1.0)

        if self._total_files > 0:
            total = self._completed_files / self._total_files
            self.totalProgressChanged.emit(min(1.0, total))

    def _on_merge_finished(self) -> None:
        self._elapsed_timer.stop()
        self.processingStatusChanged.emit(1)  # Done
        self.totalProgressChanged.emit(1.0)
        self.stageProgressChanged.emit(1.0)
        self.stageNameChanged.emit(self._tr("完成"))
        self.estimatedRemainingChanged.emit("")

    def _on_merge_error(self, message: str) -> None:
        self._elapsed_timer.stop()
        self._set_preprocess_visible(False)
        self.processingStatusChanged.emit(2)  # Error
        if message == _MERGE_CANCELLED_MESSAGE:
            self.stageNameChanged.emit(self._tr("已取消"))
        else:
            self.stageNameChanged.emit(self._tr("错误"))
            logger.error(f"Merge error: {message}")

    def _on_display_frame(self, qimage: QImage) -> None:
        self._frame_counter += 1
        image_id = f"proc_{self._frame_counter}"
        self._image_provider.set_image(image_id, qimage)
        self.frameSourceChanged.emit(f"image://thumbnail/{image_id}")

    # ── internal ─────────────────────────────────────────────────

    def _set_preprocess_visible(self, visible: bool) -> None:
        visible = bool(visible)
        if self._preprocess_visible != visible:
            self._preprocess_visible = visible
            self.preprocessVisibleChanged.emit(visible)

    def _set_preprocess_current(self, current: int) -> None:
        current = max(0, int(current))
        if self._preprocess_current != current:
            self._preprocess_current = current
            self.preprocessCurrentChanged.emit(current)

    def _set_preprocess_total(self, total: int) -> None:
        total = max(0, int(total))
        if self._preprocess_total != total:
            self._preprocess_total = total
            self.preprocessTotalChanged.emit(total)

    def _update_elapsed(self) -> None:
        elapsed = monotonic() - self._start_time
        self.elapsedTimeChanged.emit(self._format_elapsed(elapsed))

    def _compute_speed(self) -> float:
        if len(self._speed_samples) < 2 or self._effective_fps <= 0:
            return 0.0

        oldest_t, oldest_f = self._speed_samples[0]
        newest_t, newest_f = self._speed_samples[-1]
        dt = newest_t - oldest_t
        if dt < 0.5:
            return 0.0

        frames_per_second = (newest_f - oldest_f) / dt
        return frames_per_second / self._effective_fps

    def _compute_remaining(self) -> str:
        if self._file_start_time <= 0 or self._current_total_frames <= 0:
            return ""

        elapsed = monotonic() - self._file_start_time
        if elapsed < 1.0:
            return ""

        stage_progress = min(1.0, self._current_frames / self._current_total_frames)
        if stage_progress <= 0.01:
            return ""

        remaining_seconds = elapsed * (1.0 - stage_progress) / stage_progress
        return self._format_remaining(remaining_seconds)

    def _generate_project_id(self) -> str:
        return QUuid.createUuid().toString(QUuid.StringFormat.WithoutBraces).replace("-", "")[:8]
