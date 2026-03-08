from __future__ import annotations

from qthreadwithreturn import QThreadWithReturn
from PySide6.QtCore import Property, QObject, Signal, Slot

from src.core.version import VersionHandler


class AboutService(QObject):
    isCheckingForUpdatesChanged = Signal()
    updateStatusTextChanged = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._is_checking_for_updates = False
        self._update_status_text = ""
        self._update_thread: QThreadWithReturn | None = None

    def _get_version(self) -> str:
        return VersionHandler.get_current_version()

    version = Property(str, _get_version, constant=True)

    def _get_license_text(self) -> str:
        return "LGPL v3"

    licenseText = Property(str, _get_license_text, constant=True)

    def _get_is_checking_for_updates(self) -> bool:
        return self._is_checking_for_updates

    isCheckingForUpdates = Property(
        bool,
        _get_is_checking_for_updates,
        notify=isCheckingForUpdatesChanged,
    )

    def _get_update_status_text(self) -> str:
        return self._update_status_text

    updateStatusText = Property(
        str,
        _get_update_status_text,
        notify=updateStatusTextChanged,
    )

    def _set_is_checking_for_updates(self, value: bool) -> None:
        if self._is_checking_for_updates == value:
            return
        self._is_checking_for_updates = value
        self.isCheckingForUpdatesChanged.emit()

    def _set_update_status_text(self, value: str) -> None:
        if self._update_status_text == value:
            return
        self._update_status_text = value
        self.updateStatusTextChanged.emit()

    @staticmethod
    def _build_update_status_text() -> str:
        updates, error = VersionHandler.check_for_updates_detailed()
        if error:
            first_line = error.strip().splitlines()[0] if error.strip() else "未知错误"
            return f"检查更新失败：{first_line}"

        if not updates:
            return "当前已是最新版本"

        versions = [next(iter(item.keys())) for item in updates if item]
        if not versions:
            return "发现新版本，请前往仓库查看发布信息"

        if len(versions) == 1:
            return f"发现新版本：{versions[0]}"

        preview_versions = "、".join(versions[:3])
        more_suffix = " 等" if len(versions) > 3 else ""
        return f"发现新版本：{preview_versions}{more_suffix}"

    @Slot()
    def checkForUpdates(self) -> None:
        if self._is_checking_for_updates:
            return

        self._set_is_checking_for_updates(True)
        self._set_update_status_text("正在检查更新...")

        thread = QThreadWithReturn(
            self._build_update_status_text,
            thread_name="about_update_check",
        )
        thread.add_done_callback(self._on_update_check_finished)
        thread.add_failure_callback(self._on_update_check_failed)
        thread.finished_signal.connect(self._on_update_thread_finished)
        self._update_thread = thread
        thread.start()

    @Slot(str)
    def _on_update_check_finished(self, status_text: str) -> None:
        self._set_is_checking_for_updates(False)
        self._set_update_status_text(status_text)

    @Slot(object)
    def _on_update_check_failed(self, exception: Exception) -> None:
        self._set_is_checking_for_updates(False)
        self._set_update_status_text(f"检查更新失败：{exception}")

    @Slot()
    def _on_update_thread_finished(self) -> None:
        self._update_thread = None
