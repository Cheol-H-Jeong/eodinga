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
    assert Path(cast(str, namespace["ENTRY_CLI"])).as_posix().endswith("packaging/windows/cli_entry.py")
    assert Path(cast(str, namespace["ENTRY_GUI"])).as_posix().endswith("packaging/windows/gui_entry.py")


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
                '__import__("package.gamma")',
                "",
            ]
        ),
        encoding="utf-8",
    )

    discovered = discover_hidden_imports(source_root)

    assert discovered == ["package.alpha", "package.beta", "package.gamma"]


def test_pyinstaller_spec_defines_dual_collect_targets_when_pyinstaller_globals_exist() -> None:
    spec_path = Path("packaging/pyinstaller.spec")
    calls: list[tuple[str, dict[str, object]]] = []

    class FakeAnalysis:
        def __init__(self, scripts, **kwargs) -> None:
            self.scripts = scripts
            self.kwargs = kwargs
            self.pure = [Path(scripts[0]).stem]
            self.binaries = [("binary", ".")]
            self.datas = kwargs["datas"]
            calls.append(("Analysis", {"scripts": scripts, **kwargs}))

    class FakePYZ:
        def __init__(self, pure) -> None:
            self.pure = pure
            calls.append(("PYZ", {"pure": pure}))

    class FakeEXE:
        def __init__(self, pyz, scripts, *extra, **kwargs) -> None:
            self.pyz = pyz
            self.scripts = scripts
            self.extra = extra
            self.kwargs = kwargs
            calls.append(("EXE", {"scripts": scripts, "extra": extra, **kwargs}))

    class FakeCOLLECT:
        def __init__(self, exe, binaries, datas, **kwargs) -> None:
            self.exe = exe
            self.binaries = binaries
            self.datas = datas
            self.kwargs = kwargs
            calls.append(("COLLECT", {"binaries": binaries, "datas": datas, **kwargs}))

    namespace: dict[str, object] = {
        "__file__": str(spec_path.resolve()),
        "Analysis": FakeAnalysis,
        "PYZ": FakePYZ,
        "EXE": FakeEXE,
        "COLLECT": FakeCOLLECT,
    }
    exec(spec_path.read_text(encoding="utf-8"), namespace)

    analysis_calls = [payload for name, payload in calls if name == "Analysis"]
    exe_calls = [payload for name, payload in calls if name == "EXE"]
    collect_calls = [payload for name, payload in calls if name == "COLLECT"]

    assert [Path(cast(list[str], payload["scripts"])[0]).name for payload in analysis_calls] == ["cli_entry.py", "gui_entry.py"]
    assert [cast(str, payload["name"]) for payload in exe_calls] == ["eodinga-cli", "eodinga-gui"]
    assert [cast(bool, payload["console"]) for payload in exe_calls] == [True, False]
    assert [cast(str, payload["name"]) for payload in collect_calls] == ["eodinga-cli", "eodinga-gui"]
