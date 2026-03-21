from __future__ import annotations

import ctypes
import subprocess
from ctypes import wintypes
from pathlib import Path


class WindowUtils:
    MESSAGE_BOX_OK = 0x00000000
    MESSAGE_BOX_ICONWARNING = 0x00000030

    _SW_RESTORE = 9
    _SVSI_SELECT = 0x0001
    _SVSI_DESELECTOTHERS = 0x0004
    _SVSI_ENSUREVISIBLE = 0x0008
    _SVSI_FOCUSED = 0x0010
    _EXPLORER_SELECT_FLAGS = (
        _SVSI_SELECT | _SVSI_DESELECTOTHERS | _SVSI_ENSUREVISIBLE | _SVSI_FOCUSED
    )

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _enum_windows_proc = ctypes.WINFUNCTYPE(
        wintypes.BOOL,
        wintypes.HWND,
        wintypes.LPARAM,
    )
    _winapi_configured = False

    @classmethod
    def _configure_winapi(cls) -> None:
        if cls._winapi_configured:
            return

        cls._kernel32.GetCurrentThreadId.argtypes = ()
        cls._kernel32.GetCurrentThreadId.restype = wintypes.DWORD

        cls._user32.EnumWindows.argtypes = (cls._enum_windows_proc, wintypes.LPARAM)
        cls._user32.EnumWindows.restype = wintypes.BOOL
        cls._user32.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
        cls._user32.GetWindowTextLengthW.restype = ctypes.c_int
        cls._user32.GetWindowTextW.argtypes = (
            wintypes.HWND,
            wintypes.LPWSTR,
            ctypes.c_int,
        )
        cls._user32.GetWindowTextW.restype = ctypes.c_int
        cls._user32.IsWindowVisible.argtypes = (wintypes.HWND,)
        cls._user32.IsWindowVisible.restype = wintypes.BOOL
        cls._user32.IsIconic.argtypes = (wintypes.HWND,)
        cls._user32.IsIconic.restype = wintypes.BOOL
        cls._user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
        cls._user32.ShowWindow.restype = wintypes.BOOL
        cls._user32.BringWindowToTop.argtypes = (wintypes.HWND,)
        cls._user32.BringWindowToTop.restype = wintypes.BOOL
        cls._user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
        cls._user32.SetForegroundWindow.restype = wintypes.BOOL
        cls._user32.SetFocus.argtypes = (wintypes.HWND,)
        cls._user32.SetFocus.restype = wintypes.HWND
        cls._user32.GetForegroundWindow.argtypes = ()
        cls._user32.GetForegroundWindow.restype = wintypes.HWND
        cls._user32.GetWindowThreadProcessId.argtypes = (
            wintypes.HWND,
            ctypes.POINTER(wintypes.DWORD),
        )
        cls._user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        cls._user32.AttachThreadInput.argtypes = (
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.BOOL,
        )
        cls._user32.AttachThreadInput.restype = wintypes.BOOL
        cls._user32.MessageBoxW.argtypes = (
            wintypes.HWND,
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.UINT,
        )
        cls._user32.MessageBoxW.restype = ctypes.c_int

        cls._winapi_configured = True

    @staticmethod
    def _normalize_path(path: Path | str) -> str:
        normalized = Path(path).expanduser().resolve()
        return str(normalized).replace("/", "\\").rstrip("\\").lower()

    @staticmethod
    def _powershell_quote(text: str) -> str:
        return "'" + text.replace("'", "''") + "'"

    @staticmethod
    def _run_powershell(script: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                "powershell.exe",
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                script,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    @classmethod
    def find_visible_window_by_title(cls, window_title: str) -> int | None:
        cls._configure_winapi()
        matched_window: list[int] = []

        def enum_windows_proc(window_handle: wintypes.HWND, _: wintypes.LPARAM) -> bool:
            if not cls._user32.IsWindowVisible(window_handle):
                return True

            title_length = cls._user32.GetWindowTextLengthW(window_handle)
            if title_length <= 0:
                return True

            title_buffer = ctypes.create_unicode_buffer(title_length + 1)
            cls._user32.GetWindowTextW(window_handle, title_buffer, len(title_buffer))
            if title_buffer.value == window_title:
                matched_window.append(int(window_handle))
                return False

            return True

        callback = cls._enum_windows_proc(enum_windows_proc)
        cls._user32.EnumWindows(callback, 0)
        if not matched_window:
            return None

        return matched_window[0]

    @classmethod
    def bring_window_to_front(cls, window_handle: int | None) -> bool:
        cls._configure_winapi()
        if not window_handle:
            return False

        foreground_handle = cls._user32.GetForegroundWindow()
        current_thread_id = cls._kernel32.GetCurrentThreadId()
        target_thread_id = cls._user32.GetWindowThreadProcessId(window_handle, None)
        foreground_thread_id = 0

        if foreground_handle:
            foreground_thread_id = cls._user32.GetWindowThreadProcessId(foreground_handle, None)

        attached_to_foreground = False
        attached_to_target = False

        try:
            if foreground_thread_id and foreground_thread_id != current_thread_id:
                attached_to_foreground = bool(
                    cls._user32.AttachThreadInput(
                        foreground_thread_id,
                        current_thread_id,
                        True,
                    )
                )

            if foreground_thread_id and foreground_thread_id != target_thread_id:
                attached_to_target = bool(
                    cls._user32.AttachThreadInput(
                        foreground_thread_id,
                        target_thread_id,
                        True,
                    )
                )

            if cls._user32.IsIconic(window_handle):
                cls._user32.ShowWindow(window_handle, cls._SW_RESTORE)

            cls._user32.BringWindowToTop(window_handle)
            cls._user32.SetForegroundWindow(window_handle)
            cls._user32.SetFocus(window_handle)
            return True
        finally:
            if attached_to_target:
                cls._user32.AttachThreadInput(
                    foreground_thread_id,
                    target_thread_id,
                    False,
                )
            if attached_to_foreground:
                cls._user32.AttachThreadInput(
                    foreground_thread_id,
                    current_thread_id,
                    False,
                )

    @classmethod
    def show_message_box(cls, message: str, title: str, flags: int | None = None) -> int:
        cls._configure_winapi()
        effective_flags = cls.MESSAGE_BOX_OK if flags is None else flags
        return int(cls._user32.MessageBoxW(None, message, title, effective_flags))

    @classmethod
    def _find_explorer_window_for_directory(
        cls,
        directory: Path,
        selected_file_name: str | None = None,
    ) -> int | None:
        target_dir = cls._normalize_path(directory)
        selection_block = ""

        if selected_file_name:
            selection_block = f"""
                $item = $window.Document.Folder.ParseName({cls._powershell_quote(selected_file_name)})
                if ($null -ne $item) {{
                    $window.Document.SelectItem($item, {cls._EXPLORER_SELECT_FLAGS})
                }}
"""

        script = f"""
$ErrorActionPreference = 'Stop'
$target = {cls._powershell_quote(target_dir)}
$shell = New-Object -ComObject Shell.Application
foreach ($window in $shell.Windows()) {{
    try {{
        $document = $window.Document
        if ($null -eq $document -or $null -eq $document.Folder -or $null -eq $document.Folder.Self) {{
            continue
        }}

        $current = [System.IO.Path]::GetFullPath($document.Folder.Self.Path).Replace('/', '\\').TrimEnd('\\').ToLowerInvariant()
        if ($current -ne $target) {{
            continue
        }}
{selection_block}        [Console]::WriteLine([int64]$window.HWND)
        break
    }} catch {{
    }}
}}
"""
        result = cls._run_powershell(script)
        if result.returncode != 0:
            return None

        output = result.stdout.strip()
        if not output:
            return None

        try:
            return int(output.splitlines()[-1].strip())
        except ValueError:
            return None

    @classmethod
    def open_explorer_target(cls, target_path: Path | str, *, select_file: bool) -> bool:
        target = Path(target_path).expanduser().resolve()
        target_is_file = select_file and target.is_file()
        target_dir = target.parent if target_is_file else target

        if not target_dir.exists():
            target_dir = target_dir.parent

        existing_window = cls._find_explorer_window_for_directory(
            target_dir,
            selected_file_name=target.name if target_is_file else None,
        )
        if existing_window and cls.bring_window_to_front(existing_window):
            return True

        if target_is_file:
            subprocess.Popen(["explorer.exe", f"/select,{target}"])
        else:
            subprocess.Popen(["explorer.exe", str(target_dir)])
        return True
