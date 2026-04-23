from __future__ import annotations

import argparse
import json
import re
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
APPIMAGE_AUDIT = DIST_DIR / "linux-appimage-audit.json"
DEB_AUDIT = DIST_DIR / "linux-deb-audit.json"
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
        },
    }


def _write_audit(payload: dict[str, Any]) -> Path:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    target = DIST_DIR / f"{payload['target']}-audit.json"
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return target


def _load_audit_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"expected packaging audit at {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected object payload in {path}")
    return payload


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _validate_linux_appimage_audit(payload: dict[str, Any], *, version: str, package_version: str) -> None:
    _expect(payload.get("target") in {"linux-appimage-dry-run", "linux-appimage"}, "unexpected AppImage audit target")
    _expect(payload.get("version") == version, "AppImage audit version does not match pyproject")
    _expect(payload.get("version") == package_version, "AppImage audit version does not match package")
    _expect(Path(str(payload.get("appdir", ""))).exists(), "AppImage audit appdir is missing")
    _expect(Path(str(payload.get("archive", ""))).exists(), "AppImage audit archive is missing")
    desktop_entry = payload.get("desktop_entry", {})
    _expect(desktop_entry.get("name") == "eodinga", "AppImage desktop name drifted")
    _expect(desktop_entry.get("exec") == "eodinga gui", "AppImage desktop exec drifted")
    _expect(desktop_entry.get("icon") == "eodinga", "AppImage desktop icon drifted")
    _expect(desktop_entry.get("categories") == "Utility;FileTools;", "AppImage desktop categories drifted")
    _expect(desktop_entry.get("startup_notify") == "true", "AppImage desktop startup notify drifted")
    recipe = payload.get("recipe", {})
    _expect(recipe.get("exists") is True, "AppImage recipe is missing")
    _expect(recipe.get("references_desktop_entry") is True, "AppImage recipe no longer stages the desktop entry")
    _expect(recipe.get("references_icon_asset") is True, "AppImage recipe no longer stages the icon asset")
    _expect(recipe.get("launches_gui") is True, "AppImage recipe no longer launches the GUI")
    icon = payload.get("icon", {})
    _expect(icon.get("exists") is True, "AppImage icon is missing")
    _expect(icon.get("diricon_exists") is True, "AppImage .DirIcon is missing")
    _expect(icon.get("desktop_icon_matches_asset") is True, "AppImage desktop icon no longer matches the staged asset")
    apprun = payload.get("apprun", {})
    _expect(apprun.get("is_executable") is True, "AppImage AppRun is not executable")
    _expect(apprun.get("launches_gui") is True, "AppImage AppRun no longer launches the GUI")
    launcher = payload.get("launcher", {})
    _expect(launcher.get("is_executable") is True, "AppImage launcher shim is not executable")
    _expect(launcher.get("executes_python_module") is True, "AppImage launcher shim no longer executes the Python module")


