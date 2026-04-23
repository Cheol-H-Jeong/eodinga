from __future__ import annotations

import ast
import importlib.util
import sys
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
        import_module_aliases = {"import_module"}
        importlib_module_aliases = {"importlib"}
        for node in ast.walk(module):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "importlib":
                        importlib_module_aliases.add(alias.asname or alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module == "importlib":
                for alias in node.names:
                    if alias.name == "import_module":
                        import_module_aliases.add(alias.asname or alias.name)
        for node in ast.walk(module):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                if node.func.id not in import_module_aliases and node.func.id != "__import__":
                    continue
            elif isinstance(node.func, ast.Attribute):
                if node.func.attr != "import_module":
                    continue
                base = node.func.value
                if not isinstance(base, ast.Name) or base.id not in importlib_module_aliases:
                    continue
            else:
                continue
            if not node.args or not isinstance(node.args[0], ast.Constant):
                continue
            if not isinstance(node.args[0].value, str):
                continue
            discovered.add(node.args[0].value)
    return sorted(discovered)


def _is_stdlib_module(module_name: str) -> bool:
    root_name = module_name.split(".", 1)[0]
    return root_name in sys.stdlib_module_names


def _discover_datas(project_root: Path) -> list[tuple[str, str]]:
    datas = [(str(path), "eodinga/i18n") for path in sorted(I18N_DIR.glob("*.json"))]
    datas.append((str(project_root / "LICENSE"), "."))
    return datas


def _discover_source_hidden_imports(source_root: Path) -> list[str]:
    discovered: set[str] = set()
    for source_path in source_root.rglob("*.py"):
        module_name = _module_name_for_path(source_path, source_root)
        current_package = module_name if source_path.name == "__init__.py" else module_name.rpartition(".")[0]
        module = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        for node in ast.walk(module):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name
                    if module_name.startswith("eodinga.") or _is_stdlib_module(module_name):
                        continue
                    discovered.add(module_name)
            elif isinstance(node, ast.ImportFrom):
                module_name = _resolve_imported_module(node.module, node.level, current_package)
                if not module_name or module_name.startswith("eodinga") or _is_stdlib_module(module_name):
                    continue
                discovered.add(module_name)
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    candidate = f"{module_name}.{alias.name}"
                    try:
                        spec = importlib.util.find_spec(candidate)
                    except (AttributeError, ModuleNotFoundError, ValueError):
                        spec = None
                    if spec is not None:
                        discovered.add(candidate)
    return sorted(discovered)


DISCOVERED_RUNTIME_MODULES = _discover_runtime_modules(SOURCE_ROOT)
DISCOVERED_HIDDEN_IMPORTS = _discover_hidden_imports(SOURCE_ROOT)
DISCOVERED_SOURCE_HIDDEN_IMPORTS = _discover_source_hidden_imports(SOURCE_ROOT)

HIDDEN_IMPORTS = sorted(
    {
        *REQUIRED_HIDDEN_IMPORTS,
        *RUNTIME_MODULES,
        *DISCOVERED_RUNTIME_MODULES,
        *DISCOVERED_HIDDEN_IMPORTS,
        *DISCOVERED_SOURCE_HIDDEN_IMPORTS,
    }
)

DATAS = _discover_datas(PROJECT_ROOT)

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
