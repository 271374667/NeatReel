from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QImage


class MergeCancelled(Exception):
    """Raised when the user cancels the merge operation."""


class MergeSignals(QObject):
    """单例信号中枢：把 VideoMerger 工作线程的状态同步到 ProcessingService 主线程。"""

    # 由 VideoMerger 在整次处理开始时发出。
    # 连接到 ProcessingService._on_merge_started()。
    # 参数:
    #   total_files: int
    #       本次任务总共要处理多少个视频文件。
    #   effective_fps: float
    #       本次输出使用的有效帧率。
    # 用途:
    #   主要用于初始化总任务上下文，后续由 ProcessingService 发出
    #   totalCountChanged / totalCurrentChanged 给界面。
    # 进度条关系:
    #   不直接驱动主进度条或子进度条，只负责给后续进度计算提供总量信息。
    mergeStarted = Signal(int, float)

    # 由 VideoMerger 在开始处理某一个文件时发出。
    # 连接到 ProcessingService._on_file_started()。
    # 参数:
    #   file_index: int
    #       当前处理的是第几个文件，1-based（从 1 开始计数）。
    #   file_name: str
    #       当前文件名，仅文件名，不含完整路径。
    #   total_frames: int
    #       当前文件预计总帧数；如果拿不到可靠值则可能为 0。
    #   effective_fps: float
    #       当前文件实际处理时采用的有效帧率。
    # 用途:
    #   更新当前处理到第几个文件、阶段标题，并把子进度条重置为 0。
    # 进度条关系:
    #   不直接更新主进度条；
    #   会通过 ProcessingService 把子进度条 stageProgressChanged 重置为 0.0。
    fileStarted = Signal(int, str, int, float)

    # 由 VideoMerger 在处理视频帧时持续发出（做了节流，约 300ms 一次）。
    # 连接到 ProcessingService._on_frame_processed()。
    # 参数:
    #   current_frames: int
    #       当前文件已经处理完成的帧数。
    #   total_frames: int
    #       当前文件预计总帧数；如果拿不到可靠值则可能为 0。
    # 用途:
    #   这是进度更新的核心信号。
    #   ProcessingService 会用它计算 stage_progress = current_frames / total_frames，
    #   再发出 stageProgressChanged；同时再结合已完成文件数，计算总进度并发出
    #   totalProgressChanged。
    # 进度条关系:
    #   它同时间接驱动两个进度条：
    #   1. 子进度条：stageProgressChanged -> qml/Windows/Processing.qml 的 stageProgress。
    #   2. 主进度条：totalProgressChanged -> qml/Windows/Processing.qml 的 totalProgress。
    frameProcessed = Signal(int, int)

    # 由 VideoMerger 在某个文件处理完成时发出。
    # 连接到 ProcessingService._on_file_finished()。
    # 参数:
    #   file_index: int
    #       已完成的文件序号，1-based（从 1 开始计数）。
    # 用途:
    #   在文件边界把当前文件标记为完成，避免总进度和阶段进度停在小数点附近。
    # 进度条关系:
    #   会间接把子进度条补到 100%（stageProgressChanged.emit(1.0)），
    #   同时把主进度条更新到 completed_files / total_files。
    fileFinished = Signal(int)

    # 由 VideoMerger 在整次任务全部完成时发出。
    # 连接到 ProcessingService._on_merge_finished()。
    # 参数:
    #   无。
    # 用途:
    #   通知主线程任务结束，更新状态为完成。
    # 进度条关系:
    #   会把主进度条和子进度条都最终设为 100%。
    mergeFinished = Signal()

    # 由 VideoMerger 在任务取消或处理异常时发出。
    # 连接到 ProcessingService._on_merge_error()。
    # 参数:
    #   message: str
    #       错误信息；当用户取消时通常为“已取消”。
    # 用途:
    #   通知主线程本次任务失败或取消，并更新界面状态文案。
    # 进度条关系:
    #   不直接推进主/子进度条，只负责把状态切到错误或取消。
    mergeError = Signal(str)

    # 由 VideoMerger 在处理过程中输出预览帧时发出（做了节流，约 300ms 一次）。
    # 连接到 ProcessingService._on_display_frame()。
    # 参数:
    #   qimage: QImage
    #       当前处理结果对应的一帧预览图。
    # 用途:
    #   刷新处理页面中的预览画面。
    # 进度条关系:
    #   与主进度条、子进度条无直接关系。
    displayFrameReady = Signal(QImage)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._cancel_event = threading.Event()

    def request_cancel(self) -> None:
        self._cancel_event.set()

    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def reset(self) -> None:
        self._cancel_event.clear()


_instance: MergeSignals | None = None
_lock = threading.Lock()


def get_merge_signals() -> MergeSignals:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = MergeSignals()
    return _instance
