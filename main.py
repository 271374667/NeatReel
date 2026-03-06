import sys
from pathlib import Path

from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from src.service.home_service import HomeService
from src.service.image_provider import ThumbnailImageProvider
from src.service.processing_service import ProcessingService


def main() -> None:
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

    qml_path = Path(__file__).parent / "qml" / "App.qml"
    engine.load(qml_path)

    if not engine.rootObjects():
        sys.exit(-1)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
