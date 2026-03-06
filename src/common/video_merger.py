from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from time import monotonic
from typing import Sequence
from collections import Counter
from enum import Enum
import math
import sys

import av
import numpy as np
from PIL import Image
from av.video.reformatter import Interpolation
from loguru import logger
from PySide6.QtGui import QImage

from src.common.video_info_reader import VideoInfoReader, CropResult
from src.service.merge_signals import MergeCancelled, get_merge_signals
from dataclasses import dataclass

logger.remove()
logger.add(
    "log.log",
    level="DEBUG",
    encoding="utf-8",
    enqueue=True,
)
logger.add(sys.stderr, level="INFO")


@dataclass(frozen=True)
class InputVideoInfo:
    file_path: Path
    crop_result: CropResult | None = None
    rotation: Rotation | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    audio_sample_rate: int | None = None
    total_frames: int | None = None


class Orientation(Enum):
    HORIZONTAL = 0
    VERTICAL = 1


class Rotation(Enum):
    ROTATE_0 = 0
    ROTATE_90 = 90
    ROTATE_180 = 180
    ROTATE_270 = 270


class VideoProcessMode(Enum):
    QUALITY = 0
    BALANCED = 1
    SPEED = 2


_PREVIEW_MAX_EDGE = 320


def _frame_to_qimage(frame: av.VideoFrame, max_edge: int = _PREVIEW_MAX_EDGE) -> QImage:
    """VideoFrame -> low-res QImage for progress preview."""
    src_w, src_h = frame.width, frame.height
    if src_w <= 0 or src_h <= 0:
        raise ValueError("预览帧尺寸非法")

    scale = min(1.0, max_edge / max(src_w, src_h))
    preview_w = max(1, int(round(src_w * scale)))
    preview_h = max(1, int(round(src_h * scale)))

    preview_frame = frame.reformat(
        width=preview_w,
        height=preview_h,
        format="rgb24",
        interpolation=Interpolation.FAST_BILINEAR,
    )
    rgb = preview_frame.to_ndarray()
    qimg = QImage(
        rgb.data,
        preview_frame.width,
        preview_frame.height,
        rgb.strides[0],
        QImage.Format.Format_RGB888,
    )
    return qimg.copy()


