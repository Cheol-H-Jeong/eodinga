from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast


def test_pyinstaller_spec_hidden_imports_include_required_modules() -> None:
    namespace: dict[str, object] = {}
    spec_path = Path("packaging/pyinstaller.spec")
    namespace["__file__"] = str(spec_path.resolve())
    exec(spec_path.read_text(encoding="utf-8"), namespace)
    hiddenimports = cast(list[str], namespace["HIDDEN_IMPORTS"])
    discovered_runtime_modules = cast(list[str], namespace["DISCOVERED_RUNTIME_MODULES"])
    discovered_hiddenimports = cast(list[str], namespace["DISCOVERED_HIDDEN_IMPORTS"])
    required_hiddenimports = cast(list[str], namespace["REQUIRED_HIDDEN_IMPORTS"])
    runtime_modules = cast(list[str], namespace["RUNTIME_MODULES"])
    datas = cast(list[tuple[str, str]], namespace["DATAS"])
    assert "watchdog" in hiddenimports
    assert "watchdog.observers.inotify" in hiddenimports
    assert "watchdog.observers.read_directory_changes" in hiddenimports
    assert "PySide6.QtWidgets" in hiddenimports
    assert "shiboken6" in hiddenimports
    assert "pypdf" in hiddenimports
    assert "eodinga.gui.app" in hiddenimports
    assert "eodinga.content.registry" in hiddenimports
    assert "eodinga.launcher.hotkey_win" in hiddenimports
    assert "eodinga.gui.hotkey_controller" in discovered_runtime_modules
    assert "eodinga.gui.widgets" in discovered_runtime_modules
    assert "eodinga.index.storage" in discovered_runtime_modules
    assert discovered_hiddenimports == [
        "Xlib.X",
        "Xlib.XK",
        "Xlib.display",
        "pynput.keyboard",
    ]
    assert set(required_hiddenimports).issubset(set(hiddenimports))
    assert set(runtime_modules).issubset(set(hiddenimports))
    assert set(discovered_runtime_modules).issubset(set(hiddenimports))
    assert set(discovered_hiddenimports).issubset(set(hiddenimports))
    assert {"eodinga.launcher.hotkey_linux", "eodinga.launcher.hotkey_win"} <= set(runtime_modules)
    assert (str(Path("eodinga/i18n/en.json").resolve()), "eodinga/i18n") in datas
    assert (str(Path("eodinga/i18n/ko.json").resolve()), "eodinga/i18n") in datas


def test_pyinstaller_spec_exposes_expected_windows_dist_names() -> None:
    namespace: dict[str, object] = {}
    spec_path = Path("packaging/pyinstaller.spec")
    namespace["__file__"] = str(spec_path.resolve())
    exec(spec_path.read_text(encoding="utf-8"), namespace)

    assert namespace["CLI_DIST_NAME"] == "eodinga-cli"
    assert namespace["GUI_DIST_NAME"] == "eodinga-gui"
    assert namespace["CLI_EXE_NAME"] == "eodinga-cli.exe"
    assert namespace["GUI_EXE_NAME"] == "eodinga-gui.exe"


def test_pyinstaller_runtime_modules_map_to_real_sources() -> None:
    namespace: dict[str, object] = {}
    spec_path = Path("packaging/pyinstaller.spec")
    namespace["__file__"] = str(spec_path.resolve())
    exec(spec_path.read_text(encoding="utf-8"), namespace)
    runtime_modules = cast(list[str], namespace["RUNTIME_MODULES"])
    discovered_runtime_modules = cast(list[str], namespace["DISCOVERED_RUNTIME_MODULES"])

    for module_name in runtime_modules:
        module_path = Path(*module_name.split(".")).with_suffix(".py")
        assert module_path.exists(), module_name

    for module_name in discovered_runtime_modules:
        module_path = Path(*module_name.split("."))
        assert module_path.with_suffix(".py").exists() or (module_path / "__init__.py").exists(), module_name


def test_pyinstaller_spec_discovers_dynamic_hidden_import_patterns(tmp_path: Path) -> None:
    namespace: dict[str, object] = {}
    spec_path = Path("packaging/pyinstaller.spec")
    namespace["__file__"] = str(spec_path.resolve())
    exec(spec_path.read_text(encoding="utf-8"), namespace)
    discover_hidden_imports = cast(Callable[[Path], list[str]], namespace["_discover_hidden_imports"])

    source_root = tmp_path / "eodinga"
    source_root.mkdir()
    (source_root / "__init__.py").write_text("", encoding="utf-8")
    module_path = source_root / "dynamic_imports.py"
    module_path.write_text(
        "\n".join(
            [
                "import importlib as il",
                "from importlib import import_module as load_module",
                "",
                'il.import_module("package.alpha")',
                'load_module("package.beta")',
                'il.import_module(".gamma", package="package")',
                'load_module("..delta", package="package.nested")',
                '__import__("package.epsilon", fromlist=("zeta", "eta"))',
                "",
            ]
        ),
        encoding="utf-8",
    )

    discovered = discover_hidden_imports(source_root)

    assert discovered == [
        "package.alpha",
        "package.beta",
        "package.delta",
        "package.epsilon",
        "package.epsilon.eta",
        "package.epsilon.zeta",
        "package.gamma",
    ]


def test_pyinstaller_spec_source_hidden_imports_skip_internal_relative_modules(tmp_path: Path) -> None:
    namespace: dict[str, object] = {}
    spec_path = Path("packaging/pyinstaller.spec")
    namespace["__file__"] = str(spec_path.resolve())
    exec(spec_path.read_text(encoding="utf-8"), namespace)
    discover_source_hidden_imports = cast(Callable[[Path], list[str]], namespace["_discover_source_hidden_imports"])

    source_root = tmp_path / "eodinga"
    (source_root / "gui" / "tabs").mkdir(parents=True)
    (source_root / "gui" / "widgets").mkdir(parents=True)
    for path in (
        source_root / "__init__.py",
        source_root / "gui" / "__init__.py",
        source_root / "gui" / "tabs" / "__init__.py",
        source_root / "gui" / "widgets" / "__init__.py",
        source_root / "gui" / "widgets" / "button.py",
    ):
        path.write_text("", encoding="utf-8")
    (source_root / "gui" / "tabs" / "search.py").write_text(
        "\n".join(
            [
                "from ..widgets import button",
                "from PySide6 import QtCore",
                "from selectolax.parser import HTMLParser",
            ]
        ),
        encoding="utf-8",
    )

    discovered = discover_source_hidden_imports(source_root)

    assert "button" not in discovered
    assert "widgets" not in discovered
    assert "PySide6" in discovered
    assert "PySide6.QtCore" in discovered
    assert "selectolax.parser" in discovered
