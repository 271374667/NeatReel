import atexit
import ctypes
from ctypes import wintypes


class NeatReelSingleInstanceGuard:
    """使用 Windows 命名互斥量限制程序只运行一个实例。"""

    _ERROR_ALREADY_EXISTS = 183
    _MB_OK = 0x00000000
    _MB_ICONWARNING = 0x00000030
    _SW_RESTORE = 9

    def __init__(
        self,
        mutex_name: str = "Global\\NeatReel.SingleInstance",
        window_title: str = "净影连 NeatReel",
    ) -> None:
        self._mutex_name = mutex_name
        self._window_title = window_title
        self._mutex_handle: wintypes.HANDLE | None = None
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._enum_windows_proc = ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HWND,
            wintypes.LPARAM,
        )
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
        self._kernel32.GetCurrentThreadId.argtypes = ()
        self._kernel32.GetCurrentThreadId.restype = wintypes.DWORD

        self._user32.EnumWindows.argtypes = (self._enum_windows_proc, wintypes.LPARAM)
        self._user32.EnumWindows.restype = wintypes.BOOL
        self._user32.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
        self._user32.GetWindowTextLengthW.restype = ctypes.c_int
        self._user32.GetWindowTextW.argtypes = (
            wintypes.HWND,
            wintypes.LPWSTR,
            ctypes.c_int,
        )
        self._user32.GetWindowTextW.restype = ctypes.c_int
        self._user32.IsWindowVisible.argtypes = (wintypes.HWND,)
        self._user32.IsWindowVisible.restype = wintypes.BOOL
        self._user32.IsIconic.argtypes = (wintypes.HWND,)
        self._user32.IsIconic.restype = wintypes.BOOL
        self._user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
        self._user32.ShowWindow.restype = wintypes.BOOL
        self._user32.BringWindowToTop.argtypes = (wintypes.HWND,)
        self._user32.BringWindowToTop.restype = wintypes.BOOL
        self._user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
        self._user32.SetForegroundWindow.restype = wintypes.BOOL
        self._user32.SetFocus.argtypes = (wintypes.HWND,)
        self._user32.SetFocus.restype = wintypes.HWND
        self._user32.GetForegroundWindow.argtypes = ()
        self._user32.GetForegroundWindow.restype = wintypes.HWND
        self._user32.GetWindowThreadProcessId.argtypes = (
            wintypes.HWND,
            ctypes.POINTER(wintypes.DWORD),
        )
        self._user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        self._user32.AttachThreadInput.argtypes = (
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.BOOL,
        )
        self._user32.AttachThreadInput.restype = wintypes.BOOL
        self._user32.MessageBoxW.argtypes = (
            wintypes.HWND,
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.UINT,
        )
        self._user32.MessageBoxW.restype = ctypes.c_int

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

        foreground_handle = self._user32.GetForegroundWindow()
        current_thread_id = self._kernel32.GetCurrentThreadId()
        target_thread_id = self._user32.GetWindowThreadProcessId(window_handle, None)
        foreground_thread_id = 0

        if foreground_handle:
            foreground_thread_id = self._user32.GetWindowThreadProcessId(foreground_handle, None)

        attached_to_foreground = False
        attached_to_target = False

        try:
            if foreground_thread_id and foreground_thread_id != current_thread_id:
                attached_to_foreground = bool(
                    self._user32.AttachThreadInput(
                        foreground_thread_id,
                        current_thread_id,
                        True,
                    )
                )

            if foreground_thread_id and foreground_thread_id != target_thread_id:
                attached_to_target = bool(
                    self._user32.AttachThreadInput(
                        foreground_thread_id,
                        target_thread_id,
                        True,
                    )
                )

            if self._user32.IsIconic(window_handle):
                self._user32.ShowWindow(window_handle, self._SW_RESTORE)

            self._user32.BringWindowToTop(window_handle)
            self._user32.SetForegroundWindow(window_handle)
            self._user32.SetFocus(window_handle)
            return True
        finally:
            if attached_to_target:
                self._user32.AttachThreadInput(
                    foreground_thread_id,
                    target_thread_id,
                    False,
                )
            if attached_to_foreground:
                self._user32.AttachThreadInput(
                    foreground_thread_id,
                    current_thread_id,
                    False,
                )

    def show_warning_and_exit(self) -> None:
        """弹出警告框并退出当前程序。"""
        self.bring_running_instance_to_front()
        self._user32.MessageBoxW(
            None,
            "NeatReel 已经在运行中，请不要重复启动。",
            "NeatReel",
            self._MB_OK | self._MB_ICONWARNING,
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
        matched_window: list[wintypes.HWND] = []

        @self._enum_windows_proc
        def enum_windows_proc(window_handle: wintypes.HWND, _: wintypes.LPARAM) -> bool:
            if not self._user32.IsWindowVisible(window_handle):
                return True

            title_length = self._user32.GetWindowTextLengthW(window_handle)
            if title_length <= 0:
                return True

            title_buffer = ctypes.create_unicode_buffer(title_length + 1)
            self._user32.GetWindowTextW(window_handle, title_buffer, len(title_buffer))

            if title_buffer.value == self._window_title:
                matched_window.append(window_handle)
                return False

            return True

        self._user32.EnumWindows(enum_windows_proc, 0)
        if not matched_window:
            return None

        return matched_window[0]
