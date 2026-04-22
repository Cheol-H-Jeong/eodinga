from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

from eodinga.config import AppConfig, default_db_path

DEFAULT_EXCLUDES = [
    "/proc",
    "/sys",
    "/dev",
    "/snap",
    "/run",
    "/var/cache",
    "/var/lib/docker",
    "/tmp",
    "~/.cache",
    "~/.local/share/Trash",
    "~/snap",
    "C:\\Windows",
    "C:\\$Recycle.Bin",
    "%SystemRoot%",
]

REQUIRED_IMPORTS = {
    "pydantic": "pydantic",
    "loguru": "loguru",
}

OPTIONAL_IMPORTS = {
    "PySide6": "gui",
    "watchdog": "watcher",
    "pypdf": "pdf_parser",
}


def _is_importable(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _is_db_writable(db_path: Path) -> bool:
    parent = db_path.expanduser().parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    return os.access(parent, os.W_OK)


def _roots_readable(config: AppConfig) -> dict[str, bool]:
    return {
        str(root.path): root.path.expanduser().exists()
        and os.access(root.path.expanduser(), os.R_OK)
        for root in config.roots
    }


def _detect_hotkey_backend() -> str:
    if sys.platform.startswith("win"):
        return "registerhotkey"
    if os.environ.get("DISPLAY") and _is_importable("Xlib"):
        return "python-xlib"
    if _is_importable("evdev"):
        return "evdev"
    if _is_importable("pynput"):
        return "pynput"
    return "unavailable"


def run_diagnostics(config: AppConfig | None = None, db_path: Path | None = None) -> tuple[dict[str, Any], int]:
    effective_config = config or AppConfig()
    effective_db_path = db_path or effective_config.index.db_path or default_db_path()
    required = {name: _is_importable(module) for name, module in REQUIRED_IMPORTS.items()}
    optional = {name: _is_importable(module) for name, module in OPTIONAL_IMPORTS.items()}
    roots = _roots_readable(effective_config)
    result: dict[str, Any] = {
        "python": {
            "version": sys.version.split()[0],
            "supported": sys.version_info >= (3, 11),
        },
        "dependencies": {
            "required": required,
            "optional": optional,
        },
        "db": {
            "path": str(effective_db_path),
            "writable": _is_db_writable(effective_db_path),
        },
        "roots": roots,
        "hotkey_backend": _detect_hotkey_backend(),
        "default_excludes": {
            "effective": True,
            "entries": DEFAULT_EXCLUDES,
        },
    }
    exit_code = 0
    if not result["python"]["supported"] or not all(required.values()) or not result["db"]["writable"]:
        exit_code = 1
    if roots and not all(roots.values()):
        exit_code = 1
    return result, exit_code
