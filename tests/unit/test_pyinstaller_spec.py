from __future__ import annotations

from pathlib import Path
from typing import cast


def test_pyinstaller_spec_hidden_imports_include_required_modules() -> None:
    namespace: dict[str, object] = {}
    spec_path = Path("packaging/pyinstaller.spec")
    namespace["__file__"] = str(spec_path.resolve())
    exec(spec_path.read_text(encoding="utf-8"), namespace)
    hiddenimports = cast(list[str], namespace["HIDDEN_IMPORTS"])
    assert "watchdog" in hiddenimports
    assert "PySide6.QtWidgets" in hiddenimports
    assert "pypdf" in hiddenimports
