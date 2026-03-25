from __future__ import annotations

import shutil
import subprocess
import sys
from os.path import relpath
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
QML_DIR = PROJECT_ROOT / "qml"
I18N_DIR = QML_DIR / "i18n"
RESOURCE_DIR = PROJECT_ROOT / "src" / "resources"
QRC_FILE = RESOURCE_DIR / "qml_resources.qrc"
RCC_RESOURCE_FILE = RESOURCE_DIR / "qml_resources.rcc"
PY_RESOURCE_FILE = RESOURCE_DIR / "qml_resources.py"
QRC_PREFIX = "/qml"
RESOURCE_EXCLUDED_SUFFIXES = {".ts", ".pro"}
REQUIRED_RESOURCE_FILES = [
    QML_DIR / "Fonts" / "SourceHanSansSC-Regular.otf",
    QML_DIR / "Fonts" / "SourceHanSansSC-Medium.otf",
    QML_DIR / "Fonts" / "SourceHanSansSC-Bold.otf",
]


def iter_resource_files() -> list[Path]:
    return sorted(
        path
        for path in QML_DIR.rglob("*")
        if path.is_file() and path.suffix not in RESOURCE_EXCLUDED_SUFFIXES
    )


def build_qrc_content(files: list[Path]) -> str:
    lines = ["<RCC>", f'  <qresource prefix="{QRC_PREFIX}">']

    for path in files:
        alias = path.relative_to(QML_DIR).as_posix()
        source = Path(relpath(path, RESOURCE_DIR)).as_posix()
        lines.append(f'    <file alias="{alias}">{source}</file>')

    lines.extend(["  </qresource>", "</RCC>", ""])
    return "\n".join(lines)


def validate_required_resources(files: list[Path]) -> None:
    missing_files = [path for path in REQUIRED_RESOURCE_FILES if path not in files]
    if missing_files:
        missing_list = ", ".join(path.relative_to(PROJECT_ROOT).as_posix() for path in missing_files)
        raise FileNotFoundError(f"Missing required resource files: {missing_list}")


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


def find_lrelease_command() -> list[str]:
    candidates = [
        Path(sys.executable).resolve().parent / "pyside6-lrelease.exe",
        PROJECT_ROOT / ".venv" / "Scripts" / "pyside6-lrelease.exe",
    ]

    for candidate in candidates:
        if candidate.exists():
            return [str(candidate)]

    for executable_name in ("pyside6-lrelease", "lrelease"):
        executable = shutil.which(executable_name)
        if executable:
            return [executable]

    return [sys.executable, "-m", "PySide6.scripts.pyside_tool", "lrelease"]


def compile_translations() -> list[Path]:
    if not I18N_DIR.exists():
        return []

    ts_files = sorted(I18N_DIR.glob("*.ts"))
    if not ts_files:
        return []

    lrelease_command = find_lrelease_command()
    generated_files: list[Path] = []

    for ts_file in ts_files:
        qm_file = ts_file.with_suffix(".qm")
        command = [*lrelease_command, str(ts_file), "-qm", str(qm_file)]
        subprocess.run(command, cwd=PROJECT_ROOT, check=True)
        generated_files.append(qm_file)

    return generated_files


def compile_resources() -> None:
    if not QML_DIR.exists():
        raise FileNotFoundError(f"QML directory not found: {QML_DIR}")

    RESOURCE_DIR.mkdir(parents=True, exist_ok=True)
    generated_translations = compile_translations()

    files = iter_resource_files()
    if not files:
        raise RuntimeError(f"No files found under {QML_DIR}")
    validate_required_resources(files)

    QRC_FILE.write_text(build_qrc_content(files), encoding="utf-8")

    command = [*find_rcc_command(), "--binary", str(QRC_FILE), "-o", str(RCC_RESOURCE_FILE)]
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)
    if PY_RESOURCE_FILE.exists():
        try:
            PY_RESOURCE_FILE.unlink()
        except OSError as exc:
            print(f"Warning: failed to remove stale resource module {PY_RESOURCE_FILE.name}: {exc}")

    print(f"Generated: {QRC_FILE.relative_to(PROJECT_ROOT)}")
    print(f"Generated: {RCC_RESOURCE_FILE.relative_to(PROJECT_ROOT)}")
    for qm_file in generated_translations:
        print(f"Compiled translation: {qm_file.relative_to(PROJECT_ROOT)}")
    for font_file in REQUIRED_RESOURCE_FILES:
        print(f"Embedded resource: {font_file.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    compile_resources()
