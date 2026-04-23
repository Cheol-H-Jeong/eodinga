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


def _module_name_for_path(source_path: Path, source_root: Path) -> str:
    relative = source_path.relative_to(source_root.parent)
    parts = list(relative.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = source_path.stem
    return ".".join(parts)


def _module_exists(module_name: str, project_root: Path) -> bool:
    module_path = project_root.joinpath(*module_name.split("."))
    return module_path.with_suffix(".py").exists() or (module_path / "__init__.py").exists()


def _resolve_imported_module(module_name: str | None, level: int, current_package: str) -> str | None:
    if level == 0:
        return module_name
    package_parts = current_package.split(".")
    if level > len(package_parts) + 1:
        return None
    anchor = package_parts[: len(package_parts) - level + 1]
    if module_name:
        anchor.append(module_name)
    return ".".join(anchor)


def _discover_runtime_modules(source_root: Path) -> list[str]:
    discovered: set[str] = set()
    for source_path in source_root.rglob("*.py"):
        module_name = _module_name_for_path(source_path, source_root)
        current_package = module_name if source_path.name == "__init__.py" else module_name.rpartition(".")[0]
        module = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        for node in ast.walk(module):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("eodinga.") and _module_exists(alias.name, PROJECT_ROOT):
                        discovered.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                resolved = _resolve_imported_module(node.module, node.level, current_package)
                if not resolved or not resolved.startswith("eodinga"):
                    continue
                if _module_exists(resolved, PROJECT_ROOT):
                    discovered.add(resolved)
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    candidate = f"{resolved}.{alias.name}"
                    if _module_exists(candidate, PROJECT_ROOT):
                        discovered.add(candidate)
    return sorted(discovered)


def _discover_hidden_imports(source_root: Path) -> list[str]:
    discovered: set[str] = set()
    for source_path in source_root.rglob("*.py"):
        module = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        function_aliases: set[str] = set()
        module_aliases: set[str] = set()
        for node in ast.walk(module):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "importlib":
                        module_aliases.add(alias.asname or alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module == "importlib":
                for alias in node.names:
                    if alias.name == "import_module":
                        function_aliases.add(alias.asname or alias.name)
        for node in ast.walk(module):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
                is_dynamic_import = func_name in function_aliases or func_name == "__import__"
            elif (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "import_module"
                and isinstance(node.func.value, ast.Name)
            ):
                is_dynamic_import = node.func.value.id in module_aliases
            else:
                is_dynamic_import = False
            if not is_dynamic_import:
                continue
            if not node.args or not isinstance(node.args[0], ast.Constant):
                continue
            if not isinstance(node.args[0].value, str):
                continue
            discovered.add(node.args[0].value)
    return sorted(discovered)


DISCOVERED_RUNTIME_MODULES = _discover_runtime_modules(SOURCE_ROOT)
DISCOVERED_HIDDEN_IMPORTS = _discover_hidden_imports(SOURCE_ROOT)

HIDDEN_IMPORTS = sorted(
    {
        *REQUIRED_HIDDEN_IMPORTS,
        *RUNTIME_MODULES,
        *DISCOVERED_RUNTIME_MODULES,
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
