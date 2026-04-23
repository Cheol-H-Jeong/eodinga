from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import subprocess
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

_BUILD_SUPPORT_SPEC = importlib.util.spec_from_file_location("_eodinga_packaging_build_support", PROJECT_ROOT / "packaging" / "_build_support.py")
if _BUILD_SUPPORT_SPEC is None or _BUILD_SUPPORT_SPEC.loader is None:
    raise RuntimeError("could not load packaging build support module")
_build_support = importlib.util.module_from_spec(_BUILD_SUPPORT_SPEC)
_BUILD_SUPPORT_SPEC.loader.exec_module(_build_support)

_source_entries = _build_support.source_entries
_contains_data_entry = _build_support.contains_data_entry
_macro_value = _build_support.macro_value
_validate_windows_audit = _build_support.validate_windows_audit
_validate_linux_appimage_audit = _build_support.validate_linux_appimage_audit
_validate_linux_deb_audit = _build_support.validate_linux_deb_audit
_report_validation_errors = _build_support.report_validation_errors


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


def _missing_required_files(paths: list[Path]) -> list[Path]:
    return _build_support.missing_required_files(paths)


def _preflight_required_files(target: str, paths: list[Path]) -> int:
    missing = _missing_required_files(paths)
    if not missing:
        return 0
    return _report_validation_errors(
        target,
        [f"required packaging file is missing: {path}" for path in missing],
    )


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


def _audit_windows_inputs(version: str, package_version: str) -> dict[str, Any]:
    spec_namespace = _load_windows_spec_namespace()
    inno_text = INNO_SCRIPT.read_text(encoding="utf-8")
    datas = spec_namespace.get("DATAS", [])
    i18n_dir = PROJECT_ROOT / "eodinga" / "i18n"
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
            "datas": datas,
            "datas_include_i18n": all(
                _contains_data_entry(datas, i18n_dir / locale_file, "eodinga/i18n")
                for locale_file in ("en.json", "ko.json")
            ),
            "datas_include_license": _contains_data_entry(datas, PROJECT_ROOT / "LICENSE", "."),
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
            "contains_license_file": _inno_contains(rendered_text, "LicenseFile=LICENSE"),
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
            "rendered_exists": rendered_path.exists(),
        },
    }


def _write_audit(payload: dict[str, Any]) -> Path:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    target = DIST_DIR / f"{payload['target']}-audit.json"
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return target


def _load_audit(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))

def _run_windows_dry_run() -> int:
    preflight = _preflight_required_files(
        "windows-dry-run",
        [WINDOWS_SPEC, INNO_SCRIPT, PROJECT_ROOT / "LICENSE", PROJECT_ROOT / "eodinga" / "i18n" / "en.json", PROJECT_ROOT / "eodinga" / "i18n" / "ko.json"],
    )
    if preflight != 0:
        return preflight
    version = _read_project_version()
    package_version = _read_package_version()
    payload = _audit_windows_inputs(version, package_version)
    _write_audit(payload)
    return _report_validation_errors("windows-dry-run", _validate_windows_audit(payload))


def _run_windows() -> int:
    preflight = _preflight_required_commands("windows", ["pyinstaller", "iscc"])
    if preflight != 0:
        return preflight
    file_preflight = _preflight_required_files(
        "windows",
        [WINDOWS_SPEC, INNO_SCRIPT, PROJECT_ROOT / "LICENSE", PROJECT_ROOT / "eodinga" / "i18n" / "en.json", PROJECT_ROOT / "eodinga" / "i18n" / "ko.json"],
    )
    if file_preflight != 0:
        return file_preflight
    version = _read_project_version()
    package_version = _read_package_version()
    payload = _audit_windows_inputs(version, package_version)
    payload["platform_tools"] = ["pyinstaller", "iscc"]
    _write_audit(payload)
    return _report_validation_errors("windows", _validate_windows_audit(payload))


def _run_linux_appimage_dry_run() -> int:
    preflight = _preflight_required_commands("linux-appimage-dry-run", ["bash", "python3", "tar"])
    if preflight != 0:
        return preflight
    file_preflight = _preflight_required_files(
        "linux-appimage-dry-run",
        [APPIMAGE_SCRIPT, PROJECT_ROOT / "packaging" / "linux" / "appimage-builder.yml", APPIMAGE_DESKTOP, PROJECT_ROOT / "packaging" / "linux" / "eodinga.svg"],
    )
    if file_preflight != 0:
        return file_preflight
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
    file_preflight = _preflight_required_files(
        "linux-appimage",
        [APPIMAGE_SCRIPT, PROJECT_ROOT / "packaging" / "linux" / "appimage-builder.yml", APPIMAGE_DESKTOP, PROJECT_ROOT / "packaging" / "linux" / "eodinga.svg"],
    )
    if file_preflight != 0:
        return file_preflight
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
    file_preflight = _preflight_required_files(
        "linux-deb-dry-run",
        [DEB_SCRIPT, PROJECT_ROOT / "packaging" / "linux" / "debian" / "control", APPIMAGE_DESKTOP, PROJECT_ROOT / "packaging" / "linux" / "eodinga.svg", PROJECT_ROOT / "LICENSE", PROJECT_ROOT / "CHANGELOG.md"],
    )
    if file_preflight != 0:
        return file_preflight
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
    file_preflight = _preflight_required_files(
        "linux-deb",
        [DEB_SCRIPT, PROJECT_ROOT / "packaging" / "linux" / "debian" / "control", APPIMAGE_DESKTOP, PROJECT_ROOT / "packaging" / "linux" / "eodinga.svg", PROJECT_ROOT / "LICENSE", PROJECT_ROOT / "CHANGELOG.md"],
    )
    if file_preflight != 0:
        return file_preflight
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
