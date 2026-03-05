"""
视频装饰边框检测与裁剪模块 v5

核心算法：
  1. 时域：帧间差分累积变化区域 → 形态学去噪 → 最大活动矩形提取
  2. 空域：单帧自适应阈值二值化 → 形态学去噪 → 最大轮廓矩形 → 多帧投票
  两条路径互补：运动检测优先，空域分析兜底。

使用 PyAV + NumPy + SciPy

依赖：av, numpy, scipy, pathlib
"""

from __future__ import annotations

from collections import Counter
from functools import lru_cache, wraps
from io import BytesIO
import math
import os
from pathlib import Path
import time

import av
from diskcache import Cache
import numpy as np
from scipy.ndimage import (
    binary_opening,
    binary_closing,
    find_objects,
    label,
    gaussian_filter,
)
from dataclasses import dataclass
from typing import Any, Callable, Optional, TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from PIL import Image as PILImage

_CACHE_MISS = object()
_READ_INFO_CACHE_VERSION = 1
_THUMB_CACHE_VERSION = 5
_CACHE_MAX_SIZE_MB = max(1, int(os.getenv("VIDEO_INFO_CACHE_MAX_SIZE_MB", "500")))
_CACHE_EXPIRE_SECONDS = max(
    60, int(os.getenv("VIDEO_INFO_CACHE_EXPIRE_SECONDS", str(24 * 60 * 60)))
)
_CACHE_DISK_MIN_FILE_SIZE_BYTES = max(
    0, int(os.getenv("VIDEO_INFO_CACHE_DISK_MIN_FILE_SIZE", str(64 * 1024)))
)
_THUMB_CACHE_CODEC = os.getenv("VIDEO_INFO_THUMB_CACHE_CODEC", "jpeg").lower()
_THUMB_CACHE_JPEG_QUALITY = min(
    95, max(60, int(os.getenv("VIDEO_INFO_THUMB_CACHE_JPEG_QUALITY", "88")))
)
_THUMB_CACHE_WEBP_QUALITY = min(
    95, max(60, int(os.getenv("VIDEO_INFO_THUMB_CACHE_WEBP_QUALITY", "82")))
)
_THUMB_CACHE_WEBP_METHOD = min(
    6, max(0, int(os.getenv("VIDEO_INFO_THUMB_CACHE_WEBP_METHOD", "1")))
)
_MODULE_CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache" / "video_info_reader"
_MODULE_CACHE = Cache(
    str(_MODULE_CACHE_DIR),
    size_limit=_CACHE_MAX_SIZE_MB * 1024 * 1024,
    disk_min_file_size=_CACHE_DISK_MIN_FILE_SIZE_BYTES,
)


def _effective_thumb_codec() -> str:
    if _THUMB_CACHE_CODEC in {"jpeg", "webp", "raw"}:
        return _THUMB_CACHE_CODEC
    return "jpeg"


def _crop_to_cache_tuple(crop_result: Optional["CropResult"]) -> tuple | None:
    if crop_result is None:
        return None
    return (
        int(crop_result.x),
        int(crop_result.y),
        int(crop_result.width),
        int(crop_result.height),
        float(crop_result.confidence),
        bool(crop_result.has_border),
    )


def _file_signature_for_cache(video_path: Path | str) -> tuple[str, int, int] | None:
    path = Path(video_path)
    if not path.exists():
        return None
    st = path.stat()
    return str(path.resolve()), int(st.st_size), int(st.st_mtime_ns)


def _read_info_key_builder(
    reader: "VideoInfoReader",
    video_path: Path,
    crop_result: Optional["CropResult"] = None,
) -> tuple | None:
    file_sig = _file_signature_for_cache(video_path)
    if file_sig is None:
        return None
    reader_sig = (
        reader.detect_short_edge,
        reader.min_border_ratio,
        reader.safety_margin,
        reader.diff_threshold,
        reader.morph_kernel_size,
        reader.min_region_ratio,
        reader.scene_change_threshold,
        reader.seek_skip_frames,
        reader.spatial_edge_threshold,
        reader.spatial_border_max_brightness,
    )
    return (
        "read_info",
        _READ_INFO_CACHE_VERSION,
        file_sig,
        reader_sig,
        _crop_to_cache_tuple(crop_result),
    )


def _generate_thumb_key_builder(
    _: "VideoInfoReader",
    video_path: Path | str,
    thumb_resolution: tuple[int, int] = (640, 480),
    crop_result: Optional["CropResult"] = None,
    rotate_angle: int = 0,
) -> tuple | None:
    file_sig = _file_signature_for_cache(video_path)
    if file_sig is None:
        return None
    return (
        "generate_thumb_image",
        _THUMB_CACHE_VERSION,
        file_sig,
        int(thumb_resolution[0]),
        int(thumb_resolution[1]),
        _crop_to_cache_tuple(crop_result),
        int(rotate_angle),
        _effective_thumb_codec(),
        _THUMB_CACHE_JPEG_QUALITY,
        _THUMB_CACHE_WEBP_QUALITY,
        _THUMB_CACHE_WEBP_METHOD,
    )


def _diskcache_method(
    key_builder: Callable[..., tuple | None],
    on_hit: Callable[[Any], None] | None = None,
    serializer: Callable[[Any], Any] | None = None,
    deserializer: Callable[[Any], Any] | None = None,
    expire_seconds: int = _CACHE_EXPIRE_SECONDS,
):
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            key = key_builder(self, *args, **kwargs)
            if key is None:
                return func(self, *args, **kwargs)

            cached = _MODULE_CACHE.get(key, default=_CACHE_MISS)
            if cached is not _CACHE_MISS:
                if on_hit is not None:
                    on_hit(self)
                return deserializer(cached) if deserializer is not None else cached

            result = func(self, *args, **kwargs)
            value_to_cache = serializer(result) if serializer is not None else result
            _MODULE_CACHE.set(key, value_to_cache, expire=expire_seconds)
            return result

        return wrapper

    return decorator


