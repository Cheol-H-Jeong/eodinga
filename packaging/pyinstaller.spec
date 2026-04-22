from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENTRY_CLI = PROJECT_ROOT / "eodinga" / "__main__.py"
ENTRY_GUI = PROJECT_ROOT / "eodinga" / "__main__.py"
I18N_DIR = PROJECT_ROOT / "eodinga" / "i18n"
CLI_DIST_NAME = "eodinga-cli"
GUI_DIST_NAME = "eodinga-gui"

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
    "shiboken6",
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

HIDDEN_IMPORTS = [
    *REQUIRED_HIDDEN_IMPORTS,
    *RUNTIME_MODULES,
]

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
    "hiddenimports": HIDDEN_IMPORTS,
    "datas": DATAS,
    "mode": "onedir",
}
