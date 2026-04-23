from __future__ import annotations

from pathlib import Path
from typing import cast


def _load_spec_namespace() -> dict[str, object]:
    namespace: dict[str, object] = {}
    spec_path = Path("packaging/pyinstaller.spec")
    namespace["__file__"] = str(spec_path.resolve())
    exec(spec_path.read_text(encoding="utf-8"), namespace)
    return namespace


def test_pyinstaller_spec_hidden_imports_include_required_modules() -> None:
    namespace = _load_spec_namespace()
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
    namespace = _load_spec_namespace()

    assert namespace["CLI_DIST_NAME"] == "eodinga-cli"
    assert namespace["GUI_DIST_NAME"] == "eodinga-gui"
    assert namespace["CLI_EXE_NAME"] == "eodinga-cli.exe"
    assert namespace["GUI_EXE_NAME"] == "eodinga-gui.exe"


def test_pyinstaller_runtime_modules_map_to_real_sources() -> None:
    namespace = _load_spec_namespace()
    runtime_modules = cast(list[str], namespace["RUNTIME_MODULES"])
    discovered_runtime_modules = cast(list[str], namespace["DISCOVERED_RUNTIME_MODULES"])

    for module_name in runtime_modules:
        module_path = Path(*module_name.split(".")).with_suffix(".py")
        assert module_path.exists(), module_name

    for module_name in discovered_runtime_modules:
        module_path = Path(*module_name.split("."))
        assert module_path.with_suffix(".py").exists() or (module_path / "__init__.py").exists(), module_name


def test_pyinstaller_hidden_import_discovery_supports_importlib_aliases(tmp_path: Path) -> None:
    namespace = _load_spec_namespace()
    source_root = tmp_path / "pkg"
    source_root.mkdir()
    (source_root / "dynamic.py").write_text(
        "\n".join(
            [
                "import importlib as importer",
                "from importlib import import_module as load_module",
                "",
                "importer.import_module('alpha.mod')",
                "load_module('beta.mod')",
                "__import__('gamma.mod')",
            ]
        ),
        encoding="utf-8",
    )

    discover_hidden_imports = cast(object, namespace["_discover_hidden_imports"])
    assert callable(discover_hidden_imports)
    discovered = discover_hidden_imports(source_root)

    assert discovered == ["alpha.mod", "beta.mod", "gamma.mod"]
