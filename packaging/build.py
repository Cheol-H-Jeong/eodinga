from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = PROJECT_ROOT / "packaging" / "dist"
WINDOWS_SPEC = PROJECT_ROOT / "packaging" / "pyinstaller.spec"
INNO_SCRIPT = PROJECT_ROOT / "packaging" / "windows" / "eodinga.iss"
PACKAGE_INIT = PROJECT_ROOT / "eodinga" / "__init__.py"
PYPROJECT = PROJECT_ROOT / "pyproject.toml"
APPIMAGE_SCRIPT = PROJECT_ROOT / "packaging" / "linux" / "appimage.sh"
DEB_SCRIPT = PROJECT_ROOT / "packaging" / "linux" / "deb.sh"
APPIMAGE_DESKTOP = PROJECT_ROOT / "packaging" / "linux" / "eodinga.desktop"
INNO_VERSION_TOKEN = "@@APP_VERSION@@"
INNO_GUI_DIST_TOKEN = "@@GUI_DIST_NAME@@"
INNO_CLI_DIST_TOKEN = "@@CLI_DIST_NAME@@"
INNO_GUI_EXE_TOKEN = "@@GUI_EXE_NAME@@"
_INNO_APP_ID_PATTERN = re.compile(r"^\{\{[0-9A-F]{8}(?:-[0-9A-F]{4}){3}-[0-9A-F]{12}\}$")


def _read_project_version() -> str:
    payload = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    return str(payload["project"]["version"])


def _read_package_version() -> str:
    match = re.search(
        r'^__version__\s*=\s*"(?P<version>[^"]+)"',
        PACKAGE_INIT.read_text(encoding="utf-8"),
        flags=re.MULTILINE,
    )
    if match is None:
        raise ValueError(f"could not determine package version from {PACKAGE_INIT}")
    return match.group("version")


def _load_windows_spec_namespace() -> dict[str, Any]:
    spec_namespace: dict[str, Any] = {"__file__": str(WINDOWS_SPEC)}
    exec(WINDOWS_SPEC.read_text(encoding="utf-8"), spec_namespace)
    return spec_namespace


def _render_inno_script(version: str, *, gui_dist_name: str, cli_dist_name: str, gui_exe_name: str) -> Path:
    rendered = INNO_SCRIPT.read_text(encoding="utf-8")
    rendered = rendered.replace(INNO_VERSION_TOKEN, version)
    rendered = rendered.replace(INNO_GUI_DIST_TOKEN, gui_dist_name)
    rendered = rendered.replace(INNO_CLI_DIST_TOKEN, cli_dist_name)
    rendered = rendered.replace(INNO_GUI_EXE_TOKEN, gui_exe_name)
    rendered_path = DIST_DIR / "windows" / "eodinga.iss"
    rendered_path.parent.mkdir(parents=True, exist_ok=True)
    rendered_path.write_text(rendered, encoding="utf-8")
    return rendered_path


def _inno_contains(text: str, needle: str) -> bool:
    return needle in text


def _source_entries(text: str) -> list[str]:
    return re.findall(r'Source:\s*"([^"]+)"', text)


def _macro_value(text: str, macro_name: str) -> str | None:
    match = re.search(rf'^#define\s+{re.escape(macro_name)}\s+"([^"]+)"', text, flags=re.MULTILINE)
    if match is None:
        return None
    return match.group(1)