def _validate_linux_deb_audit(payload: dict[str, Any], *, version: str, package_version: str) -> None:
    _expect(payload.get("target") in {"linux-deb-dry-run", "linux-deb"}, "unexpected Debian audit target")
    _expect(payload.get("version") == version, "Debian audit version does not match pyproject")
    _expect(payload.get("version") == package_version, "Debian audit version does not match package")
    _expect(Path(str(payload.get("package_dir", ""))).exists(), "Debian package root is missing")
    _expect(Path(str(payload.get("control_path", ""))).exists(), "Debian control file is missing")
    _expect(Path(str(payload.get("archive", ""))).exists(), "Debian archive is missing")
    if payload.get("target") == "linux-deb":
        _expect(Path(str(payload.get("deb_path", ""))).exists(), "Debian package artifact is missing")
    control = payload.get("control", {})
    _expect(control.get("package") == "eodinga", "Debian package name drifted")
    _expect(control.get("version") == version, "Debian control version drifted")
    _expect(control.get("architecture") == payload.get("arch"), "Debian control architecture drifted")
    _expect(control.get("depends") == "python3 (>= 3.11)", "Debian dependency drifted")
    _expect(
        control.get("description") == "Instant lexical file search for Windows and Linux",
        "Debian description drifted",
    )
    desktop_entry = payload.get("desktop_entry", {})
    _expect(desktop_entry.get("name") == "eodinga", "Debian desktop name drifted")
    _expect(desktop_entry.get("exec") == "eodinga gui", "Debian desktop exec drifted")
    _expect(desktop_entry.get("icon") == "eodinga", "Debian desktop icon drifted")
    _expect(desktop_entry.get("categories") == "Utility;FileTools;", "Debian desktop categories drifted")
    _expect(desktop_entry.get("startup_notify") == "true", "Debian desktop startup notify drifted")
    icon = payload.get("icon", {})
    _expect(icon.get("exists") is True, "Debian icon is missing")
    _expect(icon.get("desktop_icon_matches_asset") is True, "Debian desktop icon no longer matches the staged asset")
    launcher = payload.get("launcher", {})
    _expect(launcher.get("is_executable") is True, "Debian launcher shim is not executable")
    _expect(launcher.get("executes_python_module") is True, "Debian launcher shim no longer executes the Python module")
    docs = payload.get("docs", {})
    _expect(docs.get("license_exists") is True, "Debian license is missing")
    _expect(docs.get("changelog_exists") is True, "Debian changelog is missing")


def _run_linux_packaging_script(
    script_path: Path,
    *,
    audit_path: Path,
    version: str,
    package_version: str,
    dry_run_flag: str | None,
    validator: Any,
) -> int:
    args = ["bash", str(script_path)]
    if dry_run_flag is not None:
        args.append(dry_run_flag)
    result = subprocess.run(
        args,
        cwd=PROJECT_ROOT,
        check=False,
    )
    if result.returncode != 0:
        return result.returncode
    payload = _load_audit_payload(audit_path)
    validator(payload, version=version, package_version=package_version)
    return 0


def _run_windows_dry_run() -> int:
    version = _read_project_version()
    package_version = _read_package_version()
    payload = _audit_windows_inputs(version, package_version)
    _write_audit(payload)
    return 0


def _run_windows() -> int:
    version = _read_project_version()
    package_version = _read_package_version()
    payload = _audit_windows_inputs(version, package_version)
    payload["platform_tools"] = ["pyinstaller", "iscc"]
    _write_audit(payload)
    return 0


def _run_linux_appimage_dry_run() -> int:
    version = _read_project_version()
    package_version = _read_package_version()
    return _run_linux_packaging_script(
        APPIMAGE_SCRIPT,
        audit_path=APPIMAGE_AUDIT,
        version=version,
        package_version=package_version,
        dry_run_flag="--dry-run",
        validator=_validate_linux_appimage_audit,
    )


def _run_linux_appimage() -> int:
    version = _read_project_version()
    package_version = _read_package_version()
    return _run_linux_packaging_script(
        APPIMAGE_SCRIPT,
        audit_path=APPIMAGE_AUDIT,
        version=version,
        package_version=package_version,
        dry_run_flag=None,
        validator=_validate_linux_appimage_audit,
    )


def _run_linux_deb_dry_run() -> int:
    version = _read_project_version()
    package_version = _read_package_version()
    return _run_linux_packaging_script(
        DEB_SCRIPT,
        audit_path=DEB_AUDIT,
        version=version,
        package_version=package_version,
        dry_run_flag="--dry-run",
        validator=_validate_linux_deb_audit,
    )


def _run_linux_deb() -> int:
    version = _read_project_version()
    package_version = _read_package_version()
    return _run_linux_packaging_script(
        DEB_SCRIPT,
        audit_path=DEB_AUDIT,
        version=version,
        package_version=package_version,
        dry_run_flag=None,
        validator=_validate_linux_deb_audit,
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