def _serialize_thumb_cache_value(image: "PILImage.Image") -> tuple[str, Any]:
    codec = _effective_thumb_codec()
    if codec == "raw":
        return ("raw", image.copy())

    rgb = image if image.mode == "RGB" else image.convert("RGB")
    buff = BytesIO()
    if codec == "webp":
        rgb.save(
            buff,
            format="WEBP",
            quality=_THUMB_CACHE_WEBP_QUALITY,
            method=_THUMB_CACHE_WEBP_METHOD,
        )
        return ("webp", buff.getvalue())

    rgb.save(
        buff,
        format="JPEG",
        quality=_THUMB_CACHE_JPEG_QUALITY,
        optimize=False,
        progressive=False,
    )
    return ("jpeg", buff.getvalue())


def _deserialize_thumb_cache_value(payload: tuple[str, Any]) -> "PILImage.Image":
    tag, data = payload
    if tag == "raw":
        return data.copy()

    try:
        from PIL import Image
    except ImportError as exc:
        raise ImportError("未安装 Pillow，无法读取缩略图缓存。请先安装 pillow。") from exc

    img = Image.open(BytesIO(data))
    img.load()
    return img.convert("RGB") if img.mode != "RGB" else img


@lru_cache(maxsize=32)
def _get_cached_font(font_size: int):
    try:
        from PIL import ImageFont
    except ImportError as exc:
        raise ImportError("未安装 Pillow，无法生成缩略图。请先安装 pillow。") from exc

    try:
        return ImageFont.truetype("arial.ttf", font_size)
    except OSError:
        try:
            return ImageFont.truetype("DejaVuSans.ttf", font_size)
        except OSError:
            return ImageFont.load_default()


@dataclass
class CropResult:
    """裁剪检测结果（坐标基于原始分辨率）"""

    x: int
    y: int
    width: int
    height: int
    confidence: float
    has_border: bool

    @property
    def rect(self) -> tuple[int, int, int, int]:
        return self.x, self.y, self.width, self.height

    def __repr__(self) -> str:
        return (
            f"CropResult(x={self.x}, y={self.y}, "
            f"w={self.width}, h={self.height}, "
            f"conf={self.confidence:.4f}, border={self.has_border})"
        )


@dataclass(frozen=True)
class VideoInfo:
    """视频基础元数据容器。

    Attributes:
        width: 视频帧宽度（像素）。
        height: 视频帧高度（像素）。
        fps: 帧率（每秒帧数）。
        total_frames: 总帧数；当源信息缺失时可能为估算值。
        audio_sample_rate: 音频采样率（Hz）；`-1` 表示无音频流。
        duration_second: 视频时长（秒）。
    """

    width: int
    height: int
    fps: float
    total_frames: int
    audio_sample_rate: int
    duration_second: float
    crop_result: Optional[CropResult] = None


