from dataclasses import dataclass
from pathlib import Path

import av


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


class VideoDetect:
    """用于从视频文件路径中检测元数据。"""

    def __init__(self, video_path: Path) -> None:
        """使用视频文件路径初始化检测器。

        Args:
            video_path: 目标视频文件路径。

        Raises:
            TypeError: 当 `video_path` 不是 `pathlib.Path` 类型时抛出。
        """
        if not isinstance(video_path, Path):
            raise TypeError("video_path must be a pathlib.Path")
        self.video_path = video_path

    def detect(self) -> VideoInfo:
        """读取视频元数据并返回 `VideoInfo`。

        Returns:
            VideoInfo: 解析得到的视频元数据。

        Raises:
            FileNotFoundError: 当输入文件不存在时抛出。
            ValueError: 当文件中没有视频流时抛出。
            av.error.FFmpegError: 当媒体打开或解析失败时抛出。
        """
        if not self.video_path.exists():
            raise FileNotFoundError(f"video file not found: {self.video_path}")

        with av.open(str(self.video_path)) as container:
            if not container.streams.video:
                raise ValueError(f"no video stream found: {self.video_path}")

            video_stream = container.streams.video[0]
            audio_stream = container.streams.audio[0] if container.streams.audio else None

            fps = self._resolve_fps(video_stream)
            duration_second = self._resolve_duration_second(container, video_stream)
            total_frames = self._resolve_total_frames(video_stream, fps, duration_second)

            audio_sample_rate = -1
            if audio_stream is not None:
                audio_sample_rate = int(
                    audio_stream.rate or audio_stream.codec_context.sample_rate or -1
                )

            return VideoInfo(
                width=int(video_stream.width),
                height=int(video_stream.height),
                fps=fps,
                total_frames=total_frames,
                audio_sample_rate=audio_sample_rate,
                duration_second=duration_second,
            )

    @staticmethod
    def _resolve_fps(video_stream: av.video.stream.VideoStream) -> float:
        if video_stream.average_rate is not None:
            return float(video_stream.average_rate)
        if video_stream.base_rate is not None:
            return float(video_stream.base_rate)
        return 0.0

    @staticmethod
    def _resolve_duration_second(
            container: av.container.input.InputContainer,
            video_stream: av.video.stream.VideoStream,
    ) -> float:
        if container.duration is not None:
            return float(container.duration / av.time_base)
        if video_stream.duration is not None and video_stream.time_base is not None:
            return float(video_stream.duration * video_stream.time_base)
        return 0.0

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


if __name__ == '__main__':
    import time

    start_time = time.time()
    a = r"C:\Users\PythonImporter\Videos\Captures\2.mp4"
    info = VideoDetect(Path(a)).detect()
    print(info)
    print(f"检测耗时: {time.time() - start_time:.2f} 秒")
