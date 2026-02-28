from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from typing import Callable, Sequence

import av
import cv2

from src.common.border_detector import BorderDetector


FrameProcessor = Callable[[av.VideoFrame, int, Path], av.VideoFrame]


class PyAVVideoMerger:
    def __init__(
        self,
        target_fps: int = 30,
        video_time_base: Fraction = Fraction(1, 90000),
        frame_processor: FrameProcessor | None = None,
        enable_border_detection: bool = True,
        seek_skip_frames: int = 2,
    ) -> None:
        if target_fps <= 0:
            raise ValueError("target_fps 必须是正整数")
        if seek_skip_frames < 0:
            raise ValueError("seek_skip_frames 不能为负数")
        self.target_fps = target_fps
        self.video_time_base = video_time_base
        self.frame_processor = frame_processor or self._default_frame_processor
        self.enable_border_detection = enable_border_detection
        self.seek_skip_frames = seek_skip_frames

    def merge(
        self,
        input_files: Sequence[Path],
        output_file: Path,
        fps: int | None = None,
        rotate_90_clockwise_files: set[Path] | None = None,
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
        if rotate_90_clockwise_files is not None and any(
            not isinstance(p, Path) for p in rotate_90_clockwise_files
        ):
            raise TypeError("rotate_90_clockwise_files 的元素类型必须是 pathlib.Path")

        rotate_path_set = self._normalize_path_set(rotate_90_clockwise_files or set())
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
                rotate_this_file = input_file.resolve() in rotate_path_set

                try:
                    in_video = input_container.streams.video[0]
                    in_audio = input_container.streams.audio[0]
                except IndexError as exc:
                    input_container.close()
                    raise ValueError(f"文件缺少视频或音频流: {input_file}") from exc

                border_detector = (
                    self._build_border_detector(input_file, rotate_this_file)
                    if self.enable_border_detection
                    else None
                )
                target_width, target_height = self._resolve_segment_output_size(
                    in_video=in_video,
                    rotate_90_clockwise=rotate_this_file,
                    border_detector=border_detector,
                )

                if out_video is None:
                    out_video = output_container.add_stream("libx264", rate=target_fps_fraction)
                    out_video.width = target_width
                    out_video.height = target_height
                    out_video.pix_fmt = "yuv420p"
                    out_video.time_base = self.video_time_base

                    audio_sample_rate = in_audio.rate
                    audio_time_base = Fraction(1, audio_sample_rate)
                    out_audio = output_container.add_stream("aac", rate=audio_sample_rate)
                    out_audio.time_base = audio_time_base
                elif out_video.width != target_width or out_video.height != target_height:
                    raise ValueError(
                        "视频分辨率不一致，无法直接合并。"
                        f"当前文件: {input_file}, 目标尺寸: {target_width}x{target_height}, "
                        f"输出尺寸: {out_video.width}x{out_video.height}"
                    )

                rotate_graph = self._create_rotate_90_graph(in_video) if rotate_this_file else None
                segment_audio_first_pts = None
                segment_audio_last_pts = 0
                segment_video_frame_count = 0

                for packet in input_container.demux(in_video, in_audio):
                    if packet.stream.type == "video":
                        for frame in packet.decode():
                            if rotate_graph is not None:
                                rotate_graph["src"].push(frame)
                                frame = rotate_graph["sink"].pull()

                            if border_detector is not None:
                                frame = border_detector.crop(frame)

                            if frame.width != out_video.width or frame.height != out_video.height:
                                raise ValueError(
                                    "视频分辨率不一致，无法直接合并。"
                                    f"当前文件: {input_file}, 帧尺寸: {frame.width}x{frame.height}, "
                                    f"输出尺寸: {out_video.width}x{out_video.height}"
                                )

                            new_pts = video_pts_offset + segment_video_frame_count * ticks_per_frame
                            segment_video_frame_count += 1

                            processed_frame = self.frame_processor(frame, file_index, input_file)
                            processed_frame.pts = new_pts
                            processed_frame.time_base = self.video_time_base

                            for out_packet in out_video.encode(processed_frame):
                                out_packet.stream = out_video
                                output_container.mux(out_packet)

                    elif packet.stream.type == "audio":
                        for frame in packet.decode():
                            source_pts = frame.pts or 0
                            raw_pts_in_audio_tb = int(source_pts * float(in_audio.time_base) * audio_sample_rate)

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
                print(f"  完成，video offset -> {video_pts_offset}, audio offset -> {audio_pts_offset}")

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
    def _default_frame_processor(frame: av.VideoFrame, file_index: int, input_file: Path) -> av.VideoFrame:
        img = frame.to_ndarray(format="bgr24")
        # img = cv2.putText(
        #     img,
        #     f"File {file_index + 1}",
        #     (50, 50),
        #     cv2.FONT_HERSHEY_SIMPLEX,
        #     1,
        #     (0, 0, 255),
        #     2,
        # )
        _ = input_file
        return av.VideoFrame.from_ndarray(img, format="bgr24")

    @staticmethod
    def _normalize_path_set(paths: set[Path]) -> set[Path]:
        return {p.resolve() for p in paths}

    @staticmethod
    def _create_rotate_90_graph(in_video: av.VideoStream) -> dict[str, object]:
        graph = av.filter.Graph()
        src = graph.add_buffer(template=in_video)
        transpose = graph.add("transpose", args="clock")
        sink = graph.add("buffersink")
        src.link_to(transpose)
        transpose.link_to(sink)
        graph.configure()
        return {"graph": graph, "src": src, "sink": sink}

    def _build_border_detector(
        self,
        input_file: Path,
        rotate_90_clockwise: bool,
    ) -> BorderDetector | None:
        with av.open(str(input_file)) as sample_container:
            if not sample_container.streams.video:
                return None

            sample_video = sample_container.streams.video[0]
            fps = self._resolve_video_fps(sample_video)
            duration = self._resolve_video_duration(sample_container, sample_video)
            plan = self._compute_sample_plan(duration=duration, fps=fps)

            if plan["num_frames"] <= 0:
                return None

            detector = BorderDetector()

            rotate_graph = (
                self._create_rotate_90_graph(sample_video)
                if rotate_90_clockwise
                else None
            )

            if duration < 2.0:
                sampled_frames = self._sample_frames_sequentially(
                    container=sample_container,
                    stream=sample_video,
                    num_frames=plan["num_frames"],
                    rotate_graph=rotate_graph,
                )
            else:
                sampled_frames = self._sample_frames_with_seek(
                    container=sample_container,
                    stream=sample_video,
                    timestamps=plan["timestamps"],
                    rotate_graph=rotate_graph,
                )

            for sampled_frame in sampled_frames:
                detector.feed(sampled_frame)

            if not sampled_frames:
                print(f"  采样失败，跳过边框检测: {input_file}")
                return None

            result = detector.detect()
            print(
                "  边框检测结果: "
                f"has_border={result.has_border}, rect=({result.x},{result.y},{result.width},{result.height}), "
                f"confidence={result.confidence:.4f}"
            )
            return detector

    def _resolve_segment_output_size(
        self,
        in_video: av.VideoStream,
        rotate_90_clockwise: bool,
        border_detector: BorderDetector | None,
    ) -> tuple[int, int]:
        width = in_video.height if rotate_90_clockwise else in_video.width
        height = in_video.width if rotate_90_clockwise else in_video.height

        if border_detector is None:
            return int(width), int(height)

        result = border_detector.detect()
        if result.has_border:
            return result.width, result.height
        return int(width), int(height)

    def _sample_frames_with_seek(
        self,
        container: av.container.input.InputContainer,
        stream: av.video.stream.VideoStream,
        timestamps: list[float],
        rotate_graph: dict[str, object] | None,
    ) -> list[av.VideoFrame]:
        frames: list[av.VideoFrame] = []
        for ts in timestamps:
            frame = self._seek_and_get_frame(
                container=container,
                stream=stream,
                timestamp=ts,
                rotate_graph=rotate_graph,
            )
            if frame is not None:
                frames.append(frame)
        return frames

    def _seek_and_get_frame(
        self,
        container: av.container.input.InputContainer,
        stream: av.video.stream.VideoStream,
        timestamp: float,
        rotate_graph: dict[str, object] | None,
    ) -> av.VideoFrame | None:
        stream_time_base = stream.time_base
        if stream_time_base is None:
            return None

        seek_target = max(0, int(timestamp / float(stream_time_base)))
        try:
            container.seek(seek_target, stream=stream, backward=True, any_frame=False)
        except av.error.FFmpegError:
            return None

        decoded_after_seek = 0
        max_frames_after_seek = self.seek_skip_frames + 12

        for packet in container.demux(stream):
            for frame in packet.decode():
                decoded_after_seek += 1

                if decoded_after_seek <= self.seek_skip_frames:
                    continue

                frame = self._apply_rotate_graph(frame=frame, rotate_graph=rotate_graph)
                if frame is not None:
                    return frame

                if decoded_after_seek >= max_frames_after_seek:
                    return None

            if decoded_after_seek >= max_frames_after_seek:
                return None

        return None

    def _sample_frames_sequentially(
        self,
        container: av.container.input.InputContainer,
        stream: av.video.stream.VideoStream,
        num_frames: int,
        rotate_graph: dict[str, object] | None,
    ) -> list[av.VideoFrame]:
        decoded_frames: list[av.VideoFrame] = []
        for packet in container.demux(stream):
            for frame in packet.decode():
                frame = self._apply_rotate_graph(frame=frame, rotate_graph=rotate_graph)
                if frame is not None:
                    decoded_frames.append(frame)

        if not decoded_frames:
            return []

        if len(decoded_frames) <= num_frames:
            return decoded_frames

        indices = {
            int(round(i * (len(decoded_frames) - 1) / max(num_frames - 1, 1)))
            for i in range(num_frames)
        }
        return [decoded_frames[i] for i in sorted(indices)]

    @staticmethod
    def _apply_rotate_graph(
        frame: av.VideoFrame,
        rotate_graph: dict[str, object] | None,
    ) -> av.VideoFrame | None:
        if rotate_graph is None:
            return frame
        try:
            rotate_graph["src"].push(frame)
            return rotate_graph["sink"].pull()
        except (av.error.FFmpegError, EOFError):
            return None

    @staticmethod
    def _resolve_video_fps(stream: av.video.stream.VideoStream) -> float:
        if stream.average_rate is not None:
            return float(stream.average_rate)
        if stream.base_rate is not None:
            return float(stream.base_rate)
        return 0.0

    @staticmethod
    def _resolve_video_duration(
        container: av.container.input.InputContainer,
        stream: av.video.stream.VideoStream,
    ) -> float:
        if container.duration is not None:
            return float(container.duration / av.time_base)
        if stream.duration is not None and stream.time_base is not None:
            return float(stream.duration * stream.time_base)
        return 0.0

    @staticmethod
    def _compute_sample_plan(duration: float, fps: float) -> dict[str, int | list[float]]:
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

        timestamps = [
            start + i * (end - start) / max(n - 1, 1)
            for i in range(n)
        ]
        return {"num_frames": n, "timestamps": timestamps}


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
