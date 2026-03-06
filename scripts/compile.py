from __future__ import annotations

import shutil
import subprocess
import sys
from os.path import relpath
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
QML_DIR = PROJECT_ROOT / "qml"
RESOURCE_DIR = PROJECT_ROOT / "src" / "resources"
QRC_FILE = RESOURCE_DIR / "qml_resources.qrc"
PY_RESOURCE_FILE = RESOURCE_DIR / "qml_resources.py"
QRC_PREFIX = "/qml"


def iter_qml_files() -> list[Path]:
    return sorted(path for path in QML_DIR.rglob("*") if path.is_file())


def build_qrc_content(files: list[Path]) -> str:
    lines = ["<RCC>", f'  <qresource prefix="{QRC_PREFIX}">']

    for path in files:
        alias = path.relative_to(QML_DIR).as_posix()
        source = Path(relpath(path, RESOURCE_DIR)).as_posix()
        lines.append(f'    <file alias="{alias}">{source}</file>')

    lines.extend(["  </qresource>", "</RCC>", ""])
    return "\n".join(lines)


def find_rcc_command() -> list[str]:
    candidates = [
        Path(sys.executable).resolve().parent / "pyside6-rcc.exe",
        PROJECT_ROOT / ".venv" / "Scripts" / "pyside6-rcc.exe",
    ]

    for candidate in candidates:
        if candidate.exists():
            return [str(candidate)]

    executable = shutil.which("pyside6-rcc")
    if executable:
        return [executable]

    return [sys.executable, "-m", "PySide6.scripts.pyside_tool", "rcc"]


def compile_resources() -> None:
    if not QML_DIR.exists():
        raise FileNotFoundError(f"QML directory not found: {QML_DIR}")

    RESOURCE_DIR.mkdir(parents=True, exist_ok=True)

    files = iter_qml_files()
    if not files:
        raise RuntimeError(f"No files found under {QML_DIR}")

    QRC_FILE.write_text(build_qrc_content(files), encoding="utf-8")

    command = [*find_rcc_command(), str(QRC_FILE), "-o", str(PY_RESOURCE_FILE)]
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)

    print(f"Generated: {QRC_FILE.relative_to(PROJECT_ROOT)}")
    print(f"Generated: {PY_RESOURCE_FILE.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    compile_resources()