class VideoMerger:
    # 各处理模式的编码器配置
    # QUALITY: 最高画质
    # BALANCED: 均衡模式
    # SPEED: 最高速度
    _MODE_CONFIGS: dict[VideoProcessMode, dict] = {
        VideoProcessMode.QUALITY: {
            "codec_options": {
                "preset": "slow",
                "crf": "23",
                "qcomp": "0.5",
                "psy-rd": "0.3:0",
                "aq-mode": "2",
                "aq-strength": "0.8",
            },
            "audio_bitrate": 256_000,
            "container_options": {"movflags": "+faststart"},
            "scale_flags": "bicubic",
        },
        VideoProcessMode.BALANCED: {
            "codec_options": {"preset": "medium", "bf": "0", "crf": "20"},
            "audio_bitrate": 192_000,
            "container_options": {"movflags": "+faststart"},
            "scale_flags": "bicubic",
        },
        VideoProcessMode.SPEED: {
            "codec_options": {
                "preset": "veryfast",
                "crf": "20",
            },
            "audio_bitrate": 160_000,
            "container_options": {"movflags": "+faststart"},
            "scale_flags": "bilinear",
        },
    }

    def merge(
        self,
        input_files: Sequence[InputVideoInfo],
        output_file: Path,
        process_mode: VideoProcessMode = VideoProcessMode.BALANCED,
        enable_border_detection: bool = True,
        target_fps: int = -1,
        orientation: Orientation = Orientation.VERTICAL,
        target_resolution: tuple[int, int] | None = None,
        cover_image_path: Path | None = None,
    ) -> None:
        if not input_files:
            raise ValueError("input_files 不能为空")
        if any(not isinstance(v, InputVideoInfo) for v in input_files):
            raise TypeError("input_files 的元素类型必须是 InputVideoInfo")
        if not isinstance(output_file, Path):
            raise TypeError("output_file 类型必须是 pathlib.Path")
        if not isinstance(process_mode, VideoProcessMode):
            raise TypeError("process_mode 类型必须是 VideoProcessMode")
        if not isinstance(enable_border_detection, bool):
            raise TypeError("enable_border_detection 类型必须是 bool")
        if not isinstance(target_fps, int):
            raise TypeError("target_fps 类型必须是 int")
        if target_fps != -1 and target_fps <= 0:
            raise ValueError("target_fps 必须为 -1 或正整数")

        signals = get_merge_signals()

        # ===== 预处理: 收集裁剪、旋转信息、有效尺寸、帧率和音频采样率 =====
        preprocessed: list[tuple[CropResult | None, Rotation]] = []
        effective_dimensions: list[tuple[int, int]] = []
        source_fps_values: list[float] = []
        source_audio_rates: list[int] = []

        for video_info in input_files:
            input_file = video_info.file_path
            if not input_file.exists():
                raise FileNotFoundError(f"文件不存在: {input_file}")

            # 复用调用方预先计算的裁剪结果；仅在完全缺失时才再次检测
            crop_result = video_info.crop_result
            if crop_result is None and enable_border_detection:
                crop_result = self._detect_border(input_file)
            effective_crop = (
                crop_result
                if crop_result is not None and crop_result.has_border
                else None
            )

            raw_w = video_info.width
            raw_h = video_info.height
            video_fps = video_info.fps
            audio_rate = video_info.audio_sample_rate

            # 仅当调用方没有提供完整元数据时，才回退到 probe。
            if (
                raw_w is None
                or raw_h is None
                or video_fps is None
                or video_fps <= 0
                or audio_rate is None
            ):
                with av.open(str(input_file)) as probe_container:
                    try:
                        in_video_stream = probe_container.streams.video[0]
                    except IndexError as exc:
                        raise ValueError(f"文件缺少视频流: {input_file}") from exc

                    raw_w = int(in_video_stream.width)
                    raw_h = int(in_video_stream.height)
                    video_fps = float(
                        in_video_stream.average_rate or in_video_stream.rate or 30
                    )

                    try:
                        in_audio_stream = probe_container.streams.audio[0]
                        audio_rate = int(in_audio_stream.rate)
                    except IndexError:
                        audio_rate = -1

            source_fps_values.append(video_fps)
            if audio_rate > 0:
                source_audio_rates.append(audio_rate)

            # 裁剪后的有效尺寸
            if effective_crop is not None:
                eff_w, eff_h = effective_crop.width, effective_crop.height
            else:
                eff_w, eff_h = raw_w, raw_h

            # 判断是否需要旋转
            needs_rot = self._needs_rotation(eff_w, eff_h, orientation)
            if needs_rot:
                effective_rotation = (
                    video_info.rotation
                    if video_info.rotation is not None
                    else Rotation.ROTATE_90
                )
            else:
                effective_rotation = Rotation.ROTATE_0

            # 旋转后的尺寸
            if self._rotation_swaps_dimensions(effective_rotation):
                final_w, final_h = eff_h, eff_w
            else:
                final_w, final_h = eff_w, eff_h

            preprocessed.append((effective_crop, effective_rotation))
            effective_dimensions.append((final_w, final_h))

        # ===== 确定目标帧率和音频采样率 =====
        if target_fps != -1:
            effective_fps = target_fps
        else:
            effective_fps = (
                max(int(math.ceil(f)) for f in source_fps_values)
                if source_fps_values
                else 30
            )
        target_audio_rate = max(source_audio_rates) if source_audio_rates else 44100
        target_fps_fraction = Fraction(effective_fps, 1)
        # 使用编码器原生 time_base=1/fps，PTS 直接用帧序号（0,1,2,...）
        # 避免自定义 time_base 的截断误差导致 DTS 碰撞
        video_time_base = Fraction(1, effective_fps)

        logger.info(f"目标帧率: {effective_fps} fps")
        logger.info(f"目标音频采样率: {target_audio_rate} Hz")

        # ===== 确定目标分辨率 =====
        if target_resolution is not None:
            target_width, target_height = target_resolution
            if orientation == Orientation.HORIZONTAL and target_width < target_height:
                raise ValueError(
                    f"目标分辨率 {target_width}x{target_height} 与横屏方向不一致"
                )
            if orientation == Orientation.VERTICAL and target_width > target_height:
                raise ValueError(
                    f"目标分辨率 {target_width}x{target_height} 与竖屏方向不一致"
                )
        else:
            target_width, target_height = self._get_most_compatible_resolution(
                effective_dimensions
            )

        logger.info(f"目标分辨率: {target_width}x{target_height}")

        # ===== 处理视频 =====
        output_file.parent.mkdir(parents=True, exist_ok=True)
        mode_cfg = self._MODE_CONFIGS[process_mode]
        output_container = av.open(
            str(output_file),
            mode="w",
            options=mode_cfg.get("container_options"),
        )

        audio_time_base = Fraction(1, target_audio_rate)

        # 在 mux 任何 packet 之前，先把视频和音频两个输出流都注册好，
        # 否则 MP4 muxer 在首次 mux() 时写入 header，
        # 遗漏后续添加的 stream，导致输出文件损坏。
        out_video = output_container.add_stream("libx264", rate=target_fps_fraction)
        out_video.width = target_width
        out_video.height = target_height
        out_video.pix_fmt = "yuv420p"
        out_video.time_base = video_time_base
        out_video.thread_type = "AUTO"
        out_video.codec_context.options = mode_cfg["codec_options"]

        out_audio = output_container.add_stream("aac", rate=target_audio_rate)
        out_audio.time_base = audio_time_base
        audio_bitrate = mode_cfg.get("audio_bitrate")
        if audio_bitrate:
            out_audio.bit_rate = int(audio_bitrate)

        # ===== 封面流 =====
        if cover_image_path is not None:
            if not isinstance(cover_image_path, Path):
                raise TypeError("cover_image_path 类型必须是 pathlib.Path 或 None")
            if not cover_image_path.exists():
                raise FileNotFoundError(f"封面图片不存在: {cover_image_path}")

            img = Image.open(str(cover_image_path)).convert("RGB")
            cover_stream = output_container.add_stream("mjpeg")
            cover_stream.width = img.width
            cover_stream.height = img.height
            cover_stream.pix_fmt = "yuvj420p"
            try:
                cover_stream.disposition = 0x0400  # AV_DISPOSITION_ATTACHED_PIC
            except (AttributeError, TypeError):
                logger.warning("无法设置 attached_pic disposition")

            cover_frame = av.VideoFrame.from_image(img).reformat(format="yuvj420p")
            for pkt in cover_stream.encode(cover_frame):
                pkt.stream = cover_stream
                output_container.mux(pkt)
            for pkt in cover_stream.encode():
                pkt.stream = cover_stream
                output_container.mux(pkt)

            logger.info(f"已设置封面图片: {cover_image_path}")

        video_pts_offset = 0
        audio_pts_offset = 0
        last_progress_emit = 0.0
        last_display_emit = 0.0

        signals.mergeStarted.emit(len(input_files), effective_fps)

        try:
            for file_index, video_info in enumerate(input_files):
                if signals.is_cancelled():
                    raise MergeCancelled("已取消")

                input_file = video_info.file_path
                crop_result, effective_rotation = preprocessed[file_index]

                logger.info(
                    f"处理文件 {file_index + 1}/{len(input_files)}: {input_file}"
                )
                input_container = av.open(str(input_file))

                try:
                    in_video = input_container.streams.video[0]
                except IndexError as exc:
                    input_container.close()
                    raise ValueError(f"文件缺少视频流: {input_file}") from exc

                # 音频流可选，缺失时后续会生成静音填充
                try:
                    in_audio = input_container.streams.audio[0]
                except IndexError:
                    in_audio = None
                    logger.warning(f"文件缺少音频流，将填充静音: {input_file}")

                # 多线程解码不影响画质，始终启用
                in_video.thread_type = "AUTO"

                estimated_total_frames = int(video_info.total_frames or 0)
                if estimated_total_frames <= 0:
                    estimated_total_frames = int(in_video.frames or 0)
                if (
                    estimated_total_frames <= 0
                    and in_video.duration is not None
                    and in_video.time_base is not None
                ):
                    duration_seconds = float(in_video.duration * in_video.time_base)
                    stream_fps = float(
                        in_video.average_rate or in_video.rate or effective_fps
                    )
                    if duration_seconds > 0 and stream_fps > 0:
                        estimated_total_frames = int(
                            max(1, round(duration_seconds * stream_fps))
                        )

                signals.fileStarted.emit(
                    file_index + 1,
                    input_file.name,
                    estimated_total_frames if estimated_total_frames > 0 else 0,
                )

                filter_graph = self._build_filter_graph(
                    in_video,
                    effective_rotation,
                    crop_result,
                    target_width,
                    target_height,
                    effective_fps,
                    mode_cfg["scale_flags"],
                )

                # 创建音频重采样器，统一采样率、采样格式和声道布局
                # 即使采样率相同，不同视频文件的采样格式(s16/fltp/s32)或
                # 声道布局(mono/stereo)可能不同，必须全部统一到 AAC 编码器期望的格式
                resampler = av.AudioResampler(
                    format="fltp",
                    layout="stereo",
                    rate=target_audio_rate,
                )

                segment_video_frame_count = 0
                segment_audio_sample_count = 0

                def _encode_video_frame(frm):
                    nonlocal segment_video_frame_count
                    frm.pts = video_pts_offset + segment_video_frame_count
                    frm.time_base = video_time_base
                    segment_video_frame_count += 1
                    for out_packet in out_video.encode(frm):
                        out_packet.stream = out_video
                        output_container.mux(out_packet)

                def _encode_audio_frame(frm):
                    nonlocal segment_audio_sample_count
                    new_pts = audio_pts_offset + segment_audio_sample_count
                    segment_audio_sample_count += frm.samples
                    frm.pts = new_pts
                    frm.time_base = audio_time_base
                    for out_packet in out_audio.encode(frm):
                        out_packet.stream = out_audio
                        output_container.mux(out_packet)

                # 单遍同时 demux 视频和音频，交错编码并 mux
                demux_streams = [in_video] + ([in_audio] if in_audio else [])
                for packet in input_container.demux(*demux_streams):
                    if signals.is_cancelled():
                        raise MergeCancelled("已取消")

                    if packet.stream.type == "video":
                        for frame in packet.decode():
                            filter_graph["src"].push(frame)
                            while True:
                                try:
                                    filtered_frame = filter_graph["sink"].pull()
                                except (BlockingIOError, EOFError):
                                    break

                                # Emit display frame (throttled to 300ms)
                                now = monotonic()
                                if now - last_display_emit >= 0.3:
                                    last_display_emit = now
                                    try:
                                        qimg = _frame_to_qimage(filtered_frame)
                                        signals.displayFrameReady.emit(qimg)
                                    except Exception:
                                        pass

                                _encode_video_frame(filtered_frame)

                            # Emit progress (throttled to 300ms)
                            now = monotonic()
                            if now - last_progress_emit >= 0.3:
                                last_progress_emit = now
                                signals.frameProcessed.emit(
                                    segment_video_frame_count,
                                    estimated_total_frames if estimated_total_frames > 0 else 0,
                                )

                    elif packet.stream.type == "audio":
                        for frame in packet.decode():
                            for rf in resampler.resample(frame):
                                _encode_audio_frame(rf)

                # 刷新视频滤镜图中缓冲的剩余帧
                filter_graph["src"].push(None)
                while True:
                    if signals.is_cancelled():
                        raise MergeCancelled("已取消")
                    try:
                        filtered_frame = filter_graph["sink"].pull()
                    except (BlockingIOError, EOFError):
                        break
                    _encode_video_frame(filtered_frame)

                # 刷新音频重采样器中缓冲的剩余采样
                for rf in resampler.resample(None):
                    _encode_audio_frame(rf)

                # 如果该片段没有音频轨道，生成静音帧填充对应时长
                if in_audio is None and segment_video_frame_count > 0:
                    silence_duration = segment_video_frame_count / effective_fps
                    silence_samples_needed = int(silence_duration * target_audio_rate)
                    samples_per_frame = max(
                        1024, int(out_audio.codec_context.frame_size or 0)
                    )
                    silence_buffer = np.zeros((2, samples_per_frame), dtype="float32")
                    full_silence_frames, silence_remainder = divmod(
                        silence_samples_needed, samples_per_frame
                    )

                    for _ in range(full_silence_frames):
                        silent_frame = av.AudioFrame.from_ndarray(
                            silence_buffer, format="fltp", layout="stereo"
                        )
                        silent_frame.rate = target_audio_rate
                        _encode_audio_frame(silent_frame)

                    if silence_remainder > 0:
                        silent_frame = av.AudioFrame.from_ndarray(
                            silence_buffer[:, :silence_remainder],
                            format="fltp",
                            layout="stereo",
                        )
                        silent_frame.rate = target_audio_rate
                        _encode_audio_frame(silent_frame)

                video_pts_offset += segment_video_frame_count
                # 将 audio offset 同步到 video offset 的时间线，消除累积漂移
                # 使用 max 防止回退：重采样可能产生比视频时长更多的音频样本，
                # 导致编码器内部缓冲的 PTS 高于按视频计算的值
                audio_pts_offset = max(
                    int(video_pts_offset / effective_fps * target_audio_rate),
                    audio_pts_offset + segment_audio_sample_count,
                )

                input_container.close()
                signals.fileFinished.emit(file_index + 1)
                # Final progress update for this file
                signals.frameProcessed.emit(
                    segment_video_frame_count,
                    estimated_total_frames if estimated_total_frames > 0 else 0,
                )
                logger.info(
                    f"完成，video offset -> {video_pts_offset}, "
                    f"audio offset -> {audio_pts_offset}"
                )

            # 刷新编码器缓冲区
            for out_packet in out_video.encode():
                out_packet.stream = out_video
                output_container.mux(out_packet)

            for out_packet in out_audio.encode():
                out_packet.stream = out_audio
                output_container.mux(out_packet)

            signals.mergeFinished.emit()
            logger.info(f"完成! 输出文件: {output_file}")
        except MergeCancelled:
            signals.mergeError.emit("已取消")
            logger.info("合并已取消")
        except Exception as exc:
            signals.mergeError.emit(str(exc))
            logger.exception("合并出错")
        finally:
            output_container.close()

    @staticmethod
    def _detect_border(input_file: Path) -> CropResult | None:
        detector = VideoInfoReader()
        video_info = detector.read_info(input_file)
        crop_result = video_info.crop_result
        if crop_result is not None and crop_result.has_border:
            logger.info(
                f"边框检测结果: has_border={crop_result.has_border}, "
                f"rect=({crop_result.x},{crop_result.y},"
                f"{crop_result.width},{crop_result.height}), "
                f"confidence={crop_result.confidence:.4f}"
            )
            return crop_result
        return None

    @staticmethod
    def _needs_rotation(width: int, height: int, orientation: Orientation) -> bool:
        """判断视频是否需要旋转以匹配目标方向。"""
        is_horizontal = width >= height
        want_horizontal = orientation == Orientation.HORIZONTAL
        return is_horizontal != want_horizontal

    @staticmethod
    def _rotation_swaps_dimensions(rotation: Rotation) -> bool:
        return rotation in (Rotation.ROTATE_90, Rotation.ROTATE_270)

    @staticmethod
    def _get_most_compatible_resolution(
        effective_dimensions: list[tuple[int, int]],
    ) -> tuple[int, int]:
        """根据所有视频的有效尺寸，选择最兼容的分辨率（最常见宽高比中最大的）。"""
        aspect_ratios = [round(w / h, 4) for w, h in effective_dimensions]
        most_common_ratio = Counter(aspect_ratios).most_common(1)[0][0]
        compatible = [
            dim
            for dim, ratio in zip(effective_dimensions, aspect_ratios)
            if ratio == most_common_ratio
        ]
        compatible.sort(key=lambda x: x[0] * x[1], reverse=True)
        return compatible[0]

    @staticmethod
    def _build_filter_graph(
        in_video: av.VideoStream,
        rotation: Rotation,
        crop_result: CropResult | None,
        target_width: int,
        target_height: int,
        target_fps: int | None = None,
        scale_flags: str = "bicubic",
    ) -> dict[str, object]:
        """构建滤镜图: 裁剪 -> 旋转 -> 帧率转换 -> 缩放+填充到目标尺寸。"""
        graph = av.filter.Graph()
        src = graph.add_buffer(template=in_video)
        last = src
        current_width = int(in_video.width)
        current_height = int(in_video.height)

        # 1. 裁剪
        if crop_result is not None:
            crop = graph.add(
                "crop",
                args=f"{crop_result.width}:{crop_result.height}:{crop_result.x}:{crop_result.y}",
            )
            last.link_to(crop)
            last = crop
            current_width = crop_result.width
            current_height = crop_result.height

        # 2. 旋转
        if rotation == Rotation.ROTATE_90:
            transpose = graph.add("transpose", args="clock")
            last.link_to(transpose)
            last = transpose
            current_width, current_height = current_height, current_width
        elif rotation == Rotation.ROTATE_270:
            transpose = graph.add("transpose", args="cclock")
            last.link_to(transpose)
            last = transpose
            current_width, current_height = current_height, current_width
        elif rotation == Rotation.ROTATE_180:
            vflip = graph.add("vflip")
            last.link_to(vflip)
            last = vflip
            hflip = graph.add("hflip")
            last.link_to(hflip)
            last = hflip

        # 3. 帧率转换
        source_fps = float(in_video.average_rate or in_video.base_rate or in_video.rate or 0)
        needs_fps_filter = (
            target_fps is not None
            and target_fps > 0
            and not math.isclose(source_fps, target_fps, rel_tol=0.0, abs_tol=1e-3)
        )
        if needs_fps_filter:
            fps_filter = graph.add("fps", args=str(target_fps))
            last.link_to(fps_filter)
            last = fps_filter

        # 4. 缩放 + 填充到目标尺寸
        needs_scale = current_width != target_width or current_height != target_height
        needs_pad = (
            needs_scale
            and current_width * target_height != current_height * target_width
        )
        if needs_scale:
            scale = graph.add(
                "scale",
                args=(
                    f"{target_width}:{target_height}:"
                    f"force_original_aspect_ratio=decrease:flags={scale_flags}"
                ),
            )
            last.link_to(scale)
            last = scale

        if needs_pad:
            pad = graph.add(
                "pad",
                args=f"{target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black",
            )
            last.link_to(pad)
            last = pad

        # 显式指定像素格式，避免编码器隐式转换的额外开销
        fmt = graph.add("format", args="pix_fmts=yuv420p")
        last.link_to(fmt)
        last = fmt

        sink = graph.add("buffersink")
        last.link_to(sink)
        graph.configure()

        return {"graph": graph, "src": src, "sink": sink}


if __name__ == "__main__":
    merger = VideoMerger()
    merger.merge(
        process_mode=VideoProcessMode.SPEED,
        input_files=[
            InputVideoInfo(
                file_path=Path(
                    r"E:\load\python\Project\VideoFusion\测试\dy\b7bb97e21600b07f66c21e7932cb7550.mp4"
                ),
                rotation=Rotation.ROTATE_90,
            ),
            InputVideoInfo(
                file_path=Path(r"G:\CodingSpace\Project\VideoMerger\测试视频\a1.mp4"),
                rotation=Rotation.ROTATE_90,
            ),
            InputVideoInfo(
                file_path=Path(r"G:\CodingSpace\Project\VideoMerger\测试视频\b1.mp4"),
                rotation=Rotation.ROTATE_90,
            ),
        ],
        output_file=Path("output.mp4"),
        orientation=Orientation.HORIZONTAL,
        cover_image_path=Path(r"F:\picture\R18\43759957_p0_master1200.jpg"),
    )
