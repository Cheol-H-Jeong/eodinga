from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path
from typing import Any


def source_entries(text: str) -> list[str]:
    return re.findall(r'Source:\s*"([^"]+)"', text)


def contains_data_entry(datas: list[object], source: Path, destination: str) -> bool:
    return (str(source), destination) in datas


def macro_value(text: str, macro_name: str) -> str | None:
    match = re.search(rf'^#define\s+{re.escape(macro_name)}\s+"([^"]+)"', text, flags=re.MULTILINE)
    if match is None:
        return None
    return match.group(1)


def validate_windows_audit(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not payload.get("version_matches_package"):
        errors.append("project and package versions do not match")
    spec_payload = payload.get("pyinstaller_spec", {})
    if not spec_payload.get("exists"):
        errors.append("PyInstaller spec is missing")
    if spec_payload.get("dist_names") != {"cli": "eodinga-cli", "gui": "eodinga-gui"}:
        errors.append("PyInstaller dist names drifted from the release contract")
    if spec_payload.get("exe_names") != {"cli": "eodinga-cli.exe", "gui": "eodinga-gui.exe"}:
        errors.append("PyInstaller executable names drifted from the release contract")
    if not spec_payload.get("hiddenimports"):
        errors.append("PyInstaller hidden imports are empty")
    discovered_source_hiddenimports = spec_payload.get("discovered_source_hiddenimports", [])
    if not discovered_source_hiddenimports:
        errors.append("PyInstaller source-derived hidden imports are empty")
    elif not set(discovered_source_hiddenimports).issubset(set(spec_payload.get("hiddenimports", []))):
        errors.append("PyInstaller hidden imports no longer include the source-derived modules")
    if not spec_payload.get("datas"):
        errors.append("PyInstaller data files are empty")
    if not spec_payload.get("datas_include_i18n"):
        errors.append("PyInstaller data files no longer ship both i18n catalogs")
    if not spec_payload.get("datas_include_license"):
        errors.append("PyInstaller data files no longer ship the LICENSE file")
    inno_payload = payload.get("inno_setup", {})
    required_flags = {
        "exists": "Inno setup script is missing",
        "app_id_is_guid_macro": "Inno AppId macro is not a GUID template",
        "app_version_uses_template": "Inno AppVersion macro no longer uses the template token",
        "source_entries_match_pyinstaller_dist": "Inno source entries drifted from PyInstaller dist names",
        "rendered_source_entries_match_pyinstaller_dist": "Rendered Inno source entries drifted from PyInstaller dist names",
        "rendered_exists": "Rendered Inno setup script is missing",
        "contains_license_file": "Rendered Inno installer no longer ships the LICENSE file",
        "contains_rendered_uninstall_display_icon": "Rendered Inno uninstall icon does not point at the GUI executable",
        "contains_start_menu_shortcut": "Rendered Inno start menu shortcut is missing",
        "contains_postinstall_launch": "Rendered Inno postinstall launch action is missing",
        "contains_autostart_registry": "Inno autostart registry entry is missing",
        "rendered_autostart_registry_matches_gui_exe": "Rendered Inno autostart registry entry does not point at the GUI executable",
        "contains_uninstall_purge_prompt": "Inno uninstall purge prompt is missing",
        "purge_prompt_is_opt_in": "Inno uninstall purge prompt is no longer opt-in",
        "purge_targets_local_data_dir_only": "Inno uninstall purge path no longer preserves roaming config by default",
    }
    for key, message in required_flags.items():
        if not inno_payload.get(key):
            errors.append(message)
    return errors


def validate_linux_appimage_audit(payload: dict[str, Any], project_version: str, package_version: str) -> list[str]:
    errors: list[str] = []
    if project_version != package_version:
        errors.append("project and package versions do not match")
    if payload.get("version") != package_version:
        errors.append("AppImage audit version does not match the package version")
    archive_path = payload.get("archive")
    expected_archive_name = f"eodinga-{package_version}-linux-appdir.tar.gz"
    if Path(str(archive_path)).name != expected_archive_name:
        errors.append("AppImage archive filename does not match the package version")
    if not Path(str(payload.get("appdir"))).exists():
        errors.append("AppImage AppDir is missing")
    if not Path(str(archive_path)).exists():
        errors.append("AppImage archive is missing")
    desktop_payload = payload.get("desktop_entry", {})
    recipe_payload = payload.get("recipe", {})
    icon_payload = payload.get("icon", {})
    apprun_payload = payload.get("apprun", {})
    launcher_payload = payload.get("launcher", {})
    required_flags = [
        (desktop_payload.get("name") == "eodinga", "AppImage desktop entry name drifted from eodinga"),
        (desktop_payload.get("exec") == "eodinga gui", "AppImage desktop entry no longer launches the GUI command"),
        (desktop_payload.get("icon") == "eodinga", "AppImage desktop entry icon drifted from eodinga"),
        (desktop_payload.get("categories") == "Utility;FileTools;", "AppImage desktop entry categories drifted from the release contract"),
        (desktop_payload.get("startup_notify") == "true", "AppImage desktop entry startup-notify flag drifted from the release contract"),
        (recipe_payload.get("exists"), "AppImage recipe is missing"),
        (recipe_payload.get("contains_version_template"), "AppImage recipe no longer uses the version template"),
        (recipe_payload.get("rendered_exists"), "Rendered AppImage recipe is missing"),
        (recipe_payload.get("rendered_version_matches_package"), "Rendered AppImage recipe version does not match the package version"),
        (recipe_payload.get("references_desktop_entry"), "AppImage recipe no longer references the desktop entry"),
        (recipe_payload.get("references_icon_asset"), "AppImage recipe no longer references the icon asset"),
        (recipe_payload.get("launches_gui"), "AppImage recipe no longer launches the GUI target"),
        (icon_payload.get("exists"), "AppImage icon asset is missing from the staged AppDir"),
        (icon_payload.get("diricon_exists"), "AppImage .DirIcon is missing"),
        (icon_payload.get("desktop_icon_matches_asset"), "AppImage desktop icon no longer matches the shipped asset"),
        (apprun_payload.get("is_executable"), "AppImage AppRun is not executable"),
        (apprun_payload.get("launches_gui"), "AppImage AppRun no longer launches the GUI target"),
        (launcher_payload.get("is_executable"), "AppImage launcher shim is not executable"),
        (launcher_payload.get("executes_python_module"), "AppImage launcher shim no longer executes the Python module"),
    ]
    for ok, message in required_flags:
        if not ok:
            errors.append(message)
    return errors


def validate_linux_deb_audit(payload: dict[str, Any], project_version: str, package_version: str) -> list[str]:
    errors: list[str] = []
    if project_version != package_version:
        errors.append("project and package versions do not match")
    if payload.get("version") != package_version:
        errors.append("Debian audit version does not match the package version")
    control_payload = payload.get("control", {})
    control_template_payload = payload.get("debian_control_template", {})
    desktop_payload = payload.get("desktop_entry", {})
    icon_payload = payload.get("icon", {})
    launcher_payload = payload.get("launcher", {})
    docs_payload = payload.get("docs", {})
    arch = payload.get("arch")
    if control_payload.get("package") != "eodinga":
        errors.append("Debian control package name drifted from eodinga")
    if control_payload.get("version") != package_version:
        errors.append("Debian control version does not match the package version")
    if control_payload.get("architecture") != arch:
        errors.append("Debian control architecture does not match the target arch")
    if control_payload.get("depends") != "python3 (>= 3.11)":
        errors.append("Debian control dependency contract drifted from python3 (>= 3.11)")
    expected_archive_name = f"eodinga_{package_version}_{arch}_debroot.tar.gz"
    if Path(str(payload.get("archive"))).name != expected_archive_name:
        errors.append("Debian dry-run archive filename does not match the package version and arch")
    expected_deb_name = f"eodinga_{package_version}_{arch}.deb"
    if Path(str(payload.get("deb_path"))).name != expected_deb_name:
        errors.append("Debian package filename does not match the package version and arch")
    if not Path(str(payload.get("package_dir"))).exists():
        errors.append("Debian package root is missing")
    if not Path(str(payload.get("control_path"))).exists():
        errors.append("Debian control file is missing")
    if not Path(str(payload.get("archive"))).exists():
        errors.append("Debian dry-run archive is missing")
    required_flags = [
        (control_template_payload.get("exists"), "Debian control template is missing"),
        (control_template_payload.get("contains_version_template"), "Debian control template no longer uses the version token"),
        (control_template_payload.get("contains_arch_template"), "Debian control template no longer uses the architecture token"),
        (control_template_payload.get("rendered_exists"), "Rendered Debian control file is missing"),
        (control_template_payload.get("source") == "eodinga", "Debian control template source package drifted from eodinga"),
        (control_template_payload.get("binary_package") == "eodinga", "Debian control template binary package drifted from eodinga"),
        (control_template_payload.get("description") == control_payload.get("description"), "Debian control template description drifted from the staged package"),
        (desktop_payload.get("name") == "eodinga", "Debian desktop entry name drifted from eodinga"),
        (desktop_payload.get("launches_gui"), "Debian desktop entry no longer launches the GUI command"),
        (desktop_payload.get("categories") == "Utility;FileTools;", "Debian desktop entry categories drifted from the release contract"),
        (desktop_payload.get("startup_notify") == "true", "Debian desktop entry startup-notify flag drifted from the release contract"),
        (desktop_payload.get("icon_matches_package"), "Debian desktop entry icon no longer matches the packaged asset"),
        (icon_payload.get("exists"), "Debian icon asset is missing from the package tree"),
        (icon_payload.get("desktop_icon_matches_asset"), "Debian desktop icon no longer matches the shipped asset"),
        (launcher_payload.get("is_executable"), "Debian launcher shim is not executable"),
        (launcher_payload.get("executes_python_module"), "Debian launcher shim no longer executes the Python module"),
        (docs_payload.get("license_exists"), "Debian package no longer ships the license"),
        (docs_payload.get("changelog_exists"), "Debian package no longer ships the changelog"),
        (docs_payload.get("changelog_has_current_release_heading"), "Debian package changelog no longer starts with the current release heading"),
    ]
    for ok, message in required_flags:
        if not ok:
            errors.append(message)
    return errors


def report_validation_errors(target: str, errors: list[str]) -> int:
    if not errors:
        return 0
    joined = "\n".join(f"- {error}" for error in errors)
    print(f"{target} packaging audit failed:\n{joined}", file=sys.stderr)
    return 1


def missing_required_commands(commands: list[str]) -> list[str]:
    return sorted(command for command in commands if shutil.which(command) is None)


def preflight_required_commands(target: str, commands: list[str]) -> int:
    missing = missing_required_commands(commands)
    if not missing:
        return 0
    return report_validation_errors(
        target,
        [f"required build command is missing from PATH: {command}" for command in missing],
    )


def missing_required_files(paths: list[Path]) -> list[Path]:
    return sorted(path for path in paths if not path.exists())


def preflight_required_files(target: str, paths: list[Path]) -> int:
    missing = missing_required_files(paths)
    if not missing:
        return 0
    return report_validation_errors(
        target,
        [f"required packaging file is missing: {path}" for path in missing],
    )
