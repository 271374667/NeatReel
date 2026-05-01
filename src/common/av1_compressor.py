# file: smart_av1_compressor.py
from pathlib import Path
from typing import List, Optional, Callable
import subprocess
import av
import numpy as np
from scipy.ndimage import laplace as _ndimage_laplace
from loguru import logger


class SmartAV1Compressor:
    """
    SmartAV1Compressor 提供智能 AV1 压缩功能，支持：
      - 高级噪点检测并动态降噪
      - CRF 根据分辨率和噪点自适应
      - 帧率/分辨率自适应
      - Two-pass 压缩（默认开启）
      - 日志记录（loguru）和进度回调
    """

    def __init__(
        self,
        crf_high_res: int = 28,
        crf_mid_res: int = 30,
        crf_low_res: int = 32,
        cpu_used_high_res: int = 0,
        cpu_used_low_res: int = 2,
        enable_two_pass: bool = True,
        enable_denoise: bool = True,
        max_threads: int = 8,
        max_frame_rate: Optional[int] = None,
        max_width: Optional[int] = None,
    ) -> None:
        """
        初始化 SmartAV1Compressor（激进压缩模式默认开启）。

        Args:
            crf_high_res (int): 高分辨率 CRF。
            crf_mid_res (int): 中分辨率 CRF。
            crf_low_res (int): 低分辨率 CRF。
            cpu_used_high_res (int): 高分辨率 CPU-used，0 最慢压缩最优。
            cpu_used_low_res (int): 低/中分辨率 CPU-used。
            enable_two_pass (bool): 是否启用 Two-pass 压缩（默认 True）。
            enable_denoise (bool): 是否启用轻微降噪（hqdn3d）。
            max_threads (int): FFmpeg 使用的线程数。
            max_frame_rate (Optional[int]): 最大帧率限制，可选。
            max_width (Optional[int]): 最大分辨率宽度限制，可选。
        """
        self.crf_high_res = crf_high_res
        self.crf_mid_res = crf_mid_res
        self.crf_low_res = crf_low_res
        self.cpu_used_high_res = cpu_used_high_res
        self.cpu_used_low_res = cpu_used_low_res
        self.enable_two_pass = enable_two_pass
        self.enable_denoise = enable_denoise
        self.max_threads = max_threads
        self.max_frame_rate = max_frame_rate
        self.max_width = max_width
        self._encoder = self._detect_encoder()

    def compress_videos(
        self,
        video_paths: List[str],
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> None:
        """
        批量压缩视频。

        Args:
            video_paths (List[str]): 视频文件路径列表。
            progress_callback (Optional[Callable[[str, float], None]]): 压缩进度回调，参数为文件名和进度百分比。
        """
        for path_str in video_paths:
            video_path = Path(path_str)
            if not video_path.exists():
                logger.warning(f"文件不存在: {video_path}")
                continue
            self._compress_single_video(video_path, progress_callback)

    # ===================== 私有方法 =====================
    def _get_video_info(self, video_path: Path):
        """获取视频宽高和帧率"""
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,r_frame_rate",
            "-of",
            "csv=p=0",
            str(video_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        try:
            width, height, fps_str = result.stdout.strip().split(",")
            width, height = int(width), int(height)
            num, den = map(int, fps_str.split("/"))
            fps = num / den
        except Exception:
            width, height, fps = 1920, 1080, 30.0
        return width, height, fps

    def _estimate_noise(
        self, video_path: Path, sample_frames: int = 20, block_size: int = 32
    ) -> float:
        """
        高级噪点检测：
          - 采样前 sample_frames 帧
          - 对每帧进行小块局部方差统计
          - 返回平均噪点值

        Args:
            video_path (Path): 视频路径
            sample_frames (int): 采样帧数
            block_size (int): 分块大小

        Returns:
            float: 视频噪点水平
        """
        total_noise: list[float] = []

        with av.open(str(video_path)) as container:
            stream = container.streams.video[0]
            # 跳过非参考帧（B 帧）加速采样，噪点特征在 I/P 帧上已足够
            stream.codec_context.skip_frame = "NONREF"

            total_frames = stream.frames or 0
            step = max(total_frames // sample_frames, 1) if total_frames > 0 else 1

            for frame_idx, frame in enumerate(container.decode(stream)):
                if frame_idx % step != 0:
                    continue

                # av 直接输出 gray8 格式，避免额外颜色转换
                gray: np.ndarray = frame.to_ndarray(format="gray")
                h, w = gray.shape
                block_noises: list[float] = []

                for y in range(0, h, block_size):
                    for x in range(0, w, block_size):
                        block = gray[y : y + block_size, x : x + block_size]
                        if block.size == 0:
                            continue
                        lap = _ndimage_laplace(block.astype(np.float64))
                        block_noises.append(float(lap.var()))

                if block_noises:
                    total_noise.append(float(np.mean(block_noises)))

                if len(total_noise) >= sample_frames:
                    break

        return float(np.mean(total_noise)) if total_noise else 0.0

    def _select_crf_cpu_denoise(self, width: int, noise_level: float):
        """根据分辨率和噪点选择 CRF, CPU-used 和是否降噪"""
        if width >= 3840:
            crf = self.crf_high_res
            cpu_used = self.cpu_used_high_res
        elif width >= 1920:
            crf = self.crf_mid_res
            cpu_used = self.cpu_used_low_res
        else:
            crf = self.crf_low_res
            cpu_used = self.cpu_used_low_res

        # 动态开启降噪，如果噪点超过阈值
        enable_denoise = self.enable_denoise and noise_level > 50.0  # 经验阈值
        return crf, cpu_used, enable_denoise

    def _detect_encoder(self) -> str:
        """检测可用的最优 AV1 编码器（libsvtav1 速度/质量优先于 libaom-av1）。"""
        try:
            result = subprocess.run(
                ["ffmpeg", "-encoders", "-v", "quiet"],
                capture_output=True,
                text=True,
            )
            # Windows 上 FFmpeg 可能将编码器列表写入 stderr，需同时检查
            combined = result.stdout + result.stderr
            if "libsvtav1" in combined:
                logger.info("已选用编码器: libsvtav1")
                return "libsvtav1"
        except Exception:
            pass
        logger.info("已选用编码器: libaom-av1")
        return "libaom-av1"

    def _build_encoder_args(
        self,
        crf: int,
        cpu_used: int,
        pass_num: Optional[int],
        use_grain_synthesis: bool,
    ) -> list:
        """
        构建 AV1 编码器参数列表。

        - libsvtav1：优先选用，通过 film-grain-denoise 在编码器内部去噪后合成颗粒元数据，
          压缩率更高且视觉细节保留完整，避免与 hqdn3d 双重降噪。
        - libaom-av1：回退方案，启用 AQ/QM/ARNR 提升压缩效率。

        Args:
            crf: CRF 质量值，越低质量越高。
            cpu_used: 编码速度（libaom 0-8 / libsvtav1 对应 preset 偏移）。
            pass_num: Two-pass 轮次（1 或 2），None 表示单遍。
            use_grain_synthesis: 是否启用编码器级胶片颗粒合成。
        """
        if self._encoder == "libsvtav1":
            # preset 2-6：值越小越慢/越优，根据 cpu_used 偏移映射
            preset = max(2, min(6, cpu_used + 3))
            svt_params = ["tune=0"]  # tune=0：VQ 视觉质量优化
            if use_grain_synthesis:
                # 编码器内部先分析并去除颗粒，再以元数据形式记录，解码时重建
                svt_params.append("film-grain=8:film-grain-denoise=1")
            args = [
                "-c:v",
                "libsvtav1",
                "-preset",
                str(preset),
                "-crf",
                str(crf),
                "-b:v",
                "0",
                "-svtav1-params",
                ":".join(svt_params),
            ]
        else:  # libaom-av1
            args = [
                "-c:v",
                "libaom-av1",
                "-crf",
                str(crf),
                "-b:v",
                "0",
                "-cpu-used",
                str(cpu_used),
                "-aq-mode",
                "1",  # 基于方差的自适应量化
                "-enable-chroma-deltaq",
                "1",  # 色度 Delta 量化，减少色彩失真
                "-enable-qm",
                "1",  # 量化矩阵，提升高频细节保留
                "-qm-min",
                "0",
                "-arnr-maxframes",
                "7",  # 时域降噪参考帧数
                "-arnr-strength",
                "4",  # 时域降噪强度
                "-row-mt",
                "1",
                "-threads",
                str(self.max_threads),
            ]
            if use_grain_synthesis:
                args += ["-film-grain-noise", "8"]  # 合成胶片颗粒元数据
            # libaom-av1 支持 FFmpeg 标准两遍，libsvtav1 不支持，此处仅对 libaom-av1 追加
            if pass_num is not None:
                args += ["-pass", str(pass_num)]

        return args

    def _compress_single_video(
        self,
        video_path: Path,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ):
        width, height, fps = self._get_video_info(video_path)

        # 限制分辨率或帧率
        scale_filter = ""
        if self.max_width and width > self.max_width:
            scale_filter = f"scale={self.max_width}:-2"
        fps_filter = (
            f"fps={self.max_frame_rate}"
            if self.max_frame_rate and fps > self.max_frame_rate
            else ""
        )

        noise_level = self._estimate_noise(video_path)
        crf, cpu_used, high_noise = self._select_crf_cpu_denoise(width, noise_level)
        output_path = video_path.with_name(video_path.stem + "_out" + video_path.suffix)

        # libsvtav1 通过 film-grain-denoise 内部处理噪点，避免 hqdn3d 双重降噪导致过度平滑
        use_hqdn3d = high_noise and self._encoder != "libsvtav1"
        use_grain_synthesis = high_noise  # 噪点视频启用胶片颗粒合成

        vf_filters = []
        if use_hqdn3d:
            vf_filters.append("hqdn3d=1.5:1.5:1.5:1.5")
        if scale_filter:
            vf_filters.append(scale_filter)
        if fps_filter:
            vf_filters.append(fps_filter)
        vf_filter_str = ",".join(vf_filters) if vf_filters else "null"

        # libsvtav1 CRF 模式不支持 FFmpeg 标准 two-pass；libaom-av1 支持
        use_two_pass = self.enable_two_pass and self._encoder == "libaom-av1"

        logger.info(
            f"[{self._encoder}] 压缩: {video_path.name} | "
            f"CRF={crf} cpu-used={cpu_used} 噪点={noise_level:.1f} "
            f"hqdn3d={use_hqdn3d} grain={use_grain_synthesis} two-pass={use_two_pass}"
        )

        # -fflags +genpts：重建 PTS，解决变分辨率拼接视频 DTS 非单调问题
        input_args = ["ffmpeg", "-y", "-fflags", "+genpts", "-i", str(video_path)]

        if use_two_pass:
            passlogfile = str(video_path.with_suffix(".passlog"))
            enc_p1 = self._build_encoder_args(crf, cpu_used, 1, use_grain_synthesis)
            enc_p1 += ["-passlogfile", passlogfile]
            cmd1 = input_args + ["-vf", vf_filter_str] + enc_p1 + ["-an", "-f", "null", "NUL"]
            logger.debug(f"Pass 1: {' '.join(cmd1)}")
            subprocess.run(cmd1, check=True)

            enc_p2 = self._build_encoder_args(crf, cpu_used, 2, use_grain_synthesis)
            enc_p2 += ["-passlogfile", passlogfile]
            cmd2 = input_args + ["-vf", vf_filter_str] + enc_p2 + ["-c:a", "copy", str(output_path)]
            logger.debug(f"Pass 2: {' '.join(cmd2)}")
            subprocess.run(cmd2, check=True)

            # 清理 passlog 临时文件
            for suffix in (".passlog-0.log", ".passlog-0.log.mbtree"):
                tmp = video_path.with_suffix(suffix)
                if tmp.exists():
                    tmp.unlink(missing_ok=True)
        else:
            enc = self._build_encoder_args(crf, cpu_used, None, use_grain_synthesis)
            cmd = input_args + ["-vf", vf_filter_str] + enc + ["-c:a", "copy", str(output_path)]
            logger.debug(f"Single-pass: {' '.join(cmd)}")
            subprocess.run(cmd, check=True)

        logger.info(f"完成: {output_path}")
        if progress_callback:
            progress_callback(video_path.name, 100.0)


if __name__ == "__main__":
    compressor = SmartAV1Compressor()
    compressor.compress_videos([r"G:\Movie\国产\学生\幼不漏上大号.mp4"])
