from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from eodinga import __version__


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
    datas = {tuple(item) for item in payload["pyinstaller_spec"]["datas"]}
    assert (str(Path("eodinga/i18n/en.json").resolve()), "eodinga/i18n") in datas
    assert (str(Path("eodinga/i18n/ko.json").resolve()), "eodinga/i18n") in datas
    rendered_path = Path(payload["inno_setup"]["rendered_path"])
    assert rendered_path.exists()
    rendered_text = rendered_path.read_text(encoding="utf-8")
    assert f'#define AppVersion "{__version__}"' in rendered_text
    assert "@@APP_VERSION@@" not in rendered_text
    assert payload["inno_setup"]["output_base_filename"] == f"eodinga-{__version__}-win-x64-setup"
    assert payload["inno_setup"]["contains_versioned_output_macro"] is True
    assert payload["inno_setup"]["contains_user_install_dir"] is True
    assert payload["inno_setup"]["contains_start_menu_shortcut"] is True
    assert payload["inno_setup"]["contains_desktop_shortcut_task"] is True
    assert payload["inno_setup"]["contains_postinstall_launch"] is True
    assert payload["inno_setup"]["source_entries"] == [
        'dist\\\\eodinga-gui\\\\*',
        'dist\\\\eodinga-cli\\\\*',
    ]
    assert payload["inno_setup"]["source_entries_match_pyinstaller_dist"] is True
    assert payload["inno_setup"]["privileges_lowest"] is True
    assert payload["inno_setup"]["disables_program_group_page"] is True
    assert payload["inno_setup"]["disables_dir_page"] is True
    assert payload["inno_setup"]["includes_korean_language"] is True
    assert payload["inno_setup"]["contains_autostart_task"] is True
    assert payload["inno_setup"]["contains_autostart_registry"] is True
    assert payload["inno_setup"]["contains_uninstall_purge_prompt"] is True


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
    assert payload["apprun"]["is_executable"] is True
    assert payload["apprun"]["launches_gui"] is True
    assert payload["launcher"]["is_executable"] is True
    assert payload["launcher"]["executes_python_module"] is True


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
