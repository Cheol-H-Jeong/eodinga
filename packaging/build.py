from __future__ import annotations

import argparse
import json
import re
import shutil
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
RELEASE_DRY_RUN_AUDIT = DIST_DIR / "release-dry-run-audit.json"
RELEASE_WORKFLOWS = [
    PROJECT_ROOT / ".github" / "workflows" / "release-windows.yml",
    PROJECT_ROOT / ".github" / "workflows" / "release-linux.yml",
]


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
    installer_path = DIST_DIR / f"{output_base_filename}.exe"
    gui_dist_path = PROJECT_ROOT / "dist" / gui_dist_name
    cli_dist_path = PROJECT_ROOT / "dist" / cli_dist_name
    gui_exe_path = gui_dist_path / gui_exe_name
    cli_exe_path = cli_dist_path / cli_exe_name
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
            "dist_paths": {
                "cli": str(cli_dist_path),
                "gui": str(gui_dist_path),
            },
            "dist_exists": {
                "cli": cli_dist_path.exists(),
                "gui": gui_dist_path.exists(),
            },
            "exe_paths": {
                "cli": str(cli_exe_path),
                "gui": str(gui_exe_path),
            },
            "exe_exists": {
                "cli": cli_exe_path.exists(),
                "gui": gui_exe_path.exists(),
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
            "installer_path": str(installer_path),
            "installer_artifact": _artifact_payload(installer_path),
            "rendered_source_entries": _source_entries(rendered_text),
            "rendered_source_entries_match_pyinstaller_dist": _source_entries(rendered_text) == rendered_source_entries,
            "contains_versioned_output_macro": "OutputBaseFilename=eodinga-{#AppVersion}-win-x64-setup" in rendered_text,
            "license_file_exists": (PROJECT_ROOT / "LICENSE").exists(),
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
            "contains_user_desktop_shortcut": _inno_contains(inno_text, 'Name: "{userdesktop}\\\\eodinga"; Filename: "{app}\\\\@@GUI_EXE_NAME@@"; Tasks: desktopicon'),
            "contains_rendered_desktop_shortcut": _inno_contains(
                rendered_text,
                f'Name: "{{userdesktop}}\\\\eodinga"; Filename: "{{app}}\\\\{gui_exe_name}"; Tasks: desktopicon',
            ),
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
            "contains_uninstall_purge_prompt": _inno_contains(rendered_text, "procedure PurgeUserState();")
            and _inno_contains(rendered_text, r"DelTree(ExpandConstant('{localappdata}\\eodinga'), True, True, True);")
            and _inno_contains(rendered_text, r"DelTree(ExpandConstant('{userappdata}\\eodinga'), True, True, True);"),
            "purge_prompt_is_opt_in": "MB_YESNO" in rendered_text and "if MsgBox(" in rendered_text and "= IDYES then" in rendered_text,
            "purge_targets_local_and_roaming_user_state": r"DelTree(ExpandConstant('{localappdata}\\eodinga'), True, True, True);" in rendered_text
            and r"DelTree(ExpandConstant('{userappdata}\\eodinga'), True, True, True);" in rendered_text
            and "{commonappdata}" not in rendered_text,
        },
    }


def _write_audit(payload: dict[str, Any]) -> Path:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    target = DIST_DIR / f"{payload['target']}-audit.json"
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return target


def _load_audit(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _audit_status(path: Path, result: int) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "result": result,
    }


def _artifact_payload(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else None,
    }


def _command_payload(command: list[str], result: subprocess.CompletedProcess[str] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"command": command}
    if result is not None:
        payload["returncode"] = result.returncode
        payload["stdout"] = result.stdout
        payload["stderr"] = result.stderr
    return payload


def _refresh_windows_build_artifacts(payload: dict[str, Any]) -> None:
    spec_payload = payload["pyinstaller_spec"]
    dist_paths = {name: Path(path) for name, path in spec_payload["dist_paths"].items()}
    exe_paths = {name: Path(path) for name, path in spec_payload["exe_paths"].items()}
    spec_payload["dist_exists"] = {name: path.exists() for name, path in dist_paths.items()}
    spec_payload["exe_exists"] = {name: path.exists() for name, path in exe_paths.items()}
    inno_payload = payload["inno_setup"]
    inno_payload["installer_artifact"] = _artifact_payload(Path(inno_payload["installer_path"]))


