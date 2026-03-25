import os
import sys
from pathlib import Path

from loguru import logger
from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QFont, QFontDatabase, QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine

from src.common.logging_setup import ensure_app_logger_configured
from src.common.language_manager import LanguageManager
from src.common.single_instance_guard import NeatReelSingleInstanceGuard
from src.core.paths import LOGO_FILE, PROJECT_ROOT
from src.image_provider import ThumbnailImageProvider
from src.resources.runtime_resources import ensure_qml_resources_registered
from src.service.about_service import AboutService
from src.service.home_service import HomeService
from src.service.processing_service import ProcessingService

DEBUG: bool = False
# DEBUG: bool = True
APP_FONT_FILE_NAMES = [
    "SourceHanSansSC-Regular.otf",
    "SourceHanSansSC-Medium.otf",
    "SourceHanSansSC-Bold.otf",
]
APP_FONT_PATHS = [Path(__file__).resolve().parent / "qml" / "Fonts" / name for name in APP_FONT_FILE_NAMES]
APP_FONT_RESOURCES = [f":/qml/Fonts/{name}" for name in APP_FONT_FILE_NAMES]
APP_FONT_FAMILY_FALLBACK = "Source Han Sans SC"
QT_QUICK_CONTROLS_CONF = PROJECT_ROOT / "qtquickcontrols2.conf"


def resolve_window_icon(debug: bool) -> QIcon:
    if debug:
        return QIcon(str(LOGO_FILE))

    return QIcon(":/qml/Images/SmallLogo.png")


def close_pyinstaller_splash() -> None:
    try:
        import pyi_splash
    except ImportError:
        return

    try:
        pyi_splash.close()
    except Exception:
        pass


def configure_application_font(app: QGuiApplication, *, debug: bool) -> str:
    font_sources = [str(path) for path in APP_FONT_PATHS] if debug else APP_FONT_RESOURCES
    font_family = APP_FONT_FAMILY_FALLBACK
    loaded_font_ids: list[int] = []

    for font_source in font_sources:
        font_id = QFontDatabase.addApplicationFont(font_source)
        if font_id == -1:
            raise RuntimeError(f"Failed to load application font: {font_source}")
        loaded_font_ids.append(font_id)

    for font_id in loaded_font_ids:
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            font_family = families[0]
            break

    app.setFont(QFont(font_family))
    return font_family


def load_main_qml(engine: QQmlApplicationEngine, *, debug: bool) -> None:
    if debug:
        qml_path = Path(__file__).resolve().parent / "qml" / "App.qml"
        engine.load(qml_path)
        return

    engine.load(QUrl("qrc:/qml/App.qml"))


def update_application_display_name(app: QGuiApplication, language_manager: LanguageManager) -> None:
    display_name = (
        "净影连"
        if language_manager.current_language == LanguageManager.CHINESE_LANGUAGE
        else "NeatReel"
    )
    app.setApplicationDisplayName(display_name)


def configure_qtquickcontrols_conf() -> None:
    if QT_QUICK_CONTROLS_CONF.exists():
        os.environ.setdefault("QT_QUICK_CONTROLS_CONF", str(QT_QUICK_CONTROLS_CONF))


def main(*, debug: bool = DEBUG) -> None:
    ensure_app_logger_configured()
    logger.info("NeatReel starting (debug={})", debug)
    configure_qtquickcontrols_conf()
    instance_guard = NeatReelSingleInstanceGuard()
    if instance_guard.has_running_instance():
        logger.warning("Another NeatReel instance is already running")
        instance_guard.show_warning_and_exit()

    app = QGuiApplication(sys.argv)
    ensure_qml_resources_registered(debug=debug)
    app_font_family = configure_application_font(app, debug=debug)
    language_manager = LanguageManager(app, debug=debug)
    language_manager.initialize_language()

    engine = QQmlApplicationEngine()
    language_manager.set_engine(engine)
    language_manager.currentLanguageChanged.connect(
        lambda: update_application_display_name(app, language_manager)
    )
    engine.rootContext().setContextProperty("languageManager", language_manager)
    engine.rootContext().setContextProperty("appFontFamily", app_font_family)

    # image provider (must be added before loading QML)
    image_provider = ThumbnailImageProvider()
    engine.addImageProvider("thumbnail", image_provider)

    # services -> QML context properties
    home_service = HomeService(image_provider)
    engine.rootContext().setContextProperty("homeService", home_service)

    processing_service = ProcessingService(image_provider)
    engine.rootContext().setContextProperty("processingService", processing_service)

    about_service = AboutService()
    engine.rootContext().setContextProperty("aboutService", about_service)

    load_main_qml(engine, debug=debug)
    app.setApplicationName("NeatReel")
    update_application_display_name(app, language_manager)
    app.setWindowIcon(resolve_window_icon(debug))  # 图标设在 load_main_qml 之后，不然读不出来

    if not engine.rootObjects():
        logger.error("QML root objects are missing, startup failed")
        sys.exit(-1)

    logger.info("NeatReel started successfully")
    QTimer.singleShot(0, close_pyinstaller_splash)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
