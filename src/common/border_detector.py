"""
视频装饰边框检测与裁剪模块 v4

核心算法：帧间差分累积变化区域 → 形态学去噪 → 最大活动矩形提取
使用 PyAV + NumPy + SciPy

依赖：av, numpy, scipy, pathlib
"""

from __future__ import annotations

from pathlib import Path

import av
import numpy as np
from scipy.ndimage import (
    binary_opening,
    binary_closing,
    label,
    gaussian_filter,
)
from dataclasses import dataclass
from typing import Optional

from loguru import logger


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


class BorderDetector:
    """
    视频装饰边框检测器 v4

    传入视频路径，自动完成采样与检测，返回裁剪参数。

    用法:
        detector = BorderDetector()
        result = detector.detect(Path("video.mp4"))
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
        # 有效变化区域占主体区域的最小比例
        min_change_coverage: float = 0.05,
        # 是否启用自适应阈值（开启后 diff_threshold 作为下限兜底）
        adaptive_threshold: bool = True,
        # seek 后跳过的帧数（让画面定位更接近目标时刻）
        seek_skip_frames: int = 2,
    ):
        self.detect_short_edge = detect_short_edge
        self.min_border_ratio = min_border_ratio
        self.safety_margin = safety_margin
        self.diff_threshold = diff_threshold
        self.morph_kernel_size = morph_kernel_size
        self.min_region_ratio = min_region_ratio
        self.scene_change_threshold = scene_change_threshold
        self.min_change_coverage = min_change_coverage
        self.adaptive_threshold = adaptive_threshold
        self.seek_skip_frames = seek_skip_frames

        self._prev_gray: Optional[np.ndarray] = None
        self._accumulated: Optional[np.ndarray] = None
        self._pair_count: int = 0
        self._original_size: Optional[tuple[int, int]] = None
        self._detect_size: Optional[tuple[int, int]] = None
        self._scale_factor: float = 1.0

    # ======================== 公开接口 ========================

    def detect(self, video_path: Path) -> CropResult:
        """
        传入视频路径，自动完成采样与检测，返回裁剪参数。

        内部根据视频时长自动选择采样策略：
        - 时长 < 2s：顺序解码全量帧后均匀采样
        - 时长 ≥ 2s：按均匀时间戳 seek 采样（5%~95% 区间）
        """
        self._reset()

        logger.debug("开始边框检测: {}", video_path)

        with av.open(str(video_path)) as container:
            if not container.streams.video:
                logger.debug("视频无视频流，跳过检测: {}", video_path)
                return CropResult(
                    x=0, y=0, width=0, height=0, confidence=0.0, has_border=False
                )

            stream = container.streams.video[0]
            fps = self._resolve_video_fps(stream)
            duration = self._resolve_video_duration(container, stream)
            plan = self._compute_sample_plan(duration, fps)

            strategy = "顺序解码" if duration < 2.0 else "seek跳帧"
            logger.debug(
                "视频信息: fps={:.1f}, duration={:.2f}s, 采样策略={}, 计划帧数={}",
                fps, duration, strategy, plan["num_frames"],
            )

            if duration < 2.0:
                frames = self._sample_sequentially(
                    container, stream, plan["num_frames"]
                )
            else:
                frames = self._sample_with_seek(container, stream, plan["timestamps"])

            logger.debug("实际采集帧数: {}/{}", len(frames), plan["num_frames"])
            for frame in frames:
                self._feed(frame)

        return self._run_detection()

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
            logger.debug("seek 失败 ts={:.2f}s: {}", timestamp, e)
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
            self._accumulated = np.zeros((dh, dw), dtype=np.float32)

        if self._prev_gray is not None:
            diff = np.abs(gray - self._prev_gray)
            mean_diff = diff.mean()
            if mean_diff >= self.scene_change_threshold:
                logger.debug("跳过场景切换帧 mean_diff={:.2f}", mean_diff)
            elif mean_diff > 0.3:
                self._accumulated += diff
                self._pair_count += 1

        self._prev_gray = gray

    def _reset(self) -> None:
        self._prev_gray = None
        self._accumulated = None
        self._pair_count = 0
        self._original_size = None
        self._detect_size = None
        self._scale_factor = 1.0

    def _run_detection(self) -> CropResult:
        if self._original_size is None:
            logger.debug("原始尺寸未初始化（未喂入任何帧），返回空结果")
            return CropResult(
                x=0, y=0, width=0, height=0, confidence=0.0, has_border=False
            )

        logger.debug("开始运行检测算法，有效帧对数: {}", self._pair_count)
        result = self._detect_by_motion()
        if result is not None:
            if result.has_border:
                logger.info("检测完成，发现边框: {}", result)
            else:
                logger.debug("检测完成，未发现有效边框")
            return result

        ow, oh = self._original_size
        logger.debug("运动检测无结果，返回原始尺寸 {}x{}", ow, oh)
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


        帧差分 → 高斯模糊 → 二值化 → 形态学开闭运算 → 连通域过滤 → 最大包围矩形
        """
        dw, dh = self._detect_size

        if self._pair_count == 0:
            logger.debug("pair_count=0，无有效帧对，跳过运动检测")
            return None

        # 归一化累积图
        avg_diff = self._accumulated / self._pair_count

        # 高斯模糊降噪
        blurred = gaussian_filter(avg_diff, sigma=1.0)

        # 确定二值化阈值
        if self.adaptive_threshold:
            nonzero = blurred[blurred > 0.5]
            if nonzero.size > 0:
                threshold = float(np.percentile(nonzero, 85)) * 0.4
                threshold = max(threshold, self.diff_threshold)
            else:
                threshold = self.diff_threshold
            logger.debug("自适应阈值={:.3f}", threshold)
        else:
            threshold = self.diff_threshold
            logger.debug("固定阈值={:.3f}", threshold)

        # 二值化（等价于 cv2.threshold）
        binary = blurred > threshold

        # 形态学开运算：去除孤立小噪点
        k = self.morph_kernel_size
        struct = np.ones((k, k), dtype=bool)
        binary = binary_opening(binary, structure=struct)

        # 形态学闭运算：填充小洞
        binary = binary_closing(binary, structure=struct)

        # 连通域分析
        labeled, num_features = label(binary)
        logger.debug("连通域数量: {}", num_features)

        if num_features == 0:
            logger.debug("无连通域，返回 None")
            return None

        # 过滤小区域（用 bincount 一次计算所有标签面积，避免逐标签全图扫描）
        min_area = int(dw * dh * self.min_region_ratio)
        areas = np.bincount(labeled.ravel())
        valid_labels = set(np.where(areas[1:] >= min_area)[0] + 1)
        logger.debug("有效连通域数量: {}/{} (min_area={})", len(valid_labels), num_features, min_area)
        filtered = np.isin(labeled, list(valid_labels))

        if not filtered.any():
            logger.debug("过滤后无有效区域")
            return None

        # 提取最大活动区域的包围矩形
        rows_any = np.any(filtered, axis=1)
        cols_any = np.any(filtered, axis=0)

        if not rows_any.any() or not cols_any.any():
            return None

        row_indices = np.where(rows_any)[0]
        col_indices = np.where(cols_any)[0]

        top = int(row_indices[0])
        bottom = int(row_indices[-1]) + 1
        left = int(col_indices[0])
        right = int(col_indices[-1]) + 1

        # 计算置信度：活动区域占总面积的比例 + 边框/内容对比度
        active_area = filtered.sum()
        content_area = (bottom - top) * (right - left)
        total_area = dh * dw

        if content_area < total_area * 0.05:
            logger.debug(
                "活动区域太小 content_area={} < {:.0f}，可能是噪声",
                content_area, total_area * 0.05,
            )
            return None

        coverage = active_area / content_area
        if coverage < self.min_change_coverage:
            logger.debug(
                "变化覆盖率太低 coverage={:.3f} < {}",
                coverage, self.min_change_coverage,
            )
            return None

        border_ratio = 1.0 - (content_area / total_area)
        conf = min(1.0, coverage * 2) * 0.5 + min(1.0, border_ratio * 5) * 0.5

        has_border = (
            top > dh * self.min_border_ratio
            or (dh - bottom) > dh * self.min_border_ratio
            or left > dw * self.min_border_ratio
            or (dw - right) > dw * self.min_border_ratio
        )

        if not has_border:
            logger.debug(
                "活动区域未超出边框阈值，判定为无边框 "
                "top={} bottom={} left={} right={} dh={} dw={}",
                top, bottom, left, right, dh, dw,
            )
            return None

        logger.debug(
            "检测到边框区域 top={} bottom={} left={} right={} conf={:.4f}",
            top, bottom, left, right, conf,
        )
        # 加安全边距
        top = max(0, top - self.safety_margin)
        bottom = min(dh, bottom + self.safety_margin)
        left = max(0, left - self.safety_margin)
        right = min(dw, right + self.safety_margin)

        return self._to_crop_result(top, bottom, left, right, conf, True)

    # ======================== 通用辅助 ========================

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
    video_path = r"E:\load\python\Project\VideoFusion\测试\dy\8fd68ff8825a0de6aff59c482abe7147.mp4"
    detector = BorderDetector()
    result = detector.detect(Path(video_path))
    print(result)
    print(f"检测耗时: {time.time() - start_time:.2f} 秒")

    arr = detector.preview(Path(video_path), frame_index=0, crop_result=result)
    Image.fromarray(arr).save("output.png")
    print("预览已保存到 output.png")
