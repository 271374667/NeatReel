import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine

from src.core.paths import LOGO_FILE
from src.service.home_service import HomeService
from src.service.image_provider import ThumbnailImageProvider
from src.service.processing_service import ProcessingService

DEBUG: bool = False
# DEBUG: bool = True


def resolve_window_icon(debug: bool) -> QIcon:
    if debug:
        return QIcon(str(LOGO_FILE))

    return QIcon(":/qml/Images/SmallLogo.svg")


def load_main_qml(engine: QQmlApplicationEngine, *, debug: bool) -> None:
    if debug:
        qml_path = Path(__file__).resolve().parent / "qml" / "App.qml"
        engine.load(qml_path)
        return

    try:
        from src.resources import qml_resources  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "QML resource module is missing. Run `python scripts/compile.py` "
            "or set DEBUG=True to use local QML files."
        ) from exc

    engine.load(QUrl("qrc:/qml/App.qml"))


def main(*, debug: bool = DEBUG) -> None:
    app = QGuiApplication(sys.argv)


    engine = QQmlApplicationEngine()

    # image provider (must be added before loading QML)
    image_provider = ThumbnailImageProvider()
    engine.addImageProvider("thumbnail", image_provider)

    # services -> QML context properties
    home_service = HomeService(image_provider)
    engine.rootContext().setContextProperty("homeService", home_service)

    processing_service = ProcessingService(image_provider)
    engine.rootContext().setContextProperty("processingService", processing_service)

    load_main_qml(engine, debug=debug)
    app.setApplicationName("NeatReel")
    app.setApplicationDisplayName("净影连")
    app.setWindowIcon(resolve_window_icon(debug)) # 图标设在load_main_qml之后，不然读不出来

    if not engine.rootObjects():
        sys.exit(-1)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
