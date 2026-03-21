import atexit
import ctypes
from ctypes import wintypes

from src.utils.window_utils import WindowUtils


class NeatReelSingleInstanceGuard:
    """使用 Windows 命名互斥量限制程序只运行一个实例。"""

    _ERROR_ALREADY_EXISTS = 183

    def __init__(
        self,
        mutex_name: str = "Global\\NeatReel.SingleInstance",
        window_title: str = "净影连 NeatReel",
    ) -> None:
        self._mutex_name = mutex_name
        self._window_title = window_title
        self._mutex_handle: wintypes.HANDLE | None = None
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._configure_winapi()
        atexit.register(self.release)

    def _configure_winapi(self) -> None:
        self._kernel32.CreateMutexW.argtypes = (
            wintypes.LPVOID,
            wintypes.BOOL,
            wintypes.LPCWSTR,
        )
        self._kernel32.CreateMutexW.restype = wintypes.HANDLE
        self._kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        self._kernel32.CloseHandle.restype = wintypes.BOOL

    def has_running_instance(self) -> bool:
        """
        检测是否已有另一个 NeatReel 实例在运行。

        返回 True 表示已有实例在运行；返回 False 表示当前实例已成功占用互斥量。
        """
        if self._mutex_handle is not None:
            return False

        handle = self._kernel32.CreateMutexW(None, False, self._mutex_name)
        if not handle:
            return False

        self._mutex_handle = handle
        return ctypes.get_last_error() == self._ERROR_ALREADY_EXISTS

    def bring_running_instance_to_front(self) -> bool:
        """尝试将已运行实例的主窗口切到最前。"""
        window_handle = self._find_running_window()
        if not window_handle:
            return False

        return WindowUtils.bring_window_to_front(window_handle)

    def show_warning_and_exit(self) -> None:
        """弹出警告框并退出当前程序。"""
        self.bring_running_instance_to_front()
        WindowUtils.show_message_box(
            "NeatReel 已经在运行中，请不要重复启动。",
            "NeatReel",
            WindowUtils.MESSAGE_BOX_OK | WindowUtils.MESSAGE_BOX_ICONWARNING,
        )
        self.release()
        raise SystemExit(0)

    def release(self) -> None:
        """释放当前实例持有的互斥量。"""
        if self._mutex_handle is None:
            return

        self._kernel32.CloseHandle(self._mutex_handle)
        self._mutex_handle = None

    def _find_running_window(self) -> wintypes.HWND | None:
        return WindowUtils.find_visible_window_by_title(self._window_title)
