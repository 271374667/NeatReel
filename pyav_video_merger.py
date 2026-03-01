from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from typing import Sequence
from collections import Counter
from enum import Enum

import av

from src.common.border_detector import BorderDetector, CropResult
from dataclasses import dataclass


@dataclass(frozen=True)
class InputVideoInfo:
    file_path: Path
    crop_result: CropResult | None = None
    rotation: Rotation | None = None
    cover_image_path: Path | None = None


class Orientation(Enum):
    HORIZONTAL = 0
    VERTICAL = 1


class Rotation(Enum):
    CLOCKWISE = 90
    COUNTERCLOCKWISE = 270
    UPSIDE_DOWN = 180
    NOTHING = 0


class PyAVVideoMerger:
    def __init__(
        self,
        target_fps: int = 30,
        video_time_base: Fraction = Fraction(1, 90000),
        enable_border_detection: bool = True,
    ) -> None:
        if target_fps <= 0:
            raise ValueError("target_fps 必须是正整数")
        self.target_fps = target_fps
        self.video_time_base = video_time_base
        self.enable_border_detection = enable_border_detection

    def merge(
        self,
        input_files: Sequence[InputVideoInfo],
        output_file: Path,
        fps: int | None = None,
        orientation: Orientation = Orientation.VERTICAL,
        target_resolution: tuple[int, int] | None = None,
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
        target_audio_rate = (
            max(source_audio_rates) if source_audio_rates else 44100
        )
        target_fps_fraction = Fraction(effective_fps, 1)
        ticks_per_frame = int(self.video_time_base.denominator / effective_fps)

        print(f"目标帧率: {effective_fps} fps")
        print(f"目标音频采样率: {target_audio_rate} Hz")

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

        print(f"目标分辨率: {target_width}x{target_height}")

        # ===== 处理视频 =====
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_container = av.open(str(output_file), mode="w")

        out_video = None
        out_audio = None
        audio_time_base = Fraction(1, target_audio_rate)

        video_pts_offset = 0
        audio_pts_offset = 0

        try:
            for file_index, video_info in enumerate(input_files):
                input_file = video_info.file_path
                crop_result, effective_rotation = preprocessed[file_index]

                print(f"处理文件 {file_index + 1}/{len(input_files)}: {input_file}")
                input_container = av.open(str(input_file))

                try:
                    in_video = input_container.streams.video[0]
                    in_audio = input_container.streams.audio[0]
                except IndexError as exc:
                    input_container.close()
                    raise ValueError(f"文件缺少视频或音频流: {input_file}") from exc

                if out_video is None:
                    out_video = output_container.add_stream(
                        "libx264", rate=target_fps_fraction
                    )
                    out_video.width = target_width
                    out_video.height = target_height
                    out_video.pix_fmt = "yuv420p"
                    out_video.time_base = self.video_time_base

                    out_audio = output_container.add_stream(
                        "aac", rate=target_audio_rate
                    )
                    out_audio.time_base = audio_time_base

                filter_graph = self._build_filter_graph(
                    in_video, effective_rotation, crop_result,
                    target_width, target_height, effective_fps,
                )

                # 创建音频重采样器（如果需要）
                resampler = None
                if in_audio.rate != target_audio_rate:
                    resampler = av.AudioResampler(rate=target_audio_rate)

                segment_video_frame_count = 0
                segment_audio_sample_count = 0

                def _encode_video_frame(frm):
                    nonlocal segment_video_frame_count
                    new_pts = (
                        video_pts_offset
                        + segment_video_frame_count * ticks_per_frame
                    )
                    segment_video_frame_count += 1
                    frm.pts = new_pts
                    frm.time_base = self.video_time_base
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

                for packet in input_container.demux(in_video, in_audio):
                    if packet.stream.type == "video":
                        for frame in packet.decode():
                            filter_graph["src"].push(frame)
                            # fps 滤镜可能缓冲/丢弃帧，需循环拉取
                            while True:
                                try:
                                    filtered_frame = filter_graph["sink"].pull()
                                except (BlockingIOError, EOFError):
                                    break
                                _encode_video_frame(filtered_frame)

                    elif packet.stream.type == "audio":
                        for frame in packet.decode():
                            if resampler is not None:
                                for rf in resampler.resample(frame):
                                    _encode_audio_frame(rf)
                            else:
                                _encode_audio_frame(frame)

                # 刷新视频滤镜图中缓冲的剩余帧
                filter_graph["src"].push(None)
                while True:
                    try:
                        filtered_frame = filter_graph["sink"].pull()
                    except (BlockingIOError, EOFError):
                        break
                    _encode_video_frame(filtered_frame)

                # 刷新音频重采样器中缓冲的剩余采样
                if resampler is not None:
                    for rf in resampler.resample(None):
                        _encode_audio_frame(rf)

                video_pts_offset += segment_video_frame_count * ticks_per_frame
                audio_pts_offset += segment_audio_sample_count

                input_container.close()
                print(
                    f"  完成，video offset -> {video_pts_offset}, audio offset -> {audio_pts_offset}"
                )

            if out_video is not None:
                for out_packet in out_video.encode():
                    out_packet.stream = out_video
                    output_container.mux(out_packet)

            if out_audio is not None:
                for out_packet in out_audio.encode():
                    out_packet.stream = out_audio
                    output_container.mux(out_packet)

            print(f"完成! 输出文件: {output_file}")
        finally:
            output_container.close()

    @staticmethod
    def _detect_border(input_file: Path) -> CropResult | None:
        detector = BorderDetector()
        video_info = detector.detect(input_file)
        crop_result = video_info.crop_result
        if crop_result is not None and crop_result.has_border:
            print(
                "  边框检测结果: "
                f"has_border={crop_result.has_border}, "
                f"rect=({crop_result.x},{crop_result.y},{crop_result.width},{crop_result.height}), "
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
            args=f"{target_width}:{target_height}:force_original_aspect_ratio=decrease",
        )
        last.link_to(scale)
        last = scale

        pad = graph.add(
            "pad",
            args=f"{target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black",
        )
        last.link_to(pad)
        last = pad

        sink = graph.add("buffersink")
        last.link_to(sink)
        graph.configure()

        return {"graph": graph, "src": src, "sink": sink}


if __name__ == "__main__":
    merger = PyAVVideoMerger()
    merger.merge(
        input_files=[
            # InputVideoInfo(file_path=Path(r"C:\Users\PythonImporter\Videos\Captures\1.mp4"), rotation=Rotation.CLOCKWISE),
            InputVideoInfo(file_path=Path(r"E:\load\python\Project\VideoFusion\测试\dy\4938d41224254f9f0ac996ea88814782.mp4"), rotation=Rotation.CLOCKWISE),
            InputVideoInfo(file_path=Path(r"E:\load\python\Project\VideoFusion\测试\dy\8fd68ff8825a0de6aff59c482abe7147.mp4"), rotation=Rotation.CLOCKWISE),
        ],
        output_file=Path("output.mp4"),
        orientation=Orientation.VERTICAL,
    )
