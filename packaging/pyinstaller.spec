from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENTRY_CLI = PROJECT_ROOT / "eodinga" / "__main__.py"
ENTRY_GUI = PROJECT_ROOT / "eodinga" / "__main__.py"
I18N_DIR = PROJECT_ROOT / "eodinga" / "i18n"
CLI_DIST_NAME = "eodinga-cli"
GUI_DIST_NAME = "eodinga-gui"
CLI_EXE_NAME = f"{CLI_DIST_NAME}.exe"
GUI_EXE_NAME = f"{GUI_DIST_NAME}.exe"
SOURCE_ROOT = PROJECT_ROOT / "eodinga"

RUNTIME_MODULES = [
    "eodinga.content.code",
    "eodinga.content.epub",
    "eodinga.content.html",
    "eodinga.content.hwp",
    "eodinga.content.office",
    "eodinga.content.pdf",
    "eodinga.content.registry",
    "eodinga.content.text",
    "eodinga.gui.app",
    "eodinga.gui.launcher",
    "eodinga.gui.tabs.about",
    "eodinga.gui.tabs.index",
    "eodinga.gui.tabs.roots",
    "eodinga.gui.tabs.search",
    "eodinga.gui.tabs.settings",
    "eodinga.gui.theme",
    "eodinga.gui.widgets.empty_state",
    "eodinga.gui.widgets.result_item",
    "eodinga.gui.widgets.search_field",
    "eodinga.gui.widgets.status_chip",
    "eodinga.launcher.hotkey",
    "eodinga.launcher.hotkey_linux",
    "eodinga.launcher.hotkey_win",
]

REQUIRED_HIDDEN_IMPORTS = [
    "PySide6",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "pynput.keyboard",
    "shiboken6",
    "Xlib.X",
    "Xlib.XK",
    "Xlib.display",
    "watchdog",
    "watchdog.events",
    "watchdog.observers",
    "watchdog.observers.inotify",
    "watchdog.observers.read_directory_changes",
    "pypdf",
    "pdfminer",
    "docx",
    "pptx",
    "openpyxl",
    "olefile",
    "selectolax",
    "ebooklib",
]


def _module_name_for_path(source_root: Path, source_path: Path) -> str:
    relative_path = source_path.relative_to(source_root.parent)
    if source_path.name == "__init__.py":
        return ".".join(relative_path.parts[:-1])
    return ".".join(relative_path.with_suffix("").parts)


def _package_name_for_path(source_root: Path, source_path: Path) -> str:
    module_name = _module_name_for_path(source_root, source_path)
    if source_path.name == "__init__.py":
        return module_name
    package_name, _, _ = module_name.rpartition(".")
    return package_name


def _module_exists(source_root: Path, module_name: str) -> bool:
    module_path = source_root.parent.joinpath(*module_name.split("."))
    return module_path.with_suffix(".py").exists() or (module_path / "__init__.py").exists()


def _resolve_from_import_module(source_root: Path, source_path: Path, node: ast.ImportFrom) -> str | None:
    if node.level == 0:
        return node.module

    current_package = _package_name_for_path(source_root, source_path)
    if not current_package:
        return None
    package_parts = current_package.split(".")
    if node.level > len(package_parts):
        return None
    anchor_parts = package_parts[: len(package_parts) - (node.level - 1)]
    if node.module:
        anchor_parts.extend(node.module.split("."))
    return ".".join(anchor_parts)


def _discover_hidden_imports(source_root: Path) -> list[str]:
    discovered: set[str] = set()
    for source_path in source_root.rglob("*.py"):
        module = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        for node in ast.walk(module):
            if isinstance(node, ast.Call):
                if not isinstance(node.func, ast.Name) or node.func.id != "import_module":
                    continue
                if not node.args or not isinstance(node.args[0], ast.Constant):
                    continue
                if not isinstance(node.args[0].value, str):
                    continue
                discovered.add(node.args[0].value)
                continue

            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == SOURCE_ROOT.name or alias.name.startswith(f"{SOURCE_ROOT.name}."):
                        discovered.add(alias.name)
                continue

            if not isinstance(node, ast.ImportFrom):
                continue
            module_name = _resolve_from_import_module(source_root, source_path, node)
            if module_name is None:
                continue
            if module_name == SOURCE_ROOT.name or module_name.startswith(f"{SOURCE_ROOT.name}."):
                discovered.add(module_name)
            for alias in node.names:
                if alias.name == "*":
                    continue
                imported_module_name = f"{module_name}.{alias.name}"
                if _module_exists(source_root, imported_module_name):
                    discovered.add(imported_module_name)
    return sorted(discovered)


DISCOVERED_HIDDEN_IMPORTS = _discover_hidden_imports(SOURCE_ROOT)

HIDDEN_IMPORTS = sorted(
    {
        *REQUIRED_HIDDEN_IMPORTS,
        *RUNTIME_MODULES,
        *DISCOVERED_HIDDEN_IMPORTS,
    }
)

DATAS = [
    (str(I18N_DIR / "en.json"), "eodinga/i18n"),
    (str(I18N_DIR / "ko.json"), "eodinga/i18n"),
    (str(PROJECT_ROOT / "LICENSE"), "."),
]

SPEC_AUDIT = {
    "cli_entry": str(ENTRY_CLI),
    "gui_entry": str(ENTRY_GUI),
    "cli_dist_name": CLI_DIST_NAME,
    "gui_dist_name": GUI_DIST_NAME,
    "cli_exe_name": CLI_EXE_NAME,
    "gui_exe_name": GUI_EXE_NAME,
    "hiddenimports": HIDDEN_IMPORTS,
    "datas": DATAS,
    "mode": "onedir",
}
