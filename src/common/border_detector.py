"""
视频装饰边框检测与裁剪模块 v3

核心算法：帧间差分累积变化区域 → 形态学去噪 → 最大活动矩形提取
参考并优化自用户的 OpenCV 差值法实现，使用 PyAV + NumPy + SciPy 替代 OpenCV

依赖：av, numpy, scipy
"""

from __future__ import annotations

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
    视频装饰边框检测器 v3

    算法流程：
    1. 喂入采样帧（相邻帧对），累积帧间差分
    2. 对累积变化图做形态学去噪（开运算+闭运算）
    3. 连通域分析，过滤小区域噪声
    4. 提取最大活动区域的包围矩形

    用法:
        detector = BorderDetector()
        for frame in sampled_frames:
            detector.feed(frame)
        result = detector.detect()
        if result.has_border:
            cropped = detector.crop(frame)
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
    ):
        self.detect_short_edge = detect_short_edge
        self.min_border_ratio = min_border_ratio
        self.safety_margin = safety_margin
        self.diff_threshold = diff_threshold
        self.morph_kernel_size = morph_kernel_size
        self.min_region_ratio = min_region_ratio
        self.scene_change_threshold = scene_change_threshold
        self.min_change_coverage = min_change_coverage

        self._prev_gray: Optional[np.ndarray] = None
        self._accumulated: Optional[np.ndarray] = None  # 累积变化图 (bool)
        self._pair_count: int = 0
        self._original_size: Optional[tuple[int, int]] = None  # (w, h)
        self._detect_size: Optional[tuple[int, int]] = None
        self._scale_factor: float = 1.0
        self._result: Optional[CropResult] = None

    # ======================== 公开接口 ========================

    def feed(self, frame: av.VideoFrame) -> None:
        """
        喂入一帧。内部自动与前一帧做差分并累积。

        建议按时间顺序喂入，相邻帧间隔 0.3~2 秒为佳。
        对于长视频，均匀采样 20~60 帧足够。
        """
        if self._original_size is None:
            self._original_size = (frame.width, frame.height)
            self._compute_detect_size()

        dw, dh = self._detect_size
        small = frame.reformat(width=dw, height=dh)
        gray = small.to_ndarray(format="gray").astype(np.float32)

        if self._accumulated is None:
            self._accumulated = np.zeros((dh, dw), dtype=np.float64)

        if self._prev_gray is not None:
            diff = np.abs(gray - self._prev_gray)
            mean_diff = diff.mean()

            # 跳过场景切换帧
            if mean_diff < self.scene_change_threshold:
                # 跳过完全静止帧
                if mean_diff > 0.3:
                    self._accumulated += diff
                    self._pair_count += 1

        self._prev_gray = gray
        self._result = None

    def detect(self) -> CropResult:
        """执行检测，返回裁剪参数。"""
        if self._result is not None:
            return self._result

        if self._accumulated is None:
            raise RuntimeError("请先调用 feed() 喂入帧")

        result_motion = self._detect_by_motion()

        if result_motion is not None:
            self._result = result_motion
        else:
            ow, oh = self._original_size
            self._result = CropResult(
                x=0, y=0,
                width=_align2_down(ow), height=_align2_down(oh),
                confidence=0.0, has_border=False,
            )

        return self._result

    def crop(self, frame: av.VideoFrame) -> av.VideoFrame:
        """对单帧应用裁剪。"""
        r = self.detect()
        if not r.has_border:
            return frame
        arr = frame.to_ndarray(format="rgb24")
        cropped = arr[r.y: r.y + r.height, r.x: r.x + r.width].copy()
        out = av.VideoFrame.from_ndarray(cropped, format="rgb24")
        out.pts = frame.pts
        out.time_base = frame.time_base
        return out

    def reset(self) -> None:
        """重置状态，准备处理下一个视频。"""
        self._prev_gray = None
        self._accumulated = None
        self._pair_count = 0
        self._original_size = None
        self._detect_size = None
        self._scale_factor = 1.0
        self._result = None

    # ======================== 检测路径1：运动区域检测 ========================

    def _detect_by_motion(self) -> Optional[CropResult]:
        """
        基于帧间差分的累积变化区域检测。

        等价于你原来的 OpenCV 版本：
        帧差分 → 高斯模糊 → 二值化 → 形态学开闭运算 → 连通域过滤 → 最大包围矩形
        """
        dw, dh = self._detect_size

        if self._pair_count == 0:
            return None

        # 归一化累积图
        avg_diff = self._accumulated / self._pair_count

        # 高斯模糊降噪（等价于 cv2.GaussianBlur(gray, (5,5), 0)）
        blurred = gaussian_filter(avg_diff, sigma=1.0)

        # 二值化（等价于 cv2.threshold）
        binary = blurred > self.diff_threshold

        # 形态学开运算：去除孤立小噪点
        k = self.morph_kernel_size
        struct = np.ones((k, k), dtype=bool)
        binary = binary_opening(binary, structure=struct)

        # 形态学闭运算：填充小洞
        binary = binary_closing(binary, structure=struct)

        # 连通域分析（等价于 cv2.connectedComponentsWithStats）
        labeled, num_features = label(binary)

        if num_features == 0:
            return None

        # 过滤小区域
        min_area = int(dw * dh * self.min_region_ratio)
        # 创建过滤后的 binary
        filtered = np.zeros_like(binary)

        for i in range(1, num_features + 1):
            component = labeled == i
            area = component.sum()
            if area >= min_area:
                # 对每个合格的连通域，填充其包围矩形
                # （等价于你代码中的 cv2.rectangle ... -1）
                rows = np.any(component, axis=1)
                cols = np.any(component, axis=0)
                rmin, rmax = np.where(rows)[0][[0, -1]]
                cmin, cmax = np.where(cols)[0][[0, -1]]
                filtered[rmin:rmax + 1, cmin:cmax + 1] = True

        if not filtered.any():
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

        if content_area < total_area * 0.1:
            return None  # 活动区域太小，可能是噪声

        coverage = active_area / content_area
        if coverage < self.min_change_coverage:
            return None  # 变化覆盖率太低

        border_ratio = 1.0 - (content_area / total_area)
        conf = min(1.0, coverage * 2) * 0.5 + min(1.0, border_ratio * 5) * 0.5

        has_border = (
            top > dh * self.min_border_ratio
            or (dh - bottom) > dh * self.min_border_ratio
            or left > dw * self.min_border_ratio
            or (dw - right) > dw * self.min_border_ratio
        )

        if not has_border:
            return None

        # 加安全边距
        top = max(0, top - self.safety_margin)
        bottom = min(dh, bottom + self.safety_margin)
        left = max(0, left - self.safety_margin)
        right = min(dw, right + self.safety_margin)

        return self._to_crop_result(top, bottom, left, right, conf, True)

    # ======================== 通用辅助 ========================

    def _to_crop_result(
        self, top: int, bottom: int, left: int, right: int,
        conf: float, has_border: bool,
    ) -> CropResult:
        dw, dh = self._detect_size
        ow, oh = self._original_size

        if has_border:
            s = self._scale_factor
            ox = _align2(int(round(left * s)))
            oy = _align2(int(round(top * s)))
            cw = _align2_down(int(round((right - left) * s)))
            ch = _align2_down(int(round((bottom - top) * s)))

            ox = max(0, min(ox, ow - 2))
            oy = max(0, min(oy, oh - 2))
            cw = min(cw, ow - ox)
            ch = min(ch, oh - oy)
            cw = _align2_down(cw)
            ch = _align2_down(ch)

            if cw < ow * 0.15 or ch < oh * 0.15:
                has_border = False

        if not has_border:
            ox, oy = 0, 0
            cw = _align2_down(ow)
            ch = _align2_down(oh)
            conf = 0.0

        return CropResult(
            x=ox, y=oy, width=cw, height=ch,
            confidence=round(conf, 4), has_border=has_border,
        )

    def _compute_detect_size(self) -> None:
        ow, oh = self._original_size
        short = min(ow, oh)
        if short <= self.detect_short_edge:
            self._detect_size = (ow, oh)
            self._scale_factor = 1.0
        else:
            s = self.detect_short_edge / short
            dw = max(2, _align2_down(int(round(ow * s))))
            dh = max(2, _align2_down(int(round(oh * s))))
            self._detect_size = (dw, dh)
            self._scale_factor = 1.0 / s


def _align2(v: int) -> int:
    return v + (v % 2)


def _align2_down(v: int) -> int:
    return v - (v % 2)