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


def _string_literal(node: ast.expr | None) -> str | None:
    if not isinstance(node, ast.Constant):
        return None
    if not isinstance(node.value, str):
        return None
    return node.value


def _collect_import_aliases(module: ast.AST) -> tuple[set[str], set[str], set[str]]:
    importlib_aliases = {"importlib"}
    import_module_aliases = {"import_module"}
    builtin_import_aliases = {"__import__"}
    for node in ast.walk(module):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "importlib":
                    importlib_aliases.add(alias.asname or alias.name)
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.module == "importlib":
            for alias in node.names:
                if alias.name == "import_module":
                    import_module_aliases.add(alias.asname or alias.name)
        if node.module == "builtins":
            for alias in node.names:
                if alias.name == "__import__":
                    builtin_import_aliases.add(alias.asname or alias.name)
    return importlib_aliases, import_module_aliases, builtin_import_aliases


def _dynamic_import_name(
    node: ast.Call,
    *,
    importlib_aliases: set[str],
    import_module_aliases: set[str],
    builtin_import_aliases: set[str],
) -> str | None:
    function = node.func
    if isinstance(function, ast.Name):
        if function.id in import_module_aliases | builtin_import_aliases:
            return _string_literal(node.args[0] if node.args else None)
        return None
    if not isinstance(function, ast.Attribute):
        return None
    if function.attr != "import_module":
        return None
    if not isinstance(function.value, ast.Name):
        return None
    if function.value.id not in importlib_aliases:
        return None
    return _string_literal(node.args[0] if node.args else None)


def _discover_hidden_imports(source_root: Path) -> list[str]:
    discovered: set[str] = set()
    for source_path in source_root.rglob("*.py"):
        module = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        importlib_aliases, import_module_aliases, builtin_import_aliases = _collect_import_aliases(module)
        for node in ast.walk(module):
            if not isinstance(node, ast.Call):
                continue
            import_name = _dynamic_import_name(
                node,
                importlib_aliases=importlib_aliases,
                import_module_aliases=import_module_aliases,
                builtin_import_aliases=builtin_import_aliases,
            )
            if import_name is None:
                continue
            discovered.add(import_name)
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
