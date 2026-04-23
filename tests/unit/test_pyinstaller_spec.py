from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Callable
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


def test_pyinstaller_discovers_dynamic_import_aliases(tmp_path: Path) -> None:
    source_root = tmp_path / "src"
    source_root.mkdir()
    (source_root / "dynamic_aliases.py").write_text(
        textwrap.dedent(
            """
            import importlib as loader
            from builtins import __import__ as builtin_loader
            from importlib import import_module as load_module

            loader.import_module("pkg.alpha")
            load_module("pkg.beta")
            builtin_loader("pkg.gamma")
            """
        ),
        encoding="utf-8",
    )

    namespace: dict[str, object] = {}
    spec_path = Path("packaging/pyinstaller.spec")
    namespace["__file__"] = str(spec_path.resolve())
    exec(spec_path.read_text(encoding="utf-8"), namespace)
    discover_hidden_imports = cast(Callable[[Path], list[str]], namespace["_discover_hidden_imports"])

    assert discover_hidden_imports(source_root) == [
        "pkg.alpha",
        "pkg.beta",
        "pkg.gamma",
    ]
