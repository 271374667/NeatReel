from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUILD_ROOT = PROJECT_ROOT / "build" / "pyinstaller"
DIST_ROOT = PROJECT_ROOT / "dist"
DIST_DIR = DIST_ROOT / "NeatReel"
COMPILE_SCRIPT = PROJECT_ROOT / "scripts" / "compile.py"
LAUNCHER_FILE = BUILD_ROOT / "_release_main.py"
ICON_FILE = PROJECT_ROOT / "qml" / "Images" / "SmallLogo.png"
SPLASH_FILE = PROJECT_ROOT / "qml" / "Images" / "Splash.png"
RCC_RESOURCE_FILE = PROJECT_ROOT / "src" / "resources" / "qml_resources.rcc"
QT_QUICK_CONTROLS_CONF = PROJECT_ROOT / "qtquickcontrols2.conf"


def run_compile_resources() -> None:
    subprocess.run([sys.executable, str(COMPILE_SCRIPT)], cwd=PROJECT_ROOT, check=True)

 
def write_release_launcher() -> Path:
    BUILD_ROOT.mkdir(parents=True, exist_ok=True)
    LAUNCHER_FILE.write_text(
        "from NeatReel import main\n\n"
        "if __name__ == '__main__':\n"
        "    main(debug=False)\n",
        encoding="utf-8",
    )
    return LAUNCHER_FILE


def clean_previous_output() -> None:
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)


def format_add_data(source: Path, destination: str) -> str:
    separator = ";" if os.name == "nt" else ":"
    return f"{source}{separator}{destination}"


def run_pyinstaller_build() -> None:
    launcher_file = write_release_launcher()
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--windowed",
        "--name",
        "NeatReel",
        "--distpath",
        str(DIST_ROOT),
        "--workpath",
        str(BUILD_ROOT / "work"),
        "--specpath",
        str(BUILD_ROOT),
    ]
    if RCC_RESOURCE_FILE.exists():
        command.extend(["--add-data", format_add_data(RCC_RESOURCE_FILE, "src/resources")])
    if QT_QUICK_CONTROLS_CONF.exists():
        command.extend(["--add-data", format_add_data(QT_QUICK_CONTROLS_CONF, ".")])
    if ICON_FILE.exists():
        command.extend(["--icon", str(ICON_FILE)])
    if SPLASH_FILE.exists():
        command.extend(["--splash", str(SPLASH_FILE)])
    command.append(str(launcher_file))
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def main() -> None:
    run_compile_resources()
    clean_previous_output()
    run_pyinstaller_build()
    print(f"PyInstaller build output: {DIST_DIR}")


if __name__ == "__main__":
    main()
