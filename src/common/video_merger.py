from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from typing import Sequence
from collections import Counter
from enum import Enum
import sys

import av
import numpy as np
from PIL import Image
from loguru import logger

from src.progress_reporter import ProgressReporter
from src.common.video_info_reader import VideoInfoReader, CropResult
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


class Orientation(Enum):
    HORIZONTAL = 0
    VERTICAL = 1


class Rotation(Enum):
    CLOCKWISE = 90
    COUNTERCLOCKWISE = 270
    UPSIDE_DOWN = 180
    NOTHING = 0


class VideoProcessSpeed(Enum):
    SLOW = 0
    NORMAL = 1
    FAST = 2


class VideoMerger:
    # 各速度级别的编码器配置
    # 多线程不影响画质，所有级别均启用
    # SLOW:   最慢速度，最高压缩率 → 最小体积，最佳画质
    # NORMAL: 折中速度与体积，画质清晰
    # FAST:   最快速度，最大体积，牺牲部分画质
    _SPEED_CONFIGS: dict[VideoProcessSpeed, dict] = {
        VideoProcessSpeed.SLOW: {
            "codec_options": {"preset": "slow", "bf": "0", "crf": "18"},
            "scale_flags": "bicubic",
        },
        VideoProcessSpeed.NORMAL: {
            "codec_options": {"preset": "medium", "bf": "0", "crf": "20"},
            "scale_flags": "bicubic",
        },
        VideoProcessSpeed.FAST: {
            "codec_options": {
                "preset": "ultrafast",
                "tune": "fastdecode",
                "bf": "0",
                "crf": "23",
                "threads": "0",
            },
            "scale_flags": "fast_bilinear",
        },
    }

    def __init__(
        self,
        target_fps: int = 30,
        enable_border_detection: bool = True,
        speed: VideoProcessSpeed = VideoProcessSpeed.NORMAL,
    ) -> None:
        if target_fps <= 0:
            raise ValueError("target_fps 必须是正整数")
        self.target_fps = target_fps
        self.enable_border_detection = enable_border_detection
        self.speed = speed
        self.progress_reporter = ProgressReporter(enable_tqdm=True)

    def merge(
        self,
        input_files: Sequence[InputVideoInfo],
        output_file: Path,
        fps: int | None = None,
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
        if fps is not None and not isinstance(fps, int):
            raise TypeError("fps 类型必须是 int 或 None")
        if fps is not None and fps <= 0:
            raise ValueError("fps 必须是正整数或 None")

        # ===== 预处理: 收集裁剪、旋转信息、有效尺寸、帧率和音频采样率 =====
        preprocessed: list[tuple[CropResult | None, Rotation]] = []
        effective_dimensions: list[tuple[int, int]] = []
        source_fps_values: list[float] = []
        source_audio_rates: list[int] = []

        for video_info in input_files:
            input_file = video_info.file_path
            if not input_file.exists():
                raise FileNotFoundError(f"文件不存在: {input_file}")

            # 获取裁剪信息
            crop_result = video_info.crop_result
            if crop_result is not None and not crop_result.has_border:
                crop_result = None
            if crop_result is None and self.enable_border_detection:
                crop_result = self._detect_border(input_file)

            # 获取原始尺寸、帧率和音频采样率
            probe_container = av.open(str(input_file))
            try:
                in_video_stream = probe_container.streams.video[0]
                raw_w, raw_h = int(in_video_stream.width), int(in_video_stream.height)
                video_fps = float(
                    in_video_stream.average_rate or in_video_stream.rate or 30
                )
                source_fps_values.append(video_fps)
            except IndexError:
                probe_container.close()
                raise ValueError(f"文件缺少视频流: {input_file}")
            try:
                in_audio_stream = probe_container.streams.audio[0]
                source_audio_rates.append(in_audio_stream.rate)
            except IndexError:
                pass
            probe_container.close()

            # 裁剪后的有效尺寸
            if crop_result is not None:
                eff_w, eff_h = crop_result.width, crop_result.height
            else:
                eff_w, eff_h = raw_w, raw_h

            # 判断是否需要旋转
            needs_rot = self._needs_rotation(eff_w, eff_h, orientation)
            if needs_rot:
                effective_rotation = (
                    video_info.rotation
                    if video_info.rotation is not None
                    else Rotation.CLOCKWISE
                )
            else:
                effective_rotation = Rotation.NOTHING

            # 旋转后的尺寸
            if self._rotation_swaps_dimensions(effective_rotation):
                final_w, final_h = eff_h, eff_w
            else:
                final_w, final_h = eff_w, eff_h

            preprocessed.append((crop_result, effective_rotation))
            effective_dimensions.append((final_w, final_h))

        # ===== 确定目标帧率和音频采样率 =====
        if fps is not None:
            effective_fps = fps
        else:
            effective_fps = (
                max(int(round(f)) for f in source_fps_values)
                if source_fps_values
                else self.target_fps
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
        output_container = av.open(str(output_file), mode="w")

        audio_time_base = Fraction(1, target_audio_rate)

        # 在 mux 任何 packet 之前，先把视频和音频两个输出流都注册好，
        # 否则 MP4 muxer 在首次 mux() 时写入 header，
        # 遗漏后续添加的 stream，导致输出文件损坏。
        speed_cfg = self._SPEED_CONFIGS[self.speed]

        out_video = output_container.add_stream("libx264", rate=target_fps_fraction)
        out_video.width = target_width
        out_video.height = target_height
        out_video.pix_fmt = "yuv420p"
        out_video.time_base = video_time_base
        out_video.thread_type = "AUTO"
        out_video.codec_context.options = speed_cfg["codec_options"]

        out_audio = output_container.add_stream("aac", rate=target_audio_rate)
        out_audio.time_base = audio_time_base

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
        reporter = self.progress_reporter
        reporter.start_merge(total_files=len(input_files))

        try:
            for file_index, video_info in enumerate(input_files):
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

                reporter.start_file(
                    file_index=file_index + 1,
                    file_path=input_file,
                    total_frames=(
                        estimated_total_frames if estimated_total_frames > 0 else None
                    ),
                )

                filter_graph = self._build_filter_graph(
                    in_video,
                    effective_rotation,
                    crop_result,
                    target_width,
                    target_height,
                    effective_fps,
                    speed_cfg["scale_flags"],
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
                    if packet.stream.type == "video":
                        for frame in packet.decode():
                            reporter.update_frame(1)
                            filter_graph["src"].push(frame)
                            while True:
                                try:
                                    filtered_frame = filter_graph["sink"].pull()
                                except (BlockingIOError, EOFError):
                                    break
                                _encode_video_frame(filtered_frame)

                    elif packet.stream.type == "audio":
                        for frame in packet.decode():
                            for rf in resampler.resample(frame):
                                _encode_audio_frame(rf)

                # 刷新视频滤镜图中缓冲的剩余帧
                filter_graph["src"].push(None)
                while True:
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
                    # 每次生成 1024 个采样的静音帧
                    samples_per_frame = 1024

                    while silence_samples_needed > 0:
                        n = min(samples_per_frame, silence_samples_needed)
                        silent_data = np.zeros((2, n), dtype="float32")
                        silent_frame = av.AudioFrame.from_ndarray(
                            silent_data, format="fltp", layout="stereo"
                        )
                        silent_frame.rate = target_audio_rate
                        _encode_audio_frame(silent_frame)
                        silence_samples_needed -= n

                video_pts_offset += segment_video_frame_count
                # 将 audio offset 同步到 video offset 的时间线，消除累积漂移
                audio_pts_offset = int(
                    video_pts_offset / effective_fps * target_audio_rate
                )

                input_container.close()
                reporter.finish_file()
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

            reporter.finish_merge()
            logger.info(f"完成! 输出文件: {output_file}")
        finally:
            reporter.close()
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
        return rotation in (Rotation.CLOCKWISE, Rotation.COUNTERCLOCKWISE)

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
        """构建滤镜图: 裁剪 → 旋转 → 帧率转换 → 缩放+填充到目标尺寸。"""
        graph = av.filter.Graph()
        src = graph.add_buffer(template=in_video)
        last = src

        # 1. 裁剪
        if crop_result is not None:
            crop = graph.add(
                "crop",
                args=f"{crop_result.width}:{crop_result.height}:{crop_result.x}:{crop_result.y}",
            )
            last.link_to(crop)
            last = crop

        # 2. 旋转
        if rotation == Rotation.CLOCKWISE:
            transpose = graph.add("transpose", args="clock")
            last.link_to(transpose)
            last = transpose
        elif rotation == Rotation.COUNTERCLOCKWISE:
            transpose = graph.add("transpose", args="cclock")
            last.link_to(transpose)
            last = transpose
        elif rotation == Rotation.UPSIDE_DOWN:
            vflip = graph.add("vflip")
            last.link_to(vflip)
            last = vflip
            hflip = graph.add("hflip")
            last.link_to(hflip)
            last = hflip

        # 3. 帧率转换
        if target_fps is not None:
            fps_filter = graph.add("fps", args=str(target_fps))
            last.link_to(fps_filter)
            last = fps_filter

        # 4. 缩放 + 填充到目标尺寸
        scale = graph.add(
            "scale",
            args=f"{target_width}:{target_height}:force_original_aspect_ratio=decrease:flags={scale_flags}",
        )
        last.link_to(scale)
        last = scale

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
    merger = VideoMerger(
        speed=VideoProcessSpeed.FAST,
    )
    merger.merge(
        input_files=[
            # InputVideoInfo(file_path=Path(r"C:\Users\PythonImporter\Videos\Captures\1.mp4"), rotation=Rotation.CLOCKWISE),
            InputVideoInfo(
                file_path=Path(
                    r"E:\load\python\Project\VideoFusion\测试\dy\b7bb97e21600b07f66c21e7932cb7550.mp4"
                ),
                rotation=Rotation.CLOCKWISE,
            ),
            InputVideoInfo(
                file_path=Path(r"G:\CodingSpace\Project\VideoMerger\测试视频\a1.mp4"),
                rotation=Rotation.CLOCKWISE,
            ),
            InputVideoInfo(
                file_path=Path(r"G:\CodingSpace\Project\VideoMerger\测试视频\b1.mp4"),
                rotation=Rotation.CLOCKWISE,
            ),
        ],
        output_file=Path("output.mp4"),
        orientation=Orientation.HORIZONTAL,
        cover_image_path=Path(r"F:\picture\R18\43759957_p0_master1200.jpg"),
    )
