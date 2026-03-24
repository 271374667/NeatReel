import sys
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QFont, QFontDatabase, QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine

from src.common.startup_trace import StartupTrace
from src.common.language_manager import LanguageManager
from src.common.single_instance_guard import NeatReelSingleInstanceGuard
from src.core.paths import LOGO_FILE
from src.image_provider import ThumbnailImageProvider
from src.resources.runtime_resources import ensure_qml_resources_registered
from src.service.about_service import AboutService
from src.service.home_service import HomeService
from src.service.processing_service import ProcessingService

DEBUG: bool = False
# DEBUG: bool = True
APP_FONT_PATH = Path(__file__).resolve().parent / "qml" / "Fonts" / "AlibabaPuHuiTi-3-55-Regular.ttf"
APP_FONT_RESOURCE = ":/qml/Fonts/AlibabaPuHuiTi-3-55-Regular.ttf"
APP_FONT_FAMILY_FALLBACK = "Alibaba PuHuiTi 3.0"


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
    font_source = str(APP_FONT_PATH) if debug else APP_FONT_RESOURCE
    font_id = QFontDatabase.addApplicationFont(font_source)
    if font_id == -1:
        raise RuntimeError(f"Failed to load application font: {font_source}")

    families = QFontDatabase.applicationFontFamilies(font_id)
    font_family = families[0] if families else APP_FONT_FAMILY_FALLBACK
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


def main(*, debug: bool = DEBUG) -> None:
    startup_trace = StartupTrace()
    instance_guard = NeatReelSingleInstanceGuard()
    if instance_guard.has_running_instance():
        startup_trace.mark("single_instance_detected")
        startup_trace.flush(success=False, note="already_running")
        instance_guard.show_warning_and_exit()
    startup_trace.mark("single_instance_checked")

    app = QGuiApplication(sys.argv)
    startup_trace.mark("qgui_application_created")
    ensure_qml_resources_registered(debug=debug)
    startup_trace.mark("qml_resources_registered")
    app_font_family = configure_application_font(app, debug=debug)
    startup_trace.mark("application_font_configured")
    language_manager = LanguageManager(app, debug=debug)
    language_manager.initialize_language()
    startup_trace.mark("language_initialized")

    engine = QQmlApplicationEngine()
    language_manager.set_engine(engine)
    language_manager.currentLanguageChanged.connect(
        lambda: update_application_display_name(app, language_manager)
    )
    engine.rootContext().setContextProperty("languageManager", language_manager)
    engine.rootContext().setContextProperty("appFontFamily", app_font_family)
    startup_trace.mark("qml_engine_prepared")

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
    startup_trace.mark("services_registered")

    load_main_qml(engine, debug=debug)
    startup_trace.mark("main_qml_loaded")
    app.setApplicationName("NeatReel")
    update_application_display_name(app, language_manager)
    app.setWindowIcon(resolve_window_icon(debug))  # 图标设在 load_main_qml 之后，不然读不出来

    if not engine.rootObjects():
        startup_trace.flush(success=False, note="root_objects_missing")
        sys.exit(-1)

    startup_trace.mark("root_objects_ready")
    startup_trace.flush(success=True)
    QTimer.singleShot(0, close_pyinstaller_splash)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