class VideoInfoReader:
    """
    视频装饰边框检测器 v4

    传入视频路径，自动完成采样与检测，返回裁剪参数。

    用法:
        detector = VideoInfoReader()
        result = detector.read_info(Path("video.mp4"))
        if result.has_border:
            print(result.rect)
    """

    def __init__(
        self,
        detect_short_edge: int = 480,
        min_border_ratio: float = 0.02,
        safety_margin: int = 2,
        # 帧差分二值化阈值
        diff_threshold: float = 18.0,
        # 形态学核大小
        morph_kernel_size: int = 5,
        # 连通域最小面积占比（相对于检测分辨率的总面积）
        min_region_ratio: float = 0.002,
        # 场景切换阈值
        scene_change_threshold: float = 60.0,
        # seek 后跳过的帧数（让画面定位更接近目标时刻）
        seek_skip_frames: int = 2,
        # ---- 空域分析参数 ----
        # 边缘暗度预检阈值：若四边中位亮度高于此值，认为无黑边
        spatial_edge_threshold: float = 50.0,
        # 黑边区域的最大亮度：像素亮于此值则认为是内容
        spatial_border_max_brightness: float = 30.0,
    ):
        self.detect_short_edge = detect_short_edge
        self.min_border_ratio = min_border_ratio
        self.safety_margin = safety_margin
        self.diff_threshold = diff_threshold
        self.morph_kernel_size = morph_kernel_size
        self.min_region_ratio = min_region_ratio
        self.scene_change_threshold = scene_change_threshold
        self.seek_skip_frames = seek_skip_frames

        # 空域分析参数
        self.spatial_edge_threshold = spatial_edge_threshold
        self.spatial_border_max_brightness = spatial_border_max_brightness

        self._prev_gray: Optional[np.ndarray] = None
        self._accumulated: Optional[np.ndarray] = None
        self._pair_count: int = 0
        self._original_size: Optional[tuple[int, int]] = None
        self._detect_size: Optional[tuple[int, int]] = None
        self._scale_factor: float = 1.0
        # 缓存采样帧的灰度图，供空域分析使用
        self._sampled_grays: list[np.ndarray] = []

    # ======================== 公开接口 ========================

    @_diskcache_method(_read_info_key_builder, on_hit=lambda reader: reader._reset())
    def read_info(
        self, video_path: Path, crop_result: Optional[CropResult] = None
    ) -> VideoInfo:
        """
        传入视频路径，检测视频元数据与边框裁剪参数，返回 `VideoInfo`。

        Args:
            video_path: 视频文件路径。
            crop_result: 可选的裁剪参数。若传入则跳过边框检测，直接使用该裁剪参数。

        内部根据视频时长自动选择采样策略：
        - 时长 < 2s：顺序解码全量帧后均匀采样
        - 时长 ≥ 2s：按均匀时间戳 seek 采样（5%~95% 区间）

        Raises:
            FileNotFoundError: 当输入文件不存在时抛出。
            ValueError: 当文件中没有视频流时抛出。
        """
        if not video_path.exists():
            raise FileNotFoundError(f"video file not found: {video_path}")

        self._reset()

        logger.debug(f"开始边框检测: {video_path}")

        with av.open(str(video_path)) as container:
            if not container.streams.video:
                raise ValueError(f"no video stream found: {video_path}")

            stream = container.streams.video[0]
            audio_stream = (
                container.streams.audio[0] if container.streams.audio else None
            )

            fps = self._resolve_video_fps(stream)
            duration = self._resolve_video_duration(container, stream)
            total_frames = self._resolve_total_frames(stream, fps, duration)

            audio_sample_rate = -1
            if audio_stream is not None:
                audio_sample_rate = int(
                    audio_stream.rate or audio_stream.codec_context.sample_rate or -1
                )

            width = int(stream.width)
            height = int(stream.height)

            if crop_result is not None:
                logger.debug(f"使用传入的裁剪参数，跳过边框检测: {crop_result}")
                detected_crop = crop_result
            else:
                plan = self._compute_sample_plan(duration, fps)

                strategy = "顺序解码" if duration < 2.0 else "seek跳帧"
                logger.debug(
                    f"视频信息: fps={fps:.1f}, duration={duration:.2f}s, "
                    f"采样策略={strategy}, 计划帧数={plan['num_frames']}"
                )

                if duration < 2.0:
                    frames = self._sample_sequentially(
                        container, stream, plan["num_frames"]
                    )
                else:
                    frames = self._sample_with_seek(
                        container, stream, plan["timestamps"]
                    )

                logger.debug(f"实际采集帧数: {len(frames)}/{plan['num_frames']}")
                for frame in frames:
                    self._feed(frame)

                detected_crop = self._run_detection()

        return VideoInfo(
            width=width,
            height=height,
            fps=fps,
            total_frames=total_frames,
            audio_sample_rate=audio_sample_rate,
            duration_second=duration,
            crop_result=detected_crop,
        )

    def preview(
        self, video_path: Path, frame_index: int, crop_result: CropResult
    ) -> np.ndarray:
        """
        从视频中取出第 frame_index 帧（0-based），按 crop_result 裁剪后返回 RGB numpy 数组。
        """
        with av.open(str(video_path)) as container:
            stream = container.streams.video[0]
            idx = 0
            for packet in container.demux(stream):
                for frame in packet.decode():
                    if idx == frame_index:
                        arr = frame.to_ndarray(format="rgb24")
                        if crop_result.has_border:
                            arr = arr[
                                crop_result.y : crop_result.y + crop_result.height,
                                crop_result.x : crop_result.x + crop_result.width,
                            ].copy()
                        return arr
                    idx += 1
        raise ValueError(f"帧索引 {frame_index} 超出视频范围: {video_path}")

    @_diskcache_method(
        _generate_thumb_key_builder,
        serializer=_serialize_thumb_cache_value,
        deserializer=_deserialize_thumb_cache_value,
    )
    def generate_thumb_image(
        self,
        video_path: Path | str,
        thumb_resolution: tuple[int, int] = (640, 480),
        crop_result: Optional[CropResult] = None,
        rotate_angle: int = 0,
    ) -> PILImage.Image:
        """
        从视频中均匀抽帧，自动布局并拼接成缩略图总览图。

        Args:
            video_path: 视频文件路径。
            thumb_resolution: 输出图分辨率，格式为 (宽, 高)。
            crop_result: 可选裁剪参数（基于原始分辨率坐标）。
            rotate_angle: 顺时针旋转角度，仅支持 0/90/180/270。
        """
        try:
            from PIL import Image, ImageDraw
        except ImportError as exc:
            raise ImportError(
                "未安装 Pillow，无法生成缩略图。请先安装 pillow。"
            ) from exc

        if rotate_angle not in (0, 90, 180, 270):
            raise ValueError("rotate_angle 仅支持 0、90、180、270")

        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"video file not found: {video_path}")

        canvas_w, canvas_h = thumb_resolution
        if canvas_w <= 0 or canvas_h <= 0:
            raise ValueError("thumb_resolution 必须是正整数分辨率")

        func_start = time.perf_counter()
        if hasattr(Image, "Resampling"):
            fast_resample = Image.Resampling.NEAREST
        else:
            fast_resample = Image.NEAREST

        target_count = 12
        min_thumb_area = 9_000

        with av.open(str(video_path)) as container:
            if not container.streams.video:
                raise ValueError(f"no video stream found: {video_path}")

            stream = container.streams.video[0]
            stream.thread_type = "AUTO"

            # 尽量用低成本路径解码，提升缩略图生成速度
            try:
                stream.codec_context.skip_frame = "NONKEY"
            except Exception:
                pass
            try:
                stream.codec_context.skip_loop_filter = "ALL"
            except Exception:
                pass
            try:
                stream.codec_context.skip_idct = "ALL"
            except Exception:
                pass
            try:
                max_lowres = int(getattr(stream.codec_context, "max_lowres", 0) or 0)
                if max_lowres > 0:
                    stream.codec_context.lowres = 1
            except Exception:
                pass

            fps_hint = float(stream.average_rate or stream.base_rate or 30.0)
            duration = self._resolve_video_duration(container, stream)
            if duration <= 0.0 and stream.frames:
                duration = float(stream.frames) / max(fps_hint, 1e-6)
            v_width = int(stream.codec_context.width or stream.width)
            v_height = int(stream.codec_context.height or stream.height)

            crop_box: tuple[int, int, int, int] | None = None
            if crop_result is not None:
                crop_box = self._normalize_crop_box(crop_result, v_width, v_height)

            analyzed_w = crop_box[2] - crop_box[0] if crop_box is not None else v_width
            analyzed_h = crop_box[3] - crop_box[1] if crop_box is not None else v_height
            if rotate_angle in (90, 270):
                analyzed_w, analyzed_h = analyzed_h, analyzed_w

            src_aspect = analyzed_w / max(analyzed_h, 1)
            is_landscape = analyzed_w >= analyzed_h

            best_grid: tuple[int, int] | None = None
            best_score: tuple[float, ...] | None = None
            fallback_grid = (3, 4)
            fallback_score: tuple[float, ...] | None = None

            for n in range(target_count, 0, -1):
                for cols in range(1, n + 1):
                    if n % cols != 0:
                        continue
                    rows = n // cols

                    cell_w = canvas_w / cols
                    cell_h = canvas_h / rows
                    scale = min(
                        cell_w / max(analyzed_w, 1), cell_h / max(analyzed_h, 1)
                    )
                    thumb_w = analyzed_w * scale
                    thumb_h = analyzed_h * scale
                    area = thumb_w * thumb_h
                    fill_ratio = area / max(cell_w * cell_h, 1e-9)

                    cell_aspect = cell_w / max(cell_h, 1e-9)
                    aspect_error = abs(
                        math.log(max(cell_aspect, 1e-9) / max(src_aspect, 1e-9))
                    )
                    orientation_match = (
                        1.0
                        if (is_landscape and rows >= cols)
                        or ((not is_landscape) and cols >= rows)
                        else 0.0
                    )

                    score = (float(n), orientation_match, fill_ratio, -aspect_error)
                    if fallback_score is None or score > fallback_score:
                        fallback_score = score
                        fallback_grid = (cols, rows)

                    if area < min_thumb_area:
                        continue
                    if best_score is None or score > best_score:
                        best_score = score
                        best_grid = (cols, rows)

                if best_grid is not None:
                    break

            cols, rows = best_grid if best_grid is not None else fallback_grid
            total_frames_needed = cols * rows

            outer_border_width = 1
            inner_border_width = 1 if min(canvas_w, canvas_h) >= 360 else 0
            border_width = outer_border_width + inner_border_width
            cell_slots: list[tuple[int, int, int, int, int, int, int, int]] = []

            for idx in range(total_frames_needed):
                col = idx % cols
                row = idx // cols
                x0 = int(round(col * canvas_w / cols))
                x1 = int(round((col + 1) * canvas_w / cols))
                y0 = int(round(row * canvas_h / rows))
                y1 = int(round((row + 1) * canvas_h / rows))

                ix0 = x0 + border_width
                iy0 = y0 + border_width
                ix1 = x1 - border_width
                iy1 = y1 - border_width

                if ix1 <= ix0:
                    ix0, ix1 = x0, x1
                if iy1 <= iy0:
                    iy0, iy1 = y0, y1

                inner_w = max(1, ix1 - ix0)
                inner_h = max(1, iy1 - iy0)
                cell_slots.append((x0, y0, x1, y1, ix0, iy0, inner_w, inner_h))

            avg_inner_w = max(
                1, int(sum(slot[6] for slot in cell_slots) / len(cell_slots))
            )
            font_size = max(12, avg_inner_w // 18)
            font = _get_cached_font(font_size)

            target_timestamps = self._compute_thumb_timestamps(
                duration, total_frames_needed
            )
            default_ts_step = (
                duration / max(total_frames_needed - 1, 1) if duration > 0 else 0.0
            )
            # 极致速度模式：直接按时间点 seek，抓取该位置首个可解码关键帧
            sampled_candidates = self._sample_thumb_frames_with_seek(
                container, stream, target_timestamps
            )

            canvas = Image.new("RGB", (canvas_w, canvas_h), (0, 0, 0))
            thumbnail_timestamps = target_timestamps.copy()

            if rotate_angle != 0:
                if hasattr(Image, "Transpose"):
                    rotate_map = {
                        90: Image.Transpose.ROTATE_270,
                        180: Image.Transpose.ROTATE_180,
                        270: Image.Transpose.ROTATE_90,
                    }
                else:
                    rotate_map = {
                        90: Image.ROTATE_270,
                        180: Image.ROTATE_180,
                        270: Image.ROTATE_90,
                    }
                rotate_op = rotate_map[rotate_angle]
            else:
                rotate_op = None

            available_indices = [
                idx
                for idx, (frame, _) in enumerate(sampled_candidates)
                if frame is not None
            ]
            if not available_indices:
                black_cache: dict[tuple[int, int], PILImage.Image] = {}
                for slot in cell_slots:
                    _, _, _, _, ix0, iy0, inner_w, inner_h = slot
                    size_key = (inner_w, inner_h)
                    black = black_cache.get(size_key)
                    if black is None:
                        black = Image.new("RGB", size_key, (0, 0, 0))
                        black_cache[size_key] = black
                    canvas.paste(black, (ix0, iy0))
            else:
                transformed_cache: dict[int, PILImage.Image] = {}
                crop_box_cache: dict[tuple[int, int], tuple[int, int, int, int]] = {}
                render_cache: dict[tuple[int, int, int], PILImage.Image] = {}
                for slot_idx, slot in enumerate(cell_slots):
                    _, _, _, _, ix0, iy0, inner_w, inner_h = slot
                    source_idx = slot_idx
                    frame, ts = sampled_candidates[source_idx]
                    if frame is None:
                        source_idx = min(
                            available_indices,
                            key=lambda i: abs(
                                sampled_candidates[i][1] - target_timestamps[slot_idx]
                            ),
                        )
                        frame, ts = sampled_candidates[source_idx]

                    if frame is None:
                        continue

                    thumbnail_timestamps[slot_idx] = ts
                    key = (source_idx, inner_w, inner_h)
                    cached_img = render_cache.get(key)
                    if cached_img is None:
                        transformed = transformed_cache.get(source_idx)
                        if transformed is None:
                            src_frame = frame
                            transformed = src_frame.to_image()
                            if crop_box is not None:
                                frame_shape = (transformed.width, transformed.height)
                                frame_crop_box = crop_box_cache.get(frame_shape)
                                if frame_crop_box is None:
                                    frame_crop_box = self._scale_crop_box(
                                        crop_box,
                                        (v_width, v_height),
                                        frame_shape,
                                    )
                                    crop_box_cache[frame_shape] = frame_crop_box
                                transformed = transformed.crop(frame_crop_box)
                            if rotate_op is not None:
                                transformed = transformed.transpose(rotate_op)
                            transformed_cache[source_idx] = transformed

                        if (
                            transformed.width != inner_w
                            or transformed.height != inner_h
                        ):
                            cached_img = transformed.resize(
                                (inner_w, inner_h), fast_resample
                            )
                        else:
                            cached_img = transformed

                        render_cache[key] = cached_img

                    canvas.paste(cached_img, (ix0, iy0))

            draw_canvas = ImageDraw.Draw(canvas)
            if time.perf_counter() - func_start < 0.22:
                for idx, ts in enumerate(thumbnail_timestamps):
                    use_ts = ts if ts > 0 else default_ts_step * idx
                    hours = int(use_ts // 3600)
                    minutes = int((use_ts % 3600) // 60)
                    seconds = int(use_ts % 60)
                    text = (
                        f"{hours}:{minutes:02d}:{seconds:02d}"
                        if hours > 0
                        else f"{minutes}:{seconds:02d}"
                    )
                    _, _, _, _, ix0, iy0, _, _ = cell_slots[idx]
                    tx = ix0 + (font_size // 3)
                    ty = iy0 + (font_size // 4)
                    draw_canvas.text(
                        (tx + 1, ty + 1), text, fill=(16, 16, 16), font=font
                    )
                    draw_canvas.text((tx, ty), text, fill=(238, 238, 238), font=font)

            outer_border_color = (58, 58, 58)
            inner_border_color = (132, 132, 132)
            for x0, y0, x1, y1, *_ in cell_slots:
                for i in range(outer_border_width):
                    draw_canvas.rectangle(
                        (x0 + i, y0 + i, x1 - 1 - i, y1 - 1 - i),
                        outline=outer_border_color,
                    )
                for i in range(inner_border_width):
                    offset = outer_border_width + i
                    draw_canvas.rectangle(
                        (
                            x0 + offset,
                            y0 + offset,
                            x1 - 1 - offset,
                            y1 - 1 - offset,
                        ),
                        outline=inner_border_color,
                    )

            return canvas

    # ======================== 采样策略 ========================

    def _sample_with_seek(
        self,
        container: av.container.InputContainer,
        stream: av.video.stream.VideoStream,
        timestamps: list[float],
    ) -> list[av.VideoFrame]:
        frames: list[av.VideoFrame] = []
        for ts in timestamps:
            frame = self._seek_and_get_frame(container, stream, ts)
            if frame is not None:
                frames.append(frame)
        return frames

    def _seek_and_get_frame(
        self,
        container: av.container.InputContainer,
        stream: av.video.stream.VideoStream,
        timestamp: float,
    ) -> Optional[av.VideoFrame]:
        time_base = stream.time_base
        if time_base is None:
            return None

        seek_target = max(0, int(timestamp / float(time_base)))
        try:
            container.seek(seek_target, stream=stream, backward=True, any_frame=False)
        except av.error.FFmpegError as e:
            logger.debug(f"seek 失败 ts={timestamp:.2f}s: {e}")
            return None

        decoded = 0
        max_frames = self.seek_skip_frames + 12

        for packet in container.demux(stream):
            for frame in packet.decode():
                decoded += 1
                if decoded <= self.seek_skip_frames:
                    continue
                return frame
            if decoded >= max_frames:
                return None

        return None

    @staticmethod
    def _compute_thumb_timestamps(duration: float, total_count: int) -> list[float]:
        if total_count <= 0:
            return []

        safe_duration = max(0.0, duration)
        if safe_duration <= 0.0:
            return [0.0 for _ in range(total_count)]

        if safe_duration < 4.0:
            start = 0.0
            end = safe_duration
        else:
            margin = min(3.0, safe_duration * 0.05)
            start = margin
            end = max(start, safe_duration - margin)

        if total_count == 1:
            return [0.5 * (start + end)]

        if end <= start:
            return [start for _ in range(total_count)]

        step = (end - start) / (total_count - 1)
        return [start + i * step for i in range(total_count)]

    def _sample_thumb_frames_with_seek(
        self,
        container: av.container.InputContainer,
        stream: av.video.stream.VideoStream,
        timestamps: list[float],
    ) -> list[tuple[Optional[av.VideoFrame], float]]:
        if not timestamps:
            return []

        max_probe_packets = max(
            8, min(256, int(os.getenv("VIDEO_INFO_THUMB_SEEK_MAX_PACKETS", "64")))
        )
        return [
            self._seek_first_thumb_frame(
                container=container,
                stream=stream,
                timestamp=ts,
                max_probe_packets=max_probe_packets,
            )
            for ts in timestamps
        ]

    def _seek_first_thumb_frame(
        self,
        container: av.container.InputContainer,
        stream: av.video.stream.VideoStream,
        timestamp: float,
        max_probe_packets: int,
    ) -> tuple[Optional[av.VideoFrame], float]:
        time_base = stream.time_base
        if time_base is None:
            return None, timestamp

        seek_target = max(0, int(timestamp / float(time_base)))
        try:
            container.seek(seek_target, stream=stream, backward=True, any_frame=False)
        except av.error.FFmpegError as e:
            logger.debug(f"seek 失败 ts={timestamp:.2f}s: {e}")
            return None, timestamp

        probed_packets = 0
        for packet in container.demux(stream):
            probed_packets += 1
            for frame in packet.decode():
                return frame, self._frame_timestamp_second(
                    frame=frame, stream=stream, fallback=timestamp
                )
            if probed_packets >= max_probe_packets:
                break

        return None, timestamp

    @staticmethod
    def _frame_timestamp_second(
        frame: av.VideoFrame,
        stream: av.video.stream.VideoStream,
        fallback: float,
    ) -> float:
        if frame.pts is not None and stream.time_base is not None:
            return float(frame.pts * stream.time_base)
        return fallback

    def _sample_sequentially(
        self,
        container: av.container.InputContainer,
        stream: av.video.stream.VideoStream,
        num_frames: int,
    ) -> list[av.VideoFrame]:
        all_frames: list[av.VideoFrame] = []
        for packet in container.demux(stream):
            for frame in packet.decode():
                all_frames.append(frame)

        if not all_frames:
            return []

        total = len(all_frames)
        if total <= num_frames:
            return all_frames

        indices = {
            int(round(i * (total - 1) / max(num_frames - 1, 1)))
            for i in range(num_frames)
        }
        return [all_frames[i] for i in sorted(indices)]

    # ======================== 帧采集与状态管理 ========================

    def _feed(self, frame: av.VideoFrame) -> None:
        if self._original_size is None:
            self._original_size = (frame.width, frame.height)
            self._compute_detect_size()

        dw, dh = self._detect_size
        small = frame.reformat(width=dw, height=dh)
        gray = small.to_ndarray(format="gray").astype(np.float32)

        if self._accumulated is None:
            self._accumulated = np.zeros((dh, dw), dtype=np.uint8)

        # 缓存灰度帧供空域分析
        self._sampled_grays.append(gray)

        if self._prev_gray is not None:
            diff = np.abs(gray - self._prev_gray)
            mean_diff = diff.mean()
            if mean_diff >= self.scene_change_threshold:
                logger.debug(f"跳过场景切换帧 mean_diff={mean_diff:.2f}")
            elif mean_diff > 0.3:
                self._pair_count += 1
                # 模仿旧算法：二值化 → 形态学 → 连通域 → 将合格连通域的 bounding rect 填入累积图
                blurred = gaussian_filter(diff, sigma=1.0)
                binary = blurred > self.diff_threshold

                k = self.morph_kernel_size
                struct = np.ones((k, k), dtype=bool)
                binary = binary_opening(binary, structure=struct)
                binary = binary_closing(binary, structure=struct)

                labeled_frame, n_feat = label(binary)
                if n_feat > 0:
                    min_area = int(dw * dh * self.min_region_ratio)
                    areas = np.bincount(labeled_frame.ravel())
                    objects = find_objects(labeled_frame)
                    for lbl_idx, slc in enumerate(objects, start=1):
                        if slc is None:
                            continue
                        if areas[lbl_idx] < min_area:
                            continue
                        t, b = int(slc[0].start), int(slc[0].stop)
                        le, ri = int(slc[1].start), int(slc[1].stop)
                        # 将 bounding rect 区域填为 255
                        self._accumulated[t:b, le:ri] = 255

        self._prev_gray = gray

    def _reset(self) -> None:
        self._prev_gray = None
        self._accumulated = None
        self._pair_count = 0
        self._original_size = None
        self._detect_size = None
        self._scale_factor = 1.0
        self._sampled_grays = []

    def _run_detection(self) -> CropResult:
        if self._original_size is None:
            logger.debug("原始尺寸未初始化（未喂入任何帧），返回空结果")
            return CropResult(
                x=0, y=0, width=0, height=0, confidence=0.0, has_border=False
            )

        ow, oh = self._original_size

        # —— 策略1：运动检测 ——
        logger.debug(f"开始运行运动检测算法，有效帧对数: {self._pair_count}")
        motion_result = self._detect_by_motion()
        if motion_result is not None and motion_result.has_border:
            logger.info(f"运动检测发现边框: {motion_result}")
            return motion_result

        # —— 策略2：空域分析兜底 ——
        logger.debug("运动检测未发现有效边框，尝试空域分析")
        spatial_result = self._detect_by_spatial()
        if spatial_result is not None and spatial_result.has_border:
            logger.info(f"空域分析发现边框: {spatial_result}")
            return spatial_result

        logger.debug(f"两种策略均未发现边框，返回原始尺寸 {ow}x{oh}")
        return CropResult(
            x=0,
            y=0,
            width=self._align2_down(ow),
            height=self._align2_down(oh),
            confidence=0.0,
            has_border=False,
        )

    # ======================== 运动区域检测算法 ========================

    def _detect_by_motion(self) -> Optional[CropResult]:
        """
        基于帧间差分的累积变化区域检测。

        _feed 阶段已将每帧差分的合格连通域 bounding rect 填入累积图（0/255），
        此处直接对累积图做连通域分析，取最大矩形。
        """
        dw, dh = self._detect_size

        if self._pair_count == 0:
            logger.debug("pair_count=0，无有效帧对，跳过运动检测")
            return None

        # 累积图已是 0/255 的 uint8，直接二值化
        binary = self._accumulated > 0

        if not binary.any():
            logger.debug("累积图无变化区域")
            return None

        # 连通域分析
        labeled, num_features = label(binary)
        logger.debug(f"累积图连通域数量: {num_features}")

        if num_features == 0:
            return None

        # 找最大连通域（按 bounding rect 面积）
        max_area = 0
        best_rect = None
        for slc in find_objects(labeled):
            if slc is None:
                continue
            t, b = int(slc[0].start), int(slc[0].stop)
            le, ri = int(slc[1].start), int(slc[1].stop)
            rect_area = (b - t) * (ri - le)
            if rect_area > max_area:
                max_area = rect_area
                best_rect = (t, b, le, ri)

        if best_rect is None:
            return None

        top, bottom, left, right = best_rect
        total_area = dh * dw

        if max_area < total_area * 0.3:
            logger.debug(f"最大变化区域太小 area={max_area} < {total_area * 0.3:.0f}")
            return None

        border_ratio = 1.0 - (max_area / total_area)
        conf = min(1.0, border_ratio * 5) * 0.8

        has_border = (
            top > dh * self.min_border_ratio
            or (dh - bottom) > dh * self.min_border_ratio
            or left > dw * self.min_border_ratio
            or (dw - right) > dw * self.min_border_ratio
        )

        if not has_border:
            logger.debug(
                "活动区域未超出边框阈值，判定为无边框 "
                f"top={top} bottom={bottom} left={left} right={right} "
                f"dh={dh} dw={dw}"
            )
            return None

        logger.debug(
            f"检测到边框区域 top={top} bottom={bottom} left={left} "
            f"right={right} conf={conf:.4f}"
        )
        # 向内收缩安全边距
        top = min(dh - 1, top + self.safety_margin)
        bottom = max(0, bottom - self.safety_margin)
        left = min(dw - 1, left + self.safety_margin)
        right = max(0, right - self.safety_margin)

        return self._to_crop_result(top, bottom, left, right, conf, True)

    # ======================== 空域分析算法 ========================

    def _detect_by_spatial(self) -> Optional[CropResult]:
        """
        基于全局亮度阈值的空域黑边检测。

        对每帧：边缘暗度预检 → 全局亮度二值化 → 形态学开闭 → 内容区域 bounding box
        对所有帧的矩形结果投票，取最频繁的裁剪区域。
        适用于画面变化不大但有黑色/暗色边框的场景。
        """
        if not self._sampled_grays:
            logger.debug("无缓存灰度帧，跳过空域分析")
            return None

        dw, dh = self._detect_size

        rects: list[tuple[int, int, int, int]] = []

        for gray in self._sampled_grays:
            rect = self._analyze_single_frame_spatial(gray, dw, dh)
            if rect is not None:
                rects.append(rect)

        if not rects:
            logger.debug("空域分析：所有帧均未检测到有效矩形")
            return None

        # 投票取最频繁的矩形
        most_common_rect, count = Counter(rects).most_common(1)[0]
        top, bottom, left, right = most_common_rect
        vote_ratio = count / len(rects)

        logger.debug(
            f"空域分析投票结果: top={top} bottom={bottom} left={left} right={right} "
            f"得票={count}/{len(rects)} ({vote_ratio:.1%})"
        )

        # 投票率太低说明帧间结果不一致，不可信
        if vote_ratio < 0.3:
            logger.debug(f"空域分析投票率过低 {vote_ratio:.1%}，结果不可信")
            return None

        # 检查是否真的存在边框
        has_border = (
            top > dh * self.min_border_ratio
            or (dh - bottom) > dh * self.min_border_ratio
            or left > dw * self.min_border_ratio
            or (dw - right) > dw * self.min_border_ratio
        )

        if not has_border:
            logger.debug("空域分析：活动区域未超出边框阈值")
            return None

        conf = min(1.0, vote_ratio) * 0.7

        # 向内收缩安全边距，确保不残留黑边
        top = min(dh - 1, top + self.safety_margin)
        bottom = max(0, bottom - self.safety_margin)
        left = min(dw - 1, left + self.safety_margin)
        right = max(0, right - self.safety_margin)

        return self._to_crop_result(top, bottom, left, right, conf, True)

    def _analyze_single_frame_spatial(
        self,
        gray: np.ndarray,
        dw: int,
        dh: int,
    ) -> Optional[tuple[int, int, int, int]]:
        """
        对单帧灰度图进行空域黑边检测，返回 (top, bottom, left, right) 或 None。

        从画面中心向四周扫描：
        - 用图像中心的窄带计算每行/列亮度，避免被垂直/水平方向黑边稀释
        - 从中心向外扫描，遇到第一行/列均值低于黑边阈值即为边框起点
        """
        bright_th = self.spatial_border_max_brightness

        # 预检：图像边缘是否足够暗
        edge_pixels = np.concatenate(
            [
                gray[0, :].ravel(),
                gray[-1, :].ravel(),
                gray[:, 0].ravel(),
                gray[:, -1].ravel(),
            ]
        )
        if np.median(edge_pixels) > self.spatial_edge_threshold:
            return None

        cy, cx = dh // 2, dw // 2

        # 取中心 10% 宽的水平窄带，计算每行的平均亮度
        # 这样不受左右黑边影响
        band_w = max(3, int(dw * 0.10))
        h_left = max(0, cx - band_w // 2)
        h_right = min(dw, cx + band_w // 2 + 1)
        row_means = gray[:, h_left:h_right].mean(axis=1)  # shape: (dh,)

        # 取中心 10% 高的垂直窄带，计算每列的平均亮度
        # 这样不受上下黑边影响
        band_h = max(3, int(dh * 0.10))
        v_top = max(0, cy - band_h // 2)
        v_bottom = min(dh, cy + band_h // 2 + 1)
        col_means = gray[v_top:v_bottom, :].mean(axis=0)  # shape: (dw,)

        # 确认中心确实是亮的（是内容区），否则无法从中心外扫
        if row_means[cy] <= bright_th or col_means[cx] <= bright_th:
            return None

        # 从中心向上扫描，找到第一个暗行
        top = 0
        for i in range(cy, -1, -1):
            if row_means[i] <= bright_th:
                top = i + 1
                break

        # 从中心向下扫描
        bottom = dh
        for i in range(cy, dh):
            if row_means[i] <= bright_th:
                bottom = i
                break

        # 从中心向左扫描
        left = 0
        for i in range(cx, -1, -1):
            if col_means[i] <= bright_th:
                left = i + 1
                break

        # 从中心向右扫描
        right = dw
        for i in range(cx, dw):
            if col_means[i] <= bright_th:
                right = i
                break

        # 基本合法性检查
        if top >= bottom or left >= right:
            return None

        content_area = (bottom - top) * (right - left)
        if content_area < dh * dw * 0.1:
            return None

        return (top, bottom, left, right)

    # ======================== 通用辅助 ========================

    @staticmethod
    def _normalize_crop_box(
        crop_result: CropResult,
        src_width: int,
        src_height: int,
    ) -> tuple[int, int, int, int]:
        if src_width <= 0 or src_height <= 0:
            raise ValueError("视频分辨率非法，无法应用裁剪")
        if crop_result.width <= 0 or crop_result.height <= 0:
            raise ValueError("crop_result 的 width/height 必须是正整数")

        x0 = int(crop_result.x)
        y0 = int(crop_result.y)
        x1 = int(crop_result.x + crop_result.width)
        y1 = int(crop_result.y + crop_result.height)

        x0 = max(0, min(x0, src_width))
        y0 = max(0, min(y0, src_height))
        x1 = max(0, min(x1, src_width))
        y1 = max(0, min(y1, src_height))

        if x1 <= x0 or y1 <= y0:
            raise ValueError("crop_result 超出视频范围，无法生成缩略图")
        return x0, y0, x1, y1

    @staticmethod
    def _scale_crop_box(
        crop_box: tuple[int, int, int, int],
        src_size: tuple[int, int],
        dst_size: tuple[int, int],
    ) -> tuple[int, int, int, int]:
        src_w, src_h = src_size
        dst_w, dst_h = dst_size
        if src_w <= 0 or src_h <= 0 or dst_w <= 0 or dst_h <= 0:
            raise ValueError("裁剪缩放尺寸非法")

        x0, y0, x1, y1 = crop_box
        sx = dst_w / src_w
        sy = dst_h / src_h

        nx0 = int(math.floor(x0 * sx))
        ny0 = int(math.floor(y0 * sy))
        nx1 = int(math.ceil(x1 * sx))
        ny1 = int(math.ceil(y1 * sy))

        nx0 = max(0, min(nx0, dst_w - 1))
        ny0 = max(0, min(ny0, dst_h - 1))
        nx1 = max(nx0 + 1, min(nx1, dst_w))
        ny1 = max(ny0 + 1, min(ny1, dst_h))
        return nx0, ny0, nx1, ny1

    @staticmethod
    def _resolve_total_frames(
        video_stream: av.video.stream.VideoStream,
        fps: float,
        duration_second: float,
    ) -> int:
        if video_stream.frames and video_stream.frames > 0:
            return int(video_stream.frames)
        if fps > 0 and duration_second > 0:
            return int(round(fps * duration_second))
        return 0

    @staticmethod
    def _resolve_video_fps(stream: av.video.stream.VideoStream) -> float:
        if stream.average_rate is not None:
            return float(stream.average_rate)
        if stream.base_rate is not None:
            return float(stream.base_rate)
        return 0.0

    @staticmethod
    def _resolve_video_duration(
        container: av.container.InputContainer,
        stream: av.video.stream.VideoStream,
    ) -> float:
        if container.duration is not None:
            return float(container.duration / av.time_base)
        if stream.duration is not None and stream.time_base is not None:
            return float(stream.duration * stream.time_base)
        return 0.0

    @staticmethod
    def _compute_sample_plan(duration: float, fps: float) -> dict:
        safe_duration = max(0.0, duration)
        safe_fps = fps if fps > 0 else 30.0
        total_frames = int(safe_duration * safe_fps)

        if total_frames <= 1:
            return {"num_frames": 1, "timestamps": [0.0]}

        if safe_duration < 2.0:
            n = min(total_frames, 10)
        elif safe_duration < 30.0:
            n = 10
        elif safe_duration < 600.0:
            n = 20
        else:
            n = 30

        start = safe_duration * 0.05
        end = safe_duration * 0.95
        if start >= end:
            start, end = 0.0, safe_duration

        timestamps = [start + i * (end - start) / max(n - 1, 1) for i in range(n)]
        return {"num_frames": n, "timestamps": timestamps}

    def _to_crop_result(
        self,
        top: int,
        bottom: int,
        left: int,
        right: int,
        conf: float,
        has_border: bool,
    ) -> CropResult:
        ow, oh = self._original_size

        if has_border:
            s = self._scale_factor
            ox = self._align2(int(round(left * s)))
            oy = self._align2(int(round(top * s)))
            cw = self._align2_down(int(round((right - left) * s)))
            ch = self._align2_down(int(round((bottom - top) * s)))

            ox = max(0, min(ox, ow - 2))
            oy = max(0, min(oy, oh - 2))
            cw = min(cw, ow - ox)
            ch = min(ch, oh - oy)
            cw = self._align2_down(cw)
            ch = self._align2_down(ch)

            if cw < ow * 0.15 or ch < oh * 0.15:
                has_border = False

        if not has_border:
            ox, oy = 0, 0
            cw = self._align2_down(ow)
            ch = self._align2_down(oh)
            conf = 0.0

        return CropResult(
            x=ox,
            y=oy,
            width=cw,
            height=ch,
            confidence=round(conf, 4),
            has_border=has_border,
        )

    def _compute_detect_size(self) -> None:
        ow, oh = self._original_size
        short = min(ow, oh)
        if short <= self.detect_short_edge:
            self._detect_size = (ow, oh)
            self._scale_factor = 1.0
        else:
            s = self.detect_short_edge / short
            dw = max(2, self._align2_down(int(round(ow * s))))
            dh = max(2, self._align2_down(int(round(oh * s))))
            self._detect_size = (dw, dh)
            self._scale_factor = 1.0 / s

    @staticmethod
    def _align2(v: int) -> int:
        return v + (v % 2)

    @staticmethod
    def _align2_down(v: int) -> int:
        return v - (v % 2)


if __name__ == "__main__":
    import time
    from PIL import Image

    start_time = time.time()
    # video_path = r"E:\load\python\Project\VideoFusion\测试\dy\4938d41224254f9f0ac996ea88814782.mp4"
    video_path = r"G:\CodingSpace\Project\VideoMerger\测试视频\b1.mp4"
    detector = VideoInfoReader()
    info = detector.read_info(Path(video_path))
    print(info)
    print(f"检测耗时: {time.time() - start_time:.2f} 秒")

    if info.crop_result is not None:
        arr = detector.preview(
            Path(video_path), frame_index=0, crop_result=info.crop_result
        )
        Image.fromarray(arr).save("output.png")
        print("预览已保存到 output.png")
