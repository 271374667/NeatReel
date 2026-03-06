from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUILD_ROOT = PROJECT_ROOT / "build" / "nuitka"
DIST_DIR = BUILD_ROOT / "NeatReel.dist"
COMPILE_SCRIPT = PROJECT_ROOT / "scripts" / "compile.py"
LAUNCHER_FILE = BUILD_ROOT / "_release_main.py"
RESOURCE_DIR = PROJECT_ROOT / "src" / "resources"
RESOURCE_FILES = [
    RESOURCE_DIR / "qml_resources.py",
    RESOURCE_DIR / "qml_resources.qrc",
]


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


def run_nuitka_build() -> None:
    launcher_file = write_release_launcher()
    command = [
        sys.executable,
        "-m",
        "nuitka",
        "--mode=standalone",
        "--enable-plugin=pyside6",
        "--include-qt-plugins=qml",
        "--include-module=src.resources.qml_resources",
        "--windows-console-mode=disable",
        "--assume-yes-for-downloads",
        f"--output-dir={BUILD_ROOT}",
        "--output-filename=NeatReel",
        "--remove-output",
        str(launcher_file),
    ]
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def copy_resource_files() -> None:
    target_dir = DIST_DIR / "resources"
    target_dir.mkdir(parents=True, exist_ok=True)

    for resource_file in RESOURCE_FILES:
        if not resource_file.exists():
            raise FileNotFoundError(
                f"Expected resource file was not generated: {resource_file}"
            )

        shutil.copy2(resource_file, target_dir / resource_file.name)


def main() -> None:
    run_compile_resources()
    run_nuitka_build()
    copy_resource_files()
    print(f"Nuitka build output: {DIST_DIR}")


if __name__ == "__main__":
    main()