def _audit_windows_inputs(version: str, package_version: str) -> dict[str, Any]:
    spec_namespace = _load_windows_spec_namespace()
    inno_text = INNO_SCRIPT.read_text(encoding="utf-8")
    app_id = _macro_value(inno_text, "AppId")
    app_version = _macro_value(inno_text, "AppVersion")
    cli_dist_name = str(spec_namespace.get("CLI_DIST_NAME", "eodinga-cli"))
    gui_dist_name = str(spec_namespace.get("GUI_DIST_NAME", "eodinga-gui"))
    cli_exe_name = str(spec_namespace.get("CLI_EXE_NAME", f"{cli_dist_name}.exe"))
    gui_exe_name = str(spec_namespace.get("GUI_EXE_NAME", f"{gui_dist_name}.exe"))
    rendered_path = _render_inno_script(
        version,
        gui_dist_name=gui_dist_name,
        cli_dist_name=cli_dist_name,
        gui_exe_name=gui_exe_name,
    )
    rendered_text = rendered_path.read_text(encoding="utf-8")
    output_base_filename = f"eodinga-{version}-win-x64-setup"
    source_entries = _source_entries(inno_text)
    expected_source_entries = [
        f"dist\\\\{INNO_GUI_DIST_TOKEN}\\\\*",
        f"dist\\\\{INNO_CLI_DIST_TOKEN}\\\\*",
    ]
    rendered_source_entries = [
        f"dist\\\\{gui_dist_name}\\\\*",
        f"dist\\\\{cli_dist_name}\\\\*",
    ]
    return {
        "target": "windows-dry-run",
        "version": version,
        "package_version": package_version,
        "version_matches_package": version == package_version,
        "pyinstaller_spec": {
            "path": str(WINDOWS_SPEC),
            "exists": WINDOWS_SPEC.exists(),
            "dist_names": {
                "cli": cli_dist_name,
                "gui": gui_dist_name,
            },
            "exe_names": {
                "cli": cli_exe_name,
                "gui": gui_exe_name,
            },
            "required_hiddenimports": spec_namespace.get("REQUIRED_HIDDEN_IMPORTS", []),
            "discovered_source_hiddenimports": spec_namespace.get("DISCOVERED_SOURCE_HIDDEN_IMPORTS", []),
            "hiddenimports": spec_namespace.get("HIDDEN_IMPORTS", []),
            "datas": spec_namespace.get("DATAS", []),
        },
        "inno_setup": {
            "path": str(INNO_SCRIPT),
            "exists": INNO_SCRIPT.exists(),
            "app_id": app_id,
            "app_id_is_guid_macro": app_id is not None and bool(_INNO_APP_ID_PATTERN.fullmatch(app_id)),
            "app_version_macro": app_version,
            "app_version_uses_template": app_version == INNO_VERSION_TOKEN,
            "source_entries": source_entries,
            "source_entries_match_pyinstaller_dist": source_entries == expected_source_entries,
            "contains_app_version_template": INNO_VERSION_TOKEN in inno_text,
            "rendered_path": str(rendered_path),
            "output_base_filename": output_base_filename,
            "rendered_source_entries": _source_entries(rendered_text),
            "rendered_source_entries_match_pyinstaller_dist": _source_entries(rendered_text) == rendered_source_entries,
            "contains_versioned_output_macro": "OutputBaseFilename=eodinga-{#AppVersion}-win-x64-setup" in rendered_text,
            "contains_user_install_dir": _inno_contains(rendered_text, r"DefaultDirName={userappdata}\eodinga"),
            "contains_rendered_uninstall_display_icon": _inno_contains(
                rendered_text,
                f"UninstallDisplayIcon={{app}}\\{gui_exe_name}",
            ),
            "contains_start_menu_shortcut": _inno_contains(
                rendered_text,
                f'Name: "{{group}}\\\\eodinga"; Filename: "{{app}}\\\\{gui_exe_name}"',
            ),
            "contains_desktop_shortcut_task": _inno_contains(inno_text, 'Name: "desktopicon"'),
            "contains_postinstall_launch": _inno_contains(
                rendered_text,
                f'Filename: "{{app}}\\\\{gui_exe_name}"; Description: "{{cm:LaunchProgram,eodinga}}"; Flags: nowait postinstall skipifsilent',
            ),
            "privileges_lowest": _inno_contains(rendered_text, "PrivilegesRequired=lowest"),
            "disables_program_group_page": _inno_contains(rendered_text, "DisableProgramGroupPage=yes"),
            "disables_dir_page": _inno_contains(rendered_text, "DisableDirPage=yes"),
            "includes_korean_language": _inno_contains(rendered_text, 'Name: "korean"; MessagesFile: "compiler:Languages\\Korean.isl"'),
            "contains_autostart_task": 'Name: "autostart"' in inno_text,
            "contains_autostart_registry": 'Subkey: "Software\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\Run"' in inno_text
            and 'ValueName: "eodinga"' in inno_text
            and f'ValueData: """{{app}}\\\\{INNO_GUI_EXE_TOKEN}"""' in inno_text
            and 'Tasks: autostart' in inno_text,
            "rendered_autostart_registry_matches_gui_exe": f'ValueData: """{{app}}\\\\{gui_exe_name}"""' in rendered_text,
            "contains_uninstall_purge_prompt": _inno_contains(rendered_text, r"DelTree(ExpandConstant('{localappdata}\\eodinga'), True, True, True);"),
            "purge_prompt_is_opt_in": "MB_YESNO" in rendered_text and "if MsgBox(" in rendered_text and "= IDYES then" in rendered_text,
            "purge_targets_local_data_dir_only": r"DelTree(ExpandConstant('{localappdata}\\eodinga'), True, True, True);" in rendered_text
            and "{appdata}" not in rendered_text,
        },
    }


