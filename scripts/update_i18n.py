from __future__ import annotations

import argparse
import ast
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from os.path import relpath
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET


PROJECT_ROOT = Path(__file__).resolve().parents[1]
QML_DIR = PROJECT_ROOT / "qml"
SRC_DIR = PROJECT_ROOT / "src"
I18N_DIR = QML_DIR / "i18n"
DEFAULT_TS_FILES = (
    I18N_DIR / "VideoMerger_zh_CN.ts",
    I18N_DIR / "VideoMerger_en_US.ts",
)
PYTHON_SOURCE_ROOTS = (
    PROJECT_ROOT / "NeatReel.py",
    SRC_DIR,
)
@dataclass(frozen=True, order=True)
class MessageLocation:
    file_path: Path
    line: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract translatable text from the project and incrementally update "
            "existing TS files without deleting finished translations."
        )
    )
    parser.add_argument(
        "--ts",
        nargs="+",
        type=Path,
        default=list(DEFAULT_TS_FILES),
        help="Target TS files to update. Defaults to qml/i18n/*.ts used by the project.",
    )
    parser.add_argument(
        "--qml-dir",
        type=Path,
        default=QML_DIR,
        help="Directory containing QML files to extract with lupdate.",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=PROJECT_ROOT,
        help="Project root used for relative paths and command execution.",
    )
    parser.add_argument(
        "--silent",
        action="store_true",
        help="Suppress lupdate output.",
    )
    return parser.parse_args()


def find_lupdate_command(project_root: Path) -> list[str]:
    candidates = [
        Path(sys.executable).resolve().parent / "pyside6-lupdate.exe",
        Path(sys.executable).resolve().parent / "pyside6-lupdate",
        project_root / ".venv" / "Scripts" / "pyside6-lupdate.exe",
        project_root / ".venv" / "bin" / "pyside6-lupdate",
    ]

    for candidate in candidates:
        if candidate.exists():
            return [str(candidate)]

    for executable_name in ("pyside6-lupdate", "lupdate"):
        executable = shutil.which(executable_name)
        if executable:
            return [executable]

    return [sys.executable, "-m", "PySide6.scripts.pyside_tool", "lupdate"]


def iter_qml_files(qml_dir: Path) -> list[Path]:
    return sorted(path for path in qml_dir.rglob("*.qml") if path.is_file())


def iter_python_files() -> list[Path]:
    files: list[Path] = []
    for root in PYTHON_SOURCE_ROOTS:
        if root.is_file():
            files.append(root)
        elif root.is_dir():
            files.extend(sorted(path for path in root.rglob("*.py") if path.is_file()))
    return files


def run_lupdate_for_qml(
    *,
    project_root: Path,
    qml_dir: Path,
    ts_files: list[Path],
    silent: bool,
) -> None:
    qml_files = iter_qml_files(qml_dir)
    if not qml_files:
        raise FileNotFoundError(f"No QML files found under: {qml_dir}")

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".lst",
        delete=False,
    ) as handle:
        for path in qml_files:
            handle.write(f"{path}\n")
        lst_file = Path(handle.name)

    try:
        command = [
            *find_lupdate_command(project_root),
            f"@{lst_file}",
            "-extensions",
            "qml",
            "-locations",
            "relative",
        ]
        if silent:
            command.append("-silent")
        command.extend(["-ts", *(str(path) for path in ts_files)])
        subprocess.run(command, cwd=project_root, check=True)
    finally:
        lst_file.unlink(missing_ok=True)


