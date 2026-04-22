from __future__ import annotations

import ast
from pathlib import Path
from typing import cast


def test_pyinstaller_spec_hidden_imports_include_required_modules() -> None:
    namespace: dict[str, object] = {}
    spec_path = Path("packaging/pyinstaller.spec")
    namespace["__file__"] = str(spec_path.resolve())
    exec(spec_path.read_text(encoding="utf-8"), namespace)
    hiddenimports = cast(list[str], namespace["HIDDEN_IMPORTS"])
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
    assert discovered_hiddenimports == [
        "Xlib.X",
        "Xlib.XK",
        "Xlib.display",
        "pynput.keyboard",
    ]
    assert set(required_hiddenimports).issubset(set(hiddenimports))
    assert set(runtime_modules).issubset(set(hiddenimports))
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

    for module_name in runtime_modules:
        module_path = Path(*module_name.split(".")).with_suffix(".py")
        assert module_path.exists(), module_name


def test_pyinstaller_spec_discovers_importlib_import_module_variants() -> None:
    namespace: dict[str, object] = {}
    spec_path = Path("packaging/pyinstaller.spec")
    namespace["__file__"] = str(spec_path.resolve())
    exec(spec_path.read_text(encoding="utf-8"), namespace)

    discover_hidden_imports = cast(object, namespace["_discover_hidden_imports"])
    source_root = Path("tests/fixtures/pyinstaller_imports")
    discovered = cast(list[str], discover_hidden_imports(source_root))

    assert discovered == [
        "eodinga.gui.widgets.search_field",
        "eodinga.launcher.hotkey_win",
    ]


def test_pyinstaller_spec_resolves_relative_import_targets() -> None:
    namespace: dict[str, object] = {}
    spec_path = Path("packaging/pyinstaller.spec")
    namespace["__file__"] = str(spec_path.resolve())
    exec(spec_path.read_text(encoding="utf-8"), namespace)

    resolve_import_target = cast(object, namespace["_resolve_import_target"])
    relative_call = ast.parse(
        'importlib.import_module(".hotkey_win", package="eodinga.launcher")',
        mode="eval",
    ).body
    package_call = ast.parse(
        'import_module(".widgets.search_field", package="eodinga.gui")',
        mode="eval",
    ).body

    assert cast(str, resolve_import_target(relative_call)) == "eodinga.launcher.hotkey_win"
    assert cast(str, resolve_import_target(package_call)) == "eodinga.gui.widgets.search_field"
