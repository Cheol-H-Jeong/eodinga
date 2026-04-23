from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from eodinga import __version__


def _load_metadata_module():
    spec = importlib.util.spec_from_file_location("project_metadata", Path("packaging/project_metadata.py"))
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_project_metadata_matches_pyproject_contract() -> None:
    module = _load_metadata_module()

    payload = module.read_project_metadata()

    assert payload == {
        "name": "eodinga",
        "version": __version__,
        "description": "Everything-class instant file search for Windows and Linux",
        "publisher": "Cheol-H-Jeong",
        "requires_python": ">=3.11",
        "debian_python_dependency": "python3 (>=3.11)",
    }


def test_project_metadata_shell_format_exports_safe_assignments() -> None:
    result = subprocess.run(
        [sys.executable, "packaging/project_metadata.py", "--format", "shell"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "PROJECT_NAME=eodinga" in result.stdout
    assert f"PROJECT_VERSION={__version__}" in result.stdout
    assert "PROJECT_DESCRIPTION='Everything-class instant file search for Windows and Linux'" in result.stdout


def test_project_metadata_json_format_is_machine_readable() -> None:
    result = subprocess.run(
        [sys.executable, "packaging/project_metadata.py", "--format", "json"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["publisher"] == "Cheol-H-Jeong"
    assert payload["debian_python_dependency"] == "python3 (>=3.11)"
