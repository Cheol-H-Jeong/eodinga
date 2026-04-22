from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENTRY_CLI = PROJECT_ROOT / "eodinga" / "__main__.py"
ENTRY_GUI = PROJECT_ROOT / "eodinga" / "__main__.py"

HIDDEN_IMPORTS = [
    "PySide6",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "watchdog",
    "watchdog.events",
    "watchdog.observers",
    "pypdf",
    "pdfminer",
    "docx",
    "pptx",
    "openpyxl",
    "olefile",
    "selectolax",
    "ebooklib",
]

SPEC_AUDIT = {
    "cli_entry": str(ENTRY_CLI),
    "gui_entry": str(ENTRY_GUI),
    "hiddenimports": HIDDEN_IMPORTS,
    "mode": "onedir",
}

