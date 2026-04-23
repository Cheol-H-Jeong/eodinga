from __future__ import annotations

import json
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

from eodinga import __version__


def _load_build_module():
    spec = importlib.util.spec_from_file_location("packaging_build", Path("packaging/build.py"))
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_dry_run_returns_zero_and_writes_audit() -> None:
    result = subprocess.run(
        [sys.executable, "packaging/build.py", "--target", "windows-dry-run"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    audit_path = Path("packaging/dist/windows-dry-run-audit.json")
    assert audit_path.exists()
    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    assert payload["target"] == "windows-dry-run"
    assert payload["version"] == __version__
    assert payload["version_matches_package"] is True
    assert payload["pyinstaller_spec"]["exists"] is True
    assert payload["pyinstaller_spec"]["dist_names"] == {
        "cli": "eodinga-cli",
        "gui": "eodinga-gui",
    }
    assert payload["pyinstaller_spec"]["dist_paths"] == {
        "cli": str(Path("dist/eodinga-cli").resolve()),
        "gui": str(Path("dist/eodinga-gui").resolve()),
    }
    assert payload["pyinstaller_spec"]["exe_names"] == {
        "cli": "eodinga-cli.exe",
        "gui": "eodinga-gui.exe",
    }
    assert payload["pyinstaller_spec"]["exe_paths"] == {
        "cli": str(Path("dist/eodinga-cli/eodinga-cli.exe").resolve()),
        "gui": str(Path("dist/eodinga-gui/eodinga-gui.exe").resolve()),
    }
    discovered_source_hiddenimports = set(payload["pyinstaller_spec"]["discovered_source_hiddenimports"])
    assert discovered_source_hiddenimports
    assert discovered_source_hiddenimports <= set(payload["pyinstaller_spec"]["hiddenimports"])
    datas = {tuple(item) for item in payload["pyinstaller_spec"]["datas"]}
    assert (str(Path("eodinga/i18n/en.json").resolve()), "eodinga/i18n") in datas
    assert (str(Path("eodinga/i18n/ko.json").resolve()), "eodinga/i18n") in datas
    rendered_path = Path(payload["inno_setup"]["rendered_path"])
    assert rendered_path.exists()
    rendered_text = rendered_path.read_text(encoding="utf-8")
    assert f'#define AppVersion "{__version__}"' in rendered_text
    assert "@@APP_VERSION@@" not in rendered_text
    assert "@@GUI_DIST_NAME@@" not in rendered_text
    assert "@@CLI_DIST_NAME@@" not in rendered_text
    assert "@@GUI_EXE_NAME@@" not in rendered_text
    assert payload["inno_setup"]["output_base_filename"] == f"eodinga-{__version__}-win-x64-setup"
    assert payload["inno_setup"]["app_id"] == "{{B4D25A04-71A1-45A2-A0BB-7B3F612E9E68}"
    assert payload["inno_setup"]["app_id_is_guid_macro"] is True
    assert payload["inno_setup"]["app_version_macro"] == "@@APP_VERSION@@"
    assert payload["inno_setup"]["app_version_uses_template"] is True
    assert payload["inno_setup"]["contains_versioned_output_macro"] is True
    assert payload["inno_setup"]["contains_user_install_dir"] is True
    assert payload["inno_setup"]["contains_rendered_uninstall_display_icon"] is True
    assert payload["inno_setup"]["contains_start_menu_shortcut"] is True
    assert payload["inno_setup"]["contains_desktop_shortcut_task"] is True
    assert payload["inno_setup"]["contains_user_desktop_shortcut"] is True
    assert payload["inno_setup"]["contains_postinstall_launch"] is True
    assert payload["inno_setup"]["source_entries"] == [
        'dist\\\\@@GUI_DIST_NAME@@\\\\*',
        'dist\\\\@@CLI_DIST_NAME@@\\\\*',
    ]
    assert payload["inno_setup"]["source_entries_match_pyinstaller_dist"] is True
    assert payload["inno_setup"]["rendered_source_entries"] == [
        'dist\\\\eodinga-gui\\\\*',
        'dist\\\\eodinga-cli\\\\*',
    ]
    assert payload["inno_setup"]["rendered_source_entries_match_pyinstaller_dist"] is True
    assert payload["inno_setup"]["privileges_lowest"] is True
    assert payload["inno_setup"]["disables_program_group_page"] is True
    assert payload["inno_setup"]["disables_dir_page"] is True
    assert payload["inno_setup"]["includes_korean_language"] is True
    assert payload["inno_setup"]["contains_autostart_task"] is True
    assert payload["inno_setup"]["contains_autostart_registry"] is True
    assert payload["inno_setup"]["rendered_autostart_registry_matches_gui_exe"] is True
    assert payload["inno_setup"]["contains_uninstall_purge_prompt"] is True
    assert payload["inno_setup"]["purge_prompt_is_opt_in"] is True
    assert payload["inno_setup"]["purge_targets_local_and_roaming_user_state"] is True


def test_windows_audit_validator_rejects_version_mismatch() -> None:
    module = _load_build_module()
    payload = module._audit_windows_inputs("0.1.136", "0.1.135")

    errors = module._validate_windows_audit(payload)

    assert "project and package versions do not match" in errors


def test_windows_audit_validator_rejects_missing_built_artifacts_for_release_target() -> None:
    module = _load_build_module()
    payload = module._audit_windows_inputs(__version__, __version__)
    payload["target"] = "windows"
    payload["pyinstaller_spec"]["dist_exists"] = {"cli": False, "gui": True}
    payload["pyinstaller_spec"]["exe_exists"] = {"cli": False, "gui": False}

    errors = module._validate_windows_audit(payload)

    assert "Windows build is missing the staged CLI dist directory" in errors
    assert "Windows build is missing the staged GUI executable" in errors
    assert "Windows build is missing the staged CLI executable" in errors


def test_windows_audit_validator_rejects_missing_source_hidden_import_contract() -> None:
    module = _load_build_module()
    payload = module._audit_windows_inputs(__version__, __version__)
    payload["pyinstaller_spec"]["hiddenimports"] = ["PySide6"]

    errors = module._validate_windows_audit(payload)

    assert "PyInstaller hidden imports no longer include the source-derived modules" in errors


def test_windows_audit_validator_rejects_uninstall_purge_contract_regression() -> None:
    module = _load_build_module()
    payload = module._audit_windows_inputs(__version__, __version__)
    payload["inno_setup"]["purge_targets_local_and_roaming_user_state"] = False

    errors = module._validate_windows_audit(payload)

    assert "Inno uninstall purge no longer targets both local data and roaming config" in errors


def test_build_preflight_reports_missing_windows_tool(monkeypatch) -> None:
    module = _load_build_module()

    def fake_which(command: str) -> str | None:
        if command == "iscc":
            return None
        return f"/usr/bin/{command}"

    monkeypatch.setattr(module.shutil, "which", fake_which)

    result = module._run_windows()

    assert result == 1


def test_windows_build_target_relabels_audit_and_requires_built_artifacts(monkeypatch) -> None:
    module = _load_build_module()

    def fake_which(command: str) -> str | None:
        return f"/usr/bin/{command}"

    monkeypatch.setattr(module.shutil, "which", fake_which)
    monkeypatch.setattr(module, "_run_command", lambda command, cwd=module.PROJECT_ROOT: 0)

    result = module._run_windows()

    assert result == 1
    payload = json.loads(Path("packaging/dist/windows-audit.json").read_text(encoding="utf-8"))
    assert payload["target"] == "windows"
    assert payload["inno_setup"]["installer_exists"] is False


def test_windows_audit_validator_rejects_missing_setup_artifact() -> None:
    module = _load_build_module()
    payload = module._audit_windows_inputs(__version__, __version__)
    payload["target"] = "windows"
    payload["pyinstaller_spec"]["dist_exists"] = {"cli": True, "gui": True}
    payload["pyinstaller_spec"]["exe_exists"] = {"cli": True, "gui": True}
    payload["inno_setup"]["installer_exists"] = False

    errors = module._validate_windows_audit(payload)

    assert "Windows build is missing the Inno Setup installer artifact" in errors


def test_windows_build_target_runs_pyinstaller_and_iscc(monkeypatch) -> None:
    module = _load_build_module()
    commands: list[list[str]] = []

    def fake_which(command: str) -> str | None:
        return f"/usr/bin/{command}"

    def fake_run_command(command: list[str], *, cwd: Path = Path(".")) -> int:
        commands.append(command)
        if command[0] == "pyinstaller":
            dist_name = command[command.index("--name") + 1]
            dist_dir = module.PROJECT_ROOT / "dist" / dist_name
            dist_dir.mkdir(parents=True, exist_ok=True)
            (dist_dir / f"{dist_name}.exe").write_text("binary", encoding="utf-8")
            return 0
        if command[0] == "iscc":
            installer_path = module.DIST_DIR / "windows" / f"eodinga-{__version__}-win-x64-setup.exe"
            installer_path.parent.mkdir(parents=True, exist_ok=True)
            installer_path.write_text("setup", encoding="utf-8")
            return 0
        raise AssertionError(command)

    monkeypatch.setattr(module.shutil, "which", fake_which)
    monkeypatch.setattr(module, "_run_command", fake_run_command)

    result = module._run_windows()

    assert result == 0
    assert [command[0] for command in commands] == ["pyinstaller", "pyinstaller", "iscc"]
    cli_command, gui_command, iscc_command = commands
    assert "--windowed" not in cli_command
    assert "--windowed" in gui_command
    assert str(Path("eodinga/__main__.py").resolve()) == cli_command[-1]
    assert str(Path("eodinga/__main__.py").resolve()) == gui_command[-1]
    assert "--hidden-import" in cli_command
    assert "watchdog" in cli_command
    assert "--add-data" in cli_command
    assert iscc_command[1] == "/Qp"
    assert iscc_command[-1] == str((module.DIST_DIR / "windows" / "eodinga.iss").resolve())

    payload = json.loads(Path("packaging/dist/windows-audit.json").read_text(encoding="utf-8"))
    assert payload["target"] == "windows"
    assert payload["pyinstaller_spec"]["dist_exists"] == {"cli": True, "gui": True}
    assert payload["pyinstaller_spec"]["exe_exists"] == {"cli": True, "gui": True}
    assert payload["inno_setup"]["installer_exists"] is True


def test_build_preflight_reports_missing_linux_deb_tool(monkeypatch) -> None:
    module = _load_build_module()

    def fake_which(command: str) -> str | None:
        if command == "dpkg-deb":
            return None
        return f"/usr/bin/{command}"

    monkeypatch.setattr(module.shutil, "which", fake_which)

    result = module._run_linux_deb()

    assert result == 1


def test_windows_dry_run_covers_dynamic_hotkey_hidden_imports() -> None:
    result = subprocess.run(
        [sys.executable, "packaging/build.py", "--target", "windows-dry-run"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0

    audit_path = Path("packaging/dist/windows-dry-run-audit.json")
    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    hidden_imports = set(payload["pyinstaller_spec"]["hiddenimports"])

    hotkey_module = Path("eodinga/launcher/hotkey_linux.py").read_text(encoding="utf-8")
    expected_modules = set(re.findall(r'import_module\\("([^"]+)"\\)', hotkey_module))
    assert expected_modules <= hidden_imports


def test_windows_dry_run_covers_source_imported_third_party_modules() -> None:
    result = subprocess.run(
        [sys.executable, "packaging/build.py", "--target", "windows-dry-run"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0

    audit_path = Path("packaging/dist/windows-dry-run-audit.json")
    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    hidden_imports = set(payload["pyinstaller_spec"]["hiddenimports"])
    discovered_source_hiddenimports = set(payload["pyinstaller_spec"]["discovered_source_hiddenimports"])

    assert "charset_normalizer" in hidden_imports
    assert "pathspec" in hidden_imports
    assert "ebooklib.epub" in hidden_imports
    assert {"charset_normalizer", "pathspec", "ebooklib.epub"} <= discovered_source_hiddenimports


def test_linux_appimage_audit_validator_rejects_missing_launcher_contract() -> None:
    module = _load_build_module()
    payload = {
        "version": __version__,
        "recipe": {
            "exists": True,
            "contains_version_template": True,
            "rendered_exists": True,
            "rendered_version_matches_package": True,
            "references_desktop_entry": True,
            "references_icon_asset": True,
            "launches_gui": True,
        },
        "icon": {
            "exists": True,
            "diricon_exists": True,
            "desktop_icon_matches_asset": True,
            "matches_source_asset": True,
        },
        "apprun": {
            "is_executable": True,
            "launches_gui": True,
            "has_strict_shell": True,
        },
        "launcher": {
            "is_executable": True,
            "has_strict_shell": True,
            "changes_to_project_root": True,
            "executes_python_module": False,
        },
    }

    errors = module._validate_linux_appimage_audit(payload, __version__, __version__)

    assert "AppImage launcher shim no longer executes the Python module" in errors


def test_linux_appimage_audit_validator_rejects_versioned_archive_drift() -> None:
    module = _load_build_module()
    payload = {
        "version": __version__,
        "arch": "x86_64",
        "archive": "packaging/dist/eodinga-linux-appdir.tar.gz",
        "archive_entries_sorted": True,
        "archive_mtime_zero": True,
        "archive_numeric_owner_zero": True,
        "recipe": {
            "exists": True,
            "contains_version_template": True,
            "rendered_exists": True,
            "rendered_version_matches_package": True,
            "references_desktop_entry": True,
            "references_icon_asset": True,
            "launches_gui": True,
        },
        "icon": {
            "exists": True,
            "diricon_exists": True,
            "desktop_icon_matches_asset": True,
        },
        "apprun": {
            "is_executable": True,
            "launches_gui": True,
        },
        "launcher": {
            "is_executable": True,
            "executes_python_module": True,
        },
    }

    errors = module._validate_linux_appimage_audit(payload, __version__, __version__)

    assert "AppImage archive filename does not match the package version" in errors


def test_linux_appimage_dry_run_stages_recipe() -> None:
    result = subprocess.run(
        ["bash", "packaging/linux/appimage.sh", "--dry-run"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    manifest_path = Path("packaging/dist/linux-appimage-audit.json")
    assert manifest_path.exists()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["target"] == "linux-appimage-dry-run"
    assert payload["version"] == __version__
    assert payload["arch"]
    assert Path(payload["appdir"]).exists()
    assert Path(payload["archive"]).exists()
    assert Path(payload["archive"]).name == f"eodinga-{__version__}-linux-{payload['arch']}-appdir.tar.gz"
    assert payload["archive_entries_sorted"] is True
    assert payload["archive_mtime_zero"] is True
    assert payload["archive_numeric_owner_zero"] is True
    assert payload["desktop_entry"]["name"] == "eodinga"
    assert payload["desktop_entry"]["exec"] == "eodinga gui"
    assert payload["desktop_entry"]["icon"] == "eodinga"
    assert payload["desktop_entry"]["categories"] == "Utility;FileTools;"
    assert payload["desktop_entry"]["startup_notify"] == "true"
    assert payload["recipe"]["exists"] is True
    assert payload["recipe"]["contains_version_template"] is True
    assert Path(payload["recipe"]["rendered_path"]).exists()
    assert payload["recipe"]["rendered_exists"] is True
    assert payload["recipe"]["rendered_version_matches_package"] is True
    assert payload["recipe"]["references_desktop_entry"] is True
    assert payload["recipe"]["references_icon_asset"] is True
    assert payload["recipe"]["launches_gui"] is True
    assert payload["icon"]["exists"] is True
    assert payload["icon"]["diricon_exists"] is True
    assert payload["icon"]["desktop_icon_matches_asset"] is True
    assert payload["icon"]["matches_source_asset"] is True
    assert payload["apprun"]["is_executable"] is True
    assert payload["apprun"]["launches_gui"] is True
    assert payload["apprun"]["has_strict_shell"] is True
    assert payload["launcher"]["is_executable"] is True
    assert payload["launcher"]["has_strict_shell"] is True
    assert payload["launcher"]["changes_to_project_root"] is True
    assert payload["launcher"]["executes_python_module"] is True


def test_linux_deb_dry_run_renders_control_template() -> None:
    result = subprocess.run(
        ["bash", "packaging/linux/deb.sh", "--dry-run"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    manifest_path = Path("packaging/dist/linux-deb-audit.json")
    assert manifest_path.exists()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["target"] == "linux-deb-dry-run"
    assert payload["version"] == __version__
    assert payload["arch"] == "amd64"
    assert payload["control"]["package"] == "eodinga"
    assert payload["control"]["version"] == __version__
    assert payload["control"]["architecture"] == "amd64"
    assert payload["control"]["depends"] == "python3 (>= 3.11)"
    assert payload["debian_control_template"]["exists"] is True
    assert payload["debian_control_template"]["contains_version_template"] is True
    assert payload["debian_control_template"]["contains_arch_template"] is True
    rendered_control_path = Path(payload["debian_control_template"]["rendered_path"])
    assert rendered_control_path.exists()
    assert payload["debian_control_template"]["rendered_exists"] is True
    rendered_control = rendered_control_path.read_text(encoding="utf-8")
    assert f"Version: {__version__}" in rendered_control
    assert "Architecture: amd64" in rendered_control
    assert payload["launcher"]["executes_python_module"] is True


def test_linux_deb_audit_validator_rejects_missing_docs() -> None:
    module = _load_build_module()
    payload = {
        "version": __version__,
        "control": {
            "package": "eodinga",
            "version": __version__,
        },
        "debian_control_template": {
            "exists": True,
            "source": "eodinga",
            "maintainer": "Cheol-H-Jeong",
            "binary_package": "eodinga",
            "description": "Instant lexical file search for Windows and Linux",
        },
        "desktop_entry": {
            "name": "eodinga",
            "launches_gui": True,
            "icon_matches_package": True,
            "categories": "Utility;FileTools;",
            "startup_notify": "true",
        },
        "icon": {
            "exists": True,
            "desktop_icon_matches_asset": True,
            "matches_source_asset": True,
        },
        "launcher": {
            "is_executable": True,
            "has_strict_shell": True,
            "executes_python_module": True,
        },
        "docs": {
            "license_exists": True,
            "changelog_exists": False,
            "changelog_has_current_release_heading": True,
        },
    }

    errors = module._validate_linux_deb_audit(payload, __version__, __version__)

    assert "Debian package no longer ships the changelog" in errors


def test_linux_deb_audit_validator_rejects_artifact_name_drift() -> None:
    module = _load_build_module()
    payload = {
        "version": __version__,
        "arch": "amd64",
        "archive": "packaging/dist/eodinga_latest_amd64_debroot.tar.gz",
        "deb_path": "packaging/dist/eodinga_latest_amd64.deb",
        "archive_entries_sorted": True,
        "archive_mtime_zero": True,
        "archive_numeric_owner_zero": True,
        "control": {
            "package": "eodinga",
            "version": __version__,
            "architecture": "amd64",
            "depends": "python3 (>= 3.11)",
            "description": "Instant lexical file search for Windows and Linux",
        },
        "debian_control_template": {
            "exists": True,
            "source": "eodinga",
            "maintainer": "Cheol-H-Jeong",
            "binary_package": "eodinga",
            "description": "Instant lexical file search for Windows and Linux",
        },
        "desktop_entry": {
            "name": "eodinga",
            "launches_gui": True,
            "icon_matches_package": True,
            "categories": "Utility;FileTools;",
            "startup_notify": "true",
        },
        "icon": {
            "exists": True,
            "desktop_icon_matches_asset": True,
            "matches_source_asset": True,
        },
        "launcher": {
            "is_executable": True,
            "has_strict_shell": True,
            "executes_python_module": True,
        },
        "docs": {
            "license_exists": True,
            "changelog_exists": True,
            "changelog_has_current_release_heading": True,
        },
    }

    errors = module._validate_linux_deb_audit(payload, __version__, __version__)

    assert "Debian dry-run archive filename does not match the package version and arch" in errors
    assert "Debian package filename does not match the package version and arch" in errors


def test_linux_appimage_build_target_writes_non_dry_run_audit() -> None:
    result = subprocess.run(
        [sys.executable, "packaging/build.py", "--target", "linux-appimage"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    manifest_path = Path("packaging/dist/linux-appimage-audit.json")
    assert manifest_path.exists()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["target"] == "linux-appimage"
    assert payload["dry_run"] is False
    assert payload["arch"]
    assert Path(payload["appdir"]).exists()
    assert Path(payload["archive"]).exists()
    assert Path(payload["archive"]).name == f"eodinga-{__version__}-linux-{payload['arch']}-appdir.tar.gz"


def test_linux_deb_dry_run_stages_recipe() -> None:
    result = subprocess.run(
        [sys.executable, "packaging/build.py", "--target", "linux-deb-dry-run"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    manifest_path = Path("packaging/dist/linux-deb-audit.json")
    assert manifest_path.exists()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["target"] == "linux-deb-dry-run"
    assert payload["version"] == __version__
    assert payload["arch"] == "amd64"
    assert Path(payload["package_dir"]).exists()
    assert Path(payload["control_path"]).exists()
    assert Path(payload["archive"]).exists()
    assert payload["archive_entries_sorted"] is True
    assert payload["archive_mtime_zero"] is True
    assert payload["archive_numeric_owner_zero"] is True
    assert payload["control"] == {
        "package": "eodinga",
        "version": __version__,
        "architecture": "amd64",
        "depends": "python3 (>= 3.11)",
        "description": "Instant lexical file search for Windows and Linux",
    }
    assert payload["debian_control_template"]["path"] == str(Path("packaging/linux/debian/control").resolve())
    assert payload["debian_control_template"]["exists"] is True
    assert payload["debian_control_template"]["contains_version_template"] is True
    assert payload["debian_control_template"]["contains_arch_template"] is True
    assert payload["debian_control_template"]["rendered_exists"] is True
    assert payload["debian_control_template"]["source"] == "eodinga"
    assert payload["debian_control_template"]["maintainer"] == "Cheol-H-Jeong"
    assert payload["debian_control_template"]["binary_package"] == "eodinga"
    assert payload["debian_control_template"]["description"] == "Instant lexical file search for Windows and Linux"
    assert payload["desktop_entry"]["name"] == "eodinga"
    assert payload["desktop_entry"]["exec"] == "eodinga gui"
    assert payload["desktop_entry"]["icon"] == "eodinga"
    assert payload["desktop_entry"]["categories"] == "Utility;FileTools;"
    assert payload["desktop_entry"]["startup_notify"] == "true"
    assert payload["desktop_entry"]["launches_gui"] is True
    assert payload["desktop_entry"]["icon_matches_package"] is True
    assert payload["icon"]["exists"] is True
    assert payload["icon"]["desktop_icon_matches_asset"] is True
    assert payload["icon"]["matches_source_asset"] is True
    assert payload["launcher"]["is_executable"] is True
    assert payload["launcher"]["has_strict_shell"] is True
    assert payload["launcher"]["executes_python_module"] is True
    assert payload["docs"]["license_exists"] is True
    assert payload["docs"]["changelog_exists"] is True
    assert payload["docs"]["changelog_has_current_release_heading"] is True


def test_linux_deb_build_target_writes_non_dry_run_audit() -> None:
    result = subprocess.run(
        [sys.executable, "packaging/build.py", "--target", "linux-deb"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    manifest_path = Path("packaging/dist/linux-deb-audit.json")
    assert manifest_path.exists()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["target"] == "linux-deb"
    assert payload["dry_run"] is False
    assert Path(payload["package_dir"]).exists()
    assert Path(payload["control_path"]).exists()
    assert Path(payload["deb_path"]).exists()
    assert payload["archive_entries_sorted"] is True
    assert payload["archive_mtime_zero"] is True
    assert payload["archive_numeric_owner_zero"] is True
    assert payload["icon"]["exists"] is True
    assert payload["docs"]["changelog_exists"] is True
