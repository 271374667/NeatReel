from __future__ import annotations

import threading

from PySide6.QtCore import QSize
from PySide6.QtGui import QImage
from PySide6.QtQuick import QQuickImageProvider


class ThumbnailImageProvider(QQuickImageProvider):
    """QML image://thumbnail/ provider, stores QImage by string id."""

    def __init__(self):
        super().__init__(QQuickImageProvider.ImageType.Image)
        self._images: dict[str, QImage] = {}
        self._lock = threading.Lock()

    def set_image(self, image_id: str, qimage: QImage) -> None:
        with self._lock:
            self._images[image_id] = qimage

    def requestImage(self, id: str, size: QSize, requestedSize: QSize) -> QImage:
        with self._lock:
            if id in self._images:
                return self._images[id]
        return QImage()
