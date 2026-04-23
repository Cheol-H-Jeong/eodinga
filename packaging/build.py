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
INNO_VERSION_TOKEN = "@@APP_VERSION@@"
INNO_GUI_DIST_TOKEN = "@@GUI_DIST_NAME@@"
INNO_CLI_DIST_TOKEN = "@@CLI_DIST_NAME@@"
INNO_GUI_EXE_TOKEN = "@@GUI_EXE_NAME@@"
_INNO_APP_ID_PATTERN = re.compile(r"^\{\{[0-9A-F]{8}(?:-[0-9A-F]{4}){3}-[0-9A-F]{12}\}$")
_INNO_TOKEN_PATTERN = re.compile(r"@@[A-Z_]+@@")


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


def _unresolved_inno_tokens(text: str) -> list[str]:
    return sorted(set(_INNO_TOKEN_PATTERN.findall(text)))


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
            "template_tokens": _unresolved_inno_tokens(inno_text),
            "source_entries": source_entries,
            "source_entries_match_pyinstaller_dist": source_entries == expected_source_entries,
            "contains_app_version_template": INNO_VERSION_TOKEN in inno_text,
            "rendered_path": str(rendered_path),
            "output_base_filename": output_base_filename,
            "rendered_source_entries": _source_entries(rendered_text),
            "rendered_source_entries_match_pyinstaller_dist": _source_entries(rendered_text) == rendered_source_entries,
            "rendered_tokens": _unresolved_inno_tokens(rendered_text),
            "rendered_tokens_resolved": not _unresolved_inno_tokens(rendered_text),
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


def _validate_windows_audit(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    pyinstaller_spec = payload["pyinstaller_spec"]
    inno_setup = payload["inno_setup"]

    if not payload["version_matches_package"]:
        errors.append(
            f"version mismatch: pyproject={payload['version']} package={payload['package_version']}"
        )
    if not pyinstaller_spec["exists"]:
        errors.append(f"missing pyinstaller spec: {pyinstaller_spec['path']}")
    if not inno_setup["exists"]:
        errors.append(f"missing Inno Setup script: {inno_setup['path']}")
    if not inno_setup["app_id_is_guid_macro"]:
        errors.append("Inno AppId must be a stable GUID macro")
    if not inno_setup["app_version_uses_template"]:
        errors.append("Inno AppVersion macro must use @@APP_VERSION@@")
    if not inno_setup["source_entries_match_pyinstaller_dist"]:
        errors.append("Inno source entries do not match PyInstaller dist directories")
    if not inno_setup["rendered_source_entries_match_pyinstaller_dist"]:
        errors.append("rendered Inno source entries do not match PyInstaller dist directories")
    if not inno_setup["rendered_tokens_resolved"]:
        errors.append(
            "rendered Inno script contains unresolved tokens: "
            + ", ".join(inno_setup["rendered_tokens"])
        )
    return errors


def _write_audit(payload: dict[str, Any]) -> Path:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    target = DIST_DIR / f"{payload['target']}-audit.json"
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return target


def _run_windows_dry_run() -> int:
    version = _read_project_version()
    package_version = _read_package_version()
    payload = _audit_windows_inputs(version, package_version)
    payload["errors"] = _validate_windows_audit(payload)
    _write_audit(payload)
    return 1 if payload["errors"] else 0


def _run_windows() -> int:
    version = _read_project_version()
    package_version = _read_package_version()
    payload = _audit_windows_inputs(version, package_version)
    payload["platform_tools"] = ["pyinstaller", "iscc"]
    payload["errors"] = _validate_windows_audit(payload)
    _write_audit(payload)
    return 1 if payload["errors"] else 0


def _run_linux_appimage_dry_run() -> int:
    result = subprocess.run(
        ["bash", str(APPIMAGE_SCRIPT), "--dry-run"],
        cwd=PROJECT_ROOT,
        check=False,
    )
    return result.returncode


def _run_linux_appimage() -> int:
    result = subprocess.run(
        ["bash", str(APPIMAGE_SCRIPT)],
        cwd=PROJECT_ROOT,
        check=False,
    )
    return result.returncode


def _run_linux_deb_dry_run() -> int:
    result = subprocess.run(
        ["bash", str(DEB_SCRIPT), "--dry-run"],
        cwd=PROJECT_ROOT,
        check=False,
    )
    return result.returncode


def _run_linux_deb() -> int:
    result = subprocess.run(
        ["bash", str(DEB_SCRIPT)],
        cwd=PROJECT_ROOT,
        check=False,
    )
    return result.returncode


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
