from __future__ import annotations

import json
from typing import Any

from loguru import logger
from PySide6.QtCore import Property, QLocale, QObject, QTranslator, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from src.core.paths import PROJECT_ROOT, QML_DIR


class LanguageManager(QObject):
    currentLanguageChanged = Signal()

    CHINESE_LANGUAGE = "zh_CN"
    ENGLISH_LANGUAGE = "en_US"
    SETTINGS_FILE = PROJECT_ROOT / "settings.json"
    SETTINGS_LANGUAGE_KEY = "language"
    SUPPORTED_LANGUAGES = {CHINESE_LANGUAGE, ENGLISH_LANGUAGE}

    def __init__(self, app: QGuiApplication, *, debug: bool, parent: QObject | None = None):
        super().__init__(parent)
        self._app = app
        self._debug = debug
        self._engine: QQmlApplicationEngine | None = None
        self._translator: QTranslator | None = None
        self._current_language = self.CHINESE_LANGUAGE

    @property
    def current_language(self) -> str:
        return self._current_language

    def _get_current_language(self) -> str:
        return self._current_language

    currentLanguage = Property(
        str,
        _get_current_language,
        notify=currentLanguageChanged,
    )

    def _get_chinese_language(self) -> str:
        return self.CHINESE_LANGUAGE

    chineseLanguage = Property(str, _get_chinese_language, constant=True)

    def _get_english_language(self) -> str:
        return self.ENGLISH_LANGUAGE

    englishLanguage = Property(str, _get_english_language, constant=True)

    def set_engine(self, engine: QQmlApplicationEngine) -> None:
        self._engine = engine

    @classmethod
    def normalize_language(cls, language: str | None) -> str | None:
        if not language:
            return None

        normalized = language.replace("-", "_").strip()
        lowered = normalized.lower()

        if lowered.startswith("zh"):
            return cls.CHINESE_LANGUAGE
        if lowered.startswith("en"):
            return cls.ENGLISH_LANGUAGE
        if normalized in cls.SUPPORTED_LANGUAGES:
            return normalized
        return None

    def detect_system_language(self) -> str:
        system_locale = QLocale.system()
        if system_locale.language() == QLocale.Language.Chinese:
            return self.CHINESE_LANGUAGE
        return self.ENGLISH_LANGUAGE

    def load_saved_language(self) -> str | None:
        settings = self._load_settings()
        return self.normalize_language(settings.get(self.SETTINGS_LANGUAGE_KEY))

    def save_language(self, language: str) -> None:
        normalized = self.normalize_language(language)
        if normalized is None:
            return

        settings = self._load_settings()
        settings[self.SETTINGS_LANGUAGE_KEY] = normalized
        try:
            self.SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
            self.SETTINGS_FILE.write_text(
                json.dumps(settings, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            logger.warning("Failed to write settings to {}: {}", self.SETTINGS_FILE, exc)

    def initialize_language(self) -> str:
        saved_language = self.load_saved_language()
        target_language = saved_language or self.detect_system_language()

        if not self._apply_language(target_language, persist=True):
            logger.warning("Failed to apply language {}, fallback to {}", target_language, self.CHINESE_LANGUAGE)
            self._apply_language(self.CHINESE_LANGUAGE, persist=True)

        return self._current_language

    def _load_settings(self) -> dict[str, Any]:
        if not self.SETTINGS_FILE.exists():
            return {}

        try:
            data = json.loads(self.SETTINGS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read settings from {}: {}", self.SETTINGS_FILE, exc)
            return {}

        return data if isinstance(data, dict) else {}

    def _translation_path(self, language: str) -> str:
        if self._debug:
            return str(QML_DIR / "i18n" / f"VideoMerger_{language}.qm")
        return f":/qml/i18n/VideoMerger_{language}.qm"

    def _remove_current_translator(self) -> None:
        if self._translator is None:
            return

        self._app.removeTranslator(self._translator)
        self._translator = None

    def _refresh_qml_translations(self) -> None:
        if self._engine is None or not hasattr(self._engine, "retranslate"):
            return
        self._engine.retranslate()

    def _apply_language(self, language: str, *, persist: bool) -> bool:
        normalized = self.normalize_language(language)
        if normalized is None:
            return False

        if normalized == self._current_language:
            if persist:
                self.save_language(normalized)
            return True

        new_translator: QTranslator | None = None
        if normalized == self.ENGLISH_LANGUAGE:
            new_translator = QTranslator(self)
            translation_path = self._translation_path(normalized)
            if not new_translator.load(translation_path):
                logger.warning("Failed to load translation file: {}", translation_path)
                return False

        self._remove_current_translator()

        if new_translator is not None:
            self._app.installTranslator(new_translator)
        self._translator = new_translator
        self._current_language = normalized

        if persist:
            self.save_language(normalized)

        self.currentLanguageChanged.emit()
        self._refresh_qml_translations()
        return True

    @Slot(str, result=bool)
    def setLanguage(self, language: str) -> bool:
        return self._apply_language(language, persist=True)
