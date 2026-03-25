from __future__ import annotations

import argparse
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = PROJECT_ROOT / "src" / "core" / "version.py"
PYPROJECT_FILE = PROJECT_ROOT / "pyproject.toml"
PYINSTALLER_BUILD_DIR = PROJECT_ROOT / "build" / "pyinstaller"
PYINSTALLER_VERSION_FILE = PYINSTALLER_BUILD_DIR / "version_info.txt"

VERSION_ASSIGNMENT_PATTERN = re.compile(r'(__version__\s*=\s*")([^"]+)(")')
VERSION_INPUT_PATTERN = re.compile(r"^[vV]?(\d+)\.(\d+)\.(\d+)(?:\.(\d+))?$")

FILE_DESCRIPTION = "去黑边，正朝向，一键拼出好影像"
PRODUCT_NAME = "NeatReel"
AUTHOR = "PythonImporter"
VERSION = "1.32.7"


def parse_version(raw_version: str) -> tuple[str, tuple[int, int, int, int], str]:
    match = VERSION_INPUT_PATTERN.fullmatch(raw_version.strip())
    if not match:
        raise ValueError(
            "版本号格式无效，应为 X.Y.Z、vX.Y.Z、X.Y.Z.W 或 vX.Y.Z.W。"
        )

    raw_parts = [part for part in match.groups() if part is not None]
    numeric_parts = [int(part) for part in raw_parts]
    source_version = f"v{'.'.join(raw_parts)}"
    windows_tuple = tuple(numeric_parts + [0] * (4 - len(numeric_parts)))
    windows_string = ".".join(raw_parts)
    return source_version, windows_tuple, windows_string


def write_source_version(source_version: str) -> None:
    content = VERSION_FILE.read_text(encoding="utf-8")
    updated_content, count = VERSION_ASSIGNMENT_PATTERN.subn(
        rf'\1{source_version}\3',
        content,
        count=1,
    )
    if count != 1:
        raise RuntimeError(f"更新 {VERSION_FILE} 版本号失败。")
    VERSION_FILE.write_text(updated_content, encoding="utf-8")


def write_pyproject_version(project_version: str) -> None:
    lines = PYPROJECT_FILE.read_text(encoding="utf-8").splitlines(keepends=True)
    in_project_section = False
    replaced = False

    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_project_section = stripped == "[project]"
            continue
        if in_project_section and stripped.startswith("version"):
            line_ending = "\r\n" if line.endswith("\r\n") else "\n"
            lines[index] = f'version = "{project_version}"{line_ending}'
            replaced = True
            break

    if not replaced:
        raise RuntimeError(f"更新 {PYPROJECT_FILE} 的 [project].version 失败。")

    PYPROJECT_FILE.write_text("".join(lines), encoding="utf-8")


def build_pyinstaller_version_content(
    windows_version_tuple: tuple[int, int, int, int],
    windows_version_string: str,
) -> str:
    filevers = ", ".join(str(part) for part in windows_version_tuple)
    return f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({filevers}),
    prodvers=({filevers}),
    mask=0x3F,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          '080404B0',
          [
            StringStruct('CompanyName', '{AUTHOR}'),
            StringStruct('FileDescription', '{FILE_DESCRIPTION}'),
            StringStruct('FileVersion', '{windows_version_string}'),
            StringStruct('InternalName', '{PRODUCT_NAME}'),
            StringStruct('OriginalFilename', '{PRODUCT_NAME}.exe'),
            StringStruct('ProductName', '{PRODUCT_NAME}'),
            StringStruct('ProductVersion', '{windows_version_string}'),
            StringStruct('LegalCopyright', '{AUTHOR}'),
            StringStruct('Comments', 'Author: {AUTHOR}')
          ]
        )
      ]
    ),
    VarFileInfo([VarStruct('Translation', [2052, 1200])])
  ]
)
"""


def write_pyinstaller_version_file(source_version: str) -> str:
    _, windows_version_tuple, windows_version_string = parse_version(source_version)
    PYINSTALLER_BUILD_DIR.mkdir(parents=True, exist_ok=True)
    PYINSTALLER_VERSION_FILE.write_text(
        build_pyinstaller_version_content(
            windows_version_tuple=windows_version_tuple,
            windows_version_string=windows_version_string,
        ),
        encoding="utf-8",
    )
    return windows_version_string


def sync_version_files(version: str | None = None) -> str:
    target_version = VERSION if version is None else version
    source_version, _, normalized_version = parse_version(target_version)

    write_source_version(source_version)
    write_pyproject_version(normalized_version)
    write_pyinstaller_version_file(source_version)
    return source_version


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="同步 src/core/version.py 与 PyInstaller 的 Windows 版本资源。"
    )
    parser.add_argument(
        "version",
        nargs="?",
        help=f'目标版本号，例如 v1.30.0 或 1.30.0。未传入时使用脚本内 VERSION={VERSION}。',
    )
    return parser


def main() -> None:
    args = build_argument_parser().parse_args()
    source_version = sync_version_files(args.version)
    _, windows_version_tuple, windows_version_string = parse_version(source_version)

    print(f"source version: {source_version}")
    print(f"windows version: {windows_version_string}")
    print(f"windows version tuple: {windows_version_tuple}")
    print(f"pyproject version: {windows_version_string}")
    print(f"version file: {PYINSTALLER_VERSION_FILE}")


if __name__ == "__main__":
    main()
