from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast


def _exec_spec(namespace: dict[str, object] | None = None) -> dict[str, object]:
    scope: dict[str, object] = {} if namespace is None else dict(namespace)
    spec_path = Path("packaging/pyinstaller.spec")
    scope["__file__"] = str(spec_path.resolve())
    exec(spec_path.read_text(encoding="utf-8"), scope)
    return scope


def test_pyinstaller_spec_hidden_imports_include_required_modules() -> None:
    namespace = _exec_spec()
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
    namespace = _exec_spec()

    assert namespace["CLI_DIST_NAME"] == "eodinga-cli"
    assert namespace["GUI_DIST_NAME"] == "eodinga-gui"
    assert namespace["CLI_EXE_NAME"] == "eodinga-cli.exe"
    assert namespace["GUI_EXE_NAME"] == "eodinga-gui.exe"
    assert Path(cast(str, namespace["ENTRY_CLI"])).as_posix().endswith("eodinga/__main__.py")
    assert Path(cast(str, namespace["ENTRY_GUI"])).as_posix().endswith("packaging/windows/gui_entry.py")


def test_pyinstaller_runtime_modules_map_to_real_sources() -> None:
    namespace = _exec_spec()
    runtime_modules = cast(list[str], namespace["RUNTIME_MODULES"])
    discovered_runtime_modules = cast(list[str], namespace["DISCOVERED_RUNTIME_MODULES"])

    for module_name in runtime_modules:
        module_path = Path(*module_name.split(".")).with_suffix(".py")
        assert module_path.exists(), module_name

    for module_name in discovered_runtime_modules:
        module_path = Path(*module_name.split("."))
        assert module_path.with_suffix(".py").exists() or (module_path / "__init__.py").exists(), module_name


def test_pyinstaller_spec_discovers_dynamic_hidden_import_patterns(tmp_path: Path) -> None:
    namespace = _exec_spec()
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


def test_pyinstaller_spec_exposes_real_build_targets_when_pyinstaller_symbols_exist() -> None:
    class FakeAnalysis:
        def __init__(self, scripts: list[str], **kwargs: object) -> None:
            self.scripts = scripts
            self.kwargs = kwargs
            self.pure = [f"pure:{Path(scripts[0]).name}"]
            self.binaries = [f"bin:{Path(scripts[0]).name}"]
            self.datas = [f"data:{Path(scripts[0]).name}"]

    def fake_pyz(pure: list[str]) -> dict[str, object]:
        return {"pure": pure}

    def fake_exe(*args: object, **kwargs: object) -> dict[str, object]:
        return {"args": args, "kwargs": kwargs}

    def fake_collect(*args: object, **kwargs: object) -> dict[str, object]:
        return {"args": args, "kwargs": kwargs}

    namespace = _exec_spec(
        {
            "Analysis": FakeAnalysis,
            "PYZ": fake_pyz,
            "EXE": fake_exe,
            "COLLECT": fake_collect,
        }
    )

    cli_analysis = cast(FakeAnalysis, namespace["cli_analysis"])
    gui_analysis = cast(FakeAnalysis, namespace["gui_analysis"])
    cli_exe = cast(dict[str, object], namespace["cli_exe"])
    gui_exe = cast(dict[str, object], namespace["gui_exe"])
    cli_collect = cast(dict[str, object], namespace["cli_collect"])
    gui_collect = cast(dict[str, object], namespace["gui_collect"])

    assert cli_analysis.scripts == [str(Path("eodinga/__main__.py").resolve())]
    assert gui_analysis.scripts == [str(Path("packaging/windows/gui_entry.py").resolve())]
    assert cli_analysis.kwargs["hiddenimports"] == namespace["HIDDEN_IMPORTS"]
    assert gui_analysis.kwargs["hiddenimports"] == namespace["HIDDEN_IMPORTS"]
    assert cli_analysis.kwargs["datas"] == namespace["DATAS"]
    assert gui_analysis.kwargs["datas"] == namespace["DATAS"]
    assert cli_exe["kwargs"]["name"] == "eodinga-cli"
    assert cli_exe["kwargs"]["console"] is True
    assert gui_exe["kwargs"]["name"] == "eodinga-gui"
    assert gui_exe["kwargs"]["console"] is False
    assert cli_collect["kwargs"]["name"] == "eodinga-cli"
    assert gui_collect["kwargs"]["name"] == "eodinga-gui"
