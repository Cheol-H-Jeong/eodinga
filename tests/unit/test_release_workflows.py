from __future__ import annotations

from pathlib import Path
import subprocess


def test_release_linux_workflow_uses_linux_appimage_dry_run() -> None:
    workflow = Path(".github/workflows/release-linux.yml").read_text(encoding="utf-8")
    assert "python -m pip install appimage-builder" in workflow
    assert "python packaging/build.py --target linux-appimage-dry-run" in workflow
    assert "python packaging/build.py --target linux-deb-dry-run" in workflow
    assert "python packaging/build.py --target linux-appimage" in workflow
    assert "python packaging/build.py --target linux-deb" in workflow


def test_release_windows_workflow_runs_dry_run_before_build() -> None:
    workflow = Path(".github/workflows/release-windows.yml").read_text(encoding="utf-8")
    assert "python packaging/build.py --target windows-dry-run" in workflow
    assert "python packaging/build.py --target windows" in workflow
    assert workflow.index("Validate packaging inputs") < workflow.index("\n      - name: Build\n")


def test_release_workflows_pass_yamllint() -> None:
    result = subprocess.run(
        ["yamllint", ".github/workflows/release-windows.yml", ".github/workflows/release-linux.yml"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
