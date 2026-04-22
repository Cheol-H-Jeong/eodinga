from __future__ import annotations

import shutil
import subprocess

import pytest


@pytest.mark.skipif(shutil.which("yamllint") is None, reason="yamllint not installed")
def test_workflow_files_are_yamllint_clean() -> None:
    result = subprocess.run(
        ["yamllint", ".github/workflows/ci.yml", ".github/workflows/release-windows.yml", ".github/workflows/release-linux.yml"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
