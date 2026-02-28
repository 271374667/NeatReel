"""
视��装饰边框检测与裁剪模块 - 静态检测算法 v5

修复：
- 黑边判定从「行中位数」改为「行暗像素占比」
  即使水印/Logo占据行宽30%，只要70%的像素是暗的，就判定为黑边行
- 间隙跳跃根据暗像素占比动态决定是否跳跃
- 通用边框检测不变

依赖：av, numpy, scipy
"""

from __future__ import annotations

import av
import numpy as np
from scipy.ndimage import sobel, gaussian_filter1d
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
    视频装饰边框检测器（静态分析版 v5）
    """

    def __init__(
        self,
        detect_short_edge: int = 480,
        min_border_ratio: float = 0.02,
        max_border_ratio: float = 0.45,
        safety_margin: int = 2,
        # 黑边检测：单个像素低于此值视为「暗像素」
        black_pixel_threshold: float = 30.0,
        # 黑边检测：一行/列中暗像素占比超过此值，判定该行/列为「黑边行/列」
        black_pixel_ratio: float = 0.65,
        # 多帧投票比例
        black_vote_ratio: float = 0.55,
        # 间隙跳跃容忍（0=自动计算）
        black_gap_tolerance: int = 0,
        # 通用边框检测
        border_content_ratio: float = 1.8,
    ):
        self.detect_short_edge = detect_short_edge
        self.min_border_ratio = min_border_ratio
        self.max_border_ratio = max_border_ratio
        self.safety_margin = safety_margin
        self.black_pixel_threshold = black_pixel_threshold
        self.black_pixel_ratio = black_pixel_ratio
        self.black_vote_ratio = black_vote_ratio
        self.black_gap_tolerance = black_gap_tolerance
        self.border_content_ratio = border_content_ratio

        self._frames_gray: list[np.ndarray] = []
        self._frames_rgb: list[np.ndarray] = []
        self._original_size: Optional[tuple[int, int]] = None
        self._detect_size: Optional[tuple[int, int]] = None
        self._scale_factor: float = 1.0
        self._result: Optional[CropResult] = None

    # ======================== 公开接口 ========================

    def feed(self, frame: av.VideoFrame) -> None:
        if self._original_size is None:
            self._original_size = (frame.width, frame.height)
            self._compute_detect_size()

        dw, dh = self._detect_size
        small = frame.reformat(width=dw, height=dh)
        self._frames_gray.append(
            small.to_ndarray(format="gray").astype(np.float32)
        )
        self._frames_rgb.append(
            small.to_ndarray(format="rgb24").astype(np.float32)
        )
        self._result = None

    def detect(self) -> CropResult:
        if self._result is not None:
            return self._result

        if not self._frames_gray:
            raise RuntimeError("请先调用 feed() 喂入帧")

        result_black = self._detect_black_borders()
        result_general = self._detect_general_borders()

        if result_black is not None and result_general is not None:
            self._result = self._intersect_results(result_black, result_general)
        elif result_black is not None:
            self._result = result_black
        elif result_general is not None:
            self._result = result_general
        else:
            ow, oh = self._original_size
            self._result = CropResult(
                x=0, y=0,
                width=_align2_down(ow), height=_align2_down(oh),
                confidence=0.0, has_border=False,
            )

        return self._result

    def crop(self, frame: av.VideoFrame) -> av.VideoFrame:
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
        self._frames_gray.clear()
        self._frames_rgb.clear()
        self._original_size = None
        self._detect_size = None
        self._scale_factor = 1.0
        self._result = None

    # ======================== 路径1：黑边检测 v5 ========================

    def _detect_black_borders(self) -> Optional[CropResult]:
        """
        基于「暗像素占比」的黑边检测。

        对每行/列，计算该行中亮度 < black_pixel_threshold 的像素所占比例。
        如果占比 >= black_pixel_ratio，则该行/列判定为黑边。

        相比中位数方法的优势：
        - 中位数：水印占 30% → 中位数仍低 → 但 Logo 有大面积彩色可能拉高中位数
        - 暗像素占比：水印占 30% → 暗像素占比 = 70% → 仍 >= 65% → 正确判定为黑边行

        多帧投票 + 间隙跳跃扫描。
        """
        dh, dw = self._frames_gray[0].shape
        n_frames = len(self._frames_gray)

        # ---- 每帧独立计算每行/列的暗像素占比 ----
        row_black_votes = np.zeros(dh, dtype=np.int32)
        col_black_votes = np.zeros(dw, dtype=np.int32)

        for gray in self._frames_gray:
            # 每个像素是否为暗像素
            dark_mask = gray < self.black_pixel_threshold  # (dh, dw) bool

            # 每行的暗像素占比
            row_dark_ratio = dark_mask.sum(axis=1) / dw  # (dh,)
            col_dark_ratio = dark_mask.sum(axis=0) / dh  # (dw,)

            row_black_votes += (row_dark_ratio >= self.black_pixel_ratio).astype(np.int32)
            col_black_votes += (col_dark_ratio >= self.black_pixel_ratio).astype(np.int32)

        # ---- 投票 ----
        min_votes = max(1, int(n_frames * self.black_vote_ratio))
        row_is_black = row_black_votes >= min_votes
        col_is_black = col_black_votes >= min_votes

        # ---- 间隙跳跃扫描 ----
        gap = self._compute_gap_tolerance()

        top = _scan_border(row_is_black, forward=True, gap_tolerance=gap)
        bottom = dh - _scan_border(row_is_black, forward=False, gap_tolerance=gap)
        left = _scan_border(col_is_black, forward=True, gap_tolerance=gap)
        right = dw - _scan_border(col_is_black, forward=False, gap_tolerance=gap)

        # ---- 检查有效性 ----
        min_h = max(1, int(dh * self.min_border_ratio))
        min_w = max(1, int(dw * self.min_border_ratio))

        has_any = (
            top >= min_h
            or (dh - bottom) >= min_h
            or left >= min_w
            or (dw - right) >= min_w
        )
        if not has_any:
            return None

        if top < min_h:
            top = 0
        if (dh - bottom) < min_h:
            bottom = dh
        if left < min_w:
            left = 0
        if (dw - right) < min_w:
            right = dw

        conf = self._black_confidence(top, bottom, left, right)
        if conf < 0.15:
            return None

        return self._to_crop_result(top, bottom, left, right, conf, True)

    def _compute_gap_tolerance(self) -> int:
        if self.black_gap_tolerance > 0:
            return self.black_gap_tolerance
        dh = self._detect_size[1]
        return max(5, int(dh * 0.04))

    def _black_confidence(
        self, top: int, bottom: int, left: int, right: int,
    ) -> float:
        avg = np.mean(self._frames_gray, axis=0)

        border_px = []
        if top > 0:
            border_px.append(avg[:top, :].ravel())
        if bottom < avg.shape[0]:
            border_px.append(avg[bottom:, :].ravel())
        if left > 0:
            border_px.append(avg[top:bottom, :left].ravel())
        if right < avg.shape[1]:
            border_px.append(avg[top:bottom, right:].ravel())

        content = avg[top:bottom, left:right]

        if not border_px or content.size == 0:
            return 0.0

        bm = np.concatenate(border_px).mean()
        cm = content.mean()

        if cm > 1.0:
            return float(np.clip(1.0 - bm / cm, 0.0, 1.0))
        return 0.5 if bm < self.black_pixel_threshold else 0.0

    # ======================== 路径2：通用边框检测 ========================

    def _detect_general_borders(self) -> Optional[CropResult]:
        dh, dw = self._frames_gray[0].shape

        grad_h, grad_w = self._gradient_profiles()
        var_h, var_w = self._variance_profiles()
        color_h, color_w = self._color_profiles()

        fh = (
            0.35 * _norm(grad_h)
            + 0.30 * _norm(var_h)
            + 0.35 * _norm(color_h)
        )
        fw = (
            0.35 * _norm(grad_w)
            + 0.30 * _norm(var_w)
            + 0.35 * _norm(color_w)
        )

        fh = gaussian_filter1d(fh, sigma=2.0)
        fw = gaussian_filter1d(fw, sigma=2.0)

        min_bh = max(1, int(dh * self.min_border_ratio))
        max_bh = int(dh * self.max_border_ratio)
        min_bw = max(1, int(dw * self.min_border_ratio))
        max_bw = int(dw * self.max_border_ratio)

        top = self._find_edge(fh, min_bh, max_bh)
        bottom = dh - self._find_edge(fh[::-1], min_bh, max_bh)
        left = self._find_edge(fw, min_bw, max_bw)
        right = dw - self._find_edge(fw[::-1], min_bw, max_bw)

        has_any = (top > 0 or bottom < dh or left > 0 or right < dw)
        if not has_any:
            return None

        conf = self._general_confidence(fh, fw, top, bottom, left, right)
        if conf < 0.20:
            return None

        top = min(top + self.safety_margin, dh // 2)
        bottom = max(bottom - self.safety_margin, dh // 2)
        left = min(left + self.safety_margin, dw // 2)
        right = max(right - self.safety_margin, dw // 2)

        return self._to_crop_result(top, bottom, left, right, conf, True)

    def _find_edge(self, profile: np.ndarray, min_pos: int, max_pos: int) -> int:
        n = len(profile)
        max_pos = min(max_pos, n // 2)

        if max_pos <= min_pos or max_pos < 2:
            return 0

        cumsum = np.cumsum(profile)
        verify_len = max(8, int(n * 0.08))

        best_pos = 0
        best_score = 0.0

        for pos in range(min_pos, max_pos):
            border_mean = cumsum[pos - 1] / pos

            end = min(pos + verify_len, n)
            content_sum = cumsum[end - 1] - (cumsum[pos - 1] if pos > 0 else 0)
            content_mean = content_sum / (end - pos)

            if border_mean < 1e-6:
                score = content_mean * 100.0 if content_mean > 1e-3 else 0.0
            else:
                score = content_mean / border_mean

            if score > best_score:
                best_score = score
                best_pos = pos

        if best_score < self.border_content_ratio:
            return 0

        w = max(3, min_pos)
        before = profile[max(0, best_pos - w): best_pos]
        after = profile[best_pos: min(n, best_pos + w)]

        if len(before) == 0 or len(after) == 0:
            return 0

        if after.mean() <= before.mean() * 1.15:
            return 0

        return best_pos

    def _general_confidence(
        self, fh: np.ndarray, fw: np.ndarray,
        top: int, bottom: int, left: int, right: int,
    ) -> float:
        scores: list[float] = []
        dh, dw = len(fh), len(fw)

        for prof, s, e, total in [(fh, top, bottom, dh), (fw, left, right, dw)]:
            bvals = []
            if s > 0:
                bvals.extend(prof[:s].tolist())
            if e < total:
                bvals.extend(prof[e:].tolist())
            cvals = prof[s:e].tolist() if s < e else []
            if bvals and cvals:
                bm = float(np.mean(bvals))
                cm = float(np.mean(cvals))
                if bm > 1e-8:
                    scores.append(min(1.0, max(0.0, cm / bm - 1.0)))
                elif cm > 0.01:
                    scores.append(1.0)

        for prof, pos in [(fh, top), (fh, bottom), (fw, left), (fw, right)]:
            total = len(prof)
            if 0 < pos < total:
                w = 3
                bef = prof[max(0, pos - w): pos].mean()
                aft = prof[pos: min(total, pos + w)].mean()
                rng = prof.max() - prof.min()
                if rng > 1e-8:
                    scores.append(min(1.0, abs(aft - bef) / rng * 2.0))

        return float(np.mean(scores)) if scores else 0.0

    # ======================== Profile 构建 ========================

    def _gradient_profiles(self) -> tuple[np.ndarray, np.ndarray]:
        h, w = self._frames_gray[0].shape
        rp = np.zeros(h, dtype=np.float64)
        cp = np.zeros(w, dtype=np.float64)
        for g in self._frames_gray:
            mag = np.hypot(sobel(g, axis=1), sobel(g, axis=0))
            rp += mag.mean(axis=1)
            cp += mag.mean(axis=0)
        n = len(self._frames_gray)
        return rp / n, cp / n

    def _variance_profiles(self) -> tuple[np.ndarray, np.ndarray]:
        h, w = self._frames_gray[0].shape
        rp = np.zeros(h, dtype=np.float64)
        cp = np.zeros(w, dtype=np.float64)
        for g in self._frames_gray:
            rp += g.var(axis=1)
            cp += g.var(axis=0)
        n = len(self._frames_gray)
        return rp / n, cp / n

    def _color_profiles(self) -> tuple[np.ndarray, np.ndarray]:
        h, w = self._frames_gray[0].shape
        rp = np.zeros(h, dtype=np.float64)
        cp = np.zeros(w, dtype=np.float64)
        for rgb in self._frames_rgb:
            rp += rgb.std(axis=1).mean(axis=1)
            cp += rgb.std(axis=0).mean(axis=1)
        n = len(self._frames_rgb)
        return rp / n, cp / n

    # ======================== 结果构建 ========================

    def _intersect_results(self, a: CropResult, b: CropResult) -> CropResult:
        ow, oh = self._original_size
        x = max(a.x, b.x)
        y = max(a.y, b.y)
        x2 = min(a.x + a.width, b.x + b.width)
        y2 = min(a.y + a.height, b.y + b.height)
        w, h = x2 - x, y2 - y

        if w <= 0 or h <= 0 or w < ow * 0.15 or h < oh * 0.15:
            area_a = a.width * a.height
            area_b = b.width * b.height
            return a if area_a <= area_b else b

        return CropResult(
            x=_align2(x), y=_align2(y),
            width=_align2_down(w), height=_align2_down(h),
            confidence=max(a.confidence, b.confidence),
            has_border=True,
        )

    def _to_crop_result(
        self, top: int, bottom: int, left: int, right: int,
        conf: float, has_border: bool,
    ) -> CropResult:
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


# ======================== 模块级工具函数 ========================

def _norm(arr: np.ndarray) -> np.ndarray:
    mn, mx = arr.min(), arr.max()
    return (arr - mn) / (mx - mn) if (mx - mn) > 1e-8 else np.zeros_like(arr)


def _scan_border(
    is_black: np.ndarray,
    forward: bool,
    gap_tolerance: int,
) -> int:
    """
    从一端向内扫描连续黑边，支持跳跃间隙。

    遇到非黑行时，向前看 gap_tolerance 行：
    - 范围内有黑行 → 跳过间隙继续
    - 范围内全非黑 → 到达真正边界，停止
    """
    seq = is_black if forward else is_black[::-1]
    n = len(seq)
    pos = 0

    while pos < n:
        if seq[pos]:
            pos += 1
        else:
            found = False
            for la in range(1, gap_tolerance + 1):
                if pos + la < n and seq[pos + la]:
                    found = True
                    break
            if found:
                pos += 1
            else:
                break

    return pos


def _align2(v: int) -> int:
    return v + (v % 2)


def _align2_down(v: int) -> int:
    return v - (v % 2)