from __future__ import annotations

from pathlib import Path

from eodinga import __version__

from .test_build_dry_run import _load_build_module


def test_windows_audit_validator_rejects_missing_packaged_data_contract() -> None:
    module = _load_build_module()
    payload = module._audit_windows_inputs(__version__, __version__)
    payload["pyinstaller_spec"]["datas_include_license"] = False

    errors = module._validate_windows_audit(payload)

    assert "PyInstaller data files no longer ship the LICENSE file" in errors


def test_windows_audit_validator_rejects_dist_name_drift() -> None:
    module = _load_build_module()
    payload = module._audit_windows_inputs(__version__, __version__)
    payload["pyinstaller_spec"]["dist_names"] = {"cli": "cli", "gui": "gui"}

    errors = module._validate_windows_audit(payload)

    assert "PyInstaller dist names drifted from the release contract" in errors


def test_linux_appimage_audit_validator_rejects_desktop_entry_drift(tmp_path: Path) -> None:
    module = _load_build_module()
    appdir = tmp_path / "eodinga.AppDir"
    appdir.mkdir()
    archive = tmp_path / f"eodinga-{__version__}-linux-appdir.tar.gz"
    archive.write_text("archive", encoding="utf-8")
    payload = {
        "version": __version__,
        "appdir": str(appdir),
        "archive": str(archive),
        "desktop_entry": {
            "name": "eodinga",
            "exec": "eodinga search",
            "icon": "eodinga",
            "categories": "Utility;FileTools;",
            "startup_notify": "true",
        },
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

    assert "AppImage desktop entry no longer launches the GUI command" in errors


def test_linux_deb_audit_validator_rejects_control_dependency_drift(tmp_path: Path) -> None:
    module = _load_build_module()
    package_dir = tmp_path / "pkg"
    package_dir.mkdir()
    control_path = package_dir / "DEBIAN.control"
    control_path.write_text("control", encoding="utf-8")
    archive = tmp_path / f"eodinga_{__version__}_amd64_debroot.tar.gz"
    archive.write_text("archive", encoding="utf-8")
    payload = {
        "version": __version__,
        "arch": "amd64",
        "package_dir": str(package_dir),
        "control_path": str(control_path),
        "archive": str(archive),
        "deb_path": str(tmp_path / f"eodinga_{__version__}_amd64.deb"),
        "control": {
            "package": "eodinga",
            "version": __version__,
            "architecture": "amd64",
            "depends": "python3 (>= 3.10)",
            "description": "Instant lexical file search for Windows and Linux",
        },
        "debian_control_template": {
            "exists": True,
            "contains_version_template": True,
            "contains_arch_template": True,
            "rendered_exists": True,
            "source": "eodinga",
            "binary_package": "eodinga",
            "description": "Instant lexical file search for Windows and Linux",
        },
        "desktop_entry": {
            "name": "eodinga",
            "launches_gui": True,
            "categories": "Utility;FileTools;",
            "startup_notify": "true",
            "icon_matches_package": True,
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
            "changelog_exists": True,
            "changelog_has_current_release_heading": True,
        },
    }

    errors = module._validate_linux_deb_audit(payload, __version__, __version__)

    assert "Debian control dependency contract drifted from python3 (>= 3.11)" in errors


def test_build_preflight_reports_missing_windows_asset_file(monkeypatch) -> None:
    module = _load_build_module()

    def fake_missing(paths: list[Path]) -> list[Path]:
        return [module.PROJECT_ROOT / "LICENSE"]

    monkeypatch.setattr(module, "_missing_required_files", fake_missing)

    result = module._run_windows_dry_run()

    assert result == 1


def test_build_preflight_reports_missing_linux_deb_asset_file(monkeypatch) -> None:
    module = _load_build_module()

    def fake_missing(paths: list[Path]) -> list[Path]:
        return [module.PROJECT_ROOT / "packaging" / "linux" / "debian" / "control"]

    monkeypatch.setattr(module, "_missing_required_files", fake_missing)

    result = module._run_linux_deb_dry_run()

    assert result == 1
