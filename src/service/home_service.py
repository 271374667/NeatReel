from __future__ import annotations

from pathlib import Path

from loguru import logger
from PySide6.QtCore import Property, QObject, QThread, QUrl, Signal, Slot
from PySide6.QtGui import QImage

from src.common.video_info_reader import VideoInfoReader, CropResult
from src.core.paths import OUTPUT_DIR
from src.image_provider import ThumbnailImageProvider, pil_to_qimage


# ── helpers ──────────────────────────────────────────────────────
def _format_duration(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _normalize_rotation_angle(angle: int) -> int:
    return int(angle) % 360


def _rotation_swaps_dimensions(angle: int) -> bool:
    return _normalize_rotation_angle(angle) in (90, 270)


def _resolve_effective_rotation(
    base_rotation: int,
    width: int,
    height: int,
    orientation: int,
) -> int:
    normalized_base = _normalize_rotation_angle(base_rotation)
    effective_width = int(width)
    effective_height = int(height)
    if _rotation_swaps_dimensions(normalized_base):
        effective_width, effective_height = effective_height, effective_width

    if orientation == 0:
        orientation_matches = effective_width >= effective_height
    else:
        orientation_matches = effective_height > effective_width

    return normalized_base if orientation_matches else (normalized_base + 90) % 360


# ── thumbnail worker ─────────────────────────────────────────────
class _ThumbnailWorker(QThread):
    """Background thread: read_info + generate_thumb_image."""

    finished = Signal(int, object, object)  # request_id, QImage, info_dict
    error = Signal(int, str, str)  # request_id, preview_mode, message

    def __init__(
        self,
        request_id: int,
        video_path: str,
        rotate_angle: int,
        orientation: int,
        crop_override: CropResult | None,
        use_auto_crop: bool,
        preview_mode: str,
        auto_detect_rotation: bool = False,
    ):
        super().__init__()
        self._request_id = request_id
        self._video_path = video_path
        self._rotate_angle = rotate_angle
        self._orientation = orientation
        self._crop_override = crop_override
        self._use_auto_crop = use_auto_crop
        self._preview_mode = preview_mode
        self._auto_detect_rotation = auto_detect_rotation

    def run(self) -> None:
        try:
            reader = VideoInfoReader()
            read_crop_override = self._crop_override if self._use_auto_crop else None
            video_info = reader.read_info(
                Path(self._video_path),
                crop_result=read_crop_override,
                enable_border_detection=self._use_auto_crop,
            )

            effective_crop = None
            if self._use_auto_crop:
                effective_crop = self._crop_override
                if effective_crop is None:
                    detected_crop = video_info.crop_result
                    if detected_crop is not None and detected_crop.has_border:
                        effective_crop = detected_crop
                effective_crop = VideoInfoReader.normalize_crop_result(
                    effective_crop,
                    int(video_info.width),
                    int(video_info.height),
                )

            rotate_angle = _normalize_rotation_angle(self._rotate_angle)
            recommended_rotation = None
            if self._preview_mode == "manual_crop":
                # Manual crop must always use the original, unrotated frame so the
                # crop box and emitted coordinates stay in source-video space.
                rotate_angle = 0
            elif self._auto_detect_rotation:
                eff_w = effective_crop.width if effective_crop is not None else video_info.width
                eff_h = effective_crop.height if effective_crop is not None else video_info.height
                recommended_rotation = _resolve_effective_rotation(
                    rotate_angle,
                    eff_w,
                    eff_h,
                    self._orientation,
                )
                rotate_angle = recommended_rotation

            if self._preview_mode == "manual_crop":
                pil_image = reader.generate_preview_frame_image(
                    video_path=self._video_path,
                    frame_index=0,
                    rotate_angle=rotate_angle,
                )
            else:
                pil_image = reader.generate_thumb_image(
                    video_path=self._video_path,
                    crop_result=effective_crop,
                    rotate_angle=rotate_angle,
                    orientation=self._orientation,
                )

            qimage = pil_to_qimage(pil_image)
            crop_rect = effective_crop or CropResult(
                x=0,
                y=0,
                width=int(video_info.width),
                height=int(video_info.height),
                confidence=0.0,
                has_border=False,
            )

            info_dict = {
                "previewMode": self._preview_mode,
                "durationAndResolution": (
                    f"{_format_duration(video_info.duration_second)}"
                    f" / {video_info.width}x{video_info.height}"
                ),
                "cropRect": {
                    "x": int(crop_rect.x),
                    "y": int(crop_rect.y),
                    "width": int(crop_rect.width),
                    "height": int(crop_rect.height),
                },
                "originalWidth": int(video_info.width),
                "originalHeight": int(video_info.height),
                "rotateAngle": int(rotate_angle),
            }
            if recommended_rotation is not None:
                info_dict["recommendedRotation"] = recommended_rotation
            self.finished.emit(self._request_id, qimage, info_dict)
        except Exception as exc:
            logger.exception("thumbnail worker error")
            self.error.emit(self._request_id, self._preview_mode, str(exc))


# ── HomeService (exposed to QML as context property) ─────────────
class HomeService(QObject):
    # signals -> QML
    displayStateChanged = Signal(int)       # 0=Waiting 1=Loading 2=Normal 3=Error
    thumbnailReady = Signal(str)            # image://thumbnail/<id>
    videoInfoReady = Signal(str)            # durationAndResolution string
    recommendedRotationReady = Signal(int)  # auto-detected rotation angle (0 or 90)
    cropRectReady = Signal(int, int, int, int, int, int)
    manualCropSessionReady = Signal(str, int, int, int, int, int, int, int)
    errorOccurred = Signal(str)
    manualCropErrorOccurred = Signal(str)

    def __init__(self, image_provider: ThumbnailImageProvider, parent: QObject | None = None):
        super().__init__(parent)
        self._image_provider = image_provider
        self._thumb_request_id = 0
        self._thumb_counter = 0
        self._workers: list[QThread] = []

    def _get_default_output_directory(self) -> str:
        return str(OUTPUT_DIR.resolve())

    defaultOutputDirectory = Property(
        str,
        _get_default_output_directory,
        constant=True,
    )

    # ── private helpers ──────────────────────────────────────────
    def _cleanup_workers(self) -> None:
        self._workers = [w for w in self._workers if w.isRunning()]

    def _generate_thumbnail(
        self,
        file_path: str,
        rotate_angle: int,
        orientation: int,
        crop_override: CropResult | None,
        use_auto_crop: bool,
        preview_mode: str,
        auto_detect_rotation: bool = False,
    ) -> None:
        self._cleanup_workers()
        self._thumb_request_id += 1
        rid = self._thumb_request_id

        if preview_mode == "grid":
            self.displayStateChanged.emit(1)  # Loading

        worker = _ThumbnailWorker(
            rid,
            file_path,
            rotate_angle,
            orientation,
            crop_override,
            use_auto_crop,
            preview_mode,
            auto_detect_rotation,
        )
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

        image_url = f"image://thumbnail/{image_id}"
        crop_rect = info_dict["cropRect"]
        self.cropRectReady.emit(
            int(crop_rect["x"]),
            int(crop_rect["y"]),
            int(crop_rect["width"]),
            int(crop_rect["height"]),
            int(info_dict["originalWidth"]),
            int(info_dict["originalHeight"]),
        )

        if info_dict["previewMode"] == "manual_crop":
            self.manualCropSessionReady.emit(
                image_url,
                int(info_dict["rotateAngle"]),
                int(info_dict["originalWidth"]),
                int(info_dict["originalHeight"]),
                int(crop_rect["x"]),
                int(crop_rect["y"]),
                int(crop_rect["width"]),
                int(crop_rect["height"]),
            )
            return

        self.thumbnailReady.emit(image_url)
        self.videoInfoReady.emit(info_dict["durationAndResolution"])
        if "recommendedRotation" in info_dict:
            self.recommendedRotationReady.emit(info_dict["recommendedRotation"])
        self.displayStateChanged.emit(2)  # Normal

    def _on_thumbnail_error(self, request_id: int, preview_mode: str, message: str) -> None:
        if request_id != self._thumb_request_id:
            return
        if preview_mode == "manual_crop":
            self.manualCropErrorOccurred.emit(message)
            return
        self.errorOccurred.emit(message)
        self.displayStateChanged.emit(3)  # Error

    @staticmethod
    def _coerce_crop_result(crop_data: dict | None) -> CropResult | None:
        if not crop_data:
            return None

        try:
            x = int(crop_data.get("x", 0))
            y = int(crop_data.get("y", 0))
            width = int(crop_data.get("width", 0))
            height = int(crop_data.get("height", 0))
        except (TypeError, ValueError):
            return None

        if width <= 0 or height <= 0:
            return None

        return CropResult(
            x=x,
            y=y,
            width=width,
            height=height,
            confidence=1.0,
            has_border=True,
        )

    @Slot(str, result=str)
    def normalizeLocalPath(self, raw_path: str) -> str:
        if not raw_path:
            return self.defaultOutputDirectory

        url = QUrl(raw_path)
        local_path = url.toLocalFile() if url.isLocalFile() else raw_path
        return str(Path(local_path).expanduser().resolve(strict=False))

    @Slot(str, result=str)
    def localPathToUrl(self, raw_path: str) -> str:
        normalized = self.normalizeLocalPath(raw_path)
        return QUrl.fromLocalFile(normalized).toString()

    # ── slots (called from QML) ──────────────────────────────────

    @Slot(str, int, bool, bool, bool, "QVariantMap")
    def onVideoItemClicked(
        self,
        file_path: str,
        rotation_angle: int,
        is_landscape: bool,
        use_auto_crop: bool,
        manually_edited: bool,
        crop_data: dict,
    ) -> None:
        orientation = 0 if is_landscape else 1
        crop_override = self._coerce_crop_result(crop_data)
        self._generate_thumbnail(
            file_path,
            rotation_angle,
            orientation,
            crop_override,
            use_auto_crop=use_auto_crop,
            preview_mode="grid",
            auto_detect_rotation=not manually_edited,
        )

    @Slot(str, int, bool, bool, "QVariantMap")
    def onRotatePreview(
        self,
        file_path: str,
        rotation_angle: int,
        is_landscape: bool,
        use_auto_crop: bool,
        crop_data: dict,
    ) -> None:
        orientation = 0 if is_landscape else 1
        crop_override = self._coerce_crop_result(crop_data)
        self._generate_thumbnail(
            file_path,
            rotation_angle,
            orientation,
            crop_override,
            use_auto_crop=use_auto_crop,
            preview_mode="grid",
        )

    @Slot(str, int, "QVariantMap")
    def onOpenManualCrop(
        self,
        file_path: str,
        rotation_angle: int,
        crop_data: dict,
    ) -> None:
        crop_override = self._coerce_crop_result(crop_data)
        self._generate_thumbnail(
            file_path,
            rotation_angle,
            0,
            crop_override,
            use_auto_crop=False,
            preview_mode="manual_crop",
        )
