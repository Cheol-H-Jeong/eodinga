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
    assert payload["pyinstaller_spec"]["exe_names"] == {
        "cli": "eodinga-cli.exe",
        "gui": "eodinga-gui.exe",
    }
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
    assert payload["inno_setup"]["purges_roaming_data_dir"] is True
    assert payload["inno_setup"]["purges_local_data_dir"] is True


def test_windows_audit_validator_rejects_version_mismatch() -> None:
    module = _load_build_module()
    payload = module._audit_windows_inputs("0.1.136", "0.1.135")

    errors = module._validate_windows_audit(payload)

    assert "project and package versions do not match" in errors


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


def test_linux_appimage_audit_validator_rejects_missing_launcher_contract() -> None:
    module = _load_build_module()
    payload = {
        "version": __version__,
        "recipe": {
            "exists": True,
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
            "executes_python_module": False,
        },
    }

    errors = module._validate_linux_appimage_audit(payload, __version__)

    assert "AppImage launcher shim no longer executes the Python module" in errors


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
    assert Path(payload["appdir"]).exists()
    assert Path(payload["archive"]).exists()
    assert payload["desktop_entry"]["name"] == "eodinga"
    assert payload["desktop_entry"]["exec"] == "eodinga gui"
    assert payload["desktop_entry"]["icon"] == "eodinga"
    assert payload["desktop_entry"]["categories"] == "Utility;FileTools;"
    assert payload["desktop_entry"]["startup_notify"] == "true"
    assert payload["recipe"]["exists"] is True
    assert payload["recipe"]["references_desktop_entry"] is True
    assert payload["recipe"]["references_icon_asset"] is True
    assert payload["recipe"]["launches_gui"] is True
    assert payload["icon"]["exists"] is True
    assert payload["icon"]["diricon_exists"] is True
    assert payload["icon"]["desktop_icon_matches_asset"] is True
    assert payload["apprun"]["is_executable"] is True
    assert payload["apprun"]["launches_gui"] is True
    assert payload["launcher"]["is_executable"] is True
    assert payload["launcher"]["executes_python_module"] is True


def test_linux_deb_audit_validator_rejects_missing_docs() -> None:
    module = _load_build_module()
    payload = {
        "version": __version__,
        "control": {
            "package": "eodinga",
            "version": __version__,
        },
        "icon": {
            "exists": True,
            "desktop_icon_matches_asset": True,
        },
        "launcher": {
            "is_executable": True,
            "executes_python_module": True,
        },
        "docs": {
            "license_exists": True,
            "changelog_exists": False,
        },
    }

    errors = module._validate_linux_deb_audit(payload, __version__)

    assert "Debian package no longer ships the changelog" in errors


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
    assert Path(payload["appdir"]).exists()
    assert Path(payload["archive"]).exists()


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
    assert payload["control"] == {
        "package": "eodinga",
        "version": __version__,
        "architecture": "amd64",
        "depends": "python3 (>= 3.11)",
        "description": "Instant lexical file search for Windows and Linux",
    }
    assert payload["desktop_entry"]["name"] == "eodinga"
    assert payload["desktop_entry"]["exec"] == "eodinga gui"
    assert payload["desktop_entry"]["icon"] == "eodinga"
    assert payload["desktop_entry"]["categories"] == "Utility;FileTools;"
    assert payload["desktop_entry"]["startup_notify"] == "true"
    assert payload["icon"]["exists"] is True
    assert payload["icon"]["desktop_icon_matches_asset"] is True
    assert payload["launcher"]["is_executable"] is True
    assert payload["launcher"]["executes_python_module"] is True
    assert payload["docs"]["license_exists"] is True
    assert payload["docs"]["changelog_exists"] is True


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
    assert payload["icon"]["exists"] is True
    assert payload["docs"]["changelog_exists"] is True
