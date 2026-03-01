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
        self.min_change_coverage = min_change_coverage
        self.adaptive_threshold = adaptive_threshold
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

    def detect(
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
                    for lbl_idx in range(1, len(areas)):
                        if areas[lbl_idx] < min_area:
                            continue
                        rows = np.any(labeled_frame == lbl_idx, axis=1)
                        cols = np.any(labeled_frame == lbl_idx, axis=0)
                        if not rows.any() or not cols.any():
                            continue
                        r_idx = np.where(rows)[0]
                        c_idx = np.where(cols)[0]
                        t, b = int(r_idx[0]), int(r_idx[-1]) + 1
                        le, ri = int(c_idx[0]), int(c_idx[-1]) + 1
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
        areas = np.bincount(labeled.ravel())
        # areas[0] 是背景，跳过
        max_area = 0
        best_rect = None
        for lbl_idx in range(1, len(areas)):
            rows = np.any(labeled == lbl_idx, axis=1)
            cols = np.any(labeled == lbl_idx, axis=0)
            if not rows.any() or not cols.any():
                continue
            r_idx = np.where(rows)[0]
            c_idx = np.where(cols)[0]
            t, b = int(r_idx[0]), int(r_idx[-1]) + 1
            le, ri = int(c_idx[0]), int(c_idx[-1]) + 1
            rect_area = (b - t) * (ri - le)
            if rect_area > max_area:
                max_area = rect_area
                best_rect = (t, b, le, ri)

        if best_rect is None:
            return None

        top, bottom, left, right = best_rect
        total_area = dh * dw

        if max_area < total_area * 0.3:
            logger.debug(
                f"最大变化区域太小 area={max_area} < {total_area * 0.3:.0f}"
            )
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
    video_path = r"E:\load\python\Project\VideoFusion\测试\dy\8fd68ff8825a0de6aff59c482abe7147.mp4"
    detector = BorderDetector()
    info = detector.detect(Path(video_path))
    print(info)
    print(f"检测耗时: {time.time() - start_time:.2f} 秒")

    if info.crop_result is not None:
        arr = detector.preview(
            Path(video_path), frame_index=0, crop_result=info.crop_result
        )
        Image.fromarray(arr).save("output.png")
        print("预览已保存到 output.png")