class PythonTranslationExtractor(ast.NodeVisitor):
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.helper_contexts: dict[str, str] = {}
        self.messages: dict[tuple[str, str], set[MessageLocation]] = defaultdict(set)

    def extract(self) -> dict[tuple[str, str], set[MessageLocation]]:
        tree = ast.parse(self.file_path.read_text(encoding="utf-8"), filename=str(self.file_path))
        self.visit(tree)
        return self.messages

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        context_name = self._extract_helper_context(node)
        if context_name:
            self.helper_contexts[node.name] = context_name
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        context_name = self._extract_helper_context(node)
        if context_name:
            self.helper_contexts[node.name] = context_name
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        helper_context = self._resolve_helper_context(node)
        if helper_context:
            source_text = self._extract_string_argument(node, 0)
            if source_text is not None:
                self._add_message(helper_context, source_text, node.lineno)
        else:
            direct_context, source_text = self._extract_direct_translate_call(node)
            if direct_context and source_text is not None:
                self._add_message(direct_context, source_text, node.lineno)

        self.generic_visit(node)

    def _add_message(self, context_name: str, source_text: str, line: int) -> None:
        if not context_name or not source_text:
            return
        self.messages[(context_name, source_text)].add(
            MessageLocation(self.file_path, int(line))
        )

    def _resolve_helper_context(self, node: ast.Call) -> str | None:
        if isinstance(node.func, ast.Name):
            return self.helper_contexts.get(node.func.id)
        return None

    def _extract_string_argument(self, node: ast.Call, index: int) -> str | None:
        if len(node.args) <= index:
            return None
        return self._string_literal(node.args[index])

    def _extract_direct_translate_call(self, node: ast.Call) -> tuple[str | None, str | None]:
        func = node.func
        if isinstance(func, ast.Attribute):
            if func.attr != "translate":
                return None, None
        elif isinstance(func, ast.Name):
            if func.id != "translate":
                return None, None
        else:
            return None, None

        if len(node.args) < 2:
            return None, None

        context_name = self._string_literal(node.args[0])
        source_text = self._string_literal(node.args[1])
        return context_name, source_text

    def _extract_helper_context(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> str | None:
        arg_names = [arg.arg for arg in node.args.posonlyargs + node.args.args]
        if not arg_names:
            return None
        text_arg_name = arg_names[0]

        for statement in node.body:
            if isinstance(statement, ast.Return):
                return self._extract_context_from_return(statement.value, text_arg_name)
        return None

    def _extract_context_from_return(self, value: ast.AST | None, text_arg_name: str) -> str | None:
        if not isinstance(value, ast.Call):
            return None

        func = value.func
        if isinstance(func, ast.Attribute):
            if func.attr != "translate":
                return None
        elif isinstance(func, ast.Name):
            if func.id != "translate":
                return None
        else:
            return None

        if len(value.args) < 2:
            return None

        context_name = self._string_literal(value.args[0])
        text_arg = value.args[1]
        if not isinstance(text_arg, ast.Name) or text_arg.id != text_arg_name:
            return None
        return context_name

    @staticmethod
    def _string_literal(node: ast.AST) -> str | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        return None


def collect_python_messages() -> dict[str, dict[str, set[MessageLocation]]]:
    catalog: dict[str, dict[str, set[MessageLocation]]] = defaultdict(lambda: defaultdict(set))

    for file_path in iter_python_files():
        extractor = PythonTranslationExtractor(file_path)
        for (context_name, source_text), locations in extractor.extract().items():
            catalog[context_name][source_text].update(locations)

    return catalog


def relative_location(file_path: Path, ts_file: Path) -> str:
    return Path(relpath(file_path, ts_file.parent)).as_posix()


def ensure_context(root: ET.Element, context_name: str) -> ET.Element:
    for context in root.findall("context"):
        name = context.find("name")
        if name is not None and name.text == context_name:
            return context

    context = ET.SubElement(root, "context")
    name = ET.SubElement(context, "name")
    name.text = context_name
    return context


def find_message(context: ET.Element, source_text: str) -> ET.Element | None:
    for message in context.findall("message"):
        source = message.find("source")
        if source is not None and source.text == source_text:
            return message
    return None


def ensure_translation_element(message: ET.Element) -> tuple[ET.Element, bool]:
    translation = message.find("translation")
    changed = False
    if translation is None:
        translation = ET.SubElement(message, "translation")
        translation.set("type", "unfinished")
        changed = True
    elif translation.get("type") in {"obsolete", "vanished"}:
        del translation.attrib["type"]
        changed = True
    elif not (translation.text or "").strip() and "type" not in translation.attrib:
        translation.set("type", "unfinished")
        changed = True
    return translation, changed


def update_message_locations(
    *,
    message: ET.Element,
    locations: Iterable[MessageLocation],
    ts_file: Path,
) -> bool:
    desired = [
        (relative_location(location.file_path, ts_file), str(location.line))
        for location in sorted(locations)
    ]
    existing = [
        (location.get("filename", ""), location.get("line", ""))
        for location in message.findall("location")
    ]
    if existing == desired:
        return False

    for location in list(message.findall("location")):
        message.remove(location)

    source_index = next(
        (index for index, child in enumerate(list(message)) if child.tag == "source"),
        0,
    )
    for offset, (filename, line) in enumerate(desired):
        location = ET.Element("location")
        location.set("filename", filename)
        location.set("line", line)
        message.insert(source_index + offset, location)
    return True


def upsert_python_messages(ts_file: Path, catalog: dict[str, dict[str, set[MessageLocation]]]) -> bool:
    if not ts_file.exists():
        raise FileNotFoundError(f"TS file not found: {ts_file}")

    tree = ET.parse(ts_file)
    root = tree.getroot()
    changed = False

    for context_name in sorted(catalog):
        context = ensure_context(root, context_name)
        context_changed = False

        for source_text in sorted(catalog[context_name]):
            message = find_message(context, source_text)
            if message is None:
                message = ET.SubElement(context, "message")
                for location in sorted(catalog[context_name][source_text]):
                    location_element = ET.SubElement(message, "location")
                    location_element.set("filename", relative_location(location.file_path, ts_file))
                    location_element.set("line", str(location.line))
                source = ET.SubElement(message, "source")
                source.text = source_text
                translation = ET.SubElement(message, "translation")
                translation.set("type", "unfinished")
                context_changed = True
                continue

            _, translation_changed = ensure_translation_element(message)
            if translation_changed:
                context_changed = True

            if update_message_locations(
                message=message,
                locations=catalog[context_name][source_text],
                ts_file=ts_file,
            ):
                context_changed = True

        changed = changed or context_changed

    if changed:
        ET.indent(tree, space="    ")
        xml_body = ET.tostring(root, encoding="unicode")
        ts_file.write_text(
            "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n<!DOCTYPE TS>\n" + xml_body + "\n",
            encoding="utf-8",
        )

    return changed


def validate_ts_files(ts_files: list[Path]) -> list[Path]:
    validated = [path.resolve() for path in ts_files]
    missing = [path for path in validated if not path.exists()]
    if missing:
        missing_text = ", ".join(str(path) for path in missing)
        raise FileNotFoundError(f"TS file(s) not found: {missing_text}")
    return validated


def main() -> None:
    args = parse_args()
    project_root = args.project_root.resolve()
    qml_dir = args.qml_dir.resolve()
    ts_files = validate_ts_files(args.ts)

    run_lupdate_for_qml(
        project_root=project_root,
        qml_dir=qml_dir,
        ts_files=ts_files,
        silent=args.silent,
    )

    python_catalog = collect_python_messages()
    touched_ts_files = []
    for ts_file in ts_files:
        changed = upsert_python_messages(ts_file, python_catalog)
        touched_ts_files.append((ts_file, changed))

    for ts_file, changed in touched_ts_files:
        status = "updated" if changed else "checked"
        print(f"{status}: {ts_file.relative_to(project_root)}")


if __name__ == "__main__":
    main()
