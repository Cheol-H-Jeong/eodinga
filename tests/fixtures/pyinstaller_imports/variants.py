from __future__ import annotations

import importlib
from importlib import import_module


def load_gui_widget() -> object:
    return import_module(".widgets.search_field", package="eodinga.gui")


def load_hotkey_backend() -> object:
    return importlib.import_module(".hotkey_win", package="eodinga.launcher")
