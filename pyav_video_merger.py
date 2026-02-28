from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from typing import Sequence
from enum import Enum

import av

from src.common.border_detector import BorderDetector, CropResult


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
        input_files: Sequence[Path],
        output_file: Path,
        fps: int | None = None,
        orientation: Orientation = Orientation.HORIZONTAL,
        rotation: Rotation = Rotation.CLOCKWISE,
    ) -> None:
        if not input_files:
            raise ValueError("input_files 不能为空")
        if any(not isinstance(p, Path) for p in input_files):
            raise TypeError("input_files 的元素类型必须是 pathlib.Path")
        if not isinstance(output_file, Path):
            raise TypeError("output_file 类型必须是 pathlib.Path")
        if fps is not None and not isinstance(fps, int):
            raise TypeError("fps 类型必须是 int 或 None")
        if fps is not None and fps <= 0:
            raise ValueError("fps 必须是正整数或 None")
        effective_fps = fps if fps is not None else self.target_fps
        target_fps_fraction = Fraction(effective_fps, 1)
        ticks_per_frame = int(self.video_time_base.denominator / effective_fps)

        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_container = av.open(str(output_file), mode="w")

        out_video = None
        out_audio = None
        audio_sample_rate = 44100
        audio_time_base = Fraction(1, audio_sample_rate)

        video_pts_offset = 0
        audio_pts_offset = 0

        try:
            for file_index, input_file in enumerate(input_files):
                if not input_file.exists():
                    raise FileNotFoundError(f"文件不存在: {input_file}")

                print(f"处理文件 {file_index + 1}/{len(input_files)}: {input_file}")
                input_container = av.open(str(input_file))

                try:
                    in_video = input_container.streams.video[0]
                    in_audio = input_container.streams.audio[0]
                except IndexError as exc:
                    input_container.close()
                    raise ValueError(f"文件缺少视频或音频流: {input_file}") from exc

                crop_result = (
                    self._detect_border(input_file)
                    if self.enable_border_detection
                    else None
                )
                effective_rotation = self._resolve_rotation(in_video, orientation, rotation)
                target_width, target_height = self._resolve_segment_output_size(
                    in_video=in_video,
                    rotation=effective_rotation,
                    crop_result=crop_result,
                )

                if out_video is None:
                    out_video = output_container.add_stream(
                        "libx264", rate=target_fps_fraction
                    )
                    out_video.width = target_width
                    out_video.height = target_height
                    out_video.pix_fmt = "yuv420p"
                    out_video.time_base = self.video_time_base

                    audio_sample_rate = in_audio.rate
                    audio_time_base = Fraction(1, audio_sample_rate)
                    out_audio = output_container.add_stream(
                        "aac", rate=audio_sample_rate
                    )
                    out_audio.time_base = audio_time_base
                elif (
                    out_video.width != target_width or out_video.height != target_height
                ):
                    raise ValueError(
                        "视频分辨率不一致，无法直接合并。"
                        f"当前文件: {input_file}, 目标尺寸: {target_width}x{target_height}, "
                        f"输出尺寸: {out_video.width}x{out_video.height}"
                    )

                filter_graph = self._build_filter_graph(
                    in_video, effective_rotation, crop_result
                )
                segment_audio_first_pts = None
                segment_audio_last_pts = 0
                segment_video_frame_count = 0

                for packet in input_container.demux(in_video, in_audio):
                    if packet.stream.type == "video":
                        for frame in packet.decode():
                            if filter_graph is not None:
                                filter_graph["src"].push(frame)
                                frame = filter_graph["sink"].pull()

                            if (
                                frame.width != out_video.width
                                or frame.height != out_video.height
                            ):
                                raise ValueError(
                                    "视频分辨率不一致，无法直接合并。"
                                    f"当前文件: {input_file}, 帧尺寸: {frame.width}x{frame.height}, "
                                    f"输出尺寸: {out_video.width}x{out_video.height}"
                                )

                            new_pts = (
                                video_pts_offset
                                + segment_video_frame_count * ticks_per_frame
                            )
                            segment_video_frame_count += 1

                            frame.pts = new_pts
                            frame.time_base = self.video_time_base

                            for out_packet in out_video.encode(frame):
                                out_packet.stream = out_video
                                output_container.mux(out_packet)

                    elif packet.stream.type == "audio":
                        for frame in packet.decode():
                            source_pts = frame.pts or 0
                            raw_pts_in_audio_tb = int(
                                source_pts
                                * float(in_audio.time_base)
                                * audio_sample_rate
                            )

                            if segment_audio_first_pts is None:
                                segment_audio_first_pts = raw_pts_in_audio_tb

                            relative_pts = raw_pts_in_audio_tb - segment_audio_first_pts
                            new_pts = audio_pts_offset + relative_pts

                            segment_audio_last_pts = new_pts + frame.samples
                            frame.pts = new_pts
                            frame.time_base = audio_time_base

                            for out_packet in out_audio.encode(frame):
                                out_packet.stream = out_audio
                                output_container.mux(out_packet)

                video_pts_offset += segment_video_frame_count * ticks_per_frame
                audio_pts_offset = segment_audio_last_pts

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
    def _resolve_rotation(
        in_video: av.VideoStream,
        orientation: Orientation,
        rotation: Rotation,
    ) -> Rotation:
        """根据视频实际尺寸和目标朝向，决定是否需要旋转。"""
        w, h = int(in_video.width), int(in_video.height)
        is_horizontal = w >= h
        want_horizontal = orientation == Orientation.HORIZONTAL

        if is_horizontal == want_horizontal:
            return Rotation.NOTHING
        return rotation

    @staticmethod
    def _rotation_swaps_dimensions(rotation: Rotation) -> bool:
        return rotation in (Rotation.CLOCKWISE, Rotation.COUNTERCLOCKWISE)

    @staticmethod
    def _build_filter_graph(
        in_video: av.VideoStream,
        rotation: Rotation,
        crop_result: CropResult | None,
    ) -> dict[str, object] | None:
        if rotation == Rotation.NOTHING and crop_result is None:
            return None

        graph = av.filter.Graph()
        src = graph.add_buffer(template=in_video)
        last = src

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

        if crop_result is not None:
            crop = graph.add(
                "crop",
                args=f"{crop_result.width}:{crop_result.height}:{crop_result.x}:{crop_result.y}",
            )
            last.link_to(crop)
            last = crop

        sink = graph.add("buffersink")
        last.link_to(sink)
        graph.configure()

        return {"graph": graph, "src": src, "sink": sink}

    @staticmethod
    def _resolve_segment_output_size(
        in_video: av.VideoStream,
        rotation: Rotation,
        crop_result: CropResult | None,
    ) -> tuple[int, int]:
        if crop_result is not None and crop_result.has_border:
            return crop_result.width, crop_result.height

        swaps = rotation in (Rotation.CLOCKWISE, Rotation.COUNTERCLOCKWISE)
        width = in_video.height if swaps else in_video.width
        height = in_video.width if swaps else in_video.height
        return int(width), int(height)


if __name__ == "__main__":
    merger = PyAVVideoMerger()
    merger.merge(
        input_files=[
            # Path(r"C:\Users\PythonImporter\Videos\Captures\1.mp4"),
            # Path(r"C:\Users\PythonImporter\Videos\Captures\2.mp4"),
            Path(r"C:\Users\PythonImporter\Videos\Captures\3.mp4")
        ],
        output_file=Path("output.mp4"),
    )
