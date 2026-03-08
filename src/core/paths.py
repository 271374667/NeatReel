import sys
from pathlib import Path


def _resolve_project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


PROJECT_ROOT = _resolve_project_root()

# DIR
QML_DIR = PROJECT_ROOT / "qml"
OUTPUT_DIR = PROJECT_ROOT / "output"
IMAGES_DIR = PROJECT_ROOT / "qml" / "Images"

# FILE
LOGO_FILE = IMAGES_DIR / "SmallLogo.png"