def _validate_windows_audit(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not payload.get("version_matches_package"):
        errors.append("project and package versions do not match")
    spec_payload = payload.get("pyinstaller_spec", {})
    inno_payload = payload.get("inno_setup", {})
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
    if payload.get("target") == "windows":
        dist_exists = spec_payload.get("dist_exists", {})
        exe_exists = spec_payload.get("exe_exists", {})
        if not dist_exists.get("gui"):
            errors.append("Windows build is missing the staged GUI dist directory")
        if not dist_exists.get("cli"):
            errors.append("Windows build is missing the staged CLI dist directory")
        if not exe_exists.get("gui"):
            errors.append("Windows build is missing the staged GUI executable")
        if not exe_exists.get("cli"):
            errors.append("Windows build is missing the staged CLI executable")
        installer_artifact = inno_payload.get("installer_artifact", {})
        if not installer_artifact.get("exists"):
            errors.append("Windows build is missing the versioned installer executable")
        if not isinstance(installer_artifact.get("size_bytes"), int) or installer_artifact.get("size_bytes", 0) <= 0:
            errors.append("Windows installer size is missing")
    required_flags = {
        "app_id_is_guid_macro": "Inno AppId macro is not a GUID template",
        "app_version_uses_template": "Inno AppVersion macro no longer uses the template token",
        "license_file_exists": "Inno setup no longer references a shipped LICENSE file",
        "source_entries_match_pyinstaller_dist": "Inno source entries drifted from PyInstaller dist names",
        "rendered_source_entries_match_pyinstaller_dist": "Rendered Inno source entries drifted from PyInstaller dist names",
        "contains_rendered_uninstall_display_icon": "Rendered Inno uninstall icon does not point at the GUI executable",
        "contains_start_menu_shortcut": "Rendered Inno start menu shortcut is missing",
        "contains_user_desktop_shortcut": "Inno desktop shortcut no longer targets the per-user desktop",
        "contains_rendered_desktop_shortcut": "Rendered Inno desktop shortcut does not point at the GUI executable",
        "contains_postinstall_launch": "Rendered Inno postinstall launch action is missing",
        "contains_autostart_registry": "Inno autostart registry entry is missing",
        "rendered_autostart_registry_matches_gui_exe": "Rendered Inno autostart registry entry does not point at the GUI executable",
        "contains_uninstall_purge_prompt": "Inno uninstall purge prompt is missing",
        "purge_prompt_is_opt_in": "Inno uninstall purge prompt is no longer opt-in",
        "purge_targets_local_and_roaming_user_state": "Inno uninstall purge no longer targets both local data and roaming config",
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
    arch = payload.get("arch")
    if not arch:
        errors.append("AppImage audit architecture is missing")
    archive_path = payload.get("archive")
    expected_archive_name = f"eodinga-{package_version}-linux-{arch}-appdir.tar.gz"
    if Path(str(archive_path)).name != expected_archive_name:
        errors.append("AppImage archive filename does not match the package version")
    archive_artifact = payload.get("archive_artifact", {})
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
        (payload.get("desktop_entry", {}).get("matches_source_asset"), "AppImage desktop entry no longer matches the shipped asset"),
        (payload.get("desktop_entry", {}).get("name") == "eodinga", "AppImage desktop entry name drifted from eodinga"),
        (
            payload.get("desktop_entry", {}).get("exec") == "eodinga gui",
            "AppImage desktop entry no longer launches the GUI command",
        ),
        (
            payload.get("desktop_entry", {}).get("icon") == "eodinga",
            "AppImage desktop entry icon no longer matches the packaged asset",
        ),
        (
            payload.get("desktop_entry", {}).get("categories") == "Utility;FileTools;",
            "AppImage desktop entry categories drifted from the shipped asset",
        ),
        (
            payload.get("desktop_entry", {}).get("startup_notify") == "true",
            "AppImage desktop entry no longer enables startup notifications",
        ),
        (icon_payload.get("exists"), "AppImage icon asset is missing from the staged AppDir"),
        (icon_payload.get("diricon_exists"), "AppImage .DirIcon is missing"),
        (icon_payload.get("desktop_icon_matches_asset"), "AppImage desktop icon no longer matches the shipped asset"),
        (icon_payload.get("matches_source_asset"), "AppImage icon payload no longer matches the shipped asset"),
        (apprun_payload.get("is_executable"), "AppImage AppRun is not executable"),
        (apprun_payload.get("launches_gui"), "AppImage AppRun no longer launches the GUI target"),
        (apprun_payload.get("has_strict_shell"), "AppImage AppRun no longer uses strict shell flags"),
        (launcher_payload.get("is_executable"), "AppImage launcher shim is not executable"),
        (launcher_payload.get("has_strict_shell"), "AppImage launcher shim no longer uses strict shell flags"),
        (launcher_payload.get("changes_to_project_root"), "AppImage launcher shim no longer changes to the project root"),
        (launcher_payload.get("executes_python_module"), "AppImage launcher shim no longer executes the Python module"),
        (payload.get("archive_entries_sorted"), "AppImage archive entries are no longer sorted"),
        (payload.get("archive_mtime_zero"), "AppImage archive member mtimes are no longer reproducible"),
        (payload.get("archive_numeric_owner_zero"), "AppImage archive ownership is no longer reproducible"),
        (archive_artifact.get("exists"), "AppImage archive is missing"),
        (isinstance(archive_artifact.get("size_bytes"), int) and archive_artifact.get("size_bytes", 0) > 0, "AppImage archive size is missing"),
        (bool(archive_artifact.get("sha256")), "AppImage archive digest is missing"),
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
        errors.append("Debian control architecture does not match the staged package arch")
    if control_payload.get("depends") != "python3 (>= 3.11)":
        errors.append("Debian control dependency floor drifted from python3 (>= 3.11)")
    if control_payload.get("description") != "Instant lexical file search for Windows and Linux":
        errors.append("Debian control description drifted from the release metadata")
    expected_archive_name = f"eodinga_{package_version}_{arch}_debroot.tar.gz"
    if Path(str(payload.get("archive"))).name != expected_archive_name:
        errors.append("Debian dry-run archive filename does not match the package version and arch")
    expected_deb_name = f"eodinga_{package_version}_{arch}.deb"
    if Path(str(payload.get("deb_path"))).name != expected_deb_name:
        errors.append("Debian package filename does not match the package version and arch")
    archive_artifact = payload.get("archive_artifact", {})
    deb_artifact = payload.get("deb_artifact", {})
    required_flags = [
        (control_template_payload.get("exists"), "Debian control template is missing"),
        (control_template_payload.get("contains_version_template"), "Debian control template no longer uses the version token"),
        (control_template_payload.get("contains_arch_template"), "Debian control template no longer uses the architecture token"),
        (control_template_payload.get("rendered_exists"), "Rendered Debian control file is missing"),
        (
            control_template_payload.get("source") == "eodinga",
            "Debian control template source package drifted from eodinga",
        ),
        (
            control_template_payload.get("binary_package") == "eodinga",
            "Debian control template binary package drifted from eodinga",
        ),
        (
            control_template_payload.get("maintainer") == "Cheol-H-Jeong",
            "Debian control template maintainer drifted from Cheol-H-Jeong",
        ),
        (
            control_template_payload.get("description") == control_payload.get("description"),
            "Debian control template description drifted from the staged package",
        ),
        (desktop_payload.get("matches_source_asset"), "Debian desktop entry no longer matches the shipped asset"),
        (desktop_payload.get("name") == "eodinga", "Debian desktop entry name drifted from eodinga"),
        (desktop_payload.get("launches_gui"), "Debian desktop entry no longer launches the GUI command"),
        (desktop_payload.get("icon_matches_package"), "Debian desktop entry icon no longer matches the packaged asset"),
        (
            desktop_payload.get("categories") == "Utility;FileTools;",
            "Debian desktop entry categories drifted from the shipped asset",
        ),
        (
            desktop_payload.get("startup_notify") == "true",
            "Debian desktop entry no longer enables startup notifications",
        ),
        (icon_payload.get("exists"), "Debian icon asset is missing from the package tree"),
        (icon_payload.get("desktop_icon_matches_asset"), "Debian desktop icon no longer matches the shipped asset"),
        (icon_payload.get("matches_source_asset"), "Debian icon payload no longer matches the shipped asset"),
        (launcher_payload.get("is_executable"), "Debian launcher shim is not executable"),
        (launcher_payload.get("has_strict_shell"), "Debian launcher shim no longer uses strict shell flags"),
        (launcher_payload.get("executes_python_module"), "Debian launcher shim no longer executes the Python module"),
        (docs_payload.get("license_exists"), "Debian package no longer ships the license"),
        (docs_payload.get("changelog_exists"), "Debian package no longer ships the changelog"),
        (docs_payload.get("changelog_has_current_release_heading"), "Debian package changelog no longer starts with the current release heading"),
        (docs_payload.get("changelog_gzip_mtime_zero"), "Debian package changelog gzip header is no longer reproducible"),
        (payload.get("archive_entries_sorted"), "Debian dry-run archive entries are no longer sorted"),
        (payload.get("archive_mtime_zero"), "Debian dry-run archive member mtimes are no longer reproducible"),
        (payload.get("archive_numeric_owner_zero"), "Debian dry-run archive ownership is no longer reproducible"),
        (archive_artifact.get("exists"), "Debian archive is missing"),
        (isinstance(archive_artifact.get("size_bytes"), int) and archive_artifact.get("size_bytes", 0) > 0, "Debian archive size is missing"),
        (bool(archive_artifact.get("sha256")), "Debian archive digest is missing"),
        (
            deb_artifact.get("path") == payload.get("deb_path"),
            "Debian package artifact path drifted from the planned output path",
        ),
    ]
    for ok, message in required_flags:
        if not ok:
            errors.append(message)
    if payload.get("dry_run"):
        if deb_artifact.get("exists"):
            errors.append("Debian dry run unexpectedly produced a .deb payload")
    else:
        if not deb_artifact.get("exists"):
            errors.append("Debian package is missing")
        if not isinstance(deb_artifact.get("size_bytes"), int) or deb_artifact.get("size_bytes", 0) <= 0:
            errors.append("Debian package size is missing")
        if not deb_artifact.get("sha256"):
            errors.append("Debian package digest is missing")
    return errors


def _report_validation_errors(target: str, errors: list[str]) -> int:
    if not errors:
        return 0
    joined = "\n".join(f"- {error}" for error in errors)
    print(f"{target} packaging audit failed:\n{joined}", file=sys.stderr)
    return 1


def _missing_required_commands(commands: list[str]) -> list[str]:
    return sorted(command for command in commands if shutil.which(command) is None)


def _preflight_required_commands(target: str, commands: list[str]) -> int:
    missing = _missing_required_commands(commands)
    if not missing:
        return 0
    return _report_validation_errors(
        target,
        [f"required build command is missing from PATH: {command}" for command in missing],
    )


def _run_windows_dry_run() -> int:
    version = _read_project_version()
    package_version = _read_package_version()
    payload = _audit_windows_inputs(version, package_version)
    _write_audit(payload)
    return _report_validation_errors("windows-dry-run", _validate_windows_audit(payload))


def _run_windows() -> int:
    preflight = _preflight_required_commands("windows", ["pyinstaller", "iscc"])
    if preflight != 0:
        return preflight
    version = _read_project_version()
    package_version = _read_package_version()
    payload = _audit_windows_inputs(version, package_version)
    payload["target"] = "windows"
    rendered_path = Path(payload["inno_setup"]["rendered_path"])
    payload["platform_tools"] = ["pyinstaller", "iscc"]
    pyinstaller_command = [
        "pyinstaller",
        "--noconfirm",
        "--clean",
        "--distpath",
        str(PROJECT_ROOT / "dist"),
        "--workpath",
        str(PROJECT_ROOT / "build" / "pyinstaller"),
        str(WINDOWS_SPEC),
    ]
    pyinstaller_result = subprocess.run(
        pyinstaller_command,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    payload["pyinstaller"] = _command_payload(pyinstaller_command, pyinstaller_result)
    if pyinstaller_result.returncode != 0:
        _write_audit(payload)
        return pyinstaller_result.returncode
    _refresh_windows_build_artifacts(payload)
    iscc_command = [
        "iscc",
        f"/O{DIST_DIR}",
        f"/F{payload['inno_setup']['output_base_filename']}",
        str(rendered_path),
    ]
    iscc_result = subprocess.run(
        iscc_command,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    payload["iscc"] = _command_payload(iscc_command, iscc_result)
    _refresh_windows_build_artifacts(payload)
    _write_audit(payload)
    if iscc_result.returncode != 0:
        return iscc_result.returncode
    return _report_validation_errors("windows", _validate_windows_audit(payload))


def _run_linux_appimage_dry_run() -> int:
    preflight = _preflight_required_commands("linux-appimage-dry-run", ["bash", "python3", "tar"])
    if preflight != 0:
        return preflight
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
    preflight = _preflight_required_commands("linux-appimage", ["bash", "python3", "tar"])
    if preflight != 0:
        return preflight
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
    preflight = _preflight_required_commands("linux-deb-dry-run", ["bash", "python3", "tar"])
    if preflight != 0:
        return preflight
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
    preflight = _preflight_required_commands("linux-deb", ["bash", "dpkg-deb", "python3", "tar"])
    if preflight != 0:
        return preflight
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


def _run_release_dry_run() -> int:
    results = [
        ("windows-dry-run", DIST_DIR / "windows-dry-run-audit.json", _run_windows_dry_run()),
        ("linux-appimage-dry-run", DIST_DIR / "linux-appimage-audit.json", _run_linux_appimage_dry_run()),
        ("linux-deb-dry-run", DIST_DIR / "linux-deb-audit.json", _run_linux_deb_dry_run()),
        ("workflows-lint", DIST_DIR / "workflows-lint-audit.json", _run_workflows_lint()),
    ]
    summary = {
        "target": "release-dry-run",
        "version": _read_project_version(),
        "package_version": _read_package_version(),
        "results": {
            target: _audit_status(path, result)
            for target, path, result in results
        },
    }
    summary["all_passed"] = all(result == 0 for _, _, result in results)
    RELEASE_DRY_RUN_AUDIT.parent.mkdir(parents=True, exist_ok=True)
    RELEASE_DRY_RUN_AUDIT.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return 0 if summary["all_passed"] else 1


def _run_workflows_lint() -> int:
    preflight = _preflight_required_commands("workflows-lint", ["yamllint"])
    if preflight != 0:
        return preflight
    command = ["yamllint", *(str(path) for path in RELEASE_WORKFLOWS)]
    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    payload = {
        "target": "workflows-lint",
        "command": command,
        "files": [str(path) for path in RELEASE_WORKFLOWS],
        "stdout": result.stdout,
        "stderr": result.stderr,
        "success": result.returncode == 0,
    }
    _write_audit(payload)
    if result.returncode == 0:
        return 0
    errors = [line for line in result.stdout.splitlines() if line.strip()]
    errors.extend(line for line in result.stderr.splitlines() if line.strip())
    if not errors:
        errors = ["yamllint exited with a non-zero status"]
    return _report_validation_errors("workflows-lint", errors)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--target",
        choices=(
            "release-dry-run",
            "workflows-lint",
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
    if args.target == "release-dry-run":
        return _run_release_dry_run()
    if args.target == "workflows-lint":
        return _run_workflows_lint()
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
