from __future__ import annotations

from pathlib import Path

from loguru import logger
from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtGui import QImage

from src.common.video_info_reader import VideoInfoReader, CropResult
from src.service.image_provider import ThumbnailImageProvider, pil_to_qimage


# ── helpers ──────────────────────────────────────────────────────
def _format_duration(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


# ── thumbnail worker ─────────────────────────────────────────────
class _ThumbnailWorker(QThread):
    """Background thread: read_info + generate_thumb_image."""

    finished = Signal(int, object, object)  # request_id, QImage, info_dict
    error = Signal(int, str)  # request_id, message

    def __init__(
        self,
        request_id: int,
        video_path: str,
        rotate_angle: int,
        orientation: int,
        no_crop: bool,
        auto_detect_rotation: bool = False,
    ):
        super().__init__()
        self._request_id = request_id
        self._video_path = video_path
        self._rotate_angle = rotate_angle
        self._orientation = orientation
        self._no_crop = no_crop
        self._auto_detect_rotation = auto_detect_rotation

    def run(self) -> None:
        try:
            reader = VideoInfoReader()
            video_info = reader.read_info(Path(self._video_path))

            crop = None
            if not self._no_crop and video_info.crop_result is not None and video_info.crop_result.has_border:
                crop = video_info.crop_result

            # Auto-detect rotation: check if cropped dimensions already match target orientation
            rotate_angle = self._rotate_angle
            recommended_rotation = None
            if self._auto_detect_rotation:
                eff_w = crop.width if crop is not None else video_info.width
                eff_h = crop.height if crop is not None else video_info.height
                # orientation: 0=landscape (width>=height), 1=portrait (height>width)
                if self._orientation == 0:
                    orientation_matches = eff_w >= eff_h
                else:
                    orientation_matches = eff_h > eff_w
                recommended_rotation = 0 if orientation_matches else 90
                rotate_angle = recommended_rotation

            pil_image = reader.generate_thumb_image(
                video_path=self._video_path,
                crop_result=crop,
                rotate_angle=rotate_angle,
                orientation=self._orientation,
            )

            qimage = pil_to_qimage(pil_image)

            info_dict = {
                "durationAndResolution": (
                    f"{_format_duration(video_info.duration_second)}"
                    f" / {video_info.width}x{video_info.height}"
                ),
            }
            if recommended_rotation is not None:
                info_dict["recommendedRotation"] = recommended_rotation
            self.finished.emit(self._request_id, qimage, info_dict)
        except Exception as exc:
            logger.exception("thumbnail worker error")
            self.error.emit(self._request_id, str(exc))


# ── HomeService (exposed to QML as context property) ─────────────
class HomeService(QObject):
    # signals -> QML
    displayStateChanged = Signal(int)       # 0=Waiting 1=Loading 2=Normal 3=Error
    thumbnailReady = Signal(str)            # image://thumbnail/<id>
    videoInfoReady = Signal(str)            # durationAndResolution string
    recommendedRotationReady = Signal(int)  # auto-detected rotation angle (0 or 90)
    errorOccurred = Signal(str)

    def __init__(self, image_provider: ThumbnailImageProvider, parent: QObject | None = None):
        super().__init__(parent)
        self._image_provider = image_provider
        self._thumb_request_id = 0
        self._thumb_counter = 0
        self._workers: list[QThread] = []

    # ── private helpers ──────────────────────────────────────────
    def _cleanup_workers(self) -> None:
        self._workers = [w for w in self._workers if w.isRunning()]

    def _generate_thumbnail(
        self,
        file_path: str,
        rotate_angle: int,
        orientation: int,
        no_crop: bool,
        auto_detect_rotation: bool = False,
    ) -> None:
        self._cleanup_workers()
        self._thumb_request_id += 1
        rid = self._thumb_request_id

        self.displayStateChanged.emit(1)  # Loading

        worker = _ThumbnailWorker(rid, file_path, rotate_angle, orientation, no_crop, auto_detect_rotation)
        worker.finished.connect(self._on_thumbnail_ready)
        worker.error.connect(self._on_thumbnail_error)
        worker.start()
        self._workers.append(worker)

    def _on_thumbnail_ready(self, request_id: int, qimage: QImage, info_dict: dict) -> None:
        if request_id != self._thumb_request_id:
            return  # stale result

        self._thumb_counter += 1
        image_id = f"thumb_{self._thumb_counter}"
        self._image_provider.set_image(image_id, qimage)

        self.thumbnailReady.emit(f"image://thumbnail/{image_id}")
        self.videoInfoReady.emit(info_dict["durationAndResolution"])
        if "recommendedRotation" in info_dict:
            self.recommendedRotationReady.emit(info_dict["recommendedRotation"])
        self.displayStateChanged.emit(2)  # Normal

    def _on_thumbnail_error(self, request_id: int, message: str) -> None:
        if request_id != self._thumb_request_id:
            return
        self.errorOccurred.emit(message)
        self.displayStateChanged.emit(3)  # Error

    # ── slots (called from QML) ──────────────────────────────────

    @Slot(str, int, bool)
    def onVideoItemClicked(self, file_path: str, rotation_angle: int, is_landscape: bool) -> None:
        orientation = 0 if is_landscape else 1
        self._generate_thumbnail(file_path, rotation_angle, orientation, no_crop=False, auto_detect_rotation=True)

    @Slot(str, int, bool)
    def onRotatePreview(self, file_path: str, rotation_angle: int, is_landscape: bool) -> None:
        orientation = 0 if is_landscape else 1
        self._generate_thumbnail(file_path, rotation_angle, orientation, no_crop=False)

    @Slot(str, int, bool)
    def onPreviewOriginal(self, file_path: str, rotation_angle: int, is_landscape: bool) -> None:
        orientation = 0 if is_landscape else 1
        self._generate_thumbnail(file_path, rotation_angle, orientation, no_crop=True)