def _write_audit(payload: dict[str, Any]) -> Path:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    target = DIST_DIR / f"{payload['target']}-audit.json"
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return target


def _load_audit(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_windows_audit(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not payload.get("version_matches_package"):
        errors.append("project and package versions do not match")
    spec_payload = payload.get("pyinstaller_spec", {})
    if not spec_payload.get("exists"):
        errors.append("PyInstaller spec is missing")
    if not spec_payload.get("hiddenimports"):
        errors.append("PyInstaller hidden imports are empty")
    discovered_source_hiddenimports = spec_payload.get("discovered_source_hiddenimports", [])
    if not discovered_source_hiddenimports:
        errors.append("PyInstaller source-derived hidden imports are empty")
    elif not set(discovered_source_hiddenimports).issubset(set(spec_payload.get("hiddenimports", []))):
        errors.append("PyInstaller hidden imports no longer include the source-derived modules")
    if not spec_payload.get("datas"):
        errors.append("PyInstaller data files are empty")
    inno_payload = payload.get("inno_setup", {})
    required_flags = {
        "app_id_is_guid_macro": "Inno AppId macro is not a GUID template",
        "app_version_uses_template": "Inno AppVersion macro no longer uses the template token",
        "source_entries_match_pyinstaller_dist": "Inno source entries drifted from PyInstaller dist names",
        "rendered_source_entries_match_pyinstaller_dist": "Rendered Inno source entries drifted from PyInstaller dist names",
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


def _validate_linux_appimage_audit(payload: dict[str, Any], project_version: str, package_version: str) -> list[str]:
    errors: list[str] = []
    if project_version != package_version:
        errors.append("project and package versions do not match")
    if payload.get("version") != package_version:
        errors.append("AppImage audit version does not match the package version")
    archive_path = payload.get("archive")
    expected_archive_name = f"eodinga-{package_version}-linux-appdir.tar.gz"
    if Path(str(archive_path)).name != expected_archive_name:
        errors.append("AppImage archive filename does not match the package version")
    recipe_payload = payload.get("recipe", {})
    icon_payload = payload.get("icon", {})
    apprun_payload = payload.get("apprun", {})
    launcher_payload = payload.get("launcher", {})
    required_flags = [
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


def _validate_linux_deb_audit(payload: dict[str, Any], project_version: str, package_version: str) -> list[str]:
    errors: list[str] = []
    if project_version != package_version:
        errors.append("project and package versions do not match")
    if payload.get("version") != package_version:
        errors.append("Debian audit version does not match the package version")
    control_payload = payload.get("control", {})
    control_template_payload = payload.get("debian_control_template", {})
    runtime_control_template_payload = payload.get("runtime_control_template", {})
    desktop_payload = payload.get("desktop_entry", {})
    icon_payload = payload.get("icon", {})
    launcher_payload = payload.get("launcher", {})
    docs_payload = payload.get("docs", {})
    arch = payload.get("arch")
    if control_payload.get("package") != "eodinga":
        errors.append("Debian control package name drifted from eodinga")
    if control_payload.get("version") != package_version:
        errors.append("Debian control version does not match the package version")
    expected_archive_name = f"eodinga_{package_version}_{arch}_debroot.tar.gz"
    if Path(str(payload.get("archive"))).name != expected_archive_name:
        errors.append("Debian dry-run archive filename does not match the package version and arch")
    expected_deb_name = f"eodinga_{package_version}_{arch}.deb"
    if Path(str(payload.get("deb_path"))).name != expected_deb_name:
        errors.append("Debian package filename does not match the package version and arch")
    required_flags = [
        (control_template_payload.get("exists"), "Debian control template is missing"),
        (
            control_template_payload.get("source") == "eodinga",
            "Debian control template source package drifted from eodinga",
        ),
        (
            control_template_payload.get("binary_package") == "eodinga",
            "Debian control template binary package drifted from eodinga",
        ),
        (
            control_template_payload.get("description") == control_payload.get("description"),
            "Debian control template description drifted from the staged package",
        ),
        (runtime_control_template_payload.get("exists"), "Debian runtime control template is missing"),
        (
            runtime_control_template_payload.get("contains_version_token"),
            "Debian runtime control template no longer exposes the version token",
        ),
        (
            runtime_control_template_payload.get("contains_arch_token"),
            "Debian runtime control template no longer exposes the arch token",
        ),
        (
            runtime_control_template_payload.get("package") == control_payload.get("package"),
            "Debian runtime control template package drifted from the staged package",
        ),
        (
            runtime_control_template_payload.get("maintainer") == control_template_payload.get("maintainer"),
            "Debian runtime control template maintainer drifted from Debian metadata",
        ),
        (
            runtime_control_template_payload.get("depends") == control_payload.get("depends"),
            "Debian runtime control template depends drifted from the staged package",
        ),
        (
            runtime_control_template_payload.get("description") == control_payload.get("description"),
            "Debian runtime control template description drifted from the staged package",
        ),
        (
            runtime_control_template_payload.get("rendered_has_no_tokens"),
            "Debian staged control file still contains template tokens",
        ),
        (desktop_payload.get("launches_gui"), "Debian desktop entry no longer launches the GUI command"),
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


def _report_validation_errors(target: str, errors: list[str]) -> int:
    if not errors:
        return 0
    joined = "\n".join(f"- {error}" for error in errors)
    print(f"{target} packaging audit failed:\n{joined}", file=sys.stderr)
    return 1


def _run_windows_dry_run() -> int:
    version = _read_project_version()
    package_version = _read_package_version()
    payload = _audit_windows_inputs(version, package_version)
    _write_audit(payload)
    return _report_validation_errors("windows-dry-run", _validate_windows_audit(payload))


def _run_windows() -> int:
    version = _read_project_version()
    package_version = _read_package_version()
    payload = _audit_windows_inputs(version, package_version)
    payload["platform_tools"] = ["pyinstaller", "iscc"]
    _write_audit(payload)
    return _report_validation_errors("windows", _validate_windows_audit(payload))


def _run_linux_appimage_dry_run() -> int:
    result = subprocess.run(
        ["bash", str(APPIMAGE_SCRIPT), "--dry-run"],
        cwd=PROJECT_ROOT,
        check=False,
    )
    if result.returncode != 0:
        return result.returncode
    payload = _load_audit(DIST_DIR / "linux-appimage-audit.json")
    project_version = _read_project_version()
    package_version = _read_package_version()
    return _report_validation_errors(
        "linux-appimage-dry-run",
        _validate_linux_appimage_audit(payload, project_version, package_version),
    )


def _run_linux_appimage() -> int:
    result = subprocess.run(
        ["bash", str(APPIMAGE_SCRIPT)],
        cwd=PROJECT_ROOT,
        check=False,
    )
    if result.returncode != 0:
        return result.returncode
    payload = _load_audit(DIST_DIR / "linux-appimage-audit.json")
    project_version = _read_project_version()
    package_version = _read_package_version()
    return _report_validation_errors(
        "linux-appimage",
        _validate_linux_appimage_audit(payload, project_version, package_version),
    )


def _run_linux_deb_dry_run() -> int:
    result = subprocess.run(
        ["bash", str(DEB_SCRIPT), "--dry-run"],
        cwd=PROJECT_ROOT,
        check=False,
    )
    if result.returncode != 0:
        return result.returncode
    payload = _load_audit(DIST_DIR / "linux-deb-audit.json")
    project_version = _read_project_version()
    package_version = _read_package_version()
    return _report_validation_errors(
        "linux-deb-dry-run",
        _validate_linux_deb_audit(payload, project_version, package_version),
    )


def _run_linux_deb() -> int:
    result = subprocess.run(
        ["bash", str(DEB_SCRIPT)],
        cwd=PROJECT_ROOT,
        check=False,
    )
    if result.returncode != 0:
        return result.returncode
    payload = _load_audit(DIST_DIR / "linux-deb-audit.json")
    project_version = _read_project_version()
    package_version = _read_package_version()
    return _report_validation_errors(
        "linux-deb",
        _validate_linux_deb_audit(payload, project_version, package_version),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--target",
        choices=(
            "linux-appimage-dry-run",
            "linux-appimage",
            "linux-deb-dry-run",
            "linux-deb",
            "windows-dry-run",
            "windows",
        ),
        required=True,
    )
    args = parser.parse_args(argv)
    if args.target == "linux-appimage-dry-run":
        return _run_linux_appimage_dry_run()
    if args.target == "linux-appimage":
        return _run_linux_appimage()
    if args.target == "linux-deb-dry-run":
        return _run_linux_deb_dry_run()
    if args.target == "linux-deb":
        return _run_linux_deb()
    if args.target == "windows-dry-run":
        return _run_windows_dry_run()
    return _run_windows()


if __name__ == "__main__":
    raise SystemExit(main())
